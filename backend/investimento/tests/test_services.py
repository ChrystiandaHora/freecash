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
