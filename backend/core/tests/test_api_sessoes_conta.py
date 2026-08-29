"""Testes da listagem e do encerramento de sessões da própria conta.

A tela de conta prometia "as outras sessões serão encerradas" sem que o usuário
pudesse ver sessão nenhuma. Estes endpoints fecham essa lacuna.

Dois pontos merecem verificação explícita:

**A contagem precisa refletir a realidade da blacklist.** Um token revogado ou
expirado não é sessão; contá-lo transformaria o número num alarme falso permanente,
e o usuário aprenderia a ignorá-lo.

**Encerrar não pode deslogar quem pediu.** O cookie do refresh token tem
`path=/api/token/` e não chega a esta rota, então não há como identificar a sessão
atual para poupá-la. A solução é revogar todas e emitir uma nova ao chamador — o
resultado observável é o mesmo, e o teste garante que a sessão em uso sobrevive.
"""

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.cache import caches
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.token_blacklist.models import (
    BlacklistedToken,
    OutstandingToken,
)
from rest_framework_simplejwt.tokens import RefreshToken

from core.models import ConfigUsuario

User = get_user_model()

CACHES_DE_TESTE = {
    "default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"},
    "throttle": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"},
}


@override_settings(CACHES=CACHES_DE_TESTE)
class SessoesAPITests(APITestCase):
    """Cobre a contagem de sessões ativas."""

    def setUp(self):
        """Cria e autentica um usuário, limpando o throttle."""
        caches["throttle"].clear()
        self.senha = "senha-bem-comprida-123"
        self.user = User.objects.create_user(
            username="ana", password=self.senha, email="ana@exemplo.com",
        )
        ConfigUsuario.objects.get_or_create(usuario=self.user)
        self.client.force_authenticate(user=self.user)
        self.url = reverse("api-auth-sessoes")

    def tearDown(self):
        """Evita que a contagem de throttle vaze para outros testes."""
        caches["throttle"].clear()

    def test_exige_autenticacao(self):
        """Sessões são dado da conta: nunca anônimo."""
        self.client.force_authenticate(user=None)
        self.assertEqual(
            self.client.get(self.url).status_code, status.HTTP_401_UNAUTHORIZED
        )

    def test_conta_os_tokens_vivos(self):
        """Cada refresh token válido corresponde a uma sessão."""
        RefreshToken.for_user(self.user)
        RefreshToken.for_user(self.user)

        resposta = self.client.get(self.url)

        self.assertEqual(resposta.status_code, status.HTTP_200_OK)
        self.assertEqual(resposta.data["ativas"], 2)

    def test_token_revogado_nao_conta(self):
        """Sessão encerrada não é sessão; contá-la seria alarme falso."""
        vivo = RefreshToken.for_user(self.user)
        morto = RefreshToken.for_user(self.user)
        morto.blacklist()

        resposta = self.client.get(self.url)

        self.assertEqual(resposta.data["ativas"], 1)
        # Confere que o token remanescente é mesmo o que não foi revogado.
        self.assertTrue(
            OutstandingToken.objects.filter(
                user=self.user, jti=vivo["jti"], blacklistedtoken__isnull=True
            ).exists()
        )

    def test_token_expirado_nao_conta(self):
        """Passada a validade, a sessão já não existe de fato."""
        RefreshToken.for_user(self.user)
        OutstandingToken.objects.filter(user=self.user).update(
            expires_at=timezone.now() - timedelta(days=1)
        )

        resposta = self.client.get(self.url)
        self.assertEqual(resposta.data["ativas"], 0)

    def test_informa_a_janela_da_contagem(self):
        """A interface precisa do número para não prometer precisão que não há.

        Uma sessão abandonada sem logout continua contada até o refresh token
        expirar, então o rótulo fala em "últimos N dias".
        """
        resposta = self.client.get(self.url)
        self.assertEqual(resposta.data["janela_dias"], 7)

    def test_nao_conta_sessoes_de_outro_usuario(self):
        """Isolamento: a contagem é estritamente da conta autenticada."""
        outro = User.objects.create_user(
            username="bruno", password="senha-bem-comprida-123",
            email="bruno@exemplo.com",
        )
        ConfigUsuario.objects.get_or_create(usuario=outro)
        RefreshToken.for_user(outro)
        RefreshToken.for_user(outro)

        resposta = self.client.get(self.url)
        self.assertEqual(resposta.data["ativas"], 0)


