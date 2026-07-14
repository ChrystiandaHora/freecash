from unittest.mock import patch, MagicMock
from django.contrib.auth.models import User
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import AccessToken
from decimal import Decimal
import datetime
import json

from investimento.models import Ativo, ClasseAtivo, CategoriaAtivo, SubcategoriaAtivo, Cotacao

class AtivoViewSetTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser_views",
            password="senha_segura_123"
        )
        # Autenticação com JWT
        token = str(AccessToken.for_user(self.user))
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

        # O signal de User automático pode já criar classes/categorias,
        # então usamos get_or_create para evitar colisões
        self.classe, _ = ClasseAtivo.objects.get_or_create(usuario=self.user, nome="Renda Variável")
        self.categoria, _ = CategoriaAtivo.objects.get_or_create(usuario=self.user, classe=self.classe, nome="Ações")
        self.subcategoria, _ = SubcategoriaAtivo.objects.get_or_create(usuario=self.user, categoria=self.categoria, nome="Ações Brasil")
        
        self.ativo = Ativo.objects.create(
            usuario=self.user,
            ticker="PETR4",
            nome="Petrobras",
            subcategoria=self.subcategoria
        )

    @patch("urllib.request.urlopen")
    def test_atualizar_ativo_quotes_history_success(self, mock_urlopen):
        # Mock do retorno da API do Yahoo Finance
        mock_response = MagicMock()
        mock_json_content = {
            "chart": {
                "result": [
                    {
                        "timestamp": [1687522800, 1687609200],
                        "indicators": {
                            "quote": [
                                {
                                    "close": [30.15, 30.40]
                                }
                            ]
                        }
                    }
                ],
                "error": None
            }
        }
        mock_response.read.return_value = json.dumps(mock_json_content).encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = mock_response

        url = reverse("api-ativo-atualizar", kwargs={"pk": self.ativo.id})
        response = self.client.post(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 2)
        
        # Verifica se as cotações foram criadas no banco de dados
        self.assertEqual(Cotacao.objects.filter(ativo=self.ativo).count(), 2)
        
        # 1687522800 é 23/06/2023 em UTC
        quote1 = Cotacao.objects.get(ativo=self.ativo, data=datetime.date(2023, 6, 23))
        self.assertEqual(quote1.valor, Decimal("30.15"))
        
        # 1687609200 é 24/06/2023 em UTC
        quote2 = Cotacao.objects.get(ativo=self.ativo, data=datetime.date(2023, 6, 24))
        self.assertEqual(quote2.valor, Decimal("30.40"))

    def test_atualizar_ativo_sem_ticker_error(self):
        ativo_sem_ticker = Ativo.objects.create(
            usuario=self.user,
            ticker="",
            nome="Sem Ticker",
            subcategoria=self.subcategoria
        )
        url = reverse("api-ativo-atualizar", kwargs={"pk": ativo_sem_ticker.id})
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("não possui um ticker", response.data["error"])

    @patch("urllib.request.urlopen")
    def test_atualizar_ativo_fracionario_B3_success(self, mock_urlopen):
        # Ticker fracionário (PRIO3F)
        ativo_frac = Ativo.objects.create(
            usuario=self.user,
            ticker="PRIO3F",
            nome="Petrorio",
            subcategoria=self.subcategoria
        )
        mock_response = MagicMock()
        mock_json_content = {
            "chart": {
                "result": [
                    {
                        "timestamp": [1687522800],
                        "indicators": {
                            "quote": [
                                {
                                    "close": [35.50]
                                }
                            ]
                        }
                    }
                ],
                "error": None
            }
        }
        mock_response.read.return_value = json.dumps(mock_json_content).encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = mock_response

        url = reverse("api-ativo-atualizar", kwargs={"pk": ativo_frac.id})
        response = self.client.post(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # O mock_urlopen deve ter sido chamado com a URL normalizada para PRIO3.SA (removendo F final e adicionando .SA)
        args, kwargs = mock_urlopen.call_args
        requested_req = args[0]
        self.assertIn("PRIO3.SA", requested_req.full_url)
        self.assertNotIn("PRIO3F", requested_req.full_url)

    def test_retrieve_ativo_returns_latest_30_quotes_in_chronological_order(self):
        # Create 35 quotes for the asset, one per day starting from 35 days ago
        base_date = datetime.date.today() - datetime.timedelta(days=35)
        for i in range(35):
            Cotacao.objects.create(
                ativo=self.ativo,
                data=base_date + datetime.timedelta(days=i),
                valor=Decimal("100.00") + Decimal(i)
            )

        url = reverse("api-ativo-detail", kwargs={"pk": self.ativo.id})
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        historico = response.data["historico_cotacoes"]
        
        # Should return exactly 30 quotes
        self.assertEqual(len(historico), 30)
        
        # The first returned quote should be the 6th created quote (day 5 of offset, i.e., index 5)
        expected_first_date = str(base_date + datetime.timedelta(days=5))
        expected_last_date = str(base_date + datetime.timedelta(days=34))
        
        self.assertEqual(historico[0]["data"], expected_first_date)
        self.assertEqual(historico[0]["valor"], 105.0)
        
        # The last returned quote should be the 35th created quote (day 34 of offset, i.e., index 34)
        self.assertEqual(historico[-1]["data"], expected_last_date)
        self.assertEqual(historico[-1]["valor"], 134.0)


