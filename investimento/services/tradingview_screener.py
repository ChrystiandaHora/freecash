import json
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Iterable
from urllib.error import URLError, HTTPError
from urllib.request import Request, urlopen


@dataclass(frozen=True)
class TradingViewQuote:
    symbol: str
    close: Decimal
    as_of: date


def _normalize_to_tradingview_symbol(ticker: str) -> str:
    """
    Converte o ticker salvo no sistema para o formato esperado pelo TradingView Screener.

    Heurística atual:
    - Se já vier no formato "EXCHANGE:SYMBOL", mantém.
    - Se vier como "PETR4.SA", remove ".SA".
    - Caso contrário, assume Bolsa Brasil (BMFBOVESPA).
    """
    ticker = (ticker or "").strip().upper()
    if not ticker:
        return ""

    if ":" in ticker:
        return ticker

    if ticker.endswith(".SA"):
        ticker = ticker[: -len(".SA")]

    return f"BMFBOVESPA:{ticker}"


def _build_scan_payload(symbols: list[str], limit: int) -> dict:
    return {
        "symbols": {"tickers": symbols},
        "columns": ["close"],
        "range": [0, limit],
    }


def fetch_quotes_brazil(
    tickers: Iterable[str],
    *,
    timeout_seconds: int = 15,
    limit: int = 500,
) -> dict[str, TradingViewQuote]:
    """
    Busca preço (close) via TradingView Screener (scanner endpoint Brasil).

    Retorna um dict indexado pelo ticker normalizado "EXCHANGE:SYMBOL".
    """
    symbols = []
    for ticker in tickers:
        sym = _normalize_to_tradingview_symbol(ticker)
        if sym:
            symbols.append(sym)

    if not symbols:
        return {}

    url = "https://scanner.tradingview.com/brazil/scan"
    payload = _build_scan_payload(symbols, limit=limit)

    req = Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            # Alguns ambientes bloqueiam sem UA/referer; mantemos simples.
            "User-Agent": "Mozilla/5.0 (compatible; freecash/1.0)",
            "Origin": "https://br.tradingview.com",
            "Referer": "https://br.tradingview.com/screener/",
        },
        method="POST",
    )

    try:
        with urlopen(req, timeout=timeout_seconds) as resp:
            body = resp.read().decode("utf-8")
            data = json.loads(body)
    except (URLError, HTTPError, json.JSONDecodeError) as e:
        raise RuntimeError(f"Falha ao consultar TradingView Screener: {e}") from e

    results: dict[str, TradingViewQuote] = {}
    as_of = date.today()
    for row in data.get("data", []) or []:
        symbol = row.get("s")
        cols = row.get("d") or []
        if not symbol or not cols:
            continue
        close = cols[0]
        if close is None:
            continue
        try:
            close_dec = Decimal(str(close))
        except Exception:
            continue
        results[symbol] = TradingViewQuote(symbol=symbol, close=close_dec, as_of=as_of)

    return results

