from decimal import Decimal, InvalidOperation

from django.core.paginator import Paginator
from django.views import View
from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.db.models import Sum

from core.models import Conta, Categoria, FormaPagamento


def clamp_per_page(raw, default=5, min_v=5, max_v=200):
    try:
        v = int(raw)
    except (TypeError, ValueError):
        v = default
    return max(min_v, min(v, max_v))


@method_decorator(login_required, name="dispatch")
class ReceitasView(View):
    template_name = "receitas.html"

    def get(self, request):
        usuario = request.user

        q = (request.GET.get("q") or "").strip()
        ano = (request.GET.get("ano") or "").strip()
        mes = (request.GET.get("mes") or "").strip()
        categoria_id = (request.GET.get("categoria") or "").strip()
        forma_id = (request.GET.get("forma_pagamento") or "").strip()

        qs = Conta.objects.filter(
            usuario=usuario,
            tipo=Conta.TIPO_RECEITA,
            transacao_realizada=True,
        ).select_related("categoria", "forma_pagamento")

        if ano.isdigit():
            qs = qs.filter(data_realizacao__year=int(ano))
        if mes.isdigit():
            qs = qs.filter(data_realizacao__month=int(mes))
        if categoria_id.isdigit():
            qs = qs.filter(categoria_id=int(categoria_id))
        if forma_id.isdigit():
            qs = qs.filter(forma_pagamento_id=int(forma_id))
        if q:
            qs = qs.filter(descricao__icontains=q)

        qs = qs.order_by("-data_realizacao", "-id")

        categorias = Categoria.objects.filter(
            usuario=usuario, tipo=Categoria.TIPO_RECEITA
        ).order_by("nome")
        formas = FormaPagamento.objects.filter(usuario=usuario, ativa=True).order_by(
            "nome"
        )

        hoje = timezone.localdate()
        ano_ref = int(ano) if ano.isdigit() else hoje.year
        mes_ref = int(mes) if mes.isdigit() else hoje.month

        # opção A (como você tinha): total do mês/ano ref, independente dos filtros
        total_periodo = (
            Conta.objects.filter(
                usuario=usuario,
                tipo=Conta.TIPO_RECEITA,
                transacao_realizada=True,
                data_realizacao__year=ano_ref,
                data_realizacao__month=mes_ref,
            ).aggregate(total=Sum("valor"))["total"]
            or 0
        )

        # opção B (se preferir): total considerando exatamente os filtros aplicados
        # total_periodo = qs.aggregate(total=Sum("valor"))["total"] or 0

        anos = list(range(hoje.year - 5, hoje.year + 1))
        anos.reverse()
        meses = list(range(1, 13))

        per_page = clamp_per_page(request.GET.get("per_page"), default=4, max_v=200)
        paginator = Paginator(qs, per_page)
        page_obj = paginator.get_page(request.GET.get("page") or 1)

        total_count = paginator.count  # mais barato/consistente do que qs.count()

        params = request.GET.copy()
        params.pop("page", None)
        querystring = params.urlencode()

        contexto = {
            "page_obj": page_obj,
            "receitas": page_obj.object_list,
            "per_page": per_page,
            "total_count": total_count,
            "querystring": querystring,
            "categorias": categorias,
            "formas": formas,
            "total_periodo": total_periodo,
            "ano_ref": ano_ref,
            "mes_ref": mes_ref,
            "anos": anos,
            "meses": meses,
            "filtros": {
                "q": q,
                "ano": ano,
                "mes": mes,
                "categoria": categoria_id,
                "forma_pagamento": forma_id,
            },
        }
        return render(request, self.template_name, contexto)

    def post(self, request):
        usuario = request.user

        descricao = (request.POST.get("descricao") or "").strip()
        data_realizacao_str = (request.POST.get("data_realizacao") or "").strip()
        valor_str = (request.POST.get("valor") or "").strip()
        categoria_id = (request.POST.get("categoria") or "").strip()
        forma_id = (request.POST.get("forma_pagamento") or "").strip()

        if not data_realizacao_str or not valor_str:
            messages.error(request, "Preencha data e valor.")
            return redirect("receitas")

        try:
            valor_norm = (
                valor_str.replace(".", "").replace(",", ".")
                if "," in valor_str
                else valor_str
            )
            valor = Decimal(valor_norm)
        except (InvalidOperation, TypeError):
            messages.error(request, "Valor inválido.")
            return redirect("receitas")

        categoria = (
            Categoria.objects.filter(usuario=usuario, id=categoria_id).first()
            if categoria_id.isdigit()
            else None
        )
        forma_pagamento = (
            FormaPagamento.objects.filter(usuario=usuario, id=forma_id).first()
            if forma_id.isdigit()
            else None
        )

        Conta.objects.create(
            usuario=usuario,
            tipo=Conta.TIPO_RECEITA,
            descricao=descricao,
            valor=valor,
            data_prevista=data_realizacao_str,
            transacao_realizada=True,
            data_realizacao=data_realizacao_str,
            categoria=categoria,
            forma_pagamento=forma_pagamento,
        )

        messages.success(request, "Receita registrada!")
        return redirect("receitas")
