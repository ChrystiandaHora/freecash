"""Testes da confirmação de endereço de e-mail.

O desenho sob teste tem uma propriedade que vale verificar explicitamente: o token
é de uso único **sem nenhuma tabela de controle**. Isso funciona porque
`EmailVerificationTokenGenerator._make_hash_value` inclui o estado
`email_verificado` no valor assinado — confirmar a conta altera esse estado e, com
ele, invalida o próprio token. Se alguém simplificar aquele método no futuro, o
teste de reuso abaixo é o que vai acusar a regressão.
"""

from datetime import datetime, timedelta
from unittest import mock

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import override_settings
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from rest_framework import status
from rest_framework.test import APITestCase

from core.models import ConfigUsuario
from core.services.tokens import email_verification_token

User = get_user_model()


@override_settings(
    EMAIL_ASYNC=False,
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
)
class EmailVerificacaoAPITests(APITestCase):
    """Cobre a confirmação de e-mail a partir do link enviado."""

    def setUp(self):
        """Cria um usuário com e-mail pendente de confirmação."""
        self.user = User.objects.create_user(
            username="ana", password="senha-bem-comprida-123",
            email="ana@exemplo.com",
        )
        ConfigUsuario.objects.get_or_create(usuario=self.user)
        self.url = reverse("api-auth-verificar-email")
        self.uid = urlsafe_base64_encode(force_bytes(self.user.pk))

    def _token(self):
        """Gera um token válido para o usuário do teste.

        Returns:
            str: Token de confirmação recém-emitido.
        """
        self.user.refresh_from_db()
        return email_verification_token.make_token(self.user)

    def test_token_valido_confirma_o_email(self):
        """O caminho felizes marca o e-mail como verificado e registra o momento."""
        resposta = self.client.post(
            self.url, {"uid": self.uid, "token": self._token()}, format="json"
        )

        self.assertEqual(resposta.status_code, status.HTTP_200_OK)
        self.assertTrue(resposta.data["email_verificado"])

        config = ConfigUsuario.objects.get(usuario=self.user)
        self.assertTrue(config.email_verificado)
        self.assertIsNotNone(config.email_verificado_em)

    def test_reuso_do_mesmo_token_responde_sucesso_idempotente(self):
        """Um segundo clique no link não pode parecer erro para o usuário.

        A confirmação já concluída responde 200. Isso é importante na prática:
        duplo clique e pré-carregamento de link são comuns, e uma tela de falha
        depois de a conta já estar confirmada só geraria dúvida.
        """
        token = self._token()
        primeira = self.client.post(
            self.url, {"uid": self.uid, "token": token}, format="json"
        )
        segunda = self.client.post(
            self.url, {"uid": self.uid, "token": token}, format="json"
        )

        self.assertEqual(primeira.status_code, status.HTTP_200_OK)
        self.assertEqual(segunda.status_code, status.HTTP_200_OK)
        self.assertTrue(segunda.data["email_verificado"])

    def test_token_deixa_de_valer_apos_a_confirmacao(self):
        """Prova o uso único no nível do gerador, sem passar pela idempotência da view.

        A view atalha quando já está verificado, então este teste vai direto ao
        gerador: é ele que precisa recusar o token antigo.
        """
        token = self._token()
        self.client.post(self.url, {"uid": self.uid, "token": token}, format="json")

        self.user.refresh_from_db()
        self.assertFalse(email_verification_token.check_token(self.user, token))

    def test_token_de_outro_usuario_e_recusado(self):
        """Um token válido não pode confirmar a conta de outra pessoa."""
        outro = User.objects.create_user(
            username="bruno", password="senha-bem-comprida-123",
            email="bruno@exemplo.com",
        )
        ConfigUsuario.objects.get_or_create(usuario=outro)
        token_do_outro = email_verification_token.make_token(outro)

        resposta = self.client.post(
            self.url, {"uid": self.uid, "token": token_do_outro}, format="json"
        )

        self.assertEqual(resposta.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(
            ConfigUsuario.objects.get(usuario=self.user).email_verificado
        )

    def test_token_expirado_e_recusado(self):
        """Fora da janela de validade, o link não vale mais."""
        token = self._token()

        # `_now()` do Django devolve datetime *naive* (datetime.now(), sem fuso), e
        # `_num_seconds` o subtrai de outro naive. Passar um datetime aware aqui
        # produziria TypeError dentro do gerador.
        futuro = datetime.now() + timedelta(days=1)

        with override_settings(EMAIL_VERIFICATION_TIMEOUT=0):
            with mock.patch.object(
                email_verification_token, "_now", return_value=futuro
            ):
                resposta = self.client.post(
                    self.url, {"uid": self.uid, "token": token}, format="json"
                )

        self.assertEqual(resposta.status_code, status.HTTP_400_BAD_REQUEST)

    def test_uid_malformado_responde_400_e_nunca_500(self):
        """Entrada corrompida do usuário é erro de requisição, não falha do servidor."""
        for uid_ruim in ["", "!!!", "nao-base64", "MTIzNDU2Nzg5MA"]:
            with self.subTest(uid=uid_ruim):
                resposta = self.client.post(
                    self.url, {"uid": uid_ruim, "token": self._token()}, format="json"
                )
                self.assertIn(
                    resposta.status_code,
                    [status.HTTP_400_BAD_REQUEST],
                    f"uid {uid_ruim!r} produziu {resposta.status_code}",
                )

    def test_token_alterado_e_recusado(self):
        """Um token adulterado não passa pela verificação de integridade."""
        token = self._token()
        adulterado = token[:-1] + ("a" if token[-1] != "a" else "b")

        resposta = self.client.post(
            self.url, {"uid": self.uid, "token": adulterado}, format="json"
        )
        self.assertEqual(resposta.status_code, status.HTTP_400_BAD_REQUEST)


@override_settings(
    EMAIL_ASYNC=False,
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
)
class EmailReenvioAPITests(APITestCase):
    """Cobre o reenvio do link de confirmação."""

    def setUp(self):
        """Cria e autentica um usuário com e-mail pendente."""
        self.user = User.objects.create_user(
            username="ana", password="senha-bem-comprida-123",
            email="ana@exemplo.com",
        )
        ConfigUsuario.objects.get_or_create(usuario=self.user)
        self.url = reverse("api-auth-verificar-email-reenviar")
        self.client.force_authenticate(user=self.user)

    def test_reenvio_dispara_novo_email(self):
        """Quem ainda não confirmou recebe um novo link."""
        with self.captureOnCommitCallbacks(execute=True):
            resposta = self.client.post(self.url)

        self.assertEqual(resposta.status_code, status.HTTP_200_OK)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["ana@exemplo.com"])

    def test_reenvio_para_conta_ja_verificada_nao_envia(self):
        """Não faz sentido reenviar confirmação de algo já confirmado."""
        config = ConfigUsuario.objects.get(usuario=self.user)
        config.email_verificado = True
        config.save()

        # O `get_or_create` do setUp deixou a relação `config` em cache no objeto
        # `self.user`, e é esse objeto que `force_authenticate` entrega à view. Sem
        # reautenticar com uma instância nova, a view leria o estado antigo. Em
        # produção o problema não existe: cada requisição carrega o usuário do banco.
        self.client.force_authenticate(user=User.objects.get(pk=self.user.pk))

        with self.captureOnCommitCallbacks(execute=True):
            resposta = self.client.post(self.url)

        self.assertEqual(resposta.status_code, status.HTTP_200_OK)
        self.assertEqual(len(mail.outbox), 0)

    def test_reenvio_exige_autenticacao(self):
        """Aberto, este endpoint permitiria descobrir quem tem conta e enviar spam."""
        self.client.force_authenticate(user=None)
        resposta = self.client.post(self.url)
        self.assertEqual(resposta.status_code, status.HTTP_401_UNAUTHORIZED)


