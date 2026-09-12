"""Testes do ciclo de vida da sessão JWT: cookie, revogação no logout e throttling.

Três defeitos concretos motivaram o arquivo: o cookie do refresh era gravado com
`secure=False` fixo, trafegando em claro sob HTTP; `BLACKLIST_AFTER_ROTATION` estava
ligado sem o app `token_blacklist`, então nada era revogável e um refresh copiado
valia sete dias; e o cookie usava `path="/api/token/refresh/"`, que nunca chega a
`/api/token/clear/` — o logout não conseguia ler o token que deveria revogar.
"""

from django.conf import settings
from django.core.cache import caches
from django.test import override_settings
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken
from rest_framework_simplejwt.tokens import RefreshToken

User = get_user_model()

# O throttle usa DatabaseCache em produção; nos testes, um cache local por teste
# evita depender da tabela de cache e o isolamento é garantido no setUp.
CACHES_DE_TESTE = {
    "default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"},
    "throttle": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"},
}


class CookieRefreshTokenTests(APITestCase):
    """Verifica os atributos do cookie que transporta o refresh token."""

    def setUp(self):
        """Cria um usuário e resolve a URL de login."""
        self.senha = "senha-bem-comprida-123"
        self.user = User.objects.create_user(username="ana", password=self.senha)
        self.url_login = reverse("token_obtain_pair")

    def test_cookie_de_login_usa_path_que_alcanca_o_logout(self):
        """O path deve cobrir /clear/ por prefixo, senão o logout não recebe o cookie."""
        resposta = self.client.post(
            self.url_login,
            {"username": "ana", "password": self.senha},
            format="json",
        )
        self.assertEqual(resposta.status_code, status.HTTP_200_OK)

        cookie = resposta.cookies[settings.AUTH_COOKIE_NAME]
        self.assertEqual(cookie["path"], "/api/token/")
        self.assertTrue(cookie["httponly"])

        # O caminho do logout precisa começar com o path do cookie, senão o
        # navegador não o envia e a revogação se torna impossível.
        self.assertTrue(reverse("token_clear").startswith(cookie["path"]))

    def test_cookie_max_age_derivado_do_simple_jwt(self):
        """O tempo de vida do cookie acompanha REFRESH_TOKEN_LIFETIME."""
        resposta = self.client.post(
            self.url_login,
            {"username": "ana", "password": self.senha},
            format="json",
        )
        esperado = int(settings.SIMPLE_JWT["REFRESH_TOKEN_LIFETIME"].total_seconds())
        self.assertEqual(
            int(resposta.cookies[settings.AUTH_COOKIE_NAME]["max-age"]), esperado
        )

    @override_settings(AUTH_COOKIE_SECURE=True)
    def test_cookie_respeita_flag_secure_de_configuracao(self):
        """Com AUTH_COOKIE_SECURE ligado, o cookie sai marcado como Secure."""
        resposta = self.client.post(
            self.url_login,
            {"username": "ana", "password": self.senha},
            format="json",
        )
        self.assertTrue(resposta.cookies[settings.AUTH_COOKIE_NAME]["secure"])

    @override_settings(AUTH_COOKIE_SECURE=False)
    def test_cookie_sem_secure_em_desenvolvimento(self):
        """Sem HTTPS local, o cookie não pode ser Secure ou o login não persiste."""
        resposta = self.client.post(
            self.url_login,
            {"username": "ana", "password": self.senha},
            format="json",
        )
        self.assertFalse(resposta.cookies[settings.AUTH_COOKIE_NAME]["secure"])


