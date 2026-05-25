"""Serviço de Consulta de Cotações via TradingView Screener.

Este módulo implementa a integração com a API pública de scanner do TradingView para a
Bolsa de Valores do Brasil (BMFBOVESPA). Ele permite buscar a cotação de fechamento
(close) mais recente de múltiplos ativos de renda variável de forma consolidada e eficiente,
evitando consultas individuais ou scraping ineficiente.
"""

import json
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Iterable
from urllib.error import URLError, HTTPError
from urllib.request import Request, urlopen


@dataclass(frozen=True)
class TradingViewQuote:
    """Estrutura representativa de uma cotação de ativo retornada pelo TradingView.

    Atributos:
        symbol (str): O ticker completo do ativo no formato do TradingView (ex: "BMFBOVESPA:PETR4").
        close (Decimal): O valor de fechamento/cotação mais recente do ativo.
        as_of (date): A data de referência da cotação consultada.
    """
    symbol: str
    close: Decimal
    as_of: date


def _normalize_to_tradingview_symbol(ticker: str) -> str:
    """Converte e padroniza o ticker interno para o formato esperado pelo TradingView Screener.

    Aplica heurísticas para identificar a bolsa de valores correspondente e adequar a formatação.

    Heurística aplicada:
        - Se o ticker já contiver dois pontos (ex: "EXCHANGE:SYMBOL"), mantém como está.
        - Se terminar com ".SA" (padrão Yahoo/B3 comum), remove o sufixo ".SA".
        - Caso contrário, adiciona o prefixo padrão da Bolsa do Brasil "BMFBOVESPA:".

    Args:
        ticker (str): O código do ativo cadastrado no sistema (ex: "PETR4", "PETR4.SA", "NASDAQ:AAPL").

    Returns:
        str: O ticker formatado e normalizado ou uma string vazia caso o parâmetro seja nulo/inválido.
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
    """Constrói o payload JSON de requisição para a API de varredura do TradingView.

    Gera a estrutura necessária para solicitar especificamente o campo de fechamento (`close`)
    para uma lista explícita de tickers dentro dos limites operacionais.

    Args:
        symbols (list[str]): Lista de tickers normalizados no formato do TradingView.
        limit (int): Número máximo de registros a serem processados no escopo do scanner.

    Returns:
        dict: O dicionário representando o payload JSON estruturado pronto para serialização.
    """
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
    """Consulta e extrai as cotações atualizadas de múltiplos ativos de renda variável do Brasil.

    Realiza uma requisição HTTP POST síncrona diretamente no endpoint de scan do TradingView Brasil,
    processa os resultados em formato JSON e constrói instâncias de cotações normalizadas.

    Args:
        tickers (Iterable[str]): Coleção de tickers dos ativos a serem consultados (ex: ["PETR4", "VALE3"]).
        timeout_seconds (int, optional): Tempo limite em segundos para a requisição de rede. Defaults to 15.
        limit (int, optional): Limite de paginação de registros consultados. Defaults to 500.

    Raises:
        RuntimeError: Se houver falha de rede (URLError/HTTPError) ou falha na decodificação do payload JSON.

    Returns:
        dict[str, TradingViewQuote]: Dicionário mapeando cada ticker normalizado (ex: "BMFBOVESPA:PETR4")
            à sua respectiva cotação consolidada (`TradingViewQuote`).
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


