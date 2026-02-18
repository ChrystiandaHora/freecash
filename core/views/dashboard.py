import calendar
from dataclasses import dataclass
from datetime import date
from dateutil.relativedelta import relativedelta

from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Q
from django.db.models.functions import TruncDay, TruncMonth
from django.shortcuts import render
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views import View

from core.models import Conta


@dataclass(frozen=True)
class Periodo:
    idx: int
    label: str
    inicio: date
    fim: date
    inicio_prev: date
    ultimo_dia: int


def totals_for_range_competencia(usuario, inicio: date, fim: date):
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


def serie_por_dia_competencia(usuario, tipo, inicio: date, fim: date, ultimo_dia: int):
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

    def norm_day(v):
        return v.date() if hasattr(v, "date") else v

    mapa = {norm_day(row["dia"]): float(row["total"] or 0) for row in qs}

    labels, valores = [], []
    for d in range(1, ultimo_dia + 1):
        dt = date(inicio.year, inicio.month, d)
        labels.append(f"{d:02d}")
        valores.append(mapa.get(dt, 0.0))
    return labels, valores


def serie_6m_competencia(usuario, tipo, inicio_ref: date, fim_ref: date):
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

    def norm_month(v):
        return v.date().replace(day=1) if hasattr(v, "date") else v

    mapa = {norm_month(row["mes"]): float(row["total"] or 0) for row in qs}

    labels, values = [], []
    for i in range(5, -1, -1):
        ref = (inicio_ref - relativedelta(months=i)).replace(day=1)
        labels.append(ref.strftime("%b/%Y"))
        values.append(mapa.get(ref, 0.0))
    return labels, values


def breakdown_despesas_competencia(
    usuario, inicio: date, fim: date, total_despesas: float, top_n: int = 4
):
    qs = (
        Conta.objects.filter(
            usuario=usuario,
            tipo=Conta.TIPO_DESPESA,
            data_prevista__gte=inicio,
            data_prevista__lt=fim,
        )
        .filter(Q(cartao__isnull=True) | Q(eh_fatura_cartao=True))
        .values("categoria__nome")
        .annotate(total=Sum("valor"))
        .order_by("-total")
    )

    itens = [
        {
            "nome": (row["categoria__nome"] or "Sem categoria"),
            "valor": float(row["total"] or 0),
        }
        for row in qs
    ]

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
    value = (value or "").strip()
    if not value.isdigit():
        return default
    return max(min(int(value), max_v), min_v)


def month_start(d: date) -> date:
    return d.replace(day=1)


def next_month_start(d: date) -> date:
    return (d.replace(day=28) + relativedelta(days=4)).replace(day=1)


def make_periodo(hoje: date, periodo_idx: int) -> Periodo:
    labels = {0: "Mês atual", 1: "Mês passado", 2: "Mês retrasado"}

    inicio = month_start(hoje) - relativedelta(months=periodo_idx)
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


def pct_change(atual: float, anterior: float):
    if not anterior:
        return None
    return float(((atual - anterior) / anterior) * 100.0)


def totals_for_range_realizadas(usuario, inicio: date, fim: date):
    """
    Totais por tipo considerando somente contas REALIZADAS,
    usando data_realizacao dentro do range.
    """
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


def serie_por_dia_realizadas(usuario, tipo, inicio: date, fim: date, ultimo_dia: int):
    """
    Série diária de contas REALIZADAS no mês (data_realizacao).
    """
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

    def norm_day(v):
        return v.date() if hasattr(v, "date") else v

    mapa = {norm_day(row["dia"]): float(row["total"] or 0) for row in qs}

    labels, valores = [], []
    for d in range(1, ultimo_dia + 1):
        dt = date(inicio.year, inicio.month, d)
        labels.append(f"{d:02d}")
        valores.append(mapa.get(dt, 0.0))
    return labels, valores


def serie_6m_realizadas(usuario, tipo, inicio_ref: date, fim_ref: date):
    """
    Série mensal (6 meses) de contas REALIZADAS (data_realizacao).
    """
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

    def norm_month(v):
        return v.date().replace(day=1) if hasattr(v, "date") else v

    mapa = {norm_month(row["mes"]): float(row["total"] or 0) for row in qs}

    labels, values = [], []
    for i in range(5, -1, -1):
        ref = (inicio_ref - relativedelta(months=i)).replace(day=1)
        labels.append(ref.strftime("%b/%Y"))
        values.append(mapa.get(ref, 0.0))
    return labels, values


def breakdown_despesas_realizadas(
    usuario, inicio: date, fim: date, total_despesas: float, top_n: int = 4
):
    """
    Breakdown por categoria considerando somente despesas REALIZADAS no range.
    """
    qs = (
        Conta.objects.filter(
            usuario=usuario,
            tipo=Conta.TIPO_DESPESA,
            transacao_realizada=True,
            data_realizacao__gte=inicio,
            data_realizacao__lt=fim,
        )
        .filter(Q(cartao__isnull=True) | Q(eh_fatura_cartao=True))
        .values("categoria__nome")
        .annotate(total=Sum("valor"))
        .order_by("-total")
    )

    itens = [
        {
            "nome": (row["categoria__nome"] or "Sem categoria"),
            "valor": float(row["total"] or 0),
        }
        for row in qs
    ]

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


