from datetime import date, timedelta
from django.db.models import Sum, Q

from django.views import View
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator

from core.models import Transacao, ResumoMensal, ContaPagar


@method_decorator(login_required, name="dispatch")
class DashboardView(View):
    template_name = "dashboard.html"

    def get(self, request):
        usuario = request.user
        hoje = date.today()
        ano = hoje.year
        mes = hoje.month

        # ---------- Dados Financeiros Gerais ----------
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

        # ---------- Últimas Transações ----------
        ultimas_transacoes = Transacao.objects.filter(usuario=usuario).order_by(
            "-data", "-id"
        )[:5]

        # ---------- Resumo Mensal ----------
        resumo_3_meses = ResumoMensal.objects.filter(usuario=usuario).order_by(
            "-ano", "-mes"
        )[:3]

        # ---------- Contas a Pagar (Para Gráficos) ----------
        contas = ContaPagar.objects.filter(usuario=usuario)

        total_pendentes = contas.filter(status=ContaPagar.STATUS_PENDENTE).count()
        total_pagas = contas.filter(status=ContaPagar.STATUS_PAGO).count()
        total_atrasadas = contas.filter(
            status=ContaPagar.STATUS_PENDENTE, data_vencimento__lt=hoje
        ).count()

        # ---------- Total pago por mês (últimos 6 meses) ----------
        meses_labels = []
        meses_totais = []

        for i in range(5, -1, -1):
            data_ref = hoje - timedelta(days=30 * i)
            mes_ref = data_ref.month
            ano_ref = data_ref.year

            total_mes = (
                Transacao.objects.filter(
                    usuario=usuario,
                    tipo=Transacao.TIPO_DESPESA,
                    data__year=ano_ref,
                    data__month=mes_ref,
                ).aggregate(Sum("valor"))["valor__sum"]
                or 0
            )

            meses_labels.append(f"{mes_ref}/{ano_ref}")
            meses_totais.append(float(total_mes))

        contexto = {
            "total_receitas": total_receitas,
            "total_despesas": total_despesas,
            "saldo_mes": saldo_mes,
            "ultimas_transacoes": ultimas_transacoes,
            "resumo_3_meses": resumo_3_meses,
            # CONTAS PARA GRÁFICO DE PIZZA
            "contas_pagas": total_pagas,
            "contas_pendentes": total_pendentes,
            "contas_atrasadas": total_atrasadas,
            # GRÁFICO DE BARRAS
            "meses_labels": meses_labels,
            "meses_totais": meses_totais,
        }

        print(
            f"/n/nrequest.user.config.atualizada_em :{request.user.config.atualizada_em}"
        )

        return render(request, self.template_name, contexto)
