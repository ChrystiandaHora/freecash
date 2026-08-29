"""Testes da redefinição de senha.

Duas propriedades merecem verificação explícita, porque são fáceis de quebrar sem
perceber:

**Não vazar quem tem conta.** O pedido responde exatamente a mesma coisa para um
endereço cadastrado e para um desconhecido. Basta alguém adicionar um 404 "amigável"
para transformar o endpoint num verificador de contas — e, num sistema financeiro,
saber que alguém tem conta aqui já é informação sensível.

**A troca de senha encerra as sessões abertas.** Se a senha foi trocada porque a
anterior vazou, deixar de revogar os refresh tokens manteria o invasor conectado
por até sete dias, exatamente no momento em que a vítima acredita ter resolvido o
problema.
"""

from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.core import mail
from django.test import override_settings
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from core.models import ConfigUsuario

User = get_user_model()

# Cache local: sem isolar o throttle, os vários pedidos de redefinição destes
# testes esgotariam o limite e passariam a receber 429.
CACHES_DE_TESTE = {
    "default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"},
    "throttle": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"},
}


@override_settings(
    EMAIL_ASYNC=False,
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    CACHES=CACHES_DE_TESTE,
)
class PasswordResetRequestAPITests(APITestCase):
    """Cobre o pedido de redefinição de senha."""

    def setUp(self):
        """Cria um usuário ativo e limpa o cache de throttle."""
        from django.core.cache import caches

        caches["throttle"].clear()
        self.user = User.objects.create_user(
            username="ana", password="senha-antiga-123456",
            email="ana@exemplo.com",
        )
        ConfigUsuario.objects.get_or_create(usuario=self.user)
        self.url = reverse("api-auth-senha-reset")

    def test_email_cadastrado_recebe_o_link(self):
        """O caminho felizes envia um e-mail com o link de redefinição."""
        with self.captureOnCommitCallbacks(execute=True):
            resposta = self.client.post(
                self.url, {"email": "ana@exemplo.com"}, format="json"
            )

        self.assertEqual(resposta.status_code, status.HTTP_202_ACCEPTED)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("/redefinir-senha/", mail.outbox[0].body)

    def test_resposta_identica_para_email_inexistente(self):
        """Esta é a proteção contra enumeração de contas.

        Corpo e status precisam ser indistinguíveis; qualquer diferença transforma
        o endpoint num oráculo que informa quem tem conta no sistema.
        """
        with self.captureOnCommitCallbacks(execute=True):
            existente = self.client.post(
                self.url, {"email": "ana@exemplo.com"}, format="json"
            )
        emails_apos_existente = len(mail.outbox)

        with self.captureOnCommitCallbacks(execute=True):
            inexistente = self.client.post(
                self.url, {"email": "ninguem@exemplo.com"}, format="json"
            )

        self.assertEqual(existente.status_code, inexistente.status_code)
        self.assertEqual(existente.data, inexistente.data)
        # A diferença aparece só no que sai pelo servidor, não no que o cliente vê.
        self.assertEqual(emails_apos_existente, 1)
        self.assertEqual(len(mail.outbox), 1)

    def test_resposta_identica_para_conta_inativa(self):
        """Conta suspensa também não pode ser distinguida na resposta."""
        self.user.is_active = False
        self.user.save(update_fields=["is_active"])

        with self.captureOnCommitCallbacks(execute=True):
            resposta = self.client.post(
                self.url, {"email": "ana@exemplo.com"}, format="json"
            )

        self.assertEqual(resposta.status_code, status.HTTP_202_ACCEPTED)
        self.assertEqual(len(mail.outbox), 0)

    def test_email_com_caixa_diferente_encontra_a_conta(self):
        """A busca é case-insensitive, como o índice único do banco."""
        with self.captureOnCommitCallbacks(execute=True):
            resposta = self.client.post(
                self.url, {"email": "  Ana@Exemplo.COM  "}, format="json"
            )

        self.assertEqual(resposta.status_code, status.HTTP_202_ACCEPTED)
        self.assertEqual(len(mail.outbox), 1)

    def test_pedidos_repetidos_para_o_mesmo_endereco_sao_limitados(self):
        """Impede que o sistema seja usado como disparador de mensagens.

        O limite por IP, isolado, não protege o destinatário: este teste cobre o
        throttle por endereço de destino.
        """
        codigos = []
        for _ in range(6):
            resposta = self.client.post(
                self.url, {"email": "ana@exemplo.com"}, format="json"
            )
            codigos.append(resposta.status_code)

        self.assertIn(status.HTTP_429_TOO_MANY_REQUESTS, codigos)


