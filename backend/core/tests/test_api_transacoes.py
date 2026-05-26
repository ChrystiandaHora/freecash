from django.contrib.auth.models import User
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import AccessToken
from core.models import Categoria, Conta

class TransacoesAPITestCase(APITestCase):
    def setUp(self):
        # Create users
        self.user_a = User.objects.create_user(username="usera", password="password")
        self.user_b = User.objects.create_user(username="userb", password="password")

        # Create defaults
        self.cat_receita = Categoria.objects.create(
            usuario=self.user_a, nome="Salário", tipo=Categoria.TIPO_RECEITA
        )
        self.cat_despesa = Categoria.objects.create(
            usuario=self.user_a, nome="Aluguel", tipo=Categoria.TIPO_DESPESA
        )

        # 1. Unpaid bill for User A (Due in May 2026, unpaid) - SHOULD BE EXCLUDED from Transactions
        self.unpaid_bill = Conta.objects.create(
            usuario=self.user_a,
            tipo=Conta.TIPO_DESPESA,
            descricao="Unpaid Bill",
            valor="1200.00",
            data_prevista="2026-05-15",
            transacao_realizada=False,
            categoria=self.cat_despesa
        )

        # 2. Paid bill for User A (Due in April 2026, Paid in May 2026) - SHOULD BE INCLUDED in May 2026
        self.paid_bill = Conta.objects.create(
            usuario=self.user_a,
            tipo=Conta.TIPO_DESPESA,
            descricao="Paid Bill",
            valor="150.00",
            data_prevista="2026-04-20",
            transacao_realizada=True,
            data_realizacao="2026-05-02",
            categoria=self.cat_despesa
        )

        # 3. Revenue for User A (Expected in May 2026) - SHOULD BE INCLUDED in May 2026
        self.revenue = Conta.objects.create(
            usuario=self.user_a,
            tipo=Conta.TIPO_RECEITA,
            descricao="Freelance",
            valor="800.00",
            data_prevista="2026-05-10",
            transacao_realizada=False,
            categoria=self.cat_receita
        )

        # 4. Bill for User B (Paid in May 2026) - SHOULD NOT BE VISIBLE to User A
        self.user_b_bill = Conta.objects.create(
            usuario=self.user_b,
            tipo=Conta.TIPO_DESPESA,
            descricao="User B Bill",
            valor="99.00",
            data_prevista="2026-05-10",
            transacao_realizada=True,
            data_realizacao="2026-05-10",
        )

    def test_transacoes_list_isolation_and_filtering(self):
        # Authenticate User A with JWT
        token = str(AccessToken.for_user(self.user_a))
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
        
        # Request transactions for May 2026
        url = "/api/financeiro/transacoes/?mes=05&ano=2026"
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # 1. Unpaid bills must be excluded
        # 2. User B's bills must be excluded
        # 3. Paid bill (paid in May) and Freelance (expected in May) must be included
        data = response.json()
        self.assertEqual(len(data), 2)
        
        descriptions = [tx["descricao"] for tx in data]
        self.assertIn("Paid Bill", descriptions)
        self.assertIn("Freelance", descriptions)
        self.assertNotIn("Unpaid Bill", descriptions)
        self.assertNotIn("User B Bill", descriptions)

    def test_serializer_date_mapping(self):
        # Authenticate User A with JWT
        token = str(AccessToken.for_user(self.user_a))
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
        
        url = "/api/financeiro/transacoes/?mes=05&ano=2026"
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify mapped 'data' property in serialization matches data_realizacao for paid, fallback to data_prevista
        data = response.json()
        paid_tx = next(tx for tx in data if tx["descricao"] == "Paid Bill")
        rev_tx = next(tx for tx in data if tx["descricao"] == "Freelance")
        
        # Paid bill should show payment date
        self.assertEqual(paid_tx["data"], "2026-05-02")
        self.assertTrue(paid_tx["transacao_realizada"])
        
        # Unrealized revenue should show expected date
        self.assertEqual(rev_tx["data"], "2026-05-10")
        self.assertFalse(rev_tx["transacao_realizada"])
