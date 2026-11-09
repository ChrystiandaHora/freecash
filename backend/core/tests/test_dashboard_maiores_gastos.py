"""Testes de quantas categorias o card "Maiores Gastos" do dashboard mostra.

Com 4 categorias antes de "Outros", categorias como Saúde sumiam num mês comum,
escondidas atrás de Cartão de Crédito, Moradia, Investimento e Dízimo.
"""

import datetime
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APITestCase

from core.models import Categoria, Conta

User = get_user_model()


class MaioresGastosTests(APITestCase):
    """Cobre o corte entre as categorias listadas e o "Outros" do dashboard."""

    def setUp(self):
        """Autentica um usuário sem lançamentos."""
        self.user = User.objects.create_user(username="eva", password="senha-bem-comprida-123")
        self.client.force_authenticate(user=self.user)

    def _despesas(self, valores_por_categoria):
        """Cria uma despesa no mês corrente para cada categoria."""
        hoje = datetime.date.today()
        for nome, valor in valores_por_categoria.items():
            categoria = Categoria.objects.create(
                usuario=self.user, nome=nome, tipo=Categoria.TIPO_DESPESA,
            )
            Conta.objects.create(
                usuario=self.user, tipo=Conta.TIPO_DESPESA, descricao=nome,
                valor=Decimal(valor), data_prevista=hoje, categoria=categoria,
            )

    def _maiores_gastos(self):
        """Nomes do card, na ordem em que o dashboard os devolve."""
        resposta = self.client.get(reverse("api-dashboard"))
        return [item["nome"] for item in resposta.json()["breakdown_despesas"]]

    def test_lista_seis_categorias_e_agrupa_o_resto_em_outros(self):
        self._despesas({
            "A": "800", "B": "700", "C": "600", "D": "500",
            "E": "400", "F": "300", "G": "200", "H": "100",
        })

        self.assertEqual(self._maiores_gastos(), ["A", "B", "C", "D", "E", "F", "Outros"])

    def test_sem_outros_quando_cabe_tudo(self):
        self._despesas({"A": "300", "B": "200", "C": "100"})

        self.assertEqual(self._maiores_gastos(), ["A", "B", "C"])
