"""Testes das regras de identidade e deduplicação de fatura de cartão."""

import datetime
from decimal import Decimal
from io import StringIO

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase

from core.models import CartaoCredito, Conta
from core.services.fatura_service import (
    compras_da_fatura,
    deduplicar_faturas,
    obter_ou_criar_fatura,
)


class FaturaBaseTestCase(TestCase):
    """Base com um usuário e um cartão para os cenários de fatura."""

    def setUp(self):
        self.user = User.objects.create_user(username="fatura", password="senha")
        self.cartao = CartaoCredito.objects.create(
            usuario=self.user,
            nome="Cartão Teste",
            ultimos_digitos="9999",
            dia_fechamento=25,
            dia_vencimento=5,
        )

    def criar_fatura(self, data, realizada=False):
        """Cria uma fatura consolidada direto no banco, contornando o get_or_create."""
        return Conta.objects.create(
            usuario=self.user,
            tipo=Conta.TIPO_DESPESA,
            descricao=f"Fatura {data.isoformat()}",
            valor=Decimal("0.00"),
            data_prevista=data,
            cartao=self.cartao,
            eh_fatura_cartao=True,
            transacao_realizada=realizada,
        )

    def criar_compra(self, data_prevista, valor="100.00"):
        """Cria uma compra individual vinculada ao cartão por data de vencimento."""
        return Conta.objects.create(
            usuario=self.user,
            tipo=Conta.TIPO_DESPESA,
            descricao="Compra",
            valor=Decimal(valor),
            data_prevista=data_prevista,
            cartao=self.cartao,
            eh_fatura_cartao=False,
        )


class IdentidadeDaFaturaTests(FaturaBaseTestCase):
    """A busca de fatura precisa usar a mesma chave que a soma e o pagamento."""

    def test_nao_reaproveita_fatura_de_outro_dia_do_mesmo_mes(self):
        antiga = self.criar_fatura(datetime.date(2026, 3, 10))

        nova = obter_ou_criar_fatura(
            self.user, self.cartao, datetime.date(2026, 3, 15)
        )

        self.assertNotEqual(nova.id, antiga.id)
        self.assertEqual(nova.data_prevista, datetime.date(2026, 3, 15))

    def test_compra_nao_fica_orfa_quando_a_data_diverge(self):
        self.criar_fatura(datetime.date(2026, 3, 10))
        fatura = obter_ou_criar_fatura(
            self.user, self.cartao, datetime.date(2026, 3, 15)
        )
        compra = self.criar_compra(datetime.date(2026, 3, 15))

        self.assertIn(compra, compras_da_fatura(fatura))

    def test_reaproveita_a_fatura_da_mesma_data(self):
        existente = self.criar_fatura(datetime.date(2026, 3, 10))

        obtida = obter_ou_criar_fatura(
            self.user, self.cartao, datetime.date(2026, 3, 10)
        )

        self.assertEqual(obtida.id, existente.id)

    def test_prioriza_a_fatura_liquidada_na_mesma_data(self):
        pendente = self.criar_fatura(datetime.date(2026, 3, 10))
        liquidada = self.criar_fatura(datetime.date(2026, 3, 10), realizada=True)

        obtida = obter_ou_criar_fatura(
            self.user, self.cartao, datetime.date(2026, 3, 10)
        )

        self.assertEqual(obtida.id, liquidada.id)
        self.assertNotEqual(obtida.id, pendente.id)

    def test_nao_alcanca_fatura_de_outro_usuario(self):
        outro = User.objects.create_user(username="outro", password="senha")
        Conta.objects.create(
            usuario=outro,
            tipo=Conta.TIPO_DESPESA,
            descricao="Fatura de outro",
            valor=Decimal("0.00"),
            data_prevista=datetime.date(2026, 3, 10),
            cartao=self.cartao,
            eh_fatura_cartao=True,
        )

        fatura = obter_ou_criar_fatura(
            self.user, self.cartao, datetime.date(2026, 3, 10)
        )

        self.assertEqual(fatura.usuario_id, self.user.id)


