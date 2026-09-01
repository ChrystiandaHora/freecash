"""Agregações estatísticas e helpers de série temporal para o dashboard financeiro."""

import calendar
from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from dateutil.relativedelta import relativedelta
from decimal import Decimal

from django.db.models import Q, Sum
from django.db.models.functions import TruncDay, TruncMonth

from core.models import Conta


@dataclass(frozen=True)
class Periodo:
    """Representa um período de tempo com datas limites para filtragem de lançamentos."""
    idx: int
    label: str
    inicio: date
    fim: date
    inicio_prev: date
    ultimo_dia: int


def totals_for_range_competencia(usuario, inicio: date, fim: date) -> tuple[float, float]:
    """Calcula a soma de receitas e despesas por competência no intervalo informado."""
    qs = Conta.objects.filter(
        usuario=usuario,
        data_prevista__gte=inicio,
        data_prevista__lt=fim,
    ).filter(Q(cartao__isnull=True) | Q(eh_fatura_cartao=True))
    receitas = (
        qs.filter(tipo=Conta.TIPO_RECEITA).aggregate(total=Sum("valor"))["total"] or 0
    )
    despesas = (
        qs.filter(tipo=Conta.TIPO_DESPESA).aggregate(total=Sum("valor"))["total"] or 0
    )
    return float(receitas), float(despesas)


def strip_tz(v) -> date:
    """Normaliza objeto de data/datetime para date puro sem timezone."""
    return v.date() if hasattr(v, "date") else v


def serie_por_dia_competencia(usuario, tipo: str, inicio: date, fim: date, ultimo_dia: int) -> tuple[list[str], list[float]]:
    """Gera série diária de valores previstos para o mês por competência."""
    qs = (
        Conta.objects.filter(
            usuario=usuario,
            tipo=tipo,
            data_prevista__gte=inicio,
            data_prevista__lt=fim,
        )
        .filter(Q(cartao__isnull=True) | Q(eh_fatura_cartao=True))
        .annotate(dia=TruncDay("data_prevista"))
        .values("dia")
        .annotate(total=Sum("valor"))
        .order_by("dia")
    )

    mapa = {strip_tz(row["dia"]): float(row["total"] or 0) for row in qs}

    labels, valores = [], []
    for d in range(1, ultimo_dia + 1):
        dt = date(inicio.year, inicio.month, d)
        labels.append(f"{d:02d}")
        valores.append(mapa.get(dt, 0.0))
    return labels, valores


def serie_6m_competencia(usuario, tipo: str, inicio_ref: date, fim_ref: date) -> tuple[list[str], list[float]]:
    """Gera série mensal agregada dos 6 meses anteriores por competência."""
    inicio_janela = inicio_ref - relativedelta(months=5)

    qs = (
        Conta.objects.filter(
            usuario=usuario,
            tipo=tipo,
            data_prevista__gte=inicio_janela,
            data_prevista__lt=fim_ref,
        )
        .filter(Q(cartao__isnull=True) | Q(eh_fatura_cartao=True))
        .annotate(mes=TruncMonth("data_prevista"))
        .values("mes")
        .annotate(total=Sum("valor"))
        .order_by("mes")
    )

    mapa = {strip_tz(row["mes"]).replace(day=1): float(row["total"] or 0) for row in qs}

    labels, values = [], []
    for i in range(5, -1, -1):
        ref = (inicio_ref - relativedelta(months=i)).replace(day=1)
        labels.append(ref.strftime("%b/%Y"))
        values.append(mapa.get(ref, 0.0))
    return labels, values


def serie_fluxo_projetado_competencia(usuario, tipo: str, inicio_ref: date) -> tuple[list[str], list[float]]:
    """Gera projeção de fluxo de caixa em janela de 6 meses (2 passados, atual e 3 futuros)."""
    inicio_janela = inicio_ref - relativedelta(months=2)
    fim_janela = inicio_ref + relativedelta(months=4)

    qs = (
        Conta.objects.filter(
            usuario=usuario,
            tipo=tipo,
            data_prevista__gte=inicio_janela,
            data_prevista__lt=fim_janela,
        )
        .filter(Q(cartao__isnull=True) | Q(eh_fatura_cartao=True))
        .annotate(mes=TruncMonth("data_prevista"))
        .values("mes")
        .annotate(total=Sum("valor"))
        .order_by("mes")
    )

    mapa = {strip_tz(row["mes"]).replace(day=1): float(row["total"] or 0) for row in qs}

    labels, values = [], []
    for i in range(-2, 4):
        ref = (inicio_ref + relativedelta(months=i)).replace(day=1)
        labels.append(ref.strftime("%b/%Y"))
        values.append(mapa.get(ref, 0.0))

    return labels, values


