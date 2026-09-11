"""Módulo de Cálculos e Utilitários de Carteiras de Investimentos.

Este arquivo concentra rotinas financeiras essenciais para apuração de preço médio
ponderado fiscal de aquisições de ativos, além de gerenciar a sincronização em lote
de cotações a mercado integrando com coletores remotos.
"""

import datetime
from decimal import Decimal

from django.db.models import Min, Q
from django.utils import timezone

from investimento.models import Ativo, PosicaoCarteira, Transacao, Cotacao
from investimento.services.tradingview_screener import (
    fetch_quotes_brazil,
    _normalize_to_tradingview_symbol,
)
from investimento.services.cvm_service import fetch_cvm_quotes
from investimento.services.yahoo_service import YahooIndisponivel, fetch_historico_yahoo

# Janela de histórico que a atualização em lote garante para cada ticker. Casa com o
# padrão do gráfico comparativo de Meus Ativos (`JANELA_COTACOES_DIAS` em views_api).
JANELA_HISTORICO_DIAS = 60

# O início da janela quase nunca é pregão: 60 dias atrás cai em fim de semana ou
# feriado com frequência, e o `2mo` do Yahoo também não começa exatamente ali. Sem
# folga, todo ativo pareceria descoberto para sempre.
TOLERANCIA_INICIO_DIAS = 5

# Um ticker que o Yahoo não conhece (renda fixa, papel de fora) nunca vai ficar
# coberto. Sem esta espera ele repetiria a mesma requisição e o mesmo erro a cada
# clique em «Atualizar Cotações».
REVERIFICAR_APOS_DIAS = 7

# Cada completamento é um GET separado no Yahoo, e o endpoint responde de forma
# síncrona. O teto mantém o tempo de resposta limitado; o que sobra fica para o
# próximo clique, e o número de pendentes volta na resposta.
LIMITE_HISTORICO_POR_RODADA = 12


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


def gravar_serie_cotacoes(ativo: Ativo, serie) -> int:
    """Grava uma série de fechamentos, sobrescrevendo o que já houver naquelas datas.

    Uma escrita só para a série inteira: com `update_or_create` num laço, completar
    dois meses de um ativo custava ~45 idas ao banco, e um lote de doze ativos passava
    de quinhentas.

    Args:
        ativo: Ativo dono das cotações.
        serie: Iterável de pares `(date, Decimal)`.

    Returns:
        int: Quantidade de pregões gravados.
    """
    cotacoes = [Cotacao(ativo=ativo, data=data, valor=valor) for data, valor in serie]
    if not cotacoes:
        return 0

    Cotacao.objects.bulk_create(
        cotacoes,
        update_conflicts=True,
        unique_fields=["ativo", "data"],
        update_fields=["valor", "atualizada_em"],
    )
    return len(cotacoes)


def completar_historico(base, errors: list[str]) -> tuple[int, int]:
    """Preenche no Yahoo a série dos ativos que não cobrem a janela de dois meses.

    O coletor de cotação atual (TradingView/CVM) grava um pregão por rodada, então um
    ativo recém-cadastrado leva dois meses de cliques diários até ter gráfico. Esta
    etapa fecha essa lacuna: confere quem está descoberto e busca a série de uma vez.

    A conferência é uma agregação só para todos os candidatos — a data da cotação mais
    antiga dentro da janela —, e não um `SELECT` por ativo. Quem já cobre o período
    não gera requisição nenhuma, que é o caso comum a partir da segunda rodada.

    Ativos são carimbados em `historico_verificado_em` **inclusive quando a busca
    falha**: sem isso um ticker que o Yahoo não conhece repetiria a requisição e o
    mesmo erro a cada clique, para sempre.

    Args:
        base: QuerySet de ativos já recortado por usuário.
        errors: Lista de erros da rodada, acrescida no lugar (um item por ativo que falhou).

    Returns:
        tuple[int, int]: Pregões gravados e quantos ativos ficaram para a próxima
            rodada por causa de `LIMITE_HISTORICO_POR_RODADA`.
    """
    hoje = timezone.localdate()
    inicio = hoje - datetime.timedelta(days=JANELA_HISTORICO_DIAS)
    corte_cobertura = inicio + datetime.timedelta(days=TOLERANCIA_INICIO_DIAS)
    reverificar_antes_de = hoje - datetime.timedelta(days=REVERIFICAR_APOS_DIAS)

    candidatos = list(
        base.exclude(ticker="").filter(
            Q(historico_verificado_em__isnull=True)
            | Q(historico_verificado_em__lt=reverificar_antes_de)
        )
    )
    if not candidatos:
        return 0, 0

    mais_antiga_por_ativo = {
        linha["ativo_id"]: linha["mais_antiga"]
        for linha in Cotacao.objects.filter(ativo__in=candidatos, data__gte=inicio)
        .values("ativo_id")
        .annotate(mais_antiga=Min("data"))
    }

    # Sem cotação nenhuma na janela conta como descoberto, daí o `hoje` como padrão
    descobertos = [
        ativo
        for ativo in candidatos
        if mais_antiga_por_ativo.get(ativo.id, hoje) > corte_cobertura
    ]

    count = 0
    for ativo in descobertos[:LIMITE_HISTORICO_POR_RODADA]:
        try:
            serie = fetch_historico_yahoo(ativo.ticker)
        except YahooIndisponivel as erro:
            errors.append(f"Ativo {ativo.ticker}: {erro}")
        else:
            count += gravar_serie_cotacoes(ativo, serie)
        Ativo.objects.filter(pk=ativo.pk).update(historico_verificado_em=hoje)

    return count, max(0, len(descobertos) - LIMITE_HISTORICO_POR_RODADA)


def atualizar_cotacoes(usuario=None) -> tuple[int, list[str], int]:
    """Sincroniza as cotações a mercado: o fechamento do dia e a série que faltar.

    São duas fontes com papéis distintos. TradingView (ações e FIIs) e CVM (fundos por
    CNPJ) devolvem o fechamento **de hoje** em requisições em lote, baratas o bastante
    para rodar a cada clique. O Yahoo devolve a **série**, ao custo de uma requisição
    por ticker, e por isso só é acionado para quem ainda não cobre a janela de dois
    meses (ver `completar_historico`).

    Returns:
        tuple[int, list[str], int]: Pregões gravados, erros ocorridos e quantos ativos
            ficaram com o histórico pendente para a próxima rodada.
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

    # 3. Completamento do histórico de quem não cobre a janela do gráfico
    completados, historico_pendente = completar_historico(base, errors)
    count += completados

    return count, errors, historico_pendente