class DeduplicacaoDeFaturasTests(FaturaBaseTestCase):
    """Consolidar o mês não pode deixar compra sem fatura."""

    def test_reatribui_compras_da_fatura_removida(self):
        mantida = self.criar_fatura(datetime.date(2026, 3, 10))
        removida = self.criar_fatura(datetime.date(2026, 3, 15))
        compra = self.criar_compra(datetime.date(2026, 3, 15))

        deduplicar_faturas(usuario=self.user)

        compra.refresh_from_db()
        self.assertEqual(compra.data_prevista, mantida.data_prevista)
        self.assertIn(compra, compras_da_fatura(mantida))
        self.assertFalse(Conta.objects.filter(id=removida.id).exists())

    def test_dry_run_nao_move_nem_remove(self):
        self.criar_fatura(datetime.date(2026, 3, 10))
        self.criar_fatura(datetime.date(2026, 3, 15))
        compra = self.criar_compra(datetime.date(2026, 3, 15))

        relatorio = deduplicar_faturas(usuario=self.user, dry_run=True)

        compra.refresh_from_db()
        self.assertEqual(compra.data_prevista, datetime.date(2026, 3, 15))
        self.assertEqual(Conta.objects.filter(eh_fatura_cartao=True).count(), 2)
        self.assertEqual(relatorio[0]["datas_reatribuidas"], [datetime.date(2026, 3, 15)])

    def test_preserva_a_fatura_liquidada(self):
        self.criar_fatura(datetime.date(2026, 3, 10))
        liquidada = self.criar_fatura(datetime.date(2026, 3, 20), realizada=True)

        deduplicar_faturas(usuario=self.user)

        restantes = list(Conta.objects.filter(eh_fatura_cartao=True))
        self.assertEqual([f.id for f in restantes], [liquidada.id])

    def test_nao_toca_meses_com_fatura_unica(self):
        marco = self.criar_fatura(datetime.date(2026, 3, 10))
        abril = self.criar_fatura(datetime.date(2026, 4, 10))

        relatorio = deduplicar_faturas(usuario=self.user)

        self.assertEqual(relatorio, [])
        self.assertEqual(
            set(Conta.objects.filter(eh_fatura_cartao=True).values_list("id", flat=True)),
            {marco.id, abril.id},
        )


class ComandoCorrigirFaturasDuplicadasTests(FaturaBaseTestCase):
    """O comando citado pelo aviso de `obter_ou_criar_fatura` precisa existir e rodar."""

    def test_comando_deduplica_e_relata(self):
        mantida = self.criar_fatura(datetime.date(2026, 3, 10))
        removida = self.criar_fatura(datetime.date(2026, 3, 15))
        compra = self.criar_compra(datetime.date(2026, 3, 15))

        saida = StringIO()
        call_command("corrigir_faturas_duplicadas", usuario="fatura", stdout=saida)

        compra.refresh_from_db()
        self.assertEqual(compra.data_prevista, mantida.data_prevista)
        self.assertFalse(Conta.objects.filter(id=removida.id).exists())
        self.assertIn("Removidas 1 fatura(s) duplicada(s)", saida.getvalue())

    def test_comando_dry_run_nao_grava(self):
        self.criar_fatura(datetime.date(2026, 3, 10))
        self.criar_fatura(datetime.date(2026, 3, 15))

        saida = StringIO()
        call_command("corrigir_faturas_duplicadas", "--dry-run", stdout=saida)

        self.assertEqual(Conta.objects.filter(eh_fatura_cartao=True).count(), 2)
        self.assertIn("[dry-run]", saida.getvalue())

    def test_comando_sem_duplicata(self):
        self.criar_fatura(datetime.date(2026, 3, 10))

        saida = StringIO()
        call_command("corrigir_faturas_duplicadas", stdout=saida)

        self.assertIn("Nenhuma fatura duplicada encontrada.", saida.getvalue())

    def test_comando_com_usuario_inexistente(self):
        saida = StringIO()
        call_command("corrigir_faturas_duplicadas", usuario="ninguem", stdout=saida)

        self.assertIn("não encontrado", saida.getvalue())