class MeAPITests(APITestCase):
    """Cobre o endpoint que expõe o estado da conta autenticada."""

    def setUp(self):
        """Cria um usuário com configuração associada."""
        self.user = User.objects.create_user(
            username="ana", password="senha-bem-comprida-123",
            email="ana@exemplo.com",
        )
        ConfigUsuario.objects.get_or_create(usuario=self.user)
        self.url = reverse("api-auth-me")

    def test_me_reflete_estado_atual_do_banco(self):
        """O estado vem do banco, não de claim do token.

        É essa leitura que evita o valor obsoleto: com rotação de refresh token, o
        payload original é preservado, então um estado embutido no JWT continuaria
        desatualizado por até sete dias.
        """
        self.client.force_authenticate(user=self.user)

        antes = self.client.get(self.url)
        self.assertEqual(antes.status_code, status.HTTP_200_OK)
        self.assertFalse(antes.data["email_verificado"])
        self.assertFalse(antes.data["is_staff"])
        self.assertEqual(antes.data["email"], "ana@exemplo.com")

        config = ConfigUsuario.objects.get(usuario=self.user)
        config.email_verificado = True
        config.save()

        # Instância nova: `force_authenticate` reaproveita o objeto passado, que
        # carrega a relação `config` em cache desde o setUp.
        self.client.force_authenticate(user=User.objects.get(pk=self.user.pk))

        depois = self.client.get(self.url)
        self.assertTrue(depois.data["email_verificado"])

    def test_me_exige_autenticacao(self):
        """Sem sessão não há identidade a informar."""
        resposta = self.client.get(self.url)
        self.assertEqual(resposta.status_code, status.HTTP_401_UNAUTHORIZED)
