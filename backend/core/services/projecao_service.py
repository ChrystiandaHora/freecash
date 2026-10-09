"""Projeção de saldo diário e agenda de pagamentos e recebimentos (Horizonte e Calendário).

Calcula a evolução do saldo diário somando caixa inicial realizado (âncora), pendências
anteriores e fluxo futuro, respeitando consolidação de faturas de cartão e recorrências.
"""

from calendar import monthrange
from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal

from dateutil.relativedelta import relativedelta
from django.db.models import DecimalField, ExpressionWrapper, F, Q, Sum
from django.db.models.functions import TruncMonth

from core.models import Conta, MetaFinanceira
from core.services.dashboard_helper import saldo_liquidez_ate
from core.services.recorrencia_service import garantir_horizonte

# Ignora compras individuais de cartão no saldo (o desembolso ocorre na fatura consolidada)
FILTRO_CARTAO = Q(cartao__isnull=True) | Q(eh_fatura_cartao=True)

MESES_PADRAO = 12
MESES_MAXIMO = 24

# Quantos lançamentos de cada tipo a composição do mês lista nominalmente
MAIORES_POR_TIPO = 5


def _centavos(valor) -> Decimal:
    """Normaliza valor monetário para Decimal com 2 casas decimais."""
    return Decimal(valor or 0).quantize(Decimal("0.01"))


def _valor_investido(usuario) -> Decimal:
    """Soma o custo de aquisição da carteira, menos as custódias marcadas para ficar fora.

    Parte do consolidado em `Ativo` e **desconta** as posições das carteiras com
    `considerar_no_saldo=False`, em vez de somar as posições das que ficam. As duas
    contas dão o mesmo número quando todo ativo tem posição materializada — mas só
    esta continua correta para um ativo que não tem, e é ela que garante que quem
    nunca mexeu na configuração veja exatamente o valor de antes.

    O critério é de liquidez: uma reserva de emergência em Tesouro Selic é dinheiro
    com que o usuário conta; uma posição em ações, normalmente não.
    """
    from investimento.models import Ativo, PosicaoCarteira

    custo = ExpressionWrapper(
        F("quantidade") * F("preco_medio"),
        output_field=DecimalField(max_digits=19, decimal_places=4),
    )

    total = Ativo.objects.filter(usuario=usuario).aggregate(total=Sum(custo))["total"]
    fora = PosicaoCarteira.objects.filter(
        usuario=usuario, carteira__considerar_no_saldo=False
    ).aggregate(total=Sum(custo))["total"]

    return _centavos(total) - _centavos(fora)


def _carteiras_consideradas(usuario) -> list[str]:
    """Nomes das carteiras que entram no saldo, para a tela poder dizer quais.

    Returns:
        list[str]: Nomes em ordem de exibição.
    """
    from investimento.models import Carteira

    return list(
        Carteira.objects.filter(usuario=usuario, considerar_no_saldo=True)
        .order_by("ordem", "nome")
        .values_list("nome", flat=True)
    )


def _lancamentos_da_janela(usuario, inicio: date, fim: date) -> list[dict]:
    """Lista os lançamentos que movem o saldo na janela, cada um no dia em que o dinheiro anda.

    Pendente conta pela `data_prevista`; liquidado, pela `data_realizacao` — uma conta
    prevista para setembro e paga hoje move o saldo hoje. É a fonte única dessa regra:
    o fluxo diário da grade e a composição de cada mês saem desta mesma lista, para que
    a explicação nunca divirja da curva.

    Returns:
        list[dict]: Lançamentos com `data` efetiva, em ordem indefinida.
    """
    campos = (
        "id", "tipo", "descricao", "valor", "data_prevista", "data_realizacao",
        "transacao_realizada", "categoria__nome", "evento__nome",
    )
    pendentes = (
        Conta.objects.filter(
            usuario=usuario,
            transacao_realizada=False,
            data_prevista__gte=inicio,
            data_prevista__lte=fim,
        )
        .filter(FILTRO_CARTAO)
        .values(*campos)
    )
    liquidados = (
        Conta.objects.filter(
            usuario=usuario,
            transacao_realizada=True,
            data_realizacao__gte=inicio,
            data_realizacao__lte=fim,
        )
        .filter(FILTRO_CARTAO)
        .values(*campos)
    )

    lancamentos = []
    for linha in [*pendentes, *liquidados]:
        realizado = linha["transacao_realizada"]
        lancamentos.append({
            "id": linha["id"],
            "tipo": linha["tipo"],
            "descricao": linha["descricao"],
            "valor": _centavos(linha["valor"]),
            "data": linha["data_realizacao"] if realizado else linha["data_prevista"],
            "data_prevista": linha["data_prevista"],
            "realizado": realizado,
            "categoria": linha["categoria__nome"],
            "evento": linha["evento__nome"],
        })
    return lancamentos


