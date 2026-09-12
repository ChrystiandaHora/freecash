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
from investimento.serializers import AtivoSerializer

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

    def test_retrieve_ativo_returns_latest_quotes_in_chronological_order(self):
        # 50 cotações diárias, acima do teto de 45 do serializador
        total = 50
        limite = AtivoSerializer.LIMITE_HISTORICO_COTACOES
        base_date = datetime.date.today() - datetime.timedelta(days=total)
        for i in range(total):
            Cotacao.objects.create(
                ativo=self.ativo,
                data=base_date + datetime.timedelta(days=i),
                valor=Decimal("100.00") + Decimal(i)
            )

        url = reverse("api-ativo-detail", kwargs={"pk": self.ativo.id})
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        historico = response.data["historico_cotacoes"]

        self.assertEqual(len(historico), limite)

        # Corta as mais antigas e devolve em ordem crescente de data
        primeiro = total - limite
        self.assertEqual(historico[0]["data"], str(base_date + datetime.timedelta(days=primeiro)))
        self.assertEqual(historico[0]["valor"], 100.0 + primeiro)
        self.assertEqual(historico[-1]["data"], str(base_date + datetime.timedelta(days=total - 1)))
        self.assertEqual(historico[-1]["valor"], 100.0 + total - 1)


class HistoricoCotacoesActionTests(APITestCase):
    """Cobre a série em lote que alimenta o gráfico comparativo de Meus Ativos."""

    def setUp(self):
        self.user = User.objects.create_user(username="hist_user", password="senha_segura_123")
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {AccessToken.for_user(self.user)}")
        self.url = reverse("api-ativo-historico-cotacoes")

        self.hoje = datetime.date.today()
        self.petr = Ativo.objects.create(usuario=self.user, ticker="PETR4", nome="Petrobras")
        self.hglg = Ativo.objects.create(usuario=self.user, ticker="HGLG11", nome="CSHG Logística")

        for i, valor in enumerate(["30.00", "31.00", "32.00"]):
            Cotacao.objects.create(
                ativo=self.petr,
                data=self.hoje - datetime.timedelta(days=2 - i),
                valor=Decimal(valor),
            )
        Cotacao.objects.create(ativo=self.hglg, data=self.hoje, valor=Decimal("9.50"))

    def test_devolve_uma_serie_por_ativo_em_ordem_cronologica(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["dias"], 60)

        por_ticker = {s["ticker"]: s for s in response.data["series"]}
        self.assertEqual(set(por_ticker), {"PETR4", "HGLG11"})

        pontos = por_ticker["PETR4"]["pontos"]
        self.assertEqual([p["valor"] for p in pontos], [30.0, 31.0, 32.0])
        self.assertEqual([p["data"] for p in pontos], sorted(p["data"] for p in pontos))

    def test_janela_recorta_cotacoes_fora_do_periodo(self):
        Cotacao.objects.create(
            ativo=self.petr, data=self.hoje - datetime.timedelta(days=90), valor=Decimal("20.00")
        )

        # A cotação antiga entra na janela de 120 dias e fica de fora na de 10
        response = self.client.get(self.url, {"dias": 120})
        pontos = next(s for s in response.data["series"] if s["ticker"] == "PETR4")["pontos"]
        self.assertEqual(len(pontos), 4)

        response = self.client.get(self.url, {"dias": 10})
        pontos = next(s for s in response.data["series"] if s["ticker"] == "PETR4")["pontos"]
        self.assertEqual(len(pontos), 3)

    def test_ativo_sem_cotacao_no_periodo_fica_fora_da_resposta(self):
        Ativo.objects.create(usuario=self.user, ticker="ITSA4", nome="Itaúsa")

        response = self.client.get(self.url)

        self.assertNotIn("ITSA4", [s["ticker"] for s in response.data["series"]])

    def test_nao_vaza_serie_de_outro_usuario(self):
        outro = User.objects.create_user(username="outro_hist", password="senha_segura_123")
        alheio = Ativo.objects.create(usuario=outro, ticker="VALE3", nome="Vale")
        Cotacao.objects.create(ativo=alheio, data=self.hoje, valor=Decimal("60.00"))

        response = self.client.get(self.url)

        self.assertNotIn("VALE3", [s["ticker"] for s in response.data["series"]])

    def test_dias_nao_numerico_responde_400(self):
        response = self.client.get(self.url, {"dias": "dois-meses"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_dias_acima_do_teto_e_limitado(self):
        response = self.client.get(self.url, {"dias": 9999})
        self.assertEqual(response.data["dias"], 365)

    def test_exige_autenticacao(self):
        self.client.credentials()
        self.assertEqual(self.client.get(self.url).status_code, status.HTTP_401_UNAUTHORIZED)


