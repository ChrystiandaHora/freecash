from django.test import TestCase
from django.contrib.auth.models import User
from django.utils import timezone
from investimento.models import Ativo, Transacao, ClasseAtivo, CategoriaAtivo, SubcategoriaAtivo
from investimento.forms import TransacaoForm, AtivoForm
from decimal import Decimal

class InvestimentoFormsTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="testuser", password="password")
        # Use get_or_create because signals already create default classes
        self.classe, _ = ClasseAtivo.objects.get_or_create(usuario=self.user, nome="Renda Variável")
        self.categoria, _ = CategoriaAtivo.objects.get_or_create(usuario=self.user, classe=self.classe, nome="Ações")
        self.subcategoria, _ = SubcategoriaAtivo.objects.get_or_create(usuario=self.user, categoria=self.categoria, nome="Ações Brasil")
        
        self.ativo = Ativo.objects.create(
            usuario=self.user,
            ticker="PETR4",
            subcategoria=self.subcategoria
        )

    def test_transacao_form_compra_valid(self):
        form_data = {
            "ativo": self.ativo.id,
            "tipo": Transacao.TIPO_COMPRA,
            "data": timezone.localdate().strftime("%d/%m/%Y"),
            "quantidade": "100",
            "preco_unitario": "30.00",
            "taxas": "5.00"
        }
        form = TransacaoForm(data=form_data)
        self.assertTrue(form.is_valid())
        self.assertEqual(form.cleaned_data["valor_total"], Decimal("3005.00"))

    def test_transacao_form_dividendo_logic(self):
        # Dividendos usam o campo virtual 'valor_dividendo'
        form_data = {
            "ativo": self.ativo.id,
            "tipo": Transacao.TIPO_DIVIDENDO,
            "data": timezone.localdate().strftime("%d/%m/%Y"),
            "valor_dividendo": "50.00",
            "taxas": "0.00"
        }
        form = TransacaoForm(data=form_data)
        self.assertTrue(form.is_valid())
        # A lógica do clean() deve preencher quantidade=1 e preco=valor
        self.assertEqual(form.cleaned_data["quantidade"], 1)
        self.assertEqual(form.cleaned_data["preco_unitario"], Decimal("50.00"))
        self.assertEqual(form.cleaned_data["valor_total"], Decimal("50.00"))

    def test_ativo_form_com_posicao_inicial(self):
        # Testa se o AtivoForm cria uma transação de compra automática
        form_data = {
            "ticker": "VALE3",
            "nome": "Vale SA",
            "subcategoria": self.subcategoria.id,
            "moeda": "BRL",
            "ativo": True,
            "quantidade_inicial": "10",
            "preco_medio_inicial": "70.00",
            "data_compra": timezone.localdate().strftime("%d/%m/%Y")
        }
        form = AtivoForm(data=form_data)
        self.assertTrue(form.is_valid())
        
        # Salvando o formulário para disparar process_initial_position
        ativo = form.save(commit=False)
        ativo.usuario = self.user # Atribuindo usuário manualmente pois o form não lida com isso no Meta
        ativo.save()
        form.process_initial_position(ativo)
        
        # Verifica se a transação foi criada
        transacao = Transacao.objects.filter(ativo=ativo).first()
        self.assertIsNotNone(transacao)
        self.assertEqual(transacao.quantidade, Decimal("10"))
        self.assertEqual(transacao.preco_unitario, Decimal("70.00"))
        self.assertEqual(transacao.tipo, Transacao.TIPO_COMPRA)
