from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import AccessToken
from core.models import Conta
from django.utils import timezone

User = get_user_model()

class SecurityIsolationAPITestCase(APITestCase):
    """
    Testes de Isolamento e Segurança da API REST.
    Garante que os usuários só consigam ver, editar ou deletar
    seus próprios registros, retornando 404 para tentativas de acesso cruzado.
    """
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
        self.token_joao = str(AccessToken.for_user(self.user_joao))
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.token_joao}")

        # URL da API REST correspondente à conta da Maria
        self.url = f"/api/contas/{self.conta_maria.id}/"

    def test_usuario_nao_pode_ver_conta_de_outro_via_api(self):
        # Tenta dar GET na conta da Maria com as credenciais do João
        response = self.client.get(self.url)
        # O sistema deve retornar 404 pois o viewset filtra pelo usuário autenticado
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_usuario_nao_pode_editar_conta_de_outro_via_api(self):
        # Tenta dar PUT para alterar a conta da Maria com as credenciais do João
        payload = {
            "descricao": "Invasão do João",
            "valor": "0.01"
        }
        response = self.client.put(self.url, payload, format='json')
        # Deve retornar 404
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        
        # A conta original não deve ter sido alterada
        self.conta_maria.refresh_from_db()
        self.assertEqual(self.conta_maria.descricao, "Segredo da Maria")

    def test_usuario_nao_pode_apagar_conta_de_outro_via_api(self):
        # Tenta dar DELETE na conta da Maria com as credenciais do João
        response = self.client.delete(self.url)
        # Deve retornar 404 e a conta deve continuar existindo no banco
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertTrue(Conta.objects.filter(id=self.conta_maria.id).exists())
