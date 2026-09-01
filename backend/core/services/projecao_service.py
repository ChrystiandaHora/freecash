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

from core.models import Conta, MetaFinanceira
from core.services.dashboard_helper import saldo_liquidez_ate
from core.services.recorrencia_service import garantir_horizonte

# Ignora compras individuais de cartão no saldo (o desembolso ocorre na fatura consolidada)
FILTRO_CARTAO = Q(cartao__isnull=True) | Q(eh_fatura_cartao=True)

MESES_PADRAO = 12
MESES_MAXIMO = 24


def _centavos(valor) -> Decimal:
    """Normaliza valor monetário para Decimal com 2 casas decimais."""
    return Decimal(valor or 0).quantize(Decimal("0.01"))


def _valor_investido(usuario) -> Decimal:
    """Soma o custo de aquisição da carteira (quantidade × preço médio)."""
    from investimento.models import Ativo

    total = Ativo.objects.filter(usuario=usuario).aggregate(
        total=Sum(
            ExpressionWrapper(
                F("quantidade") * F("preco_medio"),
                output_field=DecimalField(max_digits=19, decimal_places=4),
            )
        )
    )["total"]
    return _centavos(total)


def _movimentos_por_dia(usuario, inicio: date, fim: date) -> dict[date, dict]:
    """Agrupa por dia receitas e despesas pendentes (data_prevista) e liquidadas na janela."""
    movimentos = defaultdict(lambda: {"receitas": Decimal("0.00"), "despesas": Decimal("0.00")})

    def _acumular(linhas, campo_data: str) -> None:
        for linha in linhas:
            chave = "receitas" if linha["tipo"] == Conta.TIPO_RECEITA else "despesas"
            movimentos[linha[campo_data]][chave] += _centavos(linha["total"])

    pendentes = (
        Conta.objects.filter(
            usuario=usuario,
            transacao_realizada=False,
            data_prevista__gte=inicio,
            data_prevista__lte=fim,
        )
        .filter(FILTRO_CARTAO)
        .values("data_prevista", "tipo")
        .annotate(total=Sum("valor"))
    )
    _acumular(pendentes, "data_prevista")

    liquidados = (
        Conta.objects.filter(
            usuario=usuario,
            transacao_realizada=True,
            data_realizacao__gte=inicio,
            data_realizacao__lte=fim,
        )
        .filter(FILTRO_CARTAO)
        .values("data_realizacao", "tipo")
        .annotate(total=Sum("valor"))
    )
    _acumular(liquidados, "data_realizacao")

    return movimentos


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
    saldo_inicial = _centavos(saldo_liquidez_ate(usuario, hoje - timedelta(days=1)))
    atrasados = _pendencias_atrasadas(usuario, hoje)
    saldo_inicial += atrasados["receitas"] - atrasados["despesas"]

    valor_investido = _valor_investido(usuario)
    if not considerar_investimentos:
        saldo_inicial -= valor_investido

    movimentos = _movimentos_por_dia(usuario, hoje, fim)
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
            "saldo_final": dias_saida[-1]["saldo"] if dias_saida else str(saldo),
        })

        cursor = cursor + relativedelta(months=1)

    return {
        "inicio": hoje.isoformat(),
        "fim": fim.isoformat(),
        "saldo_inicial": str(saldo_inicial),
        "atrasados": {
            "receitas": str(atrasados["receitas"]),
            "despesas": str(atrasados["despesas"]),
        },
        "valor_investido": str(valor_investido),
        "investimentos_considerados": considerar_investimentos,
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

