from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from django.utils import timezone
from core.models import Categoria

class CoreViewsTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username="testuser", password="password")
        self.landing_url = reverse("landing")
        self.dashboard_url = reverse("dashboard")
        self.contas_url = reverse("contas_pagar")
        self.receitas_url = reverse("receitas")
        self.cartoes_url = reverse("cartoes")

    def test_landing_page_accessible_publicly(self):
        response = self.client.get(self.landing_url)
        self.assertEqual(response.status_code, 200)

    def test_dashboard_redirects_if_not_logged_in(self):
        response = self.client.get(self.dashboard_url)
        # Assuming LoginRequiredMixin is used
        self.assertEqual(response.status_code, 302)

    def test_dashboard_accessible_after_login(self):
        self.client.login(username="testuser", password="password")
        response = self.client.get(self.dashboard_url)
        self.assertEqual(response.status_code, 200)

    def test_contas_pagar_accessible_after_login(self):
        self.client.login(username="testuser", password="password")
        response = self.client.get(self.contas_url)
        self.assertEqual(response.status_code, 200)

    def test_receitas_accessible_after_login(self):
        self.client.login(username="testuser", password="password")
        response = self.client.get(self.receitas_url)
        self.assertEqual(response.status_code, 200)

    def test_cartoes_accessible_after_login(self):
        self.client.login(username="testuser", password="password")
        response = self.client.get(self.cartoes_url)
        self.assertEqual(response.status_code, 200)

    def test_criar_receita_post(self):
        self.client.login(username="testuser", password="password")
        categoria = Categoria.objects.create(usuario=self.user, nome="Job", tipo=Categoria.TIPO_RECEITA)
        url = reverse("receita_nova")
        data = {
            "descricao": "Job Extra",
            "valor": "500.00",
            "data_prevista": timezone.localdate().strftime("%Y-%m-%d"),
            "categoria": categoria.id,
            "transacao_realizada": True
        }
        response = self.client.post(url, data)
        # Should redirect after success
        self.assertEqual(response.status_code, 302)
        from core.models import Conta
        self.assertTrue(Conta.objects.filter(descricao="Job Extra").exists())

    def test_marcar_conta_paga_post(self):
        self.client.login(username="testuser", password="password")
        from core.models import Conta
        conta = Conta.objects.create(
            usuario=self.user,
            tipo=Conta.TIPO_DESPESA,
            descricao="Luz",
            valor="150.00",
            data_prevista=timezone.localdate(),
            transacao_realizada=False
        )
        url = reverse("marcar_conta_paga", kwargs={"conta_id": conta.id})
        response = self.client.post(url)
        self.assertEqual(response.status_code, 302)
        conta.refresh_from_db()
        self.assertTrue(conta.transacao_realizada)