@override_settings(CACHES=CACHES_DE_TESTE)
class EncerrarOutrasSessoesAPITests(APITestCase):
    """Cobre o encerramento das demais sessões."""

    def setUp(self):
        """Cria e autentica um usuário, limpando o throttle."""
        caches["throttle"].clear()
        self.senha = "senha-bem-comprida-123"
        self.user = User.objects.create_user(
            username="ana", password=self.senha, email="ana@exemplo.com",
        )
        ConfigUsuario.objects.get_or_create(usuario=self.user)
        self.client.force_authenticate(user=self.user)
        self.url = reverse("api-auth-sessoes-encerrar-outras")

    def tearDown(self):
        """Evita que a contagem de throttle vaze para outros testes."""
        caches["throttle"].clear()

    def test_exige_autenticacao(self):
        """Encerrar sessão alheia por rota anônima seria negação de serviço."""
        self.client.force_authenticate(user=None)
        self.assertEqual(
            self.client.post(self.url).status_code, status.HTTP_401_UNAUTHORIZED
        )

    def test_revoga_os_tokens_anteriores(self):
        """O propósito da ação: derrubar o que estava aberto."""
        antigo = str(RefreshToken.for_user(self.user))

        self.client.post(self.url)

        self.client.force_authenticate(user=None)
        resposta = self.client.post(
            reverse("token_refresh"), {"refresh": antigo}, format="json"
        )
        self.assertEqual(resposta.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_devolve_sessao_nova_para_quem_pediu(self):
        """Quem encerrou as outras não pode ser deslogado junto.

        Como o cookie de refresh não alcança esta rota, revogamos tudo e emitimos
        uma sessão nova. Sem isso, a ação expulsaria o próprio usuário.
        """
        resposta = self.client.post(self.url)

        self.assertEqual(resposta.status_code, status.HTTP_200_OK)
        self.assertIn("access", resposta.data)
        self.assertIn("refresh_token", resposta.cookies)

    def test_a_sessao_devolvida_funciona(self):
        """Contraprova do teste anterior: o token novo renova de verdade."""
        resposta = self.client.post(self.url)
        novo_refresh = resposta.cookies["refresh_token"].value

        self.client.force_authenticate(user=None)
        renovacao = self.client.post(
            reverse("token_refresh"), {"refresh": novo_refresh}, format="json"
        )
        self.assertEqual(renovacao.status_code, status.HTTP_200_OK)

    def test_contagem_apos_encerrar_e_de_uma_sessao(self):
        """Sobra exatamente a sessão de quem pediu."""
        RefreshToken.for_user(self.user)
        RefreshToken.for_user(self.user)

        resposta = self.client.post(self.url)
        self.assertEqual(resposta.data["ativas"], 1)

    def test_nao_afeta_sessoes_de_outro_usuario(self):
        """Isolamento na ação mais disruptiva desta tela."""
        outro = User.objects.create_user(
            username="bruno", password="senha-bem-comprida-123",
            email="bruno@exemplo.com",
        )
        ConfigUsuario.objects.get_or_create(usuario=outro)
        refresh_do_outro = str(RefreshToken.for_user(outro))

        self.client.post(self.url)

        self.assertFalse(
            BlacklistedToken.objects.filter(token__user=outro).exists()
        )
        self.client.force_authenticate(user=None)
        resposta = self.client.post(
            reverse("token_refresh"), {"refresh": refresh_do_outro}, format="json"
        )
        self.assertEqual(resposta.status_code, status.HTTP_200_OK)