SEM_CATEGORIA = "Sem categoria"


def _explodir_fatura_por_categoria(fatura: Conta) -> dict[str, Decimal]:
    """Distribui o valor consolidado da fatura entre as categorias de suas compras."""
    from core.services.fatura_service import CATEGORIA_CARTAO_NOME

    parcelas: dict[str, Decimal] = defaultdict(Decimal)
    compras = (
        Conta.objects.filter(
            usuario_id=fatura.usuario_id,
            cartao_id=fatura.cartao_id,
            eh_fatura_cartao=False,
            data_prevista=fatura.data_prevista,
        )
        .values("categoria__nome")
        .annotate(total=Sum("valor"))
    )
    for row in compras:
        nome = row["categoria__nome"] or CATEGORIA_CARTAO_NOME
        parcelas[nome] += row["total"] or Decimal("0")

    valor_fatura = fatura.valor or Decimal("0")
    soma_compras = sum(parcelas.values(), Decimal("0"))

    if soma_compras <= 0:
        nome = fatura.categoria.nome if fatura.categoria else CATEGORIA_CARTAO_NOME
        return {nome: valor_fatura}

    if soma_compras == valor_fatura:
        return dict(parcelas)

    fator = valor_fatura / soma_compras
    return {nome: valor * fator for nome, valor in parcelas.items()}


def despesas_por_categoria(usuario, inicio: date, fim: date, campo_data: str, **extra_filtros) -> list[dict]:
    """Agrupa as despesas do período por categoria, abrindo gastos de faturas em suas compras."""
    filtros = {
        "usuario": usuario,
        "tipo": Conta.TIPO_DESPESA,
        f"{campo_data}__gte": inicio,
        f"{campo_data}__lt": fim,
        **extra_filtros,
    }

    totais: dict[str, Decimal] = defaultdict(Decimal)

    despesas_comuns = (
        Conta.objects.filter(cartao__isnull=True, **filtros)
        .values("categoria__nome")
        .annotate(total=Sum("valor"))
    )
    for row in despesas_comuns:
        nome = row["categoria__nome"] or SEM_CATEGORIA
        totais[nome] += row["total"] or Decimal("0")

    faturas = Conta.objects.filter(
        eh_fatura_cartao=True, cartao__isnull=False, **filtros
    ).select_related("categoria")
    for fatura in faturas:
        for nome, valor in _explodir_fatura_por_categoria(fatura).items():
            totais[nome] += valor

    itens = [{"nome": nome, "valor": float(valor)} for nome, valor in totais.items()]
    itens.sort(key=lambda item: item["valor"], reverse=True)
    return itens


def breakdown_despesas_competencia(usuario, inicio: date, fim: date, total_despesas: float, top_n: int = 4) -> tuple[list[dict], dict]:
    """Gera ranking percentual das maiores categorias de despesa por competência."""
    itens = despesas_por_categoria(usuario, inicio, fim, "data_prevista")

    if not itens or total_despesas <= 0:
        return [], {"nome": "Sem dados", "valor": 0.0, "pct": 0.0}

    top = itens[:top_n]
    soma_top = sum(i["valor"] for i in top)
    outros = max(total_despesas - soma_top, 0.0)

    out = [
        {
            "nome": i["nome"],
            "valor": i["valor"],
            "pct": (i["valor"] / total_despesas) * 100.0,
        }
        for i in top
    ]

    if outros > 0:
        out.append(
            {
                "nome": "Outros",
                "valor": outros,
                "pct": (outros / total_despesas) * 100.0,
            }
        )

    if out:
        total_pct = sum(x["pct"] for x in out)
        out[-1]["pct"] = max(0.0, out[-1]["pct"] - (total_pct - 100.0))

    top1 = out[0] if out else {"nome": "Sem dados", "valor": 0.0, "pct": 0.0}
    return out, top1


def clamp_int(value: str, default: int = 0, min_v: int = 0, max_v: int = 2) -> int:
    """Converte string para inteiro delimitado entre min_v e max_v."""
    value = (value or "").strip()
    if not value.isdigit():
        return default
    return max(min(int(value), max_v), min_v)


