from django.contrib.auth.models import User
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import AccessToken
from core.models import Categoria, Conta, CartaoCredito
import datetime

class ComprasCartaoAPITestCase(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="testuser", password="password")
        self.token = str(AccessToken.for_user(self.user))
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.token}")

        self.cartao = CartaoCredito.objects.create(
            usuario=self.user,
            nome="Nubank Teste",
            ultimos_digitos="1234",
            dia_fechamento=25,
            dia_vencimento=5
        )

        self.categoria = Categoria.objects.create(
            usuario=self.user,
            nome="Alimentação",
            tipo=Categoria.TIPO_DESPESA
        )

    def test_criar_compra_cartao_manual_calcula_vencimento(self):
        # 1. Compra antes do fechamento (dia 05 <= dia 25)
        # Deve vencer no mesmo mês seguinte/vencimento mais próximo (05/08/2026)
        url = "/api/financeiro/compras-cartao/"
        payload = {
            "descricao": "Lanche da Tarde",
            "valor": 45.90,
            "data_compra": "2026-07-05",
            "cartao": self.cartao.id,
            "categoria": self.categoria.id
        }
        response = self.client.post(url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["descricao"], "Lanche da Tarde")
        self.assertEqual(response.data["data_vencimento"], "2026-08-05")
        
        # Test generic category fields
        self.assertEqual(response.data["categoria"], self.categoria.id)
        self.assertIsNotNone(response.data["categoria_detalhe"])
        self.assertEqual(response.data["categoria_detalhe"]["id"], self.categoria.id)

        # Check if the consolidated invoice inherited the category
        fatura = Conta.objects.get(
            usuario=self.user,
            cartao=self.cartao,
            eh_fatura_cartao=True,
            data_prevista="2026-08-05"
        )
        self.assertEqual(fatura.categoria_id, self.categoria.id)

        # 2. Compra após o fechamento (dia 26 > dia 25)
        # Deve vencer na fatura subsequente (05/09/2026)
        payload_pos = {
            "descricao": "Jantar Especial",
            "valor": 120.00,
            "data_compra": "2026-07-26",
            "cartao": self.cartao.id,
            "categoria": self.categoria.id
        }
        response_pos = self.client.post(url, payload_pos, format="json")
        self.assertEqual(response_pos.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response_pos.data["data_vencimento"], "2026-09-05")
        self.assertEqual(response_pos.data["categoria"], self.categoria.id)

    def test_editar_compra_cartao_recalcula_vencimento(self):
        # Cria uma compra
        compra = Conta.objects.create(
            usuario=self.user,
            tipo=Conta.TIPO_DESPESA,
            descricao="Compra Inicial",
            valor=100.00,
            data_compra=datetime.date(2026, 7, 5),
            data_prevista=datetime.date(2026, 8, 5),
            cartao=self.cartao
        )

        url = f"/api/financeiro/compras-cartao/{compra.id}/"
        payload = {
            "descricao": "Compra Inicial Editada",
            "valor": 150.00,
            "data_compra": "2026-07-26", # Move para após o fechamento
            "cartao": self.cartao.id,
            "categoria": self.categoria.id
        }
        response = self.client.put(url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["data_vencimento"], "2026-09-05")
        self.assertEqual(response.data["categoria"], self.categoria.id)
