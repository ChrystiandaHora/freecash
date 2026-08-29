"""Testes das operações do usuário sobre a própria conta.

O que estes testes protegem, em ordem de gravidade:

**A senha atual é exigida onde importa.** Quem alcança uma sessão aberta consegue
tudo o que a sessão consegue. Sem a exigência, bastaria um navegador destravado
para trocar o e-mail da conta e assumi-la em definitivo, já que é o e-mail que
recebe a recuperação de senha.

**A troca de e-mail não vale antes de confirmada.** Enquanto o link não é aberto, o
endereço antigo continua servindo para entrar e recuperar a conta. É o que protege
contra erro de digitação e contra sequestro de sessão.

**Trocar a senha encerra as outras sessões.** Se a senha vazou, mantê-las abertas
preservaria o acesso do invasor no exato momento em que a vítima acredita ter
resolvido o problema.
"""

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.cache import caches
from django.test import override_settings
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from core.models import Conta, ConfigUsuario
from core.services.tokens import email_change_token

User = get_user_model()

CACHES_DE_TESTE = {
    "default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"},
    "throttle": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"},
}


@override_settings(
    EMAIL_ASYNC=False,
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    CACHES=CACHES_DE_TESTE,
)
class ContaBaseTestCase(APITestCase):
    """Base com um usuário autenticado e o throttle isolado."""

    def setUp(self):
        """Cria o usuário, limpa o throttle e autentica."""
        caches["throttle"].clear()
        self.senha = "senha-atual-123456"
        self.user = User.objects.create_user(
            username="ana", password=self.senha, email="ana@exemplo.com",
        )
        ConfigUsuario.objects.get_or_create(usuario=self.user)
        self.autenticar()

    def tearDown(self):
        """Evita que a contagem de throttle vaze para os demais testes."""
        caches["throttle"].clear()

    def autenticar(self):
        """Autentica com uma instância recém-carregada do usuário."""
        self.client.force_authenticate(user=User.objects.get(pk=self.user.pk))


