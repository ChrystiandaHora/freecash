from datetime import date
from dateutil.relativedelta import relativedelta

from django.db.models import Sum
from django.db.models.functions import TruncMonth
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

        inicio_mes = hoje.replace(day=1)
        inicio_proximo_mes = (
            inicio_mes.replace(day=28) + relativedelta(days=4)
        ).replace(day=1)
        inicio_janela = inicio_mes - relativedelta(
            months=5
        )  # 6 meses incluindo o atual
        inicio_mes_anterior = inicio_mes - relativedelta(months=1)

        # Totais do mês atual
        total_receitas = (
            Transacao.objects.filter(
                usuario=usuario,
                tipo=Transacao.TIPO_RECEITA,
                data__gte=inicio_mes,
                data__lte=hoje,
            ).aggregate(total=Sum("valor"))["total"]
            or 0
        )

        total_despesas = (
            Transacao.objects.filter(
                usuario=usuario,
                tipo=Transacao.TIPO_DESPESA,
                data__gte=inicio_mes,
                data__lte=hoje,
            ).aggregate(total=Sum("valor"))["total"]
            or 0
        )

        saldo_mes = total_receitas - total_despesas

        # Totais do mês anterior (para badge percentual)
        receitas_anterior = (
            Transacao.objects.filter(
                usuario=usuario,
                tipo=Transacao.TIPO_RECEITA,
                data__gte=inicio_mes_anterior,
                data__lt=inicio_mes,
            ).aggregate(total=Sum("valor"))["total"]
            or 0
        )

        despesas_anterior = (
            Transacao.objects.filter(
                usuario=usuario,
                tipo=Transacao.TIPO_DESPESA,
                data__gte=inicio_mes_anterior,
                data__lt=inicio_mes,
            ).aggregate(total=Sum("valor"))["total"]
            or 0
        )

        def pct_change(atual, anterior):
            if anterior == 0:
                return None
            return float(((atual - anterior) / anterior) * 100)

        receitas_pct = pct_change(total_receitas, receitas_anterior)
        despesas_pct = pct_change(total_despesas, despesas_anterior)

        # Séries dos últimos 6 meses (receita e despesa) com 1 query por tipo
        def serie_por_mes(tipo):
            qs = (
                Transacao.objects.filter(
                    usuario=usuario,
                    tipo=tipo,
                    data__gte=inicio_janela,
                    data__lte=hoje,
                )
                .annotate(mes=TruncMonth("data"))
                .values("mes")
                .annotate(total=Sum("valor"))
                .order_by("mes")
            )
            return {row["mes"]: float(row["total"] or 0) for row in qs}

        receitas_map = serie_por_mes(Transacao.TIPO_RECEITA)
        despesas_map = serie_por_mes(Transacao.TIPO_DESPESA)

        meses_labels = []
        receitas_6m = []
        despesas_6m = []

        for i in range(5, -1, -1):
            ref = inicio_mes - relativedelta(months=i)
            meses_labels.append(ref.strftime("%b/%Y"))
            receitas_6m.append(receitas_map.get(ref, 0.0))
            despesas_6m.append(despesas_map.get(ref, 0.0))

        # Spending breakdown (despesas do mês por categoria)
        breakdown_qs = (
            Transacao.objects.filter(
                usuario=usuario,
                tipo=Transacao.TIPO_DESPESA,
                data__gte=inicio_mes,
                data__lte=hoje,
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

        if total_despesas_float:
            breakdown_items.append(
                {
                    "nome": "Outros",
                    "valor": outros_valor,
                    "pct": (outros_valor / total_despesas_float * 100),
                }
            )
        else:
            breakdown_items.append({"nome": "Outros", "valor": 0, "pct": 0})

        # Donut de contas a pagar (seu atual)
        contas = ContaPagar.objects.filter(
            usuario=usuario,
            data_vencimento__gte=inicio_mes,
            data_vencimento__lt=inicio_proximo_mes,
        )
        total_pendentes = contas.filter(status=ContaPagar.STATUS_PENDENTE).count()
        total_pagas = contas.filter(status=ContaPagar.STATUS_PAGO).count()
        total_atrasadas = contas.filter(
            status=ContaPagar.STATUS_PENDENTE,
            data_vencimento__lt=hoje,
        ).count()

        # Upcoming bills (próximas contas)
        upcoming_bills = ContaPagar.objects.filter(
            usuario=usuario,
            status=ContaPagar.STATUS_PENDENTE,
            data_vencimento__gte=hoje,
        ).order_by("data_vencimento")[:5]

        # Últimas transações
        ultimas_transacoes = Transacao.objects.filter(usuario=usuario).order_by(
            "-data", "-id"
        )[:5]

        # Resumo 3 meses
        resumo_3_meses = ResumoMensal.objects.filter(usuario=usuario).order_by(
            "-ano", "-mes"
        )[:3]

        contexto = {
            "total_receitas": total_receitas,
            "total_despesas": total_despesas,
            "saldo_mes": saldo_mes,
            "receitas_pct": receitas_pct,
            "despesas_pct": despesas_pct,
            "meses_labels": meses_labels,
            "receitas_6m": receitas_6m,
            "despesas_6m": despesas_6m,
            "breakdown_items": breakdown_items,
            "ultimas_transacoes": ultimas_transacoes,
            "resumo_3_meses": resumo_3_meses,
            "contas_pagas": total_pagas,
            "contas_pendentes": total_pendentes,
            "contas_atrasadas": total_atrasadas,
            "upcoming_bills": upcoming_bills,
        }

        return render(request, self.template_name, contexto)
