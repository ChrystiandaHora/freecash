"""Testes de caracterização de gastos de cartão no detalhamento por categoria.

Cobre a regressão em que todo o gasto do cartão aparecia como "Sem categoria" no
card "Maiores Gastos" do Dashboard: o painel agregava apenas a fatura consolidada
(que nascia sem categoria) e ignorava a classificação feita em cada compra.
"""

import datetime
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from core.models import CartaoCredito, Categoria, Conta
from core.services.dashboard_helper import (
    breakdown_despesas_competencia,
    despesas_por_categoria,
    totals_for_range_competencia,
)
from core.services.fatura_service import CATEGORIA_CARTAO_NOME, obter_ou_criar_fatura

User = get_user_model()


class DespesasPorCategoriaCartaoTestCase(TestCase):
    """Valida o rateio da fatura de cartão entre as categorias das compras."""

    def setUp(self):
        self.user = User.objects.create_user(username="cartaouser", password="senha12345")
        self.cartao = CartaoCredito.objects.create(
            usuario=self.user,
            nome="Nubank",
            ultimos_digitos="9999",
            dia_fechamento=25,
            dia_vencimento=5,
        )
        self.inicio = datetime.date(2026, 8, 1)
        self.fim = datetime.date(2026, 9, 1)
        self.vencimento = datetime.date(2026, 8, 5)

    def _criar_compra(self, descricao, valor, categoria=None):
        return Conta.objects.create(
            usuario=self.user,
            tipo=Conta.TIPO_DESPESA,
            descricao=descricao,
            valor=Decimal(valor),
            data_compra=datetime.date(2026, 7, 10),
            data_prevista=self.vencimento,
            cartao=self.cartao,
            eh_fatura_cartao=False,
            categoria=categoria,
        )

    def _mapa_categorias(self):
        itens = despesas_por_categoria(self.user, self.inicio, self.fim, "data_prevista")
        return {item["nome"]: item["valor"] for item in itens}

    def test_fatura_nasce_caracterizada_como_cartao(self):
        """A fatura consolidada criada pelo signal recebe a categoria de cartão."""
        self._criar_compra("Mercado", "100.00")

        fatura = Conta.objects.get(
            usuario=self.user, cartao=self.cartao, eh_fatura_cartao=True
        )
        self.assertIsNotNone(fatura.categoria)
        self.assertEqual(fatura.categoria.nome, CATEGORIA_CARTAO_NOME)
        self.assertEqual(fatura.categoria.tipo, Categoria.TIPO_DESPESA)

    def test_compra_sem_categoria_aparece_como_cartao(self):
        """Gasto de cartão não classificado é caracterizado como cartão, não como vazio."""
        self._criar_compra("Compra importada", "300.00")

        mapa = self._mapa_categorias()
        self.assertEqual(mapa, {CATEGORIA_CARTAO_NOME: 300.0})
        self.assertNotIn("Sem categoria", mapa)

    def test_categoria_da_compra_chega_ao_breakdown(self):
        """A classificação manual de cada compra é refletida no detalhamento."""
        alimentacao = Categoria.objects.create(
            usuario=self.user, nome="Alimentação", tipo=Categoria.TIPO_DESPESA
        )
        transporte = Categoria.objects.create(
            usuario=self.user, nome="Transporte", tipo=Categoria.TIPO_DESPESA
        )
        self._criar_compra("Restaurante", "200.00", categoria=alimentacao)
        self._criar_compra("Combustível", "150.00", categoria=transporte)
        self._criar_compra("Sem classificar", "50.00")

        self.assertEqual(
            self._mapa_categorias(),
            {"Alimentação": 200.0, "Transporte": 150.0, CATEGORIA_CARTAO_NOME: 50.0},
        )

    def test_detalhamento_soma_o_total_de_despesas_do_periodo(self):
        """O rateio da fatura preserva o total exibido nos cartões do topo."""
        mercado = Categoria.objects.create(
            usuario=self.user, nome="Mercado", tipo=Categoria.TIPO_DESPESA
        )
        moradia = Categoria.objects.create(
            usuario=self.user, nome="Moradia", tipo=Categoria.TIPO_DESPESA
        )
        self._criar_compra("Supermercado", "400.00", categoria=mercado)
        self._criar_compra("Farmácia", "100.00")
        Conta.objects.create(
            usuario=self.user,
            tipo=Conta.TIPO_DESPESA,
            descricao="Aluguel",
            valor=Decimal("1200.00"),
            data_prevista=datetime.date(2026, 8, 10),
            categoria=moradia,
        )

        _, total_despesas = totals_for_range_competencia(self.user, self.inicio, self.fim)
        self.assertEqual(total_despesas, 1700.0)

        soma_itens = sum(self._mapa_categorias().values())
        self.assertAlmostEqual(soma_itens, total_despesas, places=2)

    def test_fatura_paga_com_valor_congelado_e_rateada_proporcionalmente(self):
        """Fatura liquidada cujo valor divergiu das compras mantém o total do painel."""
        lazer = Categoria.objects.create(
            usuario=self.user, nome="Lazer", tipo=Categoria.TIPO_DESPESA
        )
        self._criar_compra("Cinema", "100.00", categoria=lazer)
        self._criar_compra("Streaming", "100.00")

        fatura = Conta.objects.get(
            usuario=self.user, cartao=self.cartao, eh_fatura_cartao=True
        )
        # Simula uma fatura já liquidada com valor ajustado (encargos, por exemplo)
        fatura.transacao_realizada = True
        fatura.data_realizacao = self.vencimento
        fatura.valor = Decimal("300.00")
        fatura.save()

        mapa = self._mapa_categorias()
        self.assertAlmostEqual(mapa["Lazer"], 150.0, places=2)
        self.assertAlmostEqual(mapa[CATEGORIA_CARTAO_NOME], 150.0, places=2)
        self.assertAlmostEqual(sum(mapa.values()), 300.0, places=2)

    def test_fatura_sem_compras_vinculadas_mantem_propria_categoria(self):
        """Fatura lançada à mão, sem compras, entra com a categoria que possui."""
        fatura = obter_ou_criar_fatura(self.user, self.cartao, self.vencimento)
        fatura.valor = Decimal("500.00")
        fatura.save()

        self.assertEqual(self._mapa_categorias(), {CATEGORIA_CARTAO_NOME: 500.0})

    def test_breakdown_nao_reporta_sem_categoria_para_gasto_de_cartao(self):
        """O card "Maiores Gastos" deixa de apontar cartão como "Sem categoria"."""
        self._criar_compra("Compra importada", "800.00")

        _, total_despesas = totals_for_range_competencia(self.user, self.inicio, self.fim)
        itens, top_categoria = breakdown_despesas_competencia(
            self.user, self.inicio, self.fim, total_despesas
        )

        self.assertEqual(top_categoria["nome"], CATEGORIA_CARTAO_NOME)
        self.assertNotIn("Sem categoria", [item["nome"] for item in itens])
