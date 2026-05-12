from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from django.utils import timezone

class InvestimentoViewsTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username="testuser", password="password")
        self.dashboard_url = reverse("investimento:dashboard")
        self.ativos_url = reverse("investimento:ativo_listar")
        self.transacoes_url = reverse("investimento:transacao_listar")

    def test_dashboard_redirects_if_not_logged_in(self):
        response = self.client.get(self.dashboard_url)
        self.assertEqual(response.status_code, 302)

    def test_dashboard_accessible_after_login(self):
        self.client.login(username="testuser", password="password")
        response = self.client.get(self.dashboard_url)
        self.assertEqual(response.status_code, 200)

    def test_ativos_list_accessible_after_login(self):
        self.client.login(username="testuser", password="password")
        response = self.client.get(self.ativos_url)
        self.assertEqual(response.status_code, 200)

    def test_transacoes_list_accessible_after_login(self):
        self.client.login(username="testuser", password="password")
        response = self.client.get(self.transacoes_url)
        self.assertEqual(response.status_code, 200)

    def test_criar_ativo_post(self):
        self.client.login(username="testuser", password="password")
        from investimento.models import ClasseAtivo, CategoriaAtivo, SubcategoriaAtivo, Ativo
        classe = ClasseAtivo.objects.create(usuario=self.user, nome="RV")
        cat = CategoriaAtivo.objects.create(usuario=self.user, classe=classe, nome="Ações")
        sub = SubcategoriaAtivo.objects.create(usuario=self.user, categoria=cat, nome="Brasil")
        
        url = reverse("investimento:ativo_criar")
        data = {
            "ticker": "ITUB4",
            "nome": "Itaú Unibanco",
            "subcategoria": sub.id,
            "moeda": "BRL",
            "ativo": True,
            # Campos de posição inicial opcionais
            "quantidade_inicial": "",
            "preco_medio_inicial": ""
        }
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Ativo.objects.filter(ticker="ITUB4").exists())

    def test_criar_transacao_post(self):
        self.client.login(username="testuser", password="password")
        from investimento.models import ClasseAtivo, CategoriaAtivo, SubcategoriaAtivo, Ativo, Transacao
        classe = ClasseAtivo.objects.create(usuario=self.user, nome="RV")
        cat = CategoriaAtivo.objects.create(usuario=self.user, classe=classe, nome="Ações")
        sub = SubcategoriaAtivo.objects.create(usuario=self.user, categoria=cat, nome="Brasil")
        ativo = Ativo.objects.create(usuario=self.user, ticker="BBDC4", subcategoria=sub)
        
        url = reverse("investimento:transacao_criar")
        data = {
            "ativo": ativo.id,
            "tipo": Transacao.TIPO_COMPRA,
            "data": timezone.localdate().strftime("%d/%m/%Y"),
            "quantidade": "10",
            "preco_unitario": "15.50",
            "taxas": "0.00"
        }
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Transacao.objects.filter(ativo=ativo, quantidade=10).exists())
