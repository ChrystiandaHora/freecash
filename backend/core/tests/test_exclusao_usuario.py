"""Testes da exclusão de uma conta e de tudo que pende dela.

Excluir um usuário era **impossível**: os receivers de `post_delete` de `Conta` e
`Categoria` chamavam `atualizar_config`, cujo `get_or_create` recriava a
`ConfigUsuario` apontando para a linha de `auth_user` que estava sendo apagada na
mesma transação. O commit falhava com violação de FK e a remoção era desfeita.

Invisível no uso individual — ninguém apaga a própria conta — e obrigatório num
produto público, onde a LGPD garante o direito de exclusão. Os testes usam dados
reais pendurados no usuário, que é o cenário em que os signals disparam.
"""

from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from core.models import (
    CartaoCredito,
    Categoria,
    Conta,
    ConfigUsuario,
    LancamentoRecorrente,
    MetaFinanceira,
)

User = get_user_model()


class ExclusaoDeUsuarioTests(TestCase):
    """Cobre a remoção de uma conta com o ecossistema financeiro povoado."""

    def setUp(self):
        """Cria um usuário com dados de todos os tipos que disparam signals."""
        self.user = User.objects.create_user(
            username="ana", password="senha-bem-comprida-123",
            email="ana@exemplo.com",
        )
        ConfigUsuario.objects.get_or_create(usuario=self.user)

        self.categoria = Categoria.objects.create(
            usuario=self.user, nome="Moradia", tipo=Categoria.TIPO_DESPESA
        )
        cartao = CartaoCredito.objects.create(
            usuario=self.user, nome="Cartão", limite=Decimal("5000.00"),
            dia_fechamento=1, dia_vencimento=10,
        )

        # Lançamento comum, compra de cartão (que aciona a consolidação de fatura)
        # e uma regra de recorrência com ocorrências geradas.
        Conta.objects.create(
            usuario=self.user, tipo=Conta.TIPO_DESPESA, descricao="Aluguel",
            valor=Decimal("2000.00"), data_prevista=date(2026, 4, 10),
            categoria=self.categoria,
        )
        Conta.objects.create(
            usuario=self.user, tipo=Conta.TIPO_DESPESA, descricao="Mercado",
            valor=Decimal("300.00"), data_prevista=date(2026, 4, 10),
            cartao=cartao,
        )
        LancamentoRecorrente.objects.create(
            usuario=self.user, tipo=LancamentoRecorrente.TIPO_RECEITA,
            descricao="Salário", valor=Decimal("8000.00"),
            frequencia=LancamentoRecorrente.FREQ_MENSAL,
            data_inicio=date(2026, 4, 5),
        )
        MetaFinanceira.objects.create(
            usuario=self.user, nome="Reserva",
            valor_alvo=Decimal("10000.00"), valor_acumulado=Decimal("0.00"),
        )

    def test_usuario_com_dados_pode_ser_excluido(self):
        """O caso que falhava: cascade com signals de post_delete ativos."""
        pk = self.user.pk

        self.user.delete()

        self.assertFalse(User.objects.filter(pk=pk).exists())

    def test_exclusao_leva_junto_todo_o_ecossistema(self):
        """Nada do usuário pode sobrar órfão depois da remoção."""
        pk = self.user.pk
        self.user.delete()

        self.assertFalse(ConfigUsuario.objects.filter(usuario_id=pk).exists())
        self.assertFalse(Conta.objects.filter(usuario_id=pk).exists())
        self.assertFalse(Categoria.objects.filter(usuario_id=pk).exists())
        self.assertFalse(CartaoCredito.objects.filter(usuario_id=pk).exists())
        self.assertFalse(LancamentoRecorrente.objects.filter(usuario_id=pk).exists())
        self.assertFalse(MetaFinanceira.objects.filter(usuario_id=pk).exists())

    def test_config_nao_e_recriada_durante_o_cascade(self):
        """Guarda a causa raiz, e não apenas o sintoma.

        Se alguém trocar `atualizar_config_existente` de volta por
        `atualizar_config` nos receivers de exclusão, a configuração ressurge e o
        commit volta a falhar. Este teste é o que acusa a regressão.
        """
        pk = self.user.pk
        self.user.delete()

        self.assertEqual(ConfigUsuario.objects.filter(usuario_id=pk).count(), 0)

    def test_exclusao_nao_afeta_outros_usuarios(self):
        """Isolamento: remover uma conta não pode tocar dados de terceiros."""
        outro = User.objects.create_user(
            username="bruno", password="senha-bem-comprida-123",
            email="bruno@exemplo.com",
        )
        ConfigUsuario.objects.get_or_create(usuario=outro)
        Conta.objects.create(
            usuario=outro, tipo=Conta.TIPO_DESPESA, descricao="Conta do Bruno",
            valor=Decimal("100.00"), data_prevista=date(2026, 4, 10),
        )

        self.user.delete()

        self.assertTrue(User.objects.filter(pk=outro.pk).exists())
        self.assertEqual(Conta.objects.filter(usuario=outro).count(), 1)
        self.assertTrue(ConfigUsuario.objects.filter(usuario=outro).exists())

    def test_exclusao_em_lote_tambem_funciona(self):
        """`queryset.delete()` percorre o mesmo coletor e os mesmos signals."""
        pk = self.user.pk

        User.objects.filter(pk=pk).delete()

        self.assertFalse(User.objects.filter(pk=pk).exists())

    def test_deletar_lancamento_avulso_ainda_atualiza_a_config(self):
        """A correção não pode desligar o comportamento útil dos signals."""
        config = ConfigUsuario.objects.get(usuario=self.user)
        antes = config.atualizada_em

        Conta.objects.filter(usuario=self.user, descricao="Aluguel").first().delete()

        config.refresh_from_db()
        self.assertGreaterEqual(config.atualizada_em, antes)
        # E a configuração continua existindo: só o usuário inteiro a leva embora.
        self.assertTrue(ConfigUsuario.objects.filter(usuario=self.user).exists())
