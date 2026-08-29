"""Testes da revogação de sessões.

`revogar_tokens_do_usuario` é o ponto único usado pela redefinição de senha, pela
suspensão administrativa e pelo encerramento de todas as sessões. Os fluxos que o
chamam têm testes; a função em si não tinha — e é ela que decide se um refresh
token roubado continua valendo por até sete dias.

O que precisa ser verdade:

**Revogar de fato invalida.** Não basta contar: o token precisa deixar de servir
para obter um novo access token.

**A revogação é por usuário.** Um encerramento de sessões não pode alcançar a
conta de outra pessoa.

**Chamar duas vezes não inventa revogações.** O retorno alimenta o log e a
resposta da API; contar de novo o que já estava na blacklist daria a impressão
de que havia sessões abertas que não existiam.
"""

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.token_blacklist.models import (
    BlacklistedToken,
    OutstandingToken,
)
from rest_framework_simplejwt.tokens import RefreshToken

from core.services.auth_service import revogar_tokens_do_usuario

User = get_user_model()


class RevogarTokensDoUsuarioTests(TestCase):
    """Verifica o encerramento das sessões de um usuário."""

    def setUp(self):
        """Cria duas contas, para que o isolamento possa ser observado."""
        self.usuario = User.objects.create_user(
            username="joana", email="joana@exemplo.com", password="senha-comprida-123"
        )
        self.outro = User.objects.create_user(
            username="pedro", email="pedro@exemplo.com", password="senha-comprida-123"
        )

    def test_revoga_todos_os_tokens_do_usuario(self):
        """Cada refresh token ativo vira uma entrada na blacklist."""
        RefreshToken.for_user(self.usuario)
        RefreshToken.for_user(self.usuario)

        self.assertEqual(revogar_tokens_do_usuario(self.usuario), 2)
        self.assertEqual(
            BlacklistedToken.objects.filter(token__user=self.usuario).count(), 2
        )

    def test_token_revogado_deixa_de_funcionar(self):
        """A revogação impede o uso posterior do refresh token.

        Contar registros na blacklist provaria apenas que uma linha foi gravada.
        O que importa é o efeito: o token não pode mais ser trocado por acesso.
        """
        token = RefreshToken.for_user(self.usuario)

        revogar_tokens_do_usuario(self.usuario)

        with self.assertRaises(TokenError):
            RefreshToken(str(token)).check_blacklist()

    def test_nao_alcanca_sessoes_de_outro_usuario(self):
        """Revogar as sessões de uma conta não encerra as de outra."""
        RefreshToken.for_user(self.usuario)
        token_do_outro = RefreshToken.for_user(self.outro)

        revogar_tokens_do_usuario(self.usuario)

        self.assertFalse(
            BlacklistedToken.objects.filter(token__user=self.outro).exists()
        )
        # Continua utilizável: não levanta.
        RefreshToken(str(token_do_outro)).check_blacklist()

    def test_segunda_chamada_nao_conta_de_novo(self):
        """Tokens já revogados não entram na contagem de uma nova chamada."""
        RefreshToken.for_user(self.usuario)

        self.assertEqual(revogar_tokens_do_usuario(self.usuario), 1)
        self.assertEqual(revogar_tokens_do_usuario(self.usuario), 0)

    def test_usuario_sem_sessao_retorna_zero(self):
        """Sem token emitido, não há o que revogar."""
        self.assertEqual(OutstandingToken.objects.filter(user=self.usuario).count(), 0)
        self.assertEqual(revogar_tokens_do_usuario(self.usuario), 0)

    def test_registra_a_revogacao_no_log(self):
        """A operação deixa rastro: é evento de segurança, não rotina silenciosa."""
        RefreshToken.for_user(self.usuario)

        with self.assertLogs("core", level="INFO") as capturado:
            revogar_tokens_do_usuario(self.usuario)

        self.assertTrue(
            any("Sessões revogadas" in linha for linha in capturado.output)
        )