def month_start(d: date) -> date:
    """Retorna o primeiro dia do mês de uma data."""
    return d.replace(day=1)


def next_month_start(d: date) -> date:
    """Retorna o primeiro dia do mês subsequente."""
    return (d.replace(day=28) + relativedelta(days=4)).replace(day=1)


def make_periodo(hoje: date, periodo_idx: int) -> Periodo:
    """Gera datas de controle do período (0 = mês atual, 1 = mês anterior, 2 = próximo mês)."""
    labels = {0: "Mês atual", 1: "Mês anterior", 2: "Próximo mês"}

    if periodo_idx == 0:
        inicio = month_start(hoje)
    elif periodo_idx == 1:
        inicio = month_start(hoje) - relativedelta(months=1)
    elif periodo_idx == 2:
        inicio = month_start(hoje) + relativedelta(months=1)
    else:
        inicio = month_start(hoje)

    fim = next_month_start(inicio)
    inicio_prev = inicio - relativedelta(months=1)
    ultimo_dia = calendar.monthrange(inicio.year, inicio.month)[1]

    return Periodo(
        idx=periodo_idx,
        label=labels.get(periodo_idx, "Mês atual"),
        inicio=inicio,
        fim=fim,
        inicio_prev=inicio_prev,
        ultimo_dia=ultimo_dia,
    )


def make_periodo_custom(ano: int, mes: int) -> Periodo:
    """Gera datas de controle para um mês e ano específicos."""
    inicio = date(ano, mes, 1)
    fim = next_month_start(inicio)
    inicio_prev = inicio - relativedelta(months=1)
    ultimo_dia = calendar.monthrange(ano, mes)[1]

    meses_pt = {
        1: "Janeiro", 2: "Fevereiro", 3: "Março", 4: "Abril",
        5: "Maio", 6: "Junho", 7: "Julho", 8: "Agosto",
        9: "Setembro", 10: "Outubro", 11: "Novembro", 12: "Dezembro"
    }
    label = f"{meses_pt.get(mes, '')} de {ano}"

    return Periodo(
        idx=-1,
        label=label,
        inicio=inicio,
        fim=fim,
        inicio_prev=inicio_prev,
        ultimo_dia=ultimo_dia,
    )


def pct_change(atual: float, anterior: float) -> float | None:
    """Calcula a variação percentual entre o valor atual e o anterior."""
    if not anterior:
        return None
    return float(((atual - anterior) / anterior) * 100.0)


def totals_for_range_realizadas(usuario, inicio: date, fim: date) -> tuple[float, float]:
    """Soma receitas e despesas realizadas (regime de caixa) no intervalo."""
    qs = Conta.objects.filter(
        usuario=usuario,
        transacao_realizada=True,
        data_realizacao__gte=inicio,
        data_realizacao__lt=fim,
    ).filter(Q(cartao__isnull=True) | Q(eh_fatura_cartao=True))

    receitas = (
        qs.filter(tipo=Conta.TIPO_RECEITA).aggregate(total=Sum("valor"))["total"] or 0
    )
    despesas = (
        qs.filter(tipo=Conta.TIPO_DESPESA).aggregate(total=Sum("valor"))["total"] or 0
    )
    return float(receitas), float(despesas)


def saldo_liquidez_ate(usuario, ate: date) -> float:
    """Calcula o saldo realizado acumulado (caixa) até a data informada."""
    qs = Conta.objects.filter(
        usuario=usuario,
        transacao_realizada=True,
        data_realizacao__lte=ate,
    ).filter(Q(cartao__isnull=True) | Q(eh_fatura_cartao=True))

    receitas = (
        qs.filter(tipo=Conta.TIPO_RECEITA).aggregate(total=Sum("valor"))["total"] or 0
    )
    despesas = (
        qs.filter(tipo=Conta.TIPO_DESPESA).aggregate(total=Sum("valor"))["total"] or 0
    )
    return round(float(Decimal(receitas) - Decimal(despesas)), 2)