class PerfilAPITests(ContaBaseTestCase):
    """Cobre a leitura e a edição dos dados não sensíveis."""

    def setUp(self):
        """Resolve a URL do perfil."""
        super().setUp()
        self.url = reverse("api-auth-perfil")

    def test_exige_autenticacao(self):
        """Dados de conta nunca são anônimos."""
        self.client.force_authenticate(user=None)
        self.assertEqual(
            self.client.get(self.url).status_code, status.HTTP_401_UNAUTHORIZED
        )

    def test_devolve_os_dados_da_conta(self):
        """O caminho de leitura, que alimenta a tela."""
        resposta = self.client.get(self.url)

        self.assertEqual(resposta.status_code, status.HTTP_200_OK)
        self.assertEqual(resposta.data["username"], "ana")
        self.assertEqual(resposta.data["email"], "ana@exemplo.com")
        self.assertEqual(resposta.data["moeda_padrao"], "BRL")
        self.assertEqual(resposta.data["email_pendente"], "")

    def test_altera_nome_de_usuario(self):
        """Edição básica, sem exigir senha."""
        resposta = self.client.patch(
            self.url, {"username": "ana.oliveira"}, format="json"
        )

        self.assertEqual(resposta.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertEqual(self.user.username, "ana.oliveira")

    def test_altera_moeda_padrao(self):
        """Preferência guardada em ConfigUsuario."""
        self.client.patch(self.url, {"moeda_padrao": "usd"}, format="json")

        config = ConfigUsuario.objects.get(usuario=self.user)
        self.assertEqual(config.moeda_padrao, "USD")

    def test_nome_de_usuario_ja_usado_e_recusado(self):
        """Unicidade preservada na edição, não só no cadastro."""
        User.objects.create_user(
            username="bruno", password="senha-bem-comprida-123",
            email="bruno@exemplo.com",
        )
        resposta = self.client.patch(
            self.url, {"username": "bruno"}, format="json"
        )

        self.assertEqual(resposta.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("username", resposta.data)

    def test_manter_o_proprio_nome_nao_e_conflito(self):
        """Salvar sem mudar o nome não pode acusar duplicidade consigo mesmo."""
        resposta = self.client.patch(
            self.url, {"username": "ana", "moeda_padrao": "BRL"}, format="json"
        )
        self.assertEqual(resposta.status_code, status.HTTP_200_OK)

    def test_edicao_de_perfil_nao_pede_senha(self):
        """Decisão de produto: exigir senha a cada preferência a banalizaria."""
        resposta = self.client.patch(
            self.url, {"moeda_padrao": "EUR"}, format="json"
        )
        self.assertEqual(resposta.status_code, status.HTTP_200_OK)

    def test_nao_permite_alterar_email_por_esta_rota(self):
        """O e-mail tem fluxo próprio, com senha e confirmação.

        Se um dia `email` for aceito aqui, a exigência de senha e a confirmação do
        novo endereço deixam de valer — e este teste é o que acusa.
        """
        self.client.patch(
            self.url, {"email": "outro@exemplo.com"}, format="json"
        )
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, "ana@exemplo.com")


class TrocaEmailAPITests(ContaBaseTestCase):
    """Cobre o fluxo de troca de endereço de e-mail."""

    def setUp(self):
        """Resolve as URLs do fluxo."""
        super().setUp()
        self.url_solicitar = reverse("api-auth-email-alterar")
        self.url_confirmar = reverse("api-auth-email-alterar-confirmar")
        self.url_cancelar = reverse("api-auth-email-alterar-cancelar")

    def solicitar(self, **extra):
        """Dispara um pedido de troca com dados válidos por padrão.

        Args:
            **extra: Campos a sobrescrever.

        Returns:
            Response: Resposta da requisição.
        """
        corpo = {"senha_atual": self.senha, "novo_email": "novo@exemplo.com"}
        corpo.update(extra)
        with self.captureOnCommitCallbacks(execute=True):
            return self.client.post(self.url_solicitar, corpo, format="json")

    def test_solicitacao_nao_altera_o_email_imediatamente(self):
        """O ponto central do desenho: o endereço antigo continua valendo."""
        resposta = self.solicitar()

        self.assertEqual(resposta.status_code, status.HTTP_202_ACCEPTED)
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, "ana@exemplo.com")

        config = ConfigUsuario.objects.get(usuario=self.user)
        self.assertEqual(config.email_pendente, "novo@exemplo.com")

    def test_link_de_confirmacao_vai_para_o_novo_endereco(self):
        """Enviar ao endereço atual não provaria posse do novo."""
        self.solicitar()

        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["novo@exemplo.com"])
        self.assertIn("/conta/confirmar-email/", mail.outbox[0].body)

    def test_senha_incorreta_bloqueia_a_troca(self):
        """Sem esta barreira, uma sessão tomada assumiria a conta em definitivo."""
        resposta = self.solicitar(senha_atual="chute-errado")

        self.assertEqual(resposta.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("senha_atual", resposta.data)
        self.assertEqual(
            ConfigUsuario.objects.get(usuario=self.user).email_pendente, ""
        )
        self.assertEqual(len(mail.outbox), 0)

    def test_email_de_outra_conta_e_recusado_com_mensagem_generica(self):
        """A recusa não pode confirmar quem tem conta no sistema."""
        User.objects.create_user(
            username="bruno", password="senha-bem-comprida-123",
            email="ocupado@exemplo.com",
        )
        resposta = self.solicitar(novo_email="Ocupado@Exemplo.com")

        self.assertEqual(resposta.status_code, status.HTTP_400_BAD_REQUEST)
        mensagem = " ".join(resposta.data["novo_email"]).lower()
        self.assertNotIn("já cadastrado", mensagem)
        self.assertNotIn("já existe", mensagem)

    def test_confirmar_promove_o_endereco_pendente(self):
        """O caminho felizes do fluxo."""
        self.solicitar()
        self.user.refresh_from_db()

        uid = urlsafe_base64_encode(force_bytes(self.user.pk))
        token = email_change_token.make_token(self.user)

        with self.captureOnCommitCallbacks(execute=True):
            resposta = self.client.post(
                self.url_confirmar, {"uid": uid, "token": token}, format="json"
            )

        self.assertEqual(resposta.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, "novo@exemplo.com")

        config = ConfigUsuario.objects.get(usuario=self.user)
        self.assertEqual(config.email_pendente, "")
        self.assertTrue(config.email_verificado)

    def test_endereco_antigo_e_avisado_da_troca(self):
        """Rede de segurança: é o único canal que ainda alcança o dono legítimo."""
        self.solicitar()
        self.user.refresh_from_db()
        mail.outbox.clear()

        uid = urlsafe_base64_encode(force_bytes(self.user.pk))
        token = email_change_token.make_token(self.user)
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(
                self.url_confirmar, {"uid": uid, "token": token}, format="json"
            )

        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["ana@exemplo.com"])

    def test_token_nao_serve_duas_vezes(self):
        """Uso único, garantido pelo hash que inclui o endereço pendente."""
        self.solicitar()
        self.user.refresh_from_db()
        uid = urlsafe_base64_encode(force_bytes(self.user.pk))
        token = email_change_token.make_token(self.user)

        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(
                self.url_confirmar, {"uid": uid, "token": token}, format="json"
            )
        segunda = self.client.post(
            self.url_confirmar, {"uid": uid, "token": token}, format="json"
        )

        self.assertEqual(segunda.status_code, status.HTTP_400_BAD_REQUEST)

    def test_token_de_verificacao_comum_nao_confirma_troca(self):
        """Os dois geradores precisam ser mutuamente incompatíveis."""
        from core.services.tokens import email_verification_token

        self.solicitar()
        self.user.refresh_from_db()
        uid = urlsafe_base64_encode(force_bytes(self.user.pk))
        token_errado = email_verification_token.make_token(self.user)

        resposta = self.client.post(
            self.url_confirmar, {"uid": uid, "token": token_errado}, format="json"
        )

        self.assertEqual(resposta.status_code, status.HTTP_400_BAD_REQUEST)
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, "ana@exemplo.com")

    def test_uid_malformado_responde_400_e_nunca_500(self):
        """Entrada corrompida é erro de requisição."""
        for uid_ruim in ["", "!!!", "nao-base64", "MTIzNDU2Nzg5MA"]:
            with self.subTest(uid=uid_ruim):
                resposta = self.client.post(
                    self.url_confirmar,
                    {"uid": uid_ruim, "token": "x"},
                    format="json",
                )
                self.assertEqual(resposta.status_code, status.HTTP_400_BAD_REQUEST)

    def test_cancelar_descarta_a_troca_pendente(self):
        """Permite desfazer um pedido feito por engano."""
        self.solicitar()

        resposta = self.client.post(self.url_cancelar)

        self.assertEqual(resposta.status_code, status.HTTP_200_OK)
        self.assertEqual(
            ConfigUsuario.objects.get(usuario=self.user).email_pendente, ""
        )

    def test_link_deixa_de_valer_apos_o_cancelamento(self):
        """Cancelar tem de invalidar o link já enviado, não só limpar a tela."""
        self.solicitar()
        self.user.refresh_from_db()
        uid = urlsafe_base64_encode(force_bytes(self.user.pk))
        token = email_change_token.make_token(self.user)

        self.client.post(self.url_cancelar)

        resposta = self.client.post(
            self.url_confirmar, {"uid": uid, "token": token}, format="json"
        )
        self.assertEqual(resposta.status_code, status.HTTP_400_BAD_REQUEST)

    def test_conta_legada_sem_email_consegue_cadastrar_um(self):
        """Motivo prático da funcionalidade existir.

        Contas criadas antes de o e-mail virar obrigatório não têm endereço, e sem
        ele não há como recuperar a senha.
        """
        self.user.email = ""
        self.user.save(update_fields=["email"])
        self.autenticar()

        resposta = self.solicitar(novo_email="primeiro@exemplo.com")
        self.assertEqual(resposta.status_code, status.HTTP_202_ACCEPTED)