def _movimentos_por_dia(lancamentos: list[dict]) -> dict[date, dict]:
    """Soma por dia as receitas e despesas da lista de lançamentos da janela."""
    movimentos = defaultdict(lambda: {"receitas": Decimal("0.00"), "despesas": Decimal("0.00")})
    for lancamento in lancamentos:
        chave = "receitas" if lancamento["tipo"] == Conta.TIPO_RECEITA else "despesas"
        movimentos[lancamento["data"]][chave] += lancamento["valor"]
    return movimentos


def _composicao_do_mes(lancamentos: list[dict]) -> dict:
    """Separa os maiores lançamentos de cada tipo e resume o restante do mês.

    Mostrar todos afogaria a resposta à pergunta "por que o saldo mudou?" em dezenas de
    lançamentos pequenos; os maiores explicam quase toda a variação.

    Returns:
        dict: `receitas` e `despesas`, cada um com `maiores`, `outros_qtd` e `outros_total`.
    """
    composicao = {}
    for tipo, chave in ((Conta.TIPO_RECEITA, "receitas"), (Conta.TIPO_DESPESA, "despesas")):
        do_tipo = sorted(
            (l for l in lancamentos if l["tipo"] == tipo),
            key=lambda l: (-l["valor"], l["data"], l["id"]),
        )
        maiores = do_tipo[:MAIORES_POR_TIPO]
        restantes = do_tipo[MAIORES_POR_TIPO:]
        composicao[chave] = {
            "maiores": [
                {
                    "id": l["id"],
                    "descricao": l["descricao"],
                    "valor": str(l["valor"]),
                    "data": l["data"].isoformat(),
                    "data_prevista": l["data_prevista"].isoformat(),
                    "realizado": l["realizado"],
                    "categoria": l["categoria"],
                    "evento": l["evento"],
                }
                for l in maiores
            ],
            "outros_qtd": len(restantes),
            "outros_total": str(sum((l["valor"] for l in restantes), Decimal("0.00"))),
        }
    return composicao


def _historico_realizado(usuario, ate: date) -> list[dict]:
    """Reconstrói o caixa mês a mês, do primeiro lançamento liquidado até `ate`.

    Usa o mesmo recorte de `saldo_liquidez_ate` (liquidado, pela data de realização,
    com o filtro de cartão), então o saldo final do último mês é exatamente o caixa
    realizado que ancora a projeção. Meses sem movimento entram zerados, para que a
    linha do tempo não pule meses.

    Returns:
        list[dict]: Um item por mês, em ordem; o mês de `ate` vem marcado como parcial
        quando `ate` não é o último dia dele.
    """
    linhas = (
        Conta.objects.filter(
            usuario=usuario,
            transacao_realizada=True,
            data_realizacao__lte=ate,
        )
        .filter(FILTRO_CARTAO)
        .annotate(mes=TruncMonth("data_realizacao"))
        .values("mes", "tipo")
        .annotate(total=Sum("valor"))
    )

    fluxo = defaultdict(lambda: {"receitas": Decimal("0.00"), "despesas": Decimal("0.00")})
    for linha in linhas:
        mes = linha["mes"].date() if hasattr(linha["mes"], "date") else linha["mes"]
        chave = "receitas" if linha["tipo"] == Conta.TIPO_RECEITA else "despesas"
        fluxo[mes][chave] += _centavos(linha["total"])

    if not fluxo:
        return []

    historico = []
    saldo = Decimal("0.00")
    cursor = min(fluxo)
    ultimo = ate.replace(day=1)
    while cursor <= ultimo:
        receitas = fluxo[cursor]["receitas"]
        despesas = fluxo[cursor]["despesas"]
        saldo += receitas - despesas
        historico.append({
            "ano": cursor.year,
            "mes": cursor.month,
            "receitas": str(receitas),
            "despesas": str(despesas),
            "saldo_final": str(saldo),
            "parcial": cursor == ultimo and ate.day != monthrange(ate.year, ate.month)[1],
        })
        cursor = cursor + relativedelta(months=1)
    return historico


