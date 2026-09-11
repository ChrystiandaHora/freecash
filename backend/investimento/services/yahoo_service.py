"""Serviço de consulta do histórico de cotações no Yahoo Finance.

Vive aqui, e não embutido na view, porque dois caminhos precisam dele: o botão
«Atualizar Ativo» do detalhe, que busca a série de um papel só a pedido explícito, e
o completamento automático de histórico da atualização em lote (ver
`calculators.completar_historico`).

O Yahoo é a fonte da **série**; o TradingView e a CVM continuam sendo a fonte do
fechamento **do dia**. A divisão é intencional: o screener do TradingView devolve uma
cotação por ativo numa única requisição em lote, barato o suficiente para rodar a cada
clique, mas não devolve histórico; o Yahoo devolve a série, ao custo de uma requisição
por ticker.
"""

import datetime
import json
import urllib.request
from decimal import Decimal

PERIODO_PADRAO = "2mo"

_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"
)


class YahooIndisponivel(Exception):
    """Falha ao obter a série de um ticker — rede, ticker desconhecido ou sem dados.

    Tipo próprio para que quem chama saiba distinguir "este ticker não deu certo" de
    um erro de programação, e siga para o próximo ativo em vez de abortar o lote.
    """


def normalizar_ticker_yahoo(ticker: str) -> str:
    """Traduz um ticker da B3 para o símbolo equivalente no Yahoo Finance.

    Duas conversões: o sufixo `F` do mercado fracionário é removido (PETR4F → PETR4),
    porque o Yahoo não lista o fracionário e a cotação do lote padrão é a mesma; e o
    sufixo `.SA` é acrescentado aos tickers que terminam em dígito, que é como o Yahoo
    identifica a B3. Símbolos que já trazem `.` ou `:` são deixados como estão — quem
    digitou `AAPL` ou `BTC-USD` quis um papel de fora.

    Returns:
        str: Símbolo pronto para a URL do Yahoo Finance.
    """
    simbolo = (ticker or "").strip().upper()
    if not simbolo:
        return simbolo

    if len(simbolo) >= 2 and simbolo[-1] == "F" and simbolo[-2].isdigit():
        simbolo = simbolo[:-1]

    if simbolo[-1].isdigit() and "." not in simbolo and ":" not in simbolo:
        simbolo = f"{simbolo}.SA"

    return simbolo


def fetch_historico_yahoo(
    ticker: str,
    *,
    periodo: str = PERIODO_PADRAO,
    timeout_seconds: int = 10,
) -> list[tuple[datetime.date, Decimal]]:
    """Baixa a série de fechamentos diários de um ticker.

    Args:
        ticker: Ticker como cadastrado pelo usuário; a normalização é feita aqui.
        periodo: Janela no vocabulário do Yahoo (`1mo`, `2mo`, `6mo`...).
        timeout_seconds: Teto da requisição.

    Returns:
        list[tuple[date, Decimal]]: Pares (data, fechamento) em ordem cronológica,
            já sem os pregões que voltaram com fechamento nulo.

    Raises:
        YahooIndisponivel: Ticker vazio, falha de rede, ticker desconhecido pelo
            Yahoo ou resposta sem nenhum fechamento no período.
    """
    simbolo = normalizar_ticker_yahoo(ticker)
    if not simbolo:
        raise YahooIndisponivel("Ativo sem ticker cadastrado.")

    url = (
        f"https://query1.finance.yahoo.com/v8/finance/chart/{simbolo}"
        f"?range={periodo}&interval=1d"
    )
    requisicao = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})

    try:
        with urllib.request.urlopen(requisicao, timeout=timeout_seconds) as resposta:
            corpo = json.loads(resposta.read().decode("utf-8"))
    except Exception as erro:
        raise YahooIndisponivel(f"Erro de comunicação com Yahoo Finance: {erro}") from erro

    chart = corpo.get("chart", {})
    resultados = chart.get("result")
    if not resultados:
        descricao = (chart.get("error") or {}).get(
            "description", "Ticker não encontrado ou sem cotações disponíveis."
        )
        raise YahooIndisponivel(f"Erro retornado pelo Yahoo Finance: {descricao}")

    resultado = resultados[0]
    timestamps = resultado.get("timestamp", [])
    cotacoes = (resultado.get("indicators", {}).get("quote") or [{}])[0]
    fechamentos = cotacoes.get("close", [])

    if not timestamps or not fechamentos:
        raise YahooIndisponivel(
            "Nenhuma cotação encontrada no histórico do Yahoo Finance para o período."
        )

    serie: list[tuple[datetime.date, Decimal]] = []
    for ts, fechamento in zip(timestamps, fechamentos):
        # Pregão sem negócio volta com `close: null`; gravar zero falsearia o gráfico
        if fechamento is None:
            continue
        data = datetime.datetime.fromtimestamp(ts, tz=datetime.timezone.utc).date()
        serie.append((data, Decimal(str(fechamento))))

    if not serie:
        raise YahooIndisponivel(
            "Nenhuma cotação encontrada no histórico do Yahoo Finance para o período."
        )

    return serie