def resumo_ultimos_3_meses_competencia(usuario, inicio_ref: date):
    """
    Retorna lista de 3 itens (do mais recente para o mais antigo), no formato:
    [{ano, mes, receita, outras_receitas, gastos, total}, ...]
    Tudo por COMPETÊNCIA (data_prevista).
    """
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


@method_decorator(login_required, name="dispatch")
class DashboardView(View):
    template_name = "core/dashboard/dashboard.html"

    def get(self, request):
        usuario = request.user
        hoje = timezone.localdate()

        periodo_idx = clamp_int(request.GET.get("periodo"), default=0, min_v=0, max_v=2)
        periodo = make_periodo(hoje, periodo_idx)

        # Totais do período por COMPETÊNCIA (data_prevista)
        total_receitas, total_despesas = totals_for_range_competencia(
            usuario, periodo.inicio, periodo.fim
        )
        saldo_mes = total_receitas - total_despesas

        # Comparação vs mês anterior também por COMPETÊNCIA
        receitas_prev, despesas_prev = totals_for_range_competencia(
            usuario, periodo.inicio_prev, periodo.inicio
        )
        receitas_pct = pct_change(total_receitas, receitas_prev)
        despesas_pct = pct_change(total_despesas, despesas_prev)

        # Séries diárias por COMPETÊNCIA
        dias_labels, receitas_dias = serie_por_dia_competencia(
            usuario, Conta.TIPO_RECEITA, periodo.inicio, periodo.fim, periodo.ultimo_dia
        )
        _, despesas_dias = serie_por_dia_competencia(
            usuario, Conta.TIPO_DESPESA, periodo.inicio, periodo.fim, periodo.ultimo_dia
        )

        # Séries 6 meses por COMPETÊNCIA
        meses_labels, receitas_6m = serie_6m_competencia(
            usuario, Conta.TIPO_RECEITA, periodo.inicio, periodo.fim
        )
        _, despesas_6m = serie_6m_competencia(
            usuario, Conta.TIPO_DESPESA, periodo.inicio, periodo.fim
        )
        saldos_6m = [r - d for r, d in zip(receitas_6m, despesas_6m)]

        # Breakdown por COMPETÊNCIA
        breakdown_items, top_categoria = breakdown_despesas_competencia(
            usuario, periodo.inicio, periodo.fim, total_despesas, top_n=4
        )

        media_gasto_dia = (
            (total_despesas / periodo.ultimo_dia) if periodo.ultimo_dia else 0.0
        )
        taxa_poupanca = (
            (saldo_mes / total_receitas * 100.0) if total_receitas > 0 else None
        )

        # Card "Status das contas" continua por data_prevista (já está correto)
        contas_mes = Conta.objects.filter(
            usuario=usuario,
            tipo=Conta.TIPO_DESPESA,
            data_prevista__gte=periodo.inicio,
            data_prevista__lt=periodo.fim,
        ).filter(Q(cartao__isnull=True) | Q(eh_fatura_cartao=True))

        contas_pendentes = contas_mes.filter(transacao_realizada=False).count()
        contas_pagas = contas_mes.filter(transacao_realizada=True).count()
        contas_atrasadas = contas_mes.filter(
            transacao_realizada=False, data_prevista__lt=hoje
        ).count()

        # Próximas contas (inclui atrasadas, ordenadas por vencimento)
        upcoming_bills = (
            Conta.objects.filter(
                usuario=usuario,
                tipo=Conta.TIPO_DESPESA,
                transacao_realizada=False,
            )
            .filter(Q(cartao__isnull=True) | Q(eh_fatura_cartao=True))
            .select_related("categoria", "forma_pagamento")
            .order_by("data_prevista")[:5]
        )

        # Transações recentes continuam por CAIXA (realizadas)
        ultimas_transacoes = (
            Conta.objects.filter(usuario=usuario, transacao_realizada=True)
            .filter(Q(cartao__isnull=True) | Q(eh_fatura_cartao=True))
            .select_related("categoria", "forma_pagamento")
            .order_by("-data_realizacao", "-id")[:7]
        )

        resumo_3_meses = resumo_ultimos_3_meses_competencia(usuario, periodo.inicio)
        saldo_prev = receitas_prev - despesas_prev
        saldo_pct = pct_change(saldo_mes, saldo_prev)

        contexto = {
            "periodo": periodo.idx,
            "periodo_label": periodo.label,
            "hoje": hoje,
            "total_receitas": total_receitas,
            "saldo_pct": saldo_pct,
            "total_despesas": total_despesas,
            "saldo_mes": saldo_mes,
            "receitas_pct": receitas_pct,
            "despesas_pct": despesas_pct,
            "dias_labels": dias_labels,
            "receitas_dias": receitas_dias,
            "despesas_dias": despesas_dias,
            "meses_labels": meses_labels,
            "receitas_6m": receitas_6m,
            "despesas_6m": despesas_6m,
            "saldos_6m": saldos_6m,
            "breakdown_items": breakdown_items,
            "top_categoria": top_categoria,
            "media_gasto_dia": media_gasto_dia,
            "taxa_poupanca": taxa_poupanca,
            "contas_pagas": contas_pagas,
            "contas_pendentes": contas_pendentes,
            "contas_atrasadas": contas_atrasadas,
            "upcoming_bills": upcoming_bills,
            "ultimas_transacoes": ultimas_transacoes,
            "resumo_3_meses": resumo_3_meses,
        }
        return render(request, self.template_name, contexto)