@override_settings(
    EMAIL_ASYNC=False,
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    CACHES=CACHES_DE_TESTE,
)
class PasswordResetConfirmAPITests(APITestCase):
    """Cobre a efetivação da troca de senha."""

    def setUp(self):
        """Cria o usuário, seu token de redefinição e limpa o throttle."""
        from django.core.cache import caches

        caches["throttle"].clear()
        self.senha_antiga = "senha-antiga-123456"
        self.user = User.objects.create_user(
            username="ana", password=self.senha_antiga, email="ana@exemplo.com",
        )
        ConfigUsuario.objects.get_or_create(usuario=self.user)
        self.url = reverse("api-auth-senha-reset-confirmar")
        self.uid = urlsafe_base64_encode(force_bytes(self.user.pk))
        self.token = default_token_generator.make_token(self.user)

    def _payload(self, **extra):
        """Monta um corpo de requisição válido, permitindo sobrescrever campos.

        Args:
            **extra: Campos a substituir no payload padrão.

        Returns:
            dict: Corpo pronto para envio.
        """
        base = {
            "uid": self.uid,
            "token": self.token,
            "nova_senha": "senha-nova-987654",
            "confirmar": "senha-nova-987654",
        }
        base.update(extra)
        return base

    def test_token_valido_troca_a_senha(self):
        """O caminho felizes altera a senha e remove o cookie de sessão."""
        resposta = self.client.post(self.url, self._payload(), format="json")

        self.assertEqual(resposta.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("senha-nova-987654"))
        self.assertFalse(self.user.check_password(self.senha_antiga))

    def test_token_deixa_de_valer_apos_a_troca(self):
        """Uso único, garantido pelo próprio gerador do Django.

        `_make_hash_value` inclui o hash da senha e o `last_login`, então trocar a
        senha invalida o token sem precisar registrar nada.
        """
        self.client.post(self.url, self._payload(), format="json")

        segunda = self.client.post(
            self.url,
            self._payload(nova_senha="outra-senha-55555",
                          confirmar="outra-senha-55555"),
            format="json",
        )

        self.assertEqual(segunda.status_code, status.HTTP_400_BAD_REQUEST)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("senha-nova-987654"))

    def test_troca_de_senha_revoga_as_sessoes_abertas(self):
        """Se a senha vazou, o invasor não pode continuar conectado."""
        refresh = str(RefreshToken.for_user(self.user))

        self.client.post(self.url, self._payload(), format="json")

        resposta = self.client.post(
            reverse("token_refresh"), {"refresh": refresh}, format="json"
        )
        self.assertEqual(resposta.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_troca_de_senha_marca_email_como_verificado(self):
        """Quem abriu o link provou ter acesso à caixa de entrada."""
        self.assertFalse(ConfigUsuario.objects.get(usuario=self.user).email_verificado)

        self.client.post(self.url, self._payload(), format="json")

        config = ConfigUsuario.objects.get(usuario=self.user)
        self.assertTrue(config.email_verificado)
        self.assertIsNotNone(config.email_verificado_em)

    def test_senha_fraca_e_recusada_e_a_antiga_permanece(self):
        """Os AUTH_PASSWORD_VALIDATORS valem também na redefinição."""
        resposta = self.client.post(
            self.url,
            self._payload(nova_senha="123", confirmar="123"),
            format="json",
        )

        self.assertEqual(resposta.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("nova_senha", resposta.data)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(self.senha_antiga))

    def test_senhas_divergentes_sao_recusadas(self):
        """A confirmação precisa coincidir com a nova senha."""
        resposta = self.client.post(
            self.url, self._payload(confirmar="outra-coisa-123456"), format="json"
        )

        self.assertEqual(resposta.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("confirmar", resposta.data)

    def test_token_de_outro_usuario_e_recusado(self):
        """Um token válido não redefine a senha de outra conta."""
        outro = User.objects.create_user(
            username="bruno", password="senha-do-bruno-123",
            email="bruno@exemplo.com",
        )
        token_do_outro = default_token_generator.make_token(outro)

        resposta = self.client.post(
            self.url, self._payload(token=token_do_outro), format="json"
        )

        self.assertEqual(resposta.status_code, status.HTTP_400_BAD_REQUEST)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(self.senha_antiga))

    def test_uid_malformado_responde_400_e_nunca_500(self):
        """Entrada corrompida é erro de requisição, não falha do servidor."""
        for uid_ruim in ["", "!!!", "nao-base64", "MTIzNDU2Nzg5MA"]:
            with self.subTest(uid=uid_ruim):
                resposta = self.client.post(
                    self.url, self._payload(uid=uid_ruim), format="json"
                )
                self.assertEqual(
                    resposta.status_code,
                    status.HTTP_400_BAD_REQUEST,
                    f"uid {uid_ruim!r} produziu {resposta.status_code}",
                )