def _pendencias_atrasadas(usuario, antes_de: date) -> dict:
    """Soma lançamentos vencidos e não liquidados anteriores à data de corte."""
    qs = (
        Conta.objects.filter(
            usuario=usuario,
            transacao_realizada=False,
            data_prevista__lt=antes_de,
        )
        .filter(FILTRO_CARTAO)
    )
    receitas = qs.filter(tipo=Conta.TIPO_RECEITA).aggregate(t=Sum("valor"))["t"]
    despesas = qs.filter(tipo=Conta.TIPO_DESPESA).aggregate(t=Sum("valor"))["t"]
    return {
        "receitas": _centavos(receitas),
        "despesas": _centavos(despesas),
    }


def _aportes_mensais_de_metas(usuario, inicio: date, fim: date) -> dict[date, Decimal]:
    """Calcula o aporte mensal necessário para atingir metas ativas no prazo."""
    metas = MetaFinanceira.objects.filter(
        usuario=usuario, concluida=False, prazo__isnull=False
    )

    aportes: dict[date, Decimal] = defaultdict(lambda: Decimal("0.00"))
    primeiro_mes = inicio.replace(day=1)

    for meta in metas:
        faltante = _centavos(meta.valor_alvo) - _centavos(meta.valor_acumulado)
        if faltante <= 0:
            continue

        if meta.prazo <= inicio:
            aportes[primeiro_mes] += faltante
            continue

        delta = relativedelta(meta.prazo, inicio)
        meses_restantes = max(1, delta.years * 12 + delta.months)
        parcela = (faltante / Decimal(meses_restantes)).quantize(Decimal("0.01"))

        mes = primeiro_mes
        while mes <= fim and mes <= meta.prazo:
            aportes[mes] += parcela
            mes = mes + relativedelta(months=1)

    return aportes


def horizonte_saldos(usuario, hoje: date, meses: int = MESES_PADRAO,
                     limite_atencao: Decimal | None = None,
                     considerar_investimentos: bool = False) -> dict:
    """Projeta a curva diária de saldos para os próximos meses."""
    meses = max(1, min(meses, MESES_MAXIMO))
    fim = (hoje.replace(day=1) + relativedelta(months=meses)) - timedelta(days=1)

    garantir_horizonte(usuario, fim)

    # Âncora: saldo realizado até ontem + pendências vencidas
    ontem = hoje - timedelta(days=1)
    caixa_realizado = _centavos(saldo_liquidez_ate(usuario, ontem))
    saldo_inicial = caixa_realizado
    atrasados = _pendencias_atrasadas(usuario, hoje)
    saldo_inicial += atrasados["receitas"] - atrasados["despesas"]

    valor_investido = _valor_investido(usuario)
    if not considerar_investimentos:
        saldo_inicial -= valor_investido

    lancamentos = _lancamentos_da_janela(usuario, hoje, fim)
    movimentos = _movimentos_por_dia(lancamentos)
    lancamentos_por_mes = defaultdict(list)
    for lancamento in lancamentos:
        lancamentos_por_mes[lancamento["data"].replace(day=1)].append(lancamento)
    aportes_meta = _aportes_mensais_de_metas(usuario, hoje, fim)

    saldo = saldo_inicial
    saldo_com_metas = saldo_inicial
    primeiro_negativo = None
    primeiro_negativo_com_metas = None

    meses_saida = []
    cursor = hoje.replace(day=1)

    for _ in range(meses):
        ultimo_dia = monthrange(cursor.year, cursor.month)[1]
        dias_saida = []
        total_receitas = Decimal("0.00")
        total_despesas = Decimal("0.00")

        aporte_do_mes = aportes_meta.get(cursor, Decimal("0.00"))
        abertura = saldo
        abertura_com_metas = saldo_com_metas

        for numero_dia in range(1, ultimo_dia + 1):
            dia = date(cursor.year, cursor.month, numero_dia)

            if dia < hoje:
                continue

            movimento = movimentos.get(dia)
            receitas = movimento["receitas"] if movimento else Decimal("0.00")
            despesas = movimento["despesas"] if movimento else Decimal("0.00")

            saldo += receitas - despesas
            saldo_com_metas += receitas - despesas

            if not dias_saida:
                saldo_com_metas -= aporte_do_mes

            total_receitas += receitas
            total_despesas += despesas

            if primeiro_negativo is None and saldo < 0:
                primeiro_negativo = dia.isoformat()
            if primeiro_negativo_com_metas is None and saldo_com_metas < 0:
                primeiro_negativo_com_metas = dia.isoformat()

            dias_saida.append({
                "dia": numero_dia,
                "data": dia.isoformat(),
                "saldo": str(saldo),
                "saldo_com_metas": str(saldo_com_metas),
                "receitas": str(receitas),
                "despesas": str(despesas),
                "tem_lancamentos": bool(movimento),
                "situacao": _situacao(saldo, limite_atencao),
                "situacao_com_metas": _situacao(saldo_com_metas, limite_atencao),
            })

        meses_saida.append({
            "ano": cursor.year,
            "mes": cursor.month,
            "rotulo": f"{cursor.strftime('%b')}/{cursor.strftime('%y')}",
            "dias": dias_saida,
            "total_receitas": str(total_receitas),
            "total_despesas": str(total_despesas),
            "aporte_metas": str(aporte_do_mes),
            "saldo_abertura": str(abertura),
            "saldo_abertura_com_metas": str(abertura_com_metas),
            "saldo_final": str(saldo),
            "saldo_final_com_metas": str(saldo_com_metas),
            "composicao": _composicao_do_mes(lancamentos_por_mes.get(cursor, [])),
        })

        cursor = cursor + relativedelta(months=1)

    return {
        "inicio": hoje.isoformat(),
        "fim": fim.isoformat(),
        "saldo_inicial": str(saldo_inicial),
        "caixa_realizado": str(caixa_realizado),
        "historico": _historico_realizado(usuario, ontem),
        "atrasados": {
            "receitas": str(atrasados["receitas"]),
            "despesas": str(atrasados["despesas"]),
        },
        "valor_investido": str(valor_investido),
        "investimentos_considerados": considerar_investimentos,
        "carteiras_consideradas": _carteiras_consideradas(usuario),
        "limite_atencao": str(limite_atencao) if limite_atencao is not None else None,
        "primeiro_dia_negativo": primeiro_negativo,
        "primeiro_dia_negativo_com_metas": primeiro_negativo_com_metas,
        "meses": meses_saida,
    }


