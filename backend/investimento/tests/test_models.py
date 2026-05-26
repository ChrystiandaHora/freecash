from django.test import TestCase
from django.contrib.auth.models import User
from django.utils import timezone
from investimento.models import Ativo, Transacao, Cotacao, ClasseAtivo, CategoriaAtivo, SubcategoriaAtivo
from decimal import Decimal

class InvestimentoModelsTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="testuser", password="password")
        # Creating hierarchy (Signals might handle this, but let's be explicit if needed)
        self.classe = ClasseAtivo.objects.get_or_create(usuario=self.user, nome="Renda Variável")[0]
        self.categoria = CategoriaAtivo.objects.get_or_create(usuario=self.user, classe=self.classe, nome="Ações")[0]
        self.subcategoria = SubcategoriaAtivo.objects.get_or_create(usuario=self.user, categoria=self.categoria, nome="Ações Brasil")[0]
        
        self.ativo = Ativo.objects.create(
            usuario=self.user,
            ticker="PETR4",
            nome="Petrobras PN",
            subcategoria=self.subcategoria
        )

    def test_ativo_recalculation_on_purchase(self):
        # Create a purchase transaction
        Transacao.objects.create(
            usuario=self.user,
            ativo=self.ativo,
            tipo=Transacao.TIPO_COMPRA,
            data=timezone.localdate(),
            quantidade=Decimal("100"),
            preco_unitario=Decimal("30.00"),
            valor_total=Decimal("3000.00")
        )
        
        self.ativo.refresh_from_db()
        self.assertEqual(self.ativo.quantidade, Decimal("100"))
        self.assertEqual(self.ativo.preco_medio, Decimal("30.00"))

    def test_ativo_recalculation_on_sale(self):
        # Purchase first
        Transacao.objects.create(
            usuario=self.user,
            ativo=self.ativo,
            tipo=Transacao.TIPO_COMPRA,
            data=timezone.localdate(),
            quantidade=Decimal("100"),
            preco_unitario=Decimal("30.00"),
            valor_total=Decimal("3000.00")
        )
        # Sale 50
        Transacao.objects.create(
            usuario=self.user,
            ativo=self.ativo,
            tipo=Transacao.TIPO_VENDA,
            data=timezone.localdate(),
            quantidade=Decimal("50"),
            preco_unitario=Decimal("40.00"),
            valor_total=Decimal("2000.00")
        )
        
        self.ativo.refresh_from_db()
        self.assertEqual(self.ativo.quantidade, Decimal("50"))
        self.assertEqual(self.ativo.preco_medio, Decimal("30.00")) # PM should not change on sale

    def test_ativo_rentabilidade_properties(self):
        # Setup: 100 units at 30.00 (Total 3000)
        self.ativo.quantidade = Decimal("100")
        self.ativo.preco_medio = Decimal("30.00")
        self.ativo.save()
        
        # Add a quote of 35.00
        Cotacao.objects.create(ativo=self.ativo, data=timezone.localdate(), valor=Decimal("35.00"))
        
        self.assertEqual(self.ativo.valor_investido, Decimal("3000.00"))
        self.assertEqual(self.ativo.valor_total_atual, Decimal("3500.00"))
        self.assertEqual(self.ativo.rentabilidade, Decimal("500.00"))
        self.assertEqual(self.ativo.rentabilidade_percentual, Decimal("16.66666666666666666666666667")) # 500/3000 * 100
