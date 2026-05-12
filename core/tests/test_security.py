from django.test import TestCase, Client
from django.contrib.auth.models import User
from core.models import Conta
from django.urls import reverse
from django.utils import timezone

class SecurityIsolationTestCase(TestCase):
    def setUp(self):
        # Usuário Vítima
        self.user_maria = User.objects.create_user(username="maria", password="password123")
        self.conta_maria = Conta.objects.create(
            usuario=self.user_maria,
            tipo=Conta.TIPO_DESPESA,
            descricao="Segredo da Maria",
            valor="1000.00",
            data_prevista=timezone.localdate()
        )
        
        # Usuário Atacante (Curioso)
        self.user_joao = User.objects.create_user(username="joao", password="password123")
        self.client_joao = Client()
        self.client_joao.login(username="joao", password="password123")

    def test_usuario_nao_pode_ver_conta_de_outro(self):
        # Tenta acessar a página de edição da conta da Maria
        url = reverse("conta_editar", kwargs={"conta_id": self.conta_maria.id})
        response = self.client_joao.get(url)
        # O sistema deve retornar 404 pois o filtro de usuário não encontrará a conta
        self.assertEqual(response.status_code, 404)

    def test_usuario_nao_pode_apagar_conta_de_outro(self):
        # Tenta apagar a conta da Maria via POST
        url = reverse("apagar_conta", kwargs={"conta_id": self.conta_maria.id})
        response = self.client_joao.post(url)
        # Deve retornar 404 e a conta deve continuar existindo
        self.assertEqual(response.status_code, 404)
        self.assertTrue(Conta.objects.filter(id=self.conta_maria.id).exists())

    def test_usuario_nao_pode_pagar_conta_de_outro(self):
        # Tenta marcar como paga a conta da Maria
        url = reverse("marcar_conta_paga", kwargs={"conta_id": self.conta_maria.id})
        response = self.client_joao.post(url)
        self.assertEqual(response.status_code, 404)
        self.conta_maria.refresh_from_db()
        self.assertFalse(self.conta_maria.transacao_realizada)
