from decimal import Decimal
from django.db.models import Sum, F
import yfinance as yf
from investimento.models import Ativo, Transacao, Cotacao


def recalcular_ativo(ativo: Ativo):
    """
    Recalcula o preço médio e a quantidade atual de um ativo
    baseado em todo o histórico de transações.
    """
    transacoes = ativo.transacoes.order_by("data", "criada_em")

    quantidade_total = Decimal(0)
    custo_total = Decimal(0)

    for t in transacoes:
        qtd = t.quantidade
        # valor = t.valor_total  # Já inclui taxas se a lógica de salvar estiver certa, mas vamos usar o bruto calculado aqui para garantir PM correto

        if t.tipo == Transacao.TIPO_COMPRA:
            # PM ponderado
            # Novo Custo = Custo Anterior + (Qtd * Preco) + Taxas
            # Mas PM fiscal geralmente inclui taxas. Vamos assumir valor_total como o custo de aquisição.
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
                # Venda a descoberto ou erro de dados, zera ou mantem negativo
                quantidade_total -= qtd

        # Dividendos não alteram PM nem quantidade (são entradas de caixa)

    # Evita divisão por zero e arredondamentos estranhos
    if quantidade_total > 0:
        ativo.preco_medio = custo_total / quantidade_total
    else:
        ativo.preco_medio = Decimal(0)
        quantidade_total = Decimal(0)  # evita -0.000...

    ativo.quantidade = quantidade_total
    ativo.quantidade = quantidade_total
    ativo.save(update_fields=["quantidade", "preco_medio"])


def atualizar_cotacoes():
    """
    Busca cotações atuais para todos os ativos com ticker definido.
    """
    ativos = Ativo.objects.filter(ativo=True).exclude(ticker="")

    # Mapeia sufixo .SA para ações brasileiras se necessário,
    # ou assume que o usuário já cadastrou com .SA ou o ticker correto do Yahoo Finance.
    # Vamos tentar inferir .SA se não tiver ponto e for tipicamente BR (opcional, mas ajuda na UX).
    # Por enquanto, vamos assumir que o ticker segue o padrão do Yahoo ou o usuário deve corrigir.

    count = 0
    errors = []

    for ativo in ativos:
        ticker_symbol = ativo.ticker
        if not ticker_symbol:
            continue

        # Tentativa simples de ajuste para BR se falhar?
        # O melhor é o usuário cadastrar certo (ex: PETR4.SA).
        # Mas vamos adicionar um fallback se o ticker puro não for encontrado e não tem ponto.

        try:
            # Pega dados do dia
            ticker_data = yf.Ticker(ticker_symbol)
            # history(period="1d") retorna dataframe
            hist = ticker_data.history(period="1d")

            if hist.empty:
                # Tenta adicionar .SA se não tiver
                if "." not in ticker_symbol:
                    ticker_symbol_sa = f"{ticker_symbol}.SA"
                    ticker_data = yf.Ticker(ticker_symbol_sa)
                    hist = ticker_data.history(period="1d")

            if not hist.empty:
                # Pega o último fechamento ou preço atual
                # 'Close' é o fechamento. Em mercado aberto, pode ser o preço atual (varia).
                # Yahoo finance geralmente dá o dado mais recente em 'Close' no history().
                valor_atual = hist["Close"].iloc[-1]
                data_cotacao = hist.index[-1].date()  # Data do dado

                # Salva cotação
                # Verifica se já existe cotacao para essa data e ativo
                Cotacao.objects.update_or_create(
                    ativo=ativo, data=data_cotacao, defaults={"valor": valor_atual}
                )
                count += 1
            else:
                errors.append(f"Ativo {ativo.ticker}: Dados não encontrados")

        except Exception as e:
            errors.append(f"Ativo {ativo.ticker}: Erro ao buscar cotação ({str(e)})")

    return count, errors
