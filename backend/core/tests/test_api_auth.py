from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from core.models import ConfigUsuario, Categoria

User = get_user_model()

class UserRegistrationAPITestCase(APITestCase):
    def setUp(self):
        self.url = reverse('api-register')

    def test_registration_success_and_ecosystem_creation(self):
        payload = {
            "username": "newuser",
            "password": "securepassword123",
            "confirm": "securepassword123"
        }
        response = self.client.post(self.url, payload, format='json')
        
        # Verify response code
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        # Verify access token is returned
        self.assertIn("access", response.data)
        
        # Verify refresh token cookie is set
        self.assertIn("refresh_token", response.cookies)
        cookie = response.cookies["refresh_token"]
        self.assertTrue(cookie["httponly"])
        self.assertEqual(cookie["path"], "/api/token/refresh/")
        
        # Verify user is created in database
        user_exists = User.objects.filter(username="newuser").exists()
        self.assertTrue(user_exists)
        
        user = User.objects.get(username="newuser")
        
        # Verify password is encrypted and readable
        self.assertTrue(user.check_password("securepassword123"))
        
        # Verify user settings are created (ecosystem check 1)
        config_exists = ConfigUsuario.objects.filter(usuario=user).exists()
        self.assertTrue(config_exists)
        
        # Verify user default categories are created (ecosystem check 2)
        categories = Categoria.objects.filter(usuario=user)
        self.assertEqual(categories.count(), 3)
        self.assertTrue(categories.filter(nome="Receita", tipo=Categoria.TIPO_RECEITA).exists())
        self.assertTrue(categories.filter(nome="Gastos", tipo=Categoria.TIPO_DESPESA).exists())
        self.assertTrue(categories.filter(nome="Investimento", tipo=Categoria.TIPO_INVESTIMENTO).exists())

    def test_registration_missing_fields(self):
        payload = {
            "username": "newuser",
            "password": "securepassword123"
            # confirm missing
        }
        response = self.client.post(self.url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["detail"], "Todos os campos (usuário, senha e confirmação de senha) são obrigatórios.")

    def test_registration_password_too_short(self):
        payload = {
            "username": "newuser",
            "password": "123",
            "confirm": "123"
        }
        response = self.client.post(self.url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["detail"], "A senha deve ter no mínimo 6 caracteres.")

    def test_registration_password_mismatch(self):
        payload = {
            "username": "newuser",
            "password": "password123",
            "confirm": "differentpassword"
        }
        response = self.client.post(self.url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["detail"], "As senhas não coincidem.")

    def test_registration_existing_username(self):
        # Create an existing user first
        User.objects.create_user(username="existinguser", password="password123")
        
        payload = {
            "username": "existinguser",
            "password": "securepassword123",
            "confirm": "securepassword123"
        }
        response = self.client.post(self.url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["detail"], "Este nome de usuário já está em uso.")