class LogoutRevogacaoTests(APITestCase):
    """Verifica que o logout revoga o refresh token, e não apenas apaga o cookie."""

    def setUp(self):
        """Cria um usuário e resolve as URLs de sessão."""
        self.senha = "senha-bem-comprida-123"
        self.user = User.objects.create_user(username="bruno", password=self.senha)
        self.url_login = reverse("token_obtain_pair")
        self.url_logout = reverse("token_clear")
        self.url_refresh = reverse("token_refresh")

    def test_logout_registra_token_na_blacklist(self):
        """Após o logout, o refresh token usado deve constar como revogado."""
        login = self.client.post(
            self.url_login,
            {"username": "bruno", "password": self.senha},
            format="json",
        )
        self.assertEqual(login.status_code, status.HTTP_200_OK)
        self.assertEqual(BlacklistedToken.objects.count(), 0)

        # O cookie viaja automaticamente porque o path do cookie cobre esta rota.
        logout = self.client.post(self.url_logout)
        self.assertEqual(logout.status_code, status.HTTP_200_OK)
        self.assertEqual(BlacklistedToken.objects.count(), 1)

    def test_refresh_token_nao_funciona_apos_logout(self):
        """Este é o comportamento que o usuário espera de um logout."""
        login = self.client.post(
            self.url_login,
            {"username": "bruno", "password": self.senha},
            format="json",
        )
        refresh_capturado = login.cookies[settings.AUTH_COOKIE_NAME].value

        self.client.post(self.url_logout)

        # Reapresentar o token no corpo simula um atacante que o copiou antes do
        # logout — o cookie apagado no navegador não o protegeria.
        resposta = self.client.post(
            self.url_refresh, {"refresh": refresh_capturado}, format="json"
        )
        self.assertEqual(resposta.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_logout_sem_cookie_responde_sucesso(self):
        """Sem sessão ativa, o logout é idempotente: o estado desejado já vale."""
        resposta = self.client.post(self.url_logout)
        self.assertEqual(resposta.status_code, status.HTTP_200_OK)
        self.assertEqual(BlacklistedToken.objects.count(), 0)

    def test_logout_com_token_invalido_nao_estoura(self):
        """Um cookie corrompido não deve produzir 500."""
        self.client.cookies[settings.AUTH_COOKIE_NAME] = "isto-nao-e-um-jwt"
        resposta = self.client.post(self.url_logout)
        self.assertEqual(resposta.status_code, status.HTTP_200_OK)

    def test_rotacao_invalida_o_refresh_anterior(self):
        """Com ROTATE_REFRESH_TOKENS, o token antigo deve morrer ao ser usado."""
        refresh = RefreshToken.for_user(self.user)
        primeiro = str(refresh)

        rotacao = self.client.post(
            self.url_refresh, {"refresh": primeiro}, format="json"
        )
        self.assertEqual(rotacao.status_code, status.HTTP_200_OK)

        # A view lê o cookie antes do corpo, e a rotação acima já gravou o cookie
        # novo. Sem limpá-lo, a tentativa de reuso usaria o token novo e passaria.
        self.client.cookies.clear()

        reuso = self.client.post(
            self.url_refresh, {"refresh": primeiro}, format="json"
        )
        self.assertEqual(reuso.status_code, status.HTTP_401_UNAUTHORIZED)


@override_settings(CACHES=CACHES_DE_TESTE)
class ThrottlingAutenticacaoTests(APITestCase):
    """Verifica o rate limiting dos endpoints de autenticação."""

    def setUp(self):
        """Limpa o cache de throttle para que os testes não contaminem uns aos outros."""
        caches["throttle"].clear()
        self.url_login = reverse("token_obtain_pair")
        self.url_register = reverse("api-register")
        User.objects.create_user(username="carla", password="senha-bem-comprida-123")

    def tearDown(self):
        """Evita que a contagem vaze para os demais testes da suíte."""
        caches["throttle"].clear()

    def test_login_repetido_com_senha_errada_acaba_bloqueado(self):
        """Força bruta de senha deve encontrar atrito: o limite é 10/min."""
        codigos = []
        for _ in range(12):
            resposta = self.client.post(
                self.url_login,
                {"username": "carla", "password": "errada"},
                format="json",
            )
            codigos.append(resposta.status_code)

        self.assertIn(status.HTTP_429_TOO_MANY_REQUESTS, codigos)
        # As primeiras tentativas continuam sendo avaliadas normalmente.
        self.assertEqual(codigos[0], status.HTTP_401_UNAUTHORIZED)

    def test_registro_em_massa_acaba_bloqueado(self):
        """Criação de contas em série deve ser limitada: o limite é 10/hora."""
        codigos = []
        for indice in range(12):
            resposta = self.client.post(
                self.url_register,
                {
                    "username": f"usuario{indice}",
                    "email": f"usuario{indice}@exemplo.com",
                    "password": "senha-bem-comprida-123",
                    "confirm": "senha-bem-comprida-123",
                },
                format="json",
            )
            codigos.append(resposta.status_code)

        self.assertIn(status.HTTP_429_TOO_MANY_REQUESTS, codigos)
        self.assertEqual(codigos[0], status.HTTP_201_CREATED)

    def test_throttle_de_login_nao_afeta_endpoints_de_dados(self):
        """O throttle é opt-in: o uso normal do aplicativo não é estrangulado."""
        for _ in range(12):
            self.client.post(
                self.url_login,
                {"username": "carla", "password": "errada"},
                format="json",
            )

        self.client.force_authenticate(user=User.objects.get(username="carla"))
        resposta = self.client.get(reverse("api-conta-list"))
        self.assertEqual(resposta.status_code, status.HTTP_200_OK)
