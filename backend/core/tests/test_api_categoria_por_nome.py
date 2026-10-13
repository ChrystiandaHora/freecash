"""Testes da resolução de categoria pelo nome nas rotas de lançamento.

O nome identifica a categoria do usuário (`unique_together = ("usuario", "nome")`),
mas as rotas buscavam por nome *e* tipo. Um nome já existente com outro tipo — a
"Investimento" padrão, de tipo 'I', usada numa despesa — não era encontrado, o
`create` batia na restrição única e a requisição terminava em 500.
"""

from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase

from core.models import CartaoCredito, Categoria, Conta, ConfigUsuario, Evento
from core.services.dashboard_helper import saldo_liquidez_ate

User = get_user_model()


class CategoriaPorNomeAPITests(APITestCase):
    """Cobre o reaproveitamento de categoria existente com tipo diferente."""

    def setUp(self):
        """Autentica um usuário que já tem a categoria padrão "Investimento"."""
        self.user = User.objects.create_user(
            username="ana", password="senha-bem-comprida-123",
            email="ana@exemplo.com",
        )
        ConfigUsuario.objects.get_or_create(usuario=self.user)
        self.client.force_authenticate(user=self.user)
        self.investimento = Categoria.objects.create(
            usuario=self.user, nome="Investimento",
            tipo=Categoria.TIPO_INVESTIMENTO, is_default=True,
        )

    def _assert_reaproveitou(self, resposta):
        """Confere o 201 e que nenhuma categoria nova foi criada."""
        self.assertEqual(resposta.status_code, status.HTTP_201_CREATED, resposta.data)
        self.assertEqual(Categoria.objects.filter(usuario=self.user).count(), 1)

    def test_conta_a_pagar_reaproveita_categoria_de_outro_tipo(self):
        resposta = self.client.post("/api/financeiro/contas-pagar/", {
            "descricao": "Aporte mensal",
            "valor": "500.00",
            "data_vencimento": "2026-10-15",
            "categoria": "Investimento",
        }, format="json")

        self._assert_reaproveitou(resposta)
        conta = Conta.objects.get(usuario=self.user, descricao="Aporte mensal")
        self.assertEqual(conta.categoria_id, self.investimento.id)
        self.assertEqual(conta.tipo, Conta.TIPO_DESPESA)

    def test_aporte_em_evento_fora_do_dre_sai_dos_kpis_mas_nao_do_caixa(self):
        """O lançamento da tela: categoria "Investimento" num evento fora do DRE."""
        evento = Evento.objects.create(
            usuario=self.user, nome="Investimento", inicio=date(2025, 5, 1),
            fim=date(2026, 10, 31), orcamento=Decimal("9427.43"),
            fora_dos_relatorios=True,
        )
        resposta = self.client.post("/api/financeiro/contas-pagar/", {
            "descricao": "Aporte outubro",
            "valor": "500.00",
            "data_vencimento": "2026-10-13",
            "categoria": "Investimento",
            "evento": evento.id,
        }, format="json")

        self._assert_reaproveitou(resposta)
        conta = Conta.objects.get(usuario=self.user, descricao="Aporte outubro")
        self.assertEqual(conta.evento_id, evento.id)
        self.assertFalse(
            Conta.objects.do_orcamento().filter(pk=conta.pk).exists(),
            "conta de evento fora do DRE não pode entrar nos KPIs",
        )

        Conta.objects.filter(pk=conta.pk).update(
            transacao_realizada=True, data_realizacao=date(2026, 10, 13)
        )
        self.assertEqual(saldo_liquidez_ate(self.user, date(2026, 10, 31)), -500.0)

    def test_receita_reaproveita_categoria_de_outro_tipo(self):
        resposta = self.client.post("/api/financeiro/receitas/", {
            "descricao": "Resgate",
            "valor": "300.00",
            "data_recebimento": "2026-10-15",
            "categoria": "Investimento",
        }, format="json")

        self._assert_reaproveitou(resposta)
        conta = Conta.objects.get(usuario=self.user, descricao="Resgate")
        self.assertEqual(conta.categoria_id, self.investimento.id)

    def test_lote_de_contas_reaproveita_categoria_de_outro_tipo(self):
        resposta = self.client.post("/api/financeiro/contas-pagar/lote/", {
            "itens": [{
                "descricao": "Aporte lote",
                "valor": "100.00",
                "data_vencimento": "2026-10-15",
                "categoria": "Investimento",
            }],
        }, format="json")

        self._assert_reaproveitou(resposta)
        conta = Conta.objects.get(usuario=self.user, descricao="Aporte lote")
        self.assertEqual(conta.categoria_id, self.investimento.id)

    def test_compra_cartao_reaproveita_categoria_de_outro_tipo(self):
        cartao = CartaoCredito.objects.create(
            usuario=self.user, nome="Cartão", ultimos_digitos="1234",
            dia_fechamento=25, dia_vencimento=5,
        )
        resposta = self.client.post("/api/financeiro/compras-cartao/", {
            "descricao": "Compra de cota",
            "valor": "80.00",
            "data_compra": "2026-10-05",
            "cartao": cartao.id,
            "categoria": "Investimento",
        }, format="json")

        self.assertEqual(resposta.status_code, status.HTTP_201_CREATED, resposta.data)
        conta = Conta.objects.get(usuario=self.user, descricao="Compra de cota")
        self.assertEqual(conta.categoria_id, self.investimento.id)

    def test_nome_inexistente_cria_categoria_com_o_tipo_da_rota(self):
        resposta = self.client.post("/api/financeiro/contas-pagar/", {
            "descricao": "Luz",
            "valor": "120.00",
            "data_vencimento": "2026-10-15",
            "categoria": "Moradia",
        }, format="json")

        self.assertEqual(resposta.status_code, status.HTTP_201_CREATED, resposta.data)
        criada = Categoria.objects.get(usuario=self.user, nome="Moradia")
        self.assertEqual(criada.tipo, Categoria.TIPO_DESPESA)
