"""Módulo de Cálculos e Utilitários de Carteiras de Investimentos.

Este arquivo concentra rotinas financeiras essenciais para apuração de preço médio
ponderado fiscal de aquisições de ativos, além de gerenciar a sincronização em lote
de cotações a mercado integrando com coletores remotos.
"""

from decimal import Decimal
from investimento.models import Ativo, PosicaoCarteira, Transacao, Cotacao
from investimento.services.tradingview_screener import (
    fetch_quotes_brazil,
    _normalize_to_tradingview_symbol,
)
from investimento.services.cvm_service import fetch_cvm_quotes


def recalcular_ativo(ativo: Ativo) -> None:
    """Recalcula o preço médio ponderado fiscal e a quantidade consolidada do ativo.

    Varre de forma ordenada o histórico completo de transações do ativo, acrescendo
    quantidades nas compras e computando PM proporcional, e amortizando quantidades
    nas vendas sem alterar o preço médio.

    Transferências entre carteiras são ignoradas: elas mudam onde o papel está
    custodiado, não quanto o investidor tem nem por quanto comprou. Considerá-las
    aqui alteraria o preço médio — que no Brasil é apurado por CPF, e é o número que
    o investidor declara.
    """
    transacoes = ativo.transacoes.exclude(
        tipo__in=Transacao.TIPOS_TRANSFERENCIA
    ).order_by("data", "criada_em")

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


def recalcular_posicoes_do_ativo(ativo: Ativo) -> None:
    """Recalcula a posição do ativo em **todas** as carteiras onde ele aparece.

    Recalcula todas, e não apenas a carteira da transação que disparou o cálculo,
    porque editar uma transação pode mover custódia: o gatilho só enxerga a carteira
    nova, e a antiga ficaria com uma posição obsoleta, sem nada que a corrigisse.

    A transferência de saída abate custo na proporção do preço médio da carteira de
    origem — a mesma regra da venda — e a de entrada acrescenta o custo carregado na
    perna. Assim o custo total do usuário fecha igual antes e depois de transferir.

    Escreve apenas os campos de cache: `meta_porcentagem` é intenção do usuário, e a
    linha não é apagada quando a posição zera, para que essa intenção sobreviva.
    """
    transacoes = ativo.transacoes.exclude(carteira__isnull=True).order_by(
        "data", "criada_em"
    )

    acumulado: dict[int, list[Decimal]] = {}  # carteira_id -> [quantidade, custo]

    for t in transacoes:
        quantidade, custo = acumulado.setdefault(
            t.carteira_id, [Decimal(0), Decimal(0)]
        )
        qtd = t.quantidade

        if t.tipo in (Transacao.TIPO_COMPRA, Transacao.TIPO_TRANSF_ENTRADA):
            custo += t.valor_total
            quantidade += qtd

        elif t.tipo in (Transacao.TIPO_VENDA, Transacao.TIPO_TRANSF_SAIDA):
            if quantidade > 0:
                preco_medio_atual = custo / quantidade
                custo -= qtd * preco_medio_atual
                quantidade -= qtd
            else:
                quantidade -= qtd

        # Proventos não alteram quantidade nem custo em custódia.

        acumulado[t.carteira_id] = [quantidade, custo]

    for carteira_id, (quantidade, custo) in acumulado.items():
        if quantidade > 0:
            preco_medio = custo / quantidade
        else:
            quantidade = Decimal(0)
            custo = Decimal(0)
            preco_medio = Decimal(0)

        posicao, _ = PosicaoCarteira.objects.get_or_create(
            carteira_id=carteira_id,
            ativo=ativo,
            defaults={"usuario_id": ativo.usuario_id},
        )
        posicao.quantidade = quantidade
        posicao.custo_total = custo
        posicao.preco_medio = preco_medio
        posicao.save(update_fields=["quantidade", "custo_total", "preco_medio"])

    # Carteiras que já tiveram o ativo e não têm mais: zera o cache em vez de apagar
    # a linha, senão a meta configurada para elas sumiria junto.
    PosicaoCarteira.objects.filter(ativo=ativo).exclude(
        carteira_id__in=acumulado.keys()
    ).update(quantidade=Decimal(0), custo_total=Decimal(0), preco_medio=Decimal(0))


def atualizar_cotacoes(usuario=None) -> tuple[int, list[str]]:
    """Busca em lote as cotações atuais de mercado (B3 via TradingView e Fundos via CVM).

    Atualiza ou cria o histórico diário de fechamento das cotações.

    Returns:
        tuple[int, list[str]]: Tupla contendo o número de cotações gravadas com sucesso e a lista de erros ocorridos.
    """
    count = 0
    errors = []

    base = Ativo.objects.filter(ativo=True)
    if usuario is not None:
        base = base.filter(usuario=usuario)

    # 1. Atualização de Ações / FIIs via TradingView
    ativos_b3 = base.exclude(ticker="")

    quotes_by_symbol = {}
    if ativos_b3.exists():
        try:
            tickers = [a.ticker for a in ativos_b3 if a.ticker]
            quotes_by_symbol = fetch_quotes_brazil(tickers)
        except Exception as e:
            errors.append(f"Erro ao buscar cotações no TradingView: {str(e)}")

    for ativo in ativos_b3:
        try:
            symbol = _normalize_to_tradingview_symbol(ativo.ticker)
            quote = quotes_by_symbol.get(symbol)
            if not quote:
                # Se não foi encontrado no TradingView mas possui CNPJ, tentaremos pela CVM abaixo
                if ativo.cnpj:
                    continue
                errors.append(f"Ativo {ativo.ticker}: Não encontrado no TradingView")
                continue

            Cotacao.objects.update_or_create(
                ativo=ativo, data=quote.as_of, defaults={"valor": quote.close}
            )
            count += 1
        except Exception as e:
            errors.append(f"Ativo {ativo.ticker}: Erro ao salvar cotação ({str(e)})")

    # 2. Atualização de Fundos de Investimento via CVM
    ativos_cvm = base.exclude(cnpj__isnull=True).exclude(cnpj="")
    
    # Filtra ativos para buscar apenas se não foram atualizados pelo TradingView nesta rodada
    ativos_cvm_para_buscar = []
    for a in ativos_cvm:
        symbol = _normalize_to_tradingview_symbol(a.ticker)
        if symbol not in quotes_by_symbol:
            ativos_cvm_para_buscar.append(a)

    if ativos_cvm_para_buscar:
        try:
            cnpjs = [a.cnpj for a in ativos_cvm_para_buscar]
            cvm_quotes = fetch_cvm_quotes(cnpjs)
            
            for ativo in ativos_cvm_para_buscar:
                quote_info = cvm_quotes.get(ativo.cnpj)
                if not quote_info:
                    errors.append(f"Fundo {ativo.ticker or ativo.nome} (CNPJ {ativo.cnpj}): Não encontrado nos dados da CVM")
                    continue
                
                vl_quota, dt_comptc = quote_info
                Cotacao.objects.update_or_create(
                    ativo=ativo, data=dt_comptc, defaults={"valor": vl_quota}
                )
                count += 1
        except Exception as e:
            errors.append(f"Erro ao buscar cotações na CVM: {str(e)}")

    return count, errors