def serie_por_dia_realizadas(usuario, tipo: str, inicio: date, fim: date, ultimo_dia: int) -> tuple[list[str], list[float]]:
    """Gera série temporal diária dos lançamentos realizados (caixa)."""
    qs = (
        Conta.objects.filter(
            usuario=usuario,
            tipo=tipo,
            transacao_realizada=True,
            data_realizacao__gte=inicio,
            data_realizacao__lt=fim,
        )
        .filter(Q(cartao__isnull=True) | Q(eh_fatura_cartao=True))
        .annotate(dia=TruncDay("data_realizacao"))
        .values("dia")
        .annotate(total=Sum("valor"))
        .order_by("dia")
    )

    mapa = {strip_tz(row["dia"]): float(row["total"] or 0) for row in qs}

    labels, valores = [], []
    for d in range(1, ultimo_dia + 1):
        dt = date(inicio.year, inicio.month, d)
        labels.append(f"{d:02d}")
        valores.append(mapa.get(dt, 0.0))
    return labels, valores


def serie_6m_realizadas(usuario, tipo: str, inicio_ref: date, fim_ref: date) -> tuple[list[str], list[float]]:
    """Gera série mensal dos 6 meses anteriores por regime de caixa."""
    inicio_janela = inicio_ref - relativedelta(months=5)

    qs = (
        Conta.objects.filter(
            usuario=usuario,
            tipo=tipo,
            transacao_realizada=True,
            data_realizacao__gte=inicio_janela,
            data_realizacao__lt=fim_ref,
        )
        .filter(Q(cartao__isnull=True) | Q(eh_fatura_cartao=True))
        .annotate(mes=TruncMonth("data_realizacao"))
        .values("mes")
        .annotate(total=Sum("valor"))
        .order_by("mes")
    )

    mapa = {strip_tz(row["mes"]).replace(day=1): float(row["total"] or 0) for row in qs}

    labels, values = [], []
    for i in range(5, -1, -1):
        ref = (inicio_ref - relativedelta(months=i)).replace(day=1)
        labels.append(ref.strftime("%b/%Y"))
        values.append(mapa.get(ref, 0.0))
    return labels, values


def breakdown_despesas_realizadas(usuario, inicio: date, fim: date, total_despesas: float, top_n: int = 4) -> tuple[list[dict], dict]:
    """Gera ranking percentual das maiores categorias por despesas realizadas."""
    itens = despesas_por_categoria(
        usuario, inicio, fim, "data_realizacao", transacao_realizada=True
    )

    if not itens or total_despesas <= 0:
        return [], {"nome": "Sem dados", "valor": 0.0, "pct": 0.0}

    top = itens[:top_n]
    soma_top = sum(i["valor"] for i in top)
    outros = max(total_despesas - soma_top, 0.0)

    out = []
    for i in top:
        out.append(
            {
                "nome": i["nome"],
                "valor": i["valor"],
                "pct": (i["valor"] / total_despesas) * 100.0,
            }
        )

    if outros > 0:
        out.append(
            {
                "nome": "Outros",
                "valor": outros,
                "pct": (outros / total_despesas) * 100.0,
            }
        )

    if out:
        total_pct = sum(x["pct"] for x in out)
        out[-1]["pct"] = max(0.0, out[-1]["pct"] - (total_pct - 100.0))

    top1 = out[0] if out else {"nome": "Sem dados", "valor": 0.0, "pct": 0.0}
    return out, top1


def resumo_ultimos_3_meses_competencia(usuario, inicio_ref: date) -> list[dict]:
    """Gera resumo financeiro comparativo dos últimos 3 meses por competência."""
    itens = []

    for i in range(0, 3):
        inicio_mes = (inicio_ref - relativedelta(months=i)).replace(day=1)
        fim_mes = (inicio_mes + relativedelta(months=1)).replace(day=1)

        qs = Conta.objects.filter(
            usuario=usuario,
            data_prevista__gte=inicio_mes,
            data_prevista__lt=fim_mes,
        ).filter(Q(cartao__isnull=True) | Q(eh_fatura_cartao=True))

        receita = (
            qs.filter(tipo=Conta.TIPO_RECEITA).aggregate(total=Sum("valor"))["total"]
            or 0
        )
        gastos = (
            qs.filter(tipo=Conta.TIPO_DESPESA).aggregate(total=Sum("valor"))["total"]
            or 0
        )

        itens.append(
            {
                "ano": inicio_mes.year,
                "mes": inicio_mes.month,
                "receita": float(receita),
                "outras_receitas": 0.0,
                "gastos": float(gastos),
                "total": float(receita) - float(gastos),
            }
        )

    return itens

