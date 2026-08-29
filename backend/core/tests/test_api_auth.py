"""Testes do registro de novas contas.

O registro passou a exigir e-mail e a validar a senha pelos
`AUTH_PASSWORD_VALIDATORS` do Django, que antes estavam configurados mas nunca
eram executados — a view fazia validação manual com mínimo próprio de 6
caracteres. Os erros deixaram de vir como `{"detail": "..."}` e passaram ao
formato por campo do DRF, `{"campo": ["..."]}`, para que o formulário possa
apontar o problema no campo certo.
"""

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from core.models import ConfigUsuario, Categoria

User = get_user_model()


# O envio precisa ser síncrono nos testes: com thread, `mail.outbox` é lido antes
# do envio terminar e o teste fica intermitente.
@override_settings(
    EMAIL_ASYNC=False,
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
)
class UserRegistrationAPITestCase(APITestCase):
    """Cobre o caminho felizes e as recusas do endpoint de registro."""

    def setUp(self):
        """Resolve a URL de registro e monta um payload válido reutilizável."""
        self.url = reverse("api-register")
        self.payload = {
            "username": "newuser",
            "email": "newuser@exemplo.com",
            "password": "securepassword123",
            "confirm": "securepassword123",
        }

    def test_registration_success_and_ecosystem_creation(self):
        """O registro cria a conta, o ecossistema financeiro e a sessão inicial."""
        response = self.client.post(self.url, self.payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn("access", response.data)

        self.assertIn("refresh_token", response.cookies)
        cookie = response.cookies["refresh_token"]
        self.assertTrue(cookie["httponly"])
        # O path cobre /api/token/, /refresh/ e /clear/ por prefixo. É o que permite
        # ao logout receber o cookie e revogar o refresh token — com o path antigo
        # (/api/token/refresh/) o navegador nunca o enviava para /api/token/clear/.
        self.assertEqual(cookie["path"], "/api/token/")

        user = User.objects.get(username="newuser")
        self.assertTrue(user.check_password("securepassword123"))
        self.assertEqual(user.email, "newuser@exemplo.com")

        config = ConfigUsuario.objects.get(usuario=user)
        self.assertFalse(config.email_verificado)
        self.assertIsNone(config.email_verificado_em)

        categories = Categoria.objects.filter(usuario=user)
        self.assertEqual(categories.count(), 3)
        self.assertTrue(categories.filter(nome="Receita", tipo=Categoria.TIPO_RECEITA).exists())
        self.assertTrue(categories.filter(nome="Gastos", tipo=Categoria.TIPO_DESPESA).exists())
        self.assertTrue(categories.filter(nome="Investimento", tipo=Categoria.TIPO_INVESTIMENTO).exists())

    def test_registration_envia_email_de_verificacao(self):
        """O cadastro dispara exatamente um e-mail, com link apontando ao SPA.

        O envio é agendado com `transaction.on_commit`, e num `TestCase` a
        transação nunca é confirmada — sem `captureOnCommitCallbacks` os callbacks
        não rodariam e o teste passaria a testar nada.
        """
        with override_settings(FRONTEND_BASE_URL="https://app.exemplo.com"):
            with self.captureOnCommitCallbacks(execute=True):
                self.client.post(self.url, self.payload, format="json")

        self.assertEqual(len(mail.outbox), 1)
        mensagem = mail.outbox[0]
        self.assertEqual(mensagem.to, ["newuser@exemplo.com"])
        self.assertIn("https://app.exemplo.com/verificar-email/", mensagem.body)
        # A alternativa HTML acompanha a versão em texto.
        self.assertTrue(
            any(tipo == "text/html" for _, tipo in mensagem.alternatives)
        )

    def test_registration_normaliza_email_para_minusculas(self):
        """Endereços entram no banco na forma canônica, para casar com o índice único."""
        payload = {**self.payload, "email": "  NewUser@Exemplo.COM  "}
        response = self.client.post(self.url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(
            User.objects.get(username="newuser").email, "newuser@exemplo.com"
        )

    def test_registration_sem_email_e_recusado(self):
        """O e-mail é obrigatório: sem ele não há como recuperar a conta."""
        payload = {k: v for k, v in self.payload.items() if k != "email"}
        response = self.client.post(self.url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("email", response.data)

    def test_registration_email_invalido_e_recusado(self):
        """Um endereço malformado é rejeitado antes de qualquer envio."""
        payload = {**self.payload, "email": "nao-e-um-email"}
        response = self.client.post(self.url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("email", response.data)
        self.assertEqual(len(mail.outbox), 0)

    def test_registration_email_duplicado_nao_confirma_existencia(self):
        """A recusa não revela que já existe conta com aquele endereço.

        Confirmar isso entregaria a um atacante a lista de quem tem conta num
        sistema financeiro. A mensagem é genérica de propósito.
        """
        User.objects.create_user(
            username="outro", password="senha-bem-comprida-123",
            email="ocupado@exemplo.com",
        )

        # Caixa diferente do cadastrado: o índice é sobre LOWER(email).
        payload = {**self.payload, "email": "Ocupado@Exemplo.com"}
        response = self.client.post(self.url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("email", response.data)
        mensagem = " ".join(response.data["email"]).lower()
        self.assertNotIn("já cadastrado", mensagem)
        self.assertNotIn("já existe", mensagem)

    def test_registration_missing_fields(self):
        """Campos ausentes produzem erro por campo, no formato do DRF."""
        payload = {"username": "newuser", "email": "newuser@exemplo.com",
                   "password": "securepassword123"}
        response = self.client.post(self.url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("confirm", response.data)

    def test_registration_senha_curta_reprovada_pelos_validators(self):
        """O mínimo passou a ser o do MinimumLengthValidator (8), não os 6 antigos."""
        payload = {**self.payload, "password": "abc123", "confirm": "abc123"}
        response = self.client.post(self.url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("password", response.data)

    def test_registration_senha_comum_reprovada(self):
        """O CommonPasswordValidator agora tem efeito — antes era ignorado."""
        payload = {**self.payload, "password": "password", "confirm": "password"}
        response = self.client.post(self.url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("password", response.data)

    def test_registration_senha_parecida_com_usuario_reprovada(self):
        """Prova que o UserAttributeSimilarityValidator recebe o usuário para comparar.

        Sem passar `user=` a `validate_password`, este validador está configurado
        mas não tem nada com que comparar — foi o caso durante todo o período em que
        a view validava a senha à mão.
        """
        payload = {
            "username": "mariaoliveira",
            "email": "maria@exemplo.com",
            "password": "mariaoliveira",
            "confirm": "mariaoliveira",
        }
        response = self.client.post(self.url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("password", response.data)

    def test_registration_password_mismatch(self):
        """Senha e confirmação divergentes são recusadas no campo de confirmação."""
        payload = {**self.payload, "confirm": "differentpassword"}
        response = self.client.post(self.url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("confirm", response.data)

    def test_registration_existing_username(self):
        """Nome de usuário duplicado é recusado, e isso pode ser dito abertamente.

        Diferente do e-mail: a tela de login já revela a existência de um nome de
        usuário pela própria resposta de autenticação, então esconder aqui não
        acrescentaria proteção alguma.
        """
        User.objects.create_user(
            username="existinguser", password="senha-bem-comprida-123",
            email="existente@exemplo.com",
        )
        payload = {**self.payload, "username": "existinguser"}
        response = self.client.post(self.url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("username", response.data)

    def test_registration_nao_cria_conta_quando_email_falha(self):
        """Falha de envio não derruba o cadastro: a conta é criada de todo modo.

        O usuário pode reenviar a confirmação depois. Perder a conta porque o
        servidor de e-mail estava fora do ar seria muito pior.
        """
        with override_settings(
            EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend"
        ):
            with self.settings(EMAIL_HOST="", DEFAULT_FROM_EMAIL=""):
                response = self.client.post(self.url, self.payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(User.objects.filter(username="newuser").exists())
