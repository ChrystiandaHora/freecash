from django.test import SimpleTestCase

from investimento.services.tradingview_screener import (
    _build_scan_payload,
    _normalize_to_tradingview_symbol,
 )


class TradingViewScreenerTests(SimpleTestCase):
    def test_normalize_symbol_keeps_exchange_prefix(self):
        self.assertEqual(
            _normalize_to_tradingview_symbol("BMFBOVESPA:PETR4"), "BMFBOVESPA:PETR4"
        )

    def test_normalize_symbol_strips_sa_suffix(self):
        self.assertEqual(_normalize_to_tradingview_symbol("PETR4.SA"), "BMFBOVESPA:PETR4")

    def test_normalize_symbol_defaults_bmfbovespa(self):
        self.assertEqual(_normalize_to_tradingview_symbol("VALE3"), "BMFBOVESPA:VALE3")

    def test_build_payload_shape(self):
        payload = _build_scan_payload(["BMFBOVESPA:PETR4"], limit=500)
        self.assertEqual(payload["symbols"]["tickers"], ["BMFBOVESPA:PETR4"])
        self.assertEqual(payload["columns"], ["close"])
        self.assertEqual(payload["range"], [0, 500])


from django.test import TestCase
from django.contrib.auth.models import User
from datetime import date
from decimal import Decimal
from investimento.models import CarteiraHistorico
from investimento.services.carteira_historico_service import CarteiraHistoricoService

class CarteiraHistoricoServiceTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="testuser", password="password")
        self.service = CarteiraHistoricoService(self.user)

    def test_obter_rentabilidade_mensal_por_ano(self):
        # Mês 1: Jan 2026. Investido = 1000, Patrimonio = 1050 (Rentabilidade = 50, Rentabilidade % = 5%)
        # Mês 2: Fev 2026. Investido = 1500, Patrimonio = 1600 (Rentabilidade = 100, Rentabilidade % = 6.67%)
        # Mês 3: Mar 2026. Investido = 1500, Patrimonio = 1550 (Rentabilidade = 50, Rentabilidade % = 3.33%)
        CarteiraHistorico.objects.create(
            usuario=self.user,
            data=date(2026, 1, 31),
            patrimonio=Decimal("1050.00"),
            total_compras=Decimal("1000.00"),
            total_vendas=Decimal("0.00"),
            total_dividendos=Decimal("0.00"),
            rentabilidade=Decimal("50.00"),
            rentabilidade_percentual=Decimal("5.000000"),
        )
        CarteiraHistorico.objects.create(
            usuario=self.user,
            data=date(2026, 2, 28),
            patrimonio=Decimal("1600.00"),
            total_compras=Decimal("1500.00"),
            total_vendas=Decimal("0.00"),
            total_dividendos=Decimal("0.00"),
            rentabilidade=Decimal("100.00"),
            rentabilidade_percentual=Decimal("6.666667"),
        )
        CarteiraHistorico.objects.create(
            usuario=self.user,
            data=date(2026, 3, 31),
            patrimonio=Decimal("1550.00"),
            total_compras=Decimal("1500.00"),
            total_vendas=Decimal("0.00"),
            total_dividendos=Decimal("0.00"),
            rentabilidade=Decimal("50.00"),
            rentabilidade_percentual=Decimal("3.333333"),
        )

        matrix = self.service.obter_rentabilidade_mensal_por_ano()
        
        # Verificar estrutura
        self.assertIn(2026, matrix)
        self.assertIn(1, matrix[2026])
        self.assertIn(2, matrix[2026])
        self.assertIn(3, matrix[2026])

        # Verificar cálculos:
        # Jan 2026:
        # delta_rentabilidade = 50
        # capital_base = patrimonio_prev(0) + delta_compras(1000) = 1000
        # retorno = 50 / 1000 * 100 = 5%
        self.assertAlmostEqual(matrix[2026][1], 5.0, places=2)

        # Fev 2026:
        # delta_rentabilidade = 100 - 50 = 50
        # capital_base = patrimonio_prev(1050) + delta_compras(500) = 1550
        # retorno = 50 / 1550 * 100 = 3.2258% -> 3.23%
        self.assertAlmostEqual(matrix[2026][2], 3.2258, places=2)

        # Mar 2026:
        # delta_rentabilidade = 50 - 100 = -50
        # capital_base = patrimonio_prev(1600) + delta_compras(0) = 1600
        # retorno = -50 / 1600 * 100 = -3.125% -> -3.13%
        self.assertAlmostEqual(matrix[2026][3], -3.125, places=2)