class TrocaSenhaAPITests(ContaBaseTestCase):
    """Cobre a troca de senha do usuário autenticado."""

    def setUp(self):
        """Resolve a URL de troca de senha."""
        super().setUp()
        self.url = reverse("api-auth-senha-alterar")

    def _payload(self, **extra):
        """Monta um corpo válido de troca de senha.

        Args:
            **extra: Campos a sobrescrever.

        Returns:
            dict: Corpo pronto para envio.
        """
        base = {
            "senha_atual": self.senha,
            "nova_senha": "senha-nova-987654",
            "confirmar": "senha-nova-987654",
        }
        base.update(extra)
        return base

    def test_troca_a_senha(self):
        """O caminho felizes."""
        resposta = self.client.post(self.url, self._payload(), format="json")

        self.assertEqual(resposta.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("senha-nova-987654"))

    def test_senha_atual_incorreta_bloqueia(self):
        """Impede que uma sessão tomada troque a senha e expulse o dono."""
        resposta = self.client.post(
            self.url, self._payload(senha_atual="chute"), format="json"
        )

        self.assertEqual(resposta.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("senha_atual", resposta.data)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(self.senha))

    def test_encerra_as_outras_sessoes(self):
        """Se a senha vazou, o acesso do invasor precisa cair junto."""
        refresh_antigo = str(RefreshToken.for_user(self.user))

        self.client.post(self.url, self._payload(), format="json")

        self.client.force_authenticate(user=None)
        resposta = self.client.post(
            reverse("token_refresh"), {"refresh": refresh_antigo}, format="json"
        )
        self.assertEqual(resposta.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_devolve_sessao_nova_para_quem_trocou(self):
        """Deslogar quem acabou de provar ser o dono seria hostil, sem ganho."""
        resposta = self.client.post(self.url, self._payload(), format="json")

        self.assertIn("access", resposta.data)
        self.assertIn("refresh_token", resposta.cookies)

    def test_nova_senha_igual_a_atual_e_recusada(self):
        """Trocar por ela mesma não é troca."""
        resposta = self.client.post(
            self.url,
            self._payload(nova_senha=self.senha, confirmar=self.senha),
            format="json",
        )
        self.assertEqual(resposta.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("nova_senha", resposta.data)

    def test_senha_fraca_e_recusada(self):
        """Os AUTH_PASSWORD_VALIDATORS valem aqui como no cadastro."""
        resposta = self.client.post(
            self.url,
            self._payload(nova_senha="123", confirmar="123"),
            format="json",
        )
        self.assertEqual(resposta.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("nova_senha", resposta.data)

    def test_confirmacao_divergente_e_recusada(self):
        """Protege contra erro de digitação numa credencial que não é exibida."""
        resposta = self.client.post(
            self.url, self._payload(confirmar="outra-coisa-123"), format="json"
        )
        self.assertEqual(resposta.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("confirmar", resposta.data)


class ExclusaoContaAPITests(ContaBaseTestCase):
    """Cobre a exclusão da própria conta."""

    def setUp(self):
        """Cria um lançamento, para exercitar o cascade com signals."""
        super().setUp()
        self.url = reverse("api-auth-conta-excluir")
        from datetime import date
        from decimal import Decimal

        Conta.objects.create(
            usuario=self.user, tipo=Conta.TIPO_DESPESA, descricao="Aluguel",
            valor=Decimal("2000.00"), data_prevista=date(2026, 5, 10),
        )

    def _payload(self, **extra):
        """Monta um corpo válido de exclusão.

        Args:
            **extra: Campos a sobrescrever.

        Returns:
            dict: Corpo pronto para envio.
        """
        base = {"senha_atual": self.senha, "confirmacao": "ana"}
        base.update(extra)
        return base

    def test_exclui_a_conta_e_os_dados(self):
        """O caminho felizes, com o cascade de signals ativo."""
        pk = self.user.pk
        resposta = self.client.post(self.url, self._payload(), format="json")

        self.assertEqual(resposta.status_code, status.HTTP_200_OK)
        self.assertFalse(User.objects.filter(pk=pk).exists())
        self.assertFalse(Conta.objects.filter(usuario_id=pk).exists())

    def test_senha_incorreta_bloqueia(self):
        """A ação é irreversível: uma sessão tomada não pode destruir a conta."""
        resposta = self.client.post(
            self.url, self._payload(senha_atual="chute"), format="json"
        )

        self.assertEqual(resposta.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertTrue(User.objects.filter(pk=self.user.pk).exists())

    def test_confirmacao_errada_bloqueia(self):
        """Segunda barreira: digitar o nome de usuário por extenso."""
        resposta = self.client.post(
            self.url, self._payload(confirmacao="sim"), format="json"
        )

        self.assertEqual(resposta.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("confirmacao", resposta.data)
        self.assertTrue(User.objects.filter(pk=self.user.pk).exists())

    def test_sessao_e_encerrada_apos_a_exclusao(self):
        """O cookie precisa sair junto: não há mais conta para a sessão apontar."""
        resposta = self.client.post(self.url, self._payload(), format="json")

        cookie = resposta.cookies.get("refresh_token")
        self.assertIsNotNone(cookie)
        self.assertEqual(cookie.value, "")

    def test_exclusao_nao_afeta_outras_contas(self):
        """Isolamento na operação mais destrutiva do sistema."""
        outro = User.objects.create_user(
            username="bruno", password="senha-bem-comprida-123",
            email="bruno@exemplo.com",
        )
        ConfigUsuario.objects.get_or_create(usuario=outro)

        self.client.post(self.url, self._payload(), format="json")

        self.assertTrue(User.objects.filter(pk=outro.pk).exists())
        self.assertTrue(ConfigUsuario.objects.filter(usuario=outro).exists())

    def test_exige_autenticacao(self):
        """Não há exclusão anônima."""
        self.client.force_authenticate(user=None)
        resposta = self.client.post(self.url, self._payload(), format="json")
        self.assertEqual(resposta.status_code, status.HTTP_401_UNAUTHORIZED)