def _situacao(saldo: Decimal, limite_atencao: Decimal | None) -> str:
    """Classifica a situação do saldo: 'negativo', 'atencao' ou 'confortavel'."""
    if saldo < 0:
        return "negativo"
    if limite_atencao is not None and saldo < limite_atencao:
        return "atencao"
    return "confortavel"


def calendario_mes(usuario, ano: int, mes: int) -> dict:
    """Lista os lançamentos previstos do mês dia a dia para visualização em calendário."""
    inicio = date(ano, mes, 1)
    ultimo_dia = monthrange(ano, mes)[1]
    fim = date(ano, mes, ultimo_dia)

    garantir_horizonte(usuario, fim)

    lancamentos = (
        Conta.objects.filter(
            usuario=usuario,
            data_prevista__gte=inicio,
            data_prevista__lte=fim,
        )
        .select_related("categoria", "cartao")
        .order_by("data_prevista", "-valor")
    )

    por_dia: dict[int, list] = defaultdict(list)
    for conta in lancamentos:
        por_dia[conta.data_prevista.day].append({
            "id": conta.id,
            "tipo": conta.tipo,
            "descricao": conta.descricao,
            "valor": str(_centavos(conta.valor)),
            "realizado": conta.transacao_realizada,
            "eh_fatura_cartao": conta.eh_fatura_cartao,
            "categoria": conta.categoria.nome if conta.categoria else None,
            "cartao": conta.cartao.nome if conta.cartao else None,
            "recorrente": conta.recorrencia_id is not None,
        })

    hoje = date.today()
    dias_saida = []
    for numero_dia in range(1, ultimo_dia + 1):
        itens = por_dia.get(numero_dia, [])
        dia = date(ano, mes, numero_dia)

        para_totais = [
            i for i in itens if i["cartao"] is None or i["eh_fatura_cartao"]
        ]
        receitas = sum(
            (Decimal(i["valor"]) for i in para_totais if i["tipo"] == Conta.TIPO_RECEITA),
            Decimal("0.00"),
        )
        despesas = sum(
            (Decimal(i["valor"]) for i in para_totais if i["tipo"] == Conta.TIPO_DESPESA),
            Decimal("0.00"),
        )

        dias_saida.append({
            "dia": numero_dia,
            "data": dia.isoformat(),
            "dia_semana": dia.weekday(),
            "eh_hoje": dia == hoje,
            "lancamentos": itens,
            "total_receitas": str(receitas),
            "total_despesas": str(despesas),
            "pendentes": sum(1 for i in itens if not i["realizado"]),
        })

    return {
        "ano": ano,
        "mes": mes,
        "dia_semana_do_primeiro": inicio.weekday(),
        "dias_no_mes": ultimo_dia,
        "dias": dias_saida,
    }

