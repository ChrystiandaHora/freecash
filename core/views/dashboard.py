from datetime import date
from django.views import View
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.db.models import Sum

from core.models import Transacao, ResumoMensal


@method_decorator(login_required, name="dispatch")
class DashboardView(View):
    def get(self, request):
        usuario = request.user
        hoje = date.today()
        ano = hoje.year
        mes = hoje.month

        # Totais do mês atual
        total_receitas = (
            Transacao.objects.filter(
                usuario=usuario,
                tipo=Transacao.TIPO_RECEITA,
                data__year=ano,
                data__month=mes,
            ).aggregate(Sum("valor"))["valor__sum"]
            or 0
        )

        total_despesas = (
            Transacao.objects.filter(
                usuario=usuario,
                tipo=Transacao.TIPO_DESPESA,
                data__year=ano,
                data__month=mes,
            ).aggregate(Sum("valor"))["valor__sum"]
            or 0
        )

        saldo_mes = total_receitas - total_despesas

        # Últimas transações
        ultimas_transacoes = Transacao.objects.filter(usuario=usuario).order_by(
            "-data", "-id"
        )[:5]

        # Resumo dos últimos 3 meses
        resumo_3_meses = ResumoMensal.objects.filter(usuario=usuario).order_by(
            "-ano", "-mes"
        )[:3]

        contexto = {
            "total_receitas": total_receitas,
            "total_despesas": total_despesas,
            "saldo_mes": saldo_mes,
            "ultimas_transacoes": ultimas_transacoes,
            "resumo_3_meses": resumo_3_meses,
            "mes_atual": mes,
            "ano_atual": ano,
        }

        return render(request, "dashboard.html", contexto)
