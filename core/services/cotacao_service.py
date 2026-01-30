"""
Serviço de cotações de moedas via API do Banco Central do Brasil.
"""

import json
from datetime import date, timedelta
from decimal import Decimal
from typing import Optional
from urllib.request import urlopen
from urllib.error import URLError


# Cache simples em memória para evitar chamadas repetidas
_cache: dict = {}


def obter_cotacao(moeda: str, data: Optional[date] = None) -> Optional[Decimal]:
    """
    Obtém a cotação de uma moeda em relação ao BRL.

    Args:
        moeda: Código da moeda (USD, EUR, GBP)
        data: Data da cotação (padrão: hoje)

    Returns:
        Taxa de câmbio ou None se não encontrada
    """
    if moeda == "BRL":
        return Decimal("1.0")

    if data is None:
        data = date.today()

    # Chave de cache
    cache_key = f"{moeda}_{data.isoformat()}"
    if cache_key in _cache:
        return _cache[cache_key]

    # Tenta buscar cotação dos últimos 5 dias úteis
    for dias in range(5):
        data_busca = data - timedelta(days=dias)
        taxa = _buscar_cotacao_bcb(moeda, data_busca)
        if taxa:
            _cache[cache_key] = taxa
            return taxa

    return None


def _buscar_cotacao_bcb(moeda: str, data: date) -> Optional[Decimal]:
    """
    Busca cotação na API PTAX do Banco Central.
    """
    # Formato de data da API: MM-DD-YYYY
    data_str = data.strftime("%m-%d-%Y")

    url = (
        f"https://olinda.bcb.gov.br/olinda/servico/PTAX/versao/v1/odata/"
        f"CotacaoMoedaDia(moeda=@moeda,dataCotacao=@data)?"
        f"@moeda='{moeda}'&@data='{data_str}'&$format=json"
    )

    try:
        with urlopen(url, timeout=10) as response:
            dados = json.loads(response.read().decode("utf-8"))

            if dados.get("value"):
                # Usa a cotação de venda (mais comum para despesas)
                cotacao = dados["value"][-1].get("cotacaoVenda")
                if cotacao:
                    return Decimal(str(cotacao))
    except (URLError, json.JSONDecodeError, KeyError, IndexError):
        pass

    return None


def converter_para_brl(
    valor: Decimal, moeda: str, data: Optional[date] = None
) -> tuple:
    """
    Converte um valor de uma moeda para BRL.

    Args:
        valor: Valor na moeda original
        moeda: Código da moeda
        data: Data para buscar cotação

    Returns:
        Tupla (valor_brl, taxa_cambio)
    """
    if moeda == "BRL":
        return valor, Decimal("1.0")

    taxa = obter_cotacao(moeda, data)
    if taxa:
        valor_brl = valor * taxa
        return valor_brl.quantize(Decimal("0.01")), taxa

    # Fallback: retorna o valor original se não conseguir cotação
    return valor, None


# Cotações fallback (caso API falhe)
COTACOES_FALLBACK = {
    "USD": Decimal("5.00"),
    "EUR": Decimal("5.50"),
    "GBP": Decimal("6.30"),
}


def obter_cotacao_com_fallback(moeda: str, data: Optional[date] = None) -> Decimal:
    """
    Obtém cotação com fallback para valores fixos.
    """
    if moeda == "BRL":
        return Decimal("1.0")

    taxa = obter_cotacao(moeda, data)
    if taxa:
        return taxa

    return COTACOES_FALLBACK.get(moeda, Decimal("1.0"))
