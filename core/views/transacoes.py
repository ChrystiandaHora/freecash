from datetime import date

from decimal import Decimal
from django.db.models import Sum, Q
from django.views import View
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.core.paginator import Paginator

from core.models import Conta, Categoria, FormaPagamento


def clamp_per_page(raw, default=10, min_v=5, max_v=200):
    try:
        v = int(raw)
    except (TypeError, ValueError):
        v = default
    return max(min_v, min(v, max_v))


@method_decorator(login_required, name="dispatch")
class TransacoesView(View):
    template_name = "transacoes.html"

    def get(self, request):
        usuario = request.user
        hoje = date.today()

        q = (request.GET.get("q") or "").strip()
        ano = (request.GET.get("ano") or "").strip()
        mes = (request.GET.get("mes") or "").strip()
        tipo = (request.GET.get("tipo") or "").strip()
        categoria = (request.GET.get("categoria") or "").strip()
        forma_pagamento = (request.GET.get("forma_pagamento") or "").strip()

        # Default: Se não houver filtros de data nem busca, exibe mês atual
        if not q and not ano and not mes:
            ano = str(hoje.year)
            mes = str(hoje.month)

        qs = (
            Conta.objects.filter(usuario=usuario, transacao_realizada=True)
            .select_related("categoria", "forma_pagamento")
            # Timeline: Apenas passado até hoje (inclusive)
            .filter(data_realizacao__lte=hoje)
            .order_by("-data_realizacao", "-atualizada_em", "-id")
        )

        if q:
            qs = qs.filter(descricao__icontains=q)

        if ano.isdigit():
            qs = qs.filter(data_realizacao__year=int(ano))

        if mes.isdigit():
            qs = qs.filter(data_realizacao__month=int(mes))

        if tipo:
            t = tipo.lower()
            if t == "receita":
                qs = qs.filter(tipo=Conta.TIPO_RECEITA)
            elif t == "despesa":
                qs = qs.filter(tipo=Conta.TIPO_DESPESA)
            elif t == "investimento":
                qs = qs.filter(tipo=Conta.TIPO_INVESTIMENTO)

        if categoria.isdigit():
            qs = qs.filter(categoria_id=int(categoria))

        if forma_pagamento.isdigit():
            qs = qs.filter(forma_pagamento_id=int(forma_pagamento))

        per_page = clamp_per_page(request.GET.get("per_page"), default=10, max_v=200)

        # Totals for the header (Bank Statement style)
        resumo = qs.aggregate(
            receitas=Sum("valor", filter=Q(tipo=Conta.TIPO_RECEITA)),
            despesas=Sum("valor", filter=Q(tipo=Conta.TIPO_DESPESA)),
        )
        total_receitas = resumo["receitas"] or Decimal("0.00")
        total_despesas = resumo["despesas"] or Decimal("0.00")
        saldo_periodo = total_receitas - total_despesas

        total_count = qs.count()

        paginator = Paginator(qs, per_page)
        page_obj = paginator.get_page(request.GET.get("page") or 1)

        params = request.GET.copy()
        params.pop("page", None)
        querystring = params.urlencode()

        ano_atual = date.today().year
        anos = list(range(2020, ano_atual + 1))
        meses = list(range(1, 13))

        contexto = {
            "page_obj": page_obj,
            "transacoes": page_obj.object_list,
            "total_count": total_count,
            "total_receitas": total_receitas,
            "total_despesas": total_despesas,
            "saldo_periodo": saldo_periodo,
            "per_page": per_page,
            "querystring": querystring,
            "categorias": Categoria.objects.filter(usuario=usuario).order_by("nome"),
            "formas_pagamento": FormaPagamento.objects.filter(usuario=usuario).order_by(
                "nome"
            ),
            "anos": anos,
            "meses": meses,
            "hoje": hoje,
            "filtros": {
                "q": q,
                "ano": ano,
                "mes": mes,
                "tipo": tipo,
                "categoria": categoria,
                "forma_pagamento": forma_pagamento,
            },
        }
        return render(request, self.template_name, contexto)
