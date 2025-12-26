import calendar
from datetime import date
from dateutil.relativedelta import relativedelta

from django.db.models import Sum
from django.db.models.functions import TruncMonth, TruncDay
from django.shortcuts import render
from django.utils.decorators import method_decorator
from django.contrib.auth.decorators import login_required
from django.views import View

from core.models import Transacao, ResumoMensal, ContaPagar


@method_decorator(login_required, name="dispatch")
class DashboardView(View):
    template_name = "dashboard.html"

    def get(self, request):
        usuario = request.user
        hoje = date.today()

        # periodo: 0 = mês atual, 1 = mês passado, 2 = mês retrasado
        periodo_str = (request.GET.get("periodo") or "0").strip()
        periodo = int(periodo_str) if periodo_str.isdigit() else 0
        periodo = min(max(periodo, 0), 2)

        labels_periodo = {
            0: "Mês atual",
            1: "Mês passado",
            2: "Mês retrasado",
        }
        periodo_label = labels_periodo.get(periodo, "Mês atual")

        inicio_mes_ref = hoje.replace(day=1) - relativedelta(months=periodo)
        inicio_prox_mes_ref = (
            inicio_mes_ref.replace(day=28) + relativedelta(days=4)
        ).replace(day=1)

        # para badges percentuais (comparar contra o mês anterior ao mês selecionado)
        inicio_mes_prev = inicio_mes_ref - relativedelta(months=1)

        # Totais do mês selecionado
        qs_receitas_ref = Transacao.objects.filter(
            usuario=usuario,
            tipo=Transacao.TIPO_RECEITA,
            data__gte=inicio_mes_ref,
            data__lt=inicio_prox_mes_ref,
        )
        qs_despesas_ref = Transacao.objects.filter(
            usuario=usuario,
            tipo=Transacao.TIPO_DESPESA,
            data__gte=inicio_mes_ref,
            data__lt=inicio_prox_mes_ref,
        )

        total_receitas = qs_receitas_ref.aggregate(total=Sum("valor"))["total"] or 0
        total_despesas = qs_despesas_ref.aggregate(total=Sum("valor"))["total"] or 0
        saldo_mes = total_receitas - total_despesas

        # Totais do mês anterior (ao mês selecionado)
        receitas_prev = (
            Transacao.objects.filter(
                usuario=usuario,
                tipo=Transacao.TIPO_RECEITA,
                data__gte=inicio_mes_prev,
                data__lt=inicio_mes_ref,
            ).aggregate(total=Sum("valor"))["total"]
            or 0
        )

        despesas_prev = (
            Transacao.objects.filter(
                usuario=usuario,
                tipo=Transacao.TIPO_DESPESA,
                data__gte=inicio_mes_prev,
                data__lt=inicio_mes_ref,
            ).aggregate(total=Sum("valor"))["total"]
            or 0
        )

        def pct_change(atual, anterior):
            if anterior == 0:
                return None
            return float(((atual - anterior) / anterior) * 100)

        receitas_pct = pct_change(total_receitas, receitas_prev)
        despesas_pct = pct_change(total_despesas, despesas_prev)

        # -------- Séries DIÁRIAS (para "Visão geral dos ganhos" e "Visão geral dos gastos") --------
        is_mes_atual = (inicio_mes_ref.year == hoje.year) and (
            inicio_mes_ref.month == hoje.month
        )
        ultimo_dia = (
            hoje.day
            if is_mes_atual
            else calendar.monthrange(inicio_mes_ref.year, inicio_mes_ref.month)[1]
        )

        def serie_por_dia(tipo):
            qs = (
                Transacao.objects.filter(
                    usuario=usuario,
                    tipo=tipo,
                    data__gte=inicio_mes_ref,
                    data__lt=inicio_prox_mes_ref,
                )
                .annotate(dia=TruncDay("data"))
                .values("dia")
                .annotate(total=Sum("valor"))
                .order_by("dia")
            )

            def norm_day(v):
                return v.date() if hasattr(v, "date") else v

            mapa = {norm_day(row["dia"]): float(row["total"] or 0) for row in qs}

            labels = []
            valores = []
            for d in range(1, ultimo_dia + 1):
                data_d = date(inicio_mes_ref.year, inicio_mes_ref.month, d)
                labels.append(f"{d:02d}")
                valores.append(mapa.get(data_d, 0.0))
            return labels, valores

        dias_labels, receitas_dias = serie_por_dia(Transacao.TIPO_RECEITA)
        _, despesas_dias = serie_por_dia(Transacao.TIPO_DESPESA)

        # -------- Séries MENSAIS (últimos 6 meses terminando no mês selecionado) para Fluxo de Caixa --------
        inicio_janela = inicio_mes_ref - relativedelta(months=5)

        def serie_por_mes(tipo):
            qs = (
                Transacao.objects.filter(
                    usuario=usuario,
                    tipo=tipo,
                    data__gte=inicio_janela,
                    data__lt=inicio_prox_mes_ref,
                )
                .annotate(mes=TruncMonth("data"))
                .values("mes")
                .annotate(total=Sum("valor"))
                .order_by("mes")
            )

            def norm_month(v):
                return v.date().replace(day=1) if hasattr(v, "date") else v

            return {norm_month(row["mes"]): float(row["total"] or 0) for row in qs}

        receitas_map = serie_por_mes(Transacao.TIPO_RECEITA)
        despesas_map = serie_por_mes(Transacao.TIPO_DESPESA)

        meses_labels = []
        receitas_6m = []
        despesas_6m = []
        saldos_6m = []

        for i in range(5, -1, -1):
            ref = (inicio_mes_ref - relativedelta(months=i)).replace(day=1)
            meses_labels.append(ref.strftime("%b/%Y"))
            r = receitas_map.get(ref, 0.0)
            d = despesas_map.get(ref, 0.0)
            receitas_6m.append(r)
            despesas_6m.append(d)
            saldos_6m.append(r - d)

        # Spending breakdown (despesas do mês selecionado por categoria)
        breakdown_qs = (
            Transacao.objects.filter(
                usuario=usuario,
                tipo=Transacao.TIPO_DESPESA,
                data__gte=inicio_mes_ref,
                data__lt=inicio_prox_mes_ref,
            )
            .values("categoria__nome")
            .annotate(total=Sum("valor"))
            .order_by("-total")
        )

        breakdown = []
        for row in breakdown_qs:
            nome = row["categoria__nome"] or "Sem categoria"
            valor = float(row["total"] or 0)
            breakdown.append({"nome": nome, "valor": valor})

        total_despesas_float = float(total_despesas or 0)
        top3 = breakdown[:3]
        soma_top3 = sum(x["valor"] for x in top3)
        outros_valor = max(total_despesas_float - soma_top3, 0)

        breakdown_items = []
        for item in top3:
            pct = (
                (item["valor"] / total_despesas_float * 100)
                if total_despesas_float
                else 0
            )
            breakdown_items.append(
                {"nome": item["nome"], "valor": item["valor"], "pct": pct}
            )

        breakdown_items.append(
            {
                "nome": "Outros",
                "valor": outros_valor if total_despesas_float else 0,
                "pct": (outros_valor / total_despesas_float * 100)
                if total_despesas_float
                else 0,
            }
        )

        # Donut de contas a pagar (mês selecionado)
        contas = ContaPagar.objects.filter(
            usuario=usuario,
            data_vencimento__gte=inicio_mes_ref,
            data_vencimento__lt=inicio_prox_mes_ref,
        )
        total_pendentes = contas.filter(status=ContaPagar.STATUS_PENDENTE).count()
        total_pagas = contas.filter(status=ContaPagar.STATUS_PAGO).count()
        total_atrasadas = contas.filter(
            status=ContaPagar.STATUS_PENDENTE,
            data_vencimento__lt=hoje,
        ).count()

        upcoming_bills = ContaPagar.objects.filter(
            usuario=usuario,
            status=ContaPagar.STATUS_PENDENTE,
            data_vencimento__gte=hoje,
        ).order_by("data_vencimento")[:5]

        ultimas_transacoes = Transacao.objects.filter(usuario=usuario).order_by(
            "-data", "-id"
        )[:5]
        resumo_3_meses = ResumoMensal.objects.filter(usuario=usuario).order_by(
            "-ano", "-mes"
        )[:3]

        contexto = {
            "periodo": periodo,
            "periodo_label": periodo_label,
            "ano_ref": inicio_mes_ref.year,
            "mes_ref": inicio_mes_ref.month,
            "total_receitas": total_receitas,
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
            "ultimas_transacoes": ultimas_transacoes,
            "resumo_3_meses": resumo_3_meses,
            "contas_pagas": total_pagas,
            "contas_pendentes": total_pendentes,
            "contas_atrasadas": total_atrasadas,
            "upcoming_bills": upcoming_bills,
        }
        return render(request, self.template_name, contexto)
