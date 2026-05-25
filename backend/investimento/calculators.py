"""Módulo de Cálculos e Utilitários de Carteiras de Investimentos.

Este arquivo concentra rotinas financeiras essenciais para apuração de preço médio
ponderado fiscal de aquisições de ativos, além de gerenciar a sincronização em lote
de cotações a mercado integrando com coletores remotos.
"""

from decimal import Decimal
from django.db.models import Sum, F
from investimento.models import Ativo, Transacao, Cotacao
from investimento.services.tradingview_screener import (
    fetch_quotes_brazil,
    _normalize_to_tradingview_symbol,
)


def recalcular_ativo(ativo: Ativo) -> None:
    """Recalcula o preço médio ponderado fiscal e a quantidade em custódia do ativo.

    Varre de forma ordenada o histórico completo de transações do ativo na carteira,
    acrescendo quantidades nas compras e computando PM proporcional, e amortizando
    quantidades nas vendas sem alterar o preço médio.

    Args:
        ativo (Ativo): Instância do ativo custodiado a ser recalculado.
    """
    transacoes = ativo.transacoes.order_by("data", "criada_em")

    quantidade_total = Decimal(0)
    custo_total = Decimal(0)

    for t in transacoes:
        qtd = t.quantidade

        if t.tipo == Transacao.TIPO_COMPRA:
            # PM ponderado
            # Novo Custo = Custo Anterior + (Qtd * Preco) + Taxas
            custo_aquisicao = t.valor_total

            custo_total += custo_aquisicao
            quantidade_total += qtd

        elif t.tipo == Transacao.TIPO_VENDA:
            # Venda reduz quantidade, mas NÃO altera preço médio
            if quantidade_total > 0:
                # Proporção vendida
                preco_medio_atual = custo_total / quantidade_total

                # Custo abatido = Quantidade Vendida * Preço Médio Atual
                custo_abatido = qtd * preco_medio_atual

                custo_total -= custo_abatido
                quantidade_total -= qtd
            else:
                # Venda a descoberto ou erro de dados
                quantidade_total -= qtd

        # Dividendos não alteram PM nem quantidade (são entradas de caixa)

    # Evita divisão por zero e arredondamentos estranhos
    if quantidade_total > 0:
        ativo.preco_medio = custo_total / quantidade_total
    else:
        ativo.preco_medio = Decimal(0)
        quantidade_total = Decimal(0)  # evita -0.000...

    ativo.quantidade = quantidade_total
    ativo.save(update_fields=["quantidade", "preco_medio"])


def atualizar_cotacoes() -> tuple[int, list[str]]:
    """Busca em lote as cotações atuais B3 de mercado para todos os ativos sob custódia.

    Realiza uma requisição otimizada única em lote ao TradingView para economizar requisições
    e atualiza ou cria o histórico diário de fechamento das cotações.

    Returns:
        tuple[int, list[str]]: Tupla contendo o número de cotações gravadas com sucesso e a lista de erros ocorridos.
    """
    ativos = Ativo.objects.filter(ativo=True).exclude(ticker="")

    count = 0
    errors = []

    # Busca em lote no TradingView para evitar N requisições.
    try:
        tickers = [a.ticker for a in ativos if a.ticker]
        quotes_by_symbol = fetch_quotes_brazil(tickers)
    except Exception as e:
        return 0, [f"Erro ao buscar cotações no TradingView: {str(e)}"]

    for ativo in ativos:
        try:
            symbol = _normalize_to_tradingview_symbol(ativo.ticker)
            quote = quotes_by_symbol.get(symbol)
            if not quote:
                errors.append(f"Ativo {ativo.ticker}: Não encontrado no TradingView")
                continue

            Cotacao.objects.update_or_create(
                ativo=ativo, data=quote.as_of, defaults={"valor": quote.close}
            )
            count += 1
        except Exception as e:
            errors.append(f"Ativo {ativo.ticker}: Erro ao salvar cotação ({str(e)})")

    return count, errors

