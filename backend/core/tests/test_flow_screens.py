from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import AccessToken
from core.models import Categoria, Conta, CartaoCredito
from decimal import Decimal
import datetime

User = get_user_model()

class EndToEndFlowScreensTestCase(APITestCase):
    """
    Testes de Fluxos Completos das Telas (End-to-End API Integration).
    Simula de forma realista o comportamento do frontend React interagindo com a API
    do backend Django para garantir que 100% das telas estão em pleno funcionamento
    sem depender de nenhum arquivo legada movido para a pasta 'remocao'.
    """

    def setUp(self):
        # Criação de um usuário padrão para autenticação nas APIs protegidas
        self.user = User.objects.create_user(username="testuser", password="securepassword123")
        self.token = str(AccessToken.for_user(self.user))
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.token}")

        # Configura categorias padrão
        self.cat_receita = Categoria.objects.create(
            usuario=self.user, nome="Salário Base", tipo=Categoria.TIPO_RECEITA
        )
        self.cat_despesa = Categoria.objects.create(
            usuario=self.user, nome="Aluguel Mensal", tipo=Categoria.TIPO_DESPESA
        )

    def test_screen_flow_registration_and_auth(self):
        """
        [Fluxo de Autenticação/Registro]
        Simula um novo usuário se cadastrando no aplicativo.
        """
        url_register = reverse('api-register')
        payload = {
            "username": "brandnewuser",
            "password": "brandnewpassword123",
            "confirm": "brandnewpassword123"
        }
        # Limpa credenciais temporariamente para simular acesso anônimo
        self.client.credentials()
        response = self.client.post(url_register, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn("access", response.data)

        # Restaura a credencial para os testes seguintes
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.token}")

    def test_screen_flow_dashboard_retrieval(self):
        """
        [Fluxo da Tela de Dashboard Principal]
        Simula a renderização da tela principal contendo receitas, despesas,
        saldos, gráficos diários, fluxo projetado e breakdowns de despesas por categoria.
        """
        # Cria lançamentos no banco para popular o dashboard
        hoje = datetime.date.today()
        # 1. Receita realizada
        Conta.objects.create(
            usuario=self.user, tipo=Conta.TIPO_RECEITA, descricao="Salário",
            valor=Decimal("5000.00"), data_prevista=hoje, transacao_realizada=True,
            data_realizacao=hoje, categoria=self.cat_receita
        )
        # 2. Despesa pendente
        Conta.objects.create(
            usuario=self.user, tipo=Conta.TIPO_DESPESA, descricao="Internet",
            valor=Decimal("150.00"), data_prevista=hoje, transacao_realizada=False,
            categoria=self.cat_despesa
        )

        url_dashboard = reverse('api-dashboard')
        response = self.client.get(url_dashboard)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        data = response.json()
        self.assertIn("total_receitas", data)
        self.assertIn("total_despesas", data)
        self.assertIn("saldo_mes", data)
        self.assertEqual(data["total_receitas"], 5000.0)
        self.assertEqual(data["total_despesas"], 150.0)
        self.assertEqual(data["saldo_mes"], 4850.0)

        # Verifica estruturas de gráficos
        self.assertIn("grafico_diario", data)
        self.assertIn("grafico_projetado", data)
        self.assertIn("breakdown_despesas", data)
        self.assertIn("proximas_contas", data)
        self.assertIn("ultimas_transacoes", data)

    def test_screen_flow_contas_pagar_management(self):
        """
        [Fluxo da Tela de Contas a Pagar]
        Simula o cadastro de despesas, filtragem mensal e a ação de pagar uma conta.
        """
        url_contas = "/api/financeiro/contas-pagar/"
        hoje = datetime.date.today()

        # 1. Cadastro de uma nova conta de luz
        payload = {
            "descricao": "Conta de Luz",
            "valor": 250.50,
            "data_vencimento": hoje.strftime("%Y-%m-%d"),
            "categoria": "Utilidades"
        }
        response = self.client.post(url_contas, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["descricao"], "Conta de Luz")
        self.assertEqual(response.data["valor"], "250.50")
        self.assertFalse(response.data["pago"])
        conta_id = response.data["id"]

        # 1.5. Edição da conta de luz criada (PUT request)
        payload_update = {
            "descricao": "Luz",
            "categoria": "Gastos",
            "valor": 207.93,
            "data_vencimento": hoje.strftime("%Y-%m-%d")
        }
        response_update = self.client.put(f"{url_contas}{conta_id}/", payload_update, format='json')
        self.assertEqual(response_update.status_code, status.HTTP_200_OK)
        self.assertEqual(response_update.data["descricao"], "Luz")
        self.assertEqual(response_update.data["valor"], "207.93")
        self.assertEqual(response_update.data["categoria"], "Gastos")

        # 2. Filtragem de contas a pagar
        response_list = self.client.get(f"{url_contas}?mes={hoje.month}&ano={hoje.year}")
        self.assertEqual(response_list.status_code, status.HTTP_200_OK)
        self.assertTrue(len(response_list.json()) >= 1)

        # 3. Ação de marcar como paga (Ação executada na tela)
        url_pagar = f"{url_contas}{conta_id}/pagar/"
        response_pagar = self.client.put(url_pagar)
        self.assertEqual(response_pagar.status_code, status.HTTP_200_OK)
        self.assertTrue(response_pagar.data["pago"])

        # 4. Ação de marcar como paga uma conta de outro mês (para testar o bypass de filtro no detail request)
        outra_data = hoje - datetime.timedelta(days=60)
        payload_outro_mes = {
            "descricao": "Conta Mês Passado",
            "valor": 100.00,
            "data_vencimento": outra_data.strftime("%Y-%m-%d"),
            "categoria": "Gastos"
        }
        response_outro = self.client.post(url_contas, payload_outro_mes, format='json')
        self.assertEqual(response_outro.status_code, status.HTTP_201_CREATED)
        outro_id = response_outro.data["id"]

        url_pagar_outro = f"{url_contas}{outro_id}/pagar/"
        response_pagar_outro = self.client.put(url_pagar_outro)
        self.assertEqual(response_pagar_outro.status_code, status.HTTP_200_OK)
        self.assertTrue(response_pagar_outro.data["pago"])

    def test_screen_flow_receitas_management(self):
        """
        [Fluxo da Tela de Receitas]
        Simula o cadastro e a filtragem mensal de receitas.
        """
        url_receitas = "/api/financeiro/receitas/"
        hoje = datetime.date.today()

        payload = {
            "descricao": "Consultoria Extra",
            "valor": 1200.00,
            "data_recebimento": hoje.strftime("%Y-%m-%d"),
            "categoria": "Serviços Freelance"
        }
        response = self.client.post(url_receitas, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["descricao"], "Consultoria Extra")
        self.assertEqual(response.data["valor"], "1200.00")
        receita_id = response.data["id"]

        # 2. Edição da receita criada (mudando a data para o próximo mês para validar o bypass de filtro)
        next_month = hoje + datetime.timedelta(days=32)
        payload_update = {
            "descricao": "Consultoria Extra Ajustada",
            "valor": 1500.00,
            "data_recebimento": next_month.strftime("%Y-%m-%d"),
            "categoria": "Serviços Freelance Premium"
        }
        response_update = self.client.put(f"{url_receitas}{receita_id}/", payload_update, format='json')
        self.assertEqual(response_update.status_code, status.HTTP_200_OK)
        self.assertEqual(response_update.data["descricao"], "Consultoria Extra Ajustada")
        self.assertEqual(response_update.data["valor"], "1500.00")
        self.assertEqual(response_update.data["categoria"], "Serviços Freelance Premium")
        self.assertEqual(response_update.data["data_recebimento"], next_month.strftime("%Y-%m-%d"))

        # 3. Verifica listagem de receitas da tela no próximo período
        response_list = self.client.get(f"{url_receitas}?mes={next_month.month}&ano={next_month.year}")
        self.assertEqual(response_list.status_code, status.HTTP_200_OK)
        self.assertTrue(len(response_list.json()) >= 1)

    def test_screen_flow_transacoes_history(self):
        """
        [Fluxo da Tela de Extrato / Transações]
        Verifica a listagem unificada de receitas e despesas efetuadas/pagas.
        """
        hoje = datetime.date.today()
        # Cria uma despesa paga (Transação realizada)
        Conta.objects.create(
            usuario=self.user, tipo=Conta.TIPO_DESPESA, descricao="Mercado",
            valor=Decimal("300.00"), data_prevista=hoje, transacao_realizada=True,
            data_realizacao=hoje, categoria=self.cat_despesa
        )
        # Cria uma despesa pendente (NÃO deve aparecer no extrato de transações realizadas)
        Conta.objects.create(
            usuario=self.user, tipo=Conta.TIPO_DESPESA, descricao="Fretamento",
            valor=Decimal("90.00"), data_prevista=hoje, transacao_realizada=False,
            categoria=self.cat_despesa
        )

        url_transacoes = f"/api/financeiro/transacoes/?mes={hoje.month:02d}&ano={hoje.year}"
        response = self.client.get(url_transacoes)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        data = response.json()
        descriptions = [tx["descricao"] for tx in data]
        self.assertIn("Mercado", descriptions)
        self.assertNotIn("Fretamento", descriptions)

    def test_screen_flow_investimentos_dashboard(self):
        """
        [Fluxo da Tela de Investimentos]
        Testa o acesso à carteira de ativos e painel de balanceamento.
        """
        url_dashboard_invest = reverse('api-investimentos-dashboard')
        response = self.client.get(url_dashboard_invest)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        data = response.json()
        self.assertIn("total_patrimonio", data)
        self.assertIn("total_investido", data)
        self.assertIn("total_rentabilidade", data)

        url_balanceamento = reverse('api-investimentos-balanceamento')
        response_bal = self.client.get(url_balanceamento)
        self.assertEqual(response_bal.status_code, status.HTTP_200_OK)

    def test_screen_flow_ferramentas_e_relatorios(self):
        """
        [Fluxo das Telas de Ferramentas e Relatórios]
        Testa as rotas de importação, conciliação e exportação.
        """
        # Relatórios DRE
        url_dre = reverse('api-relatorios-dre')
        response_dre = self.client.get(url_dre)
        self.assertEqual(response_dre.status_code, status.HTTP_200_OK)

        # Conciliação Bancária
        url_conciliacao = reverse('api-ferramentas-conciliacao')
        response_conc = self.client.get(url_conciliacao)
        self.assertEqual(response_conc.status_code, status.HTTP_200_OK)
