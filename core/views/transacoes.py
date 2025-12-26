from datetime import date

from django.views import View
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.core.paginator import Paginator

from core.models import Transacao, Categoria, FormaPagamento


@method_decorator(login_required, name="dispatch")
class TransacoesView(View):
    template_name = "transacoes.html"

    def get(self, request):
        usuario = request.user

        # Filtros
        ano = (request.GET.get("ano") or "").strip()
        mes = (request.GET.get("mes") or "").strip()
        tipo = (request.GET.get("tipo") or "").strip()  # "receita" | "despesa" | ""
        categoria = (request.GET.get("categoria") or "").strip()
        forma_pagamento = (request.GET.get("forma_pagamento") or "").strip()

        qs = (
            Transacao.objects.filter(usuario=usuario)
            .select_related("categoria", "forma_pagamento")
            .order_by("-data", "-id")
        )

        # Aplicando filtros
        if ano.isdigit():
            qs = qs.filter(data__year=int(ano))

        if mes.isdigit():
            qs = qs.filter(data__month=int(mes))

        if tipo:
            # Seu model usa "R" e "D"
            if tipo.lower() == "receita":
                qs = qs.filter(tipo=Transacao.TIPO_RECEITA)
            elif tipo.lower() == "despesa":
                qs = qs.filter(tipo=Transacao.TIPO_DESPESA)

        if categoria.isdigit():
            qs = qs.filter(categoria_id=int(categoria))

        if forma_pagamento.isdigit():
            qs = qs.filter(forma_pagamento_id=int(forma_pagamento))

        # Paginação
        try:
            per_page = int(request.GET.get("per_page", 5))
        except ValueError:
            per_page = 5
        per_page = max(5, min(per_page, 200))  # trava por segurança

        total_count = qs.count()
        paginator = Paginator(qs, per_page)
        page_obj = paginator.get_page(request.GET.get("page") or 1)

        # Querystring sem "page" para manter filtros na navegação
        params = request.GET.copy()
        params.pop("page", None)
        querystring = params.urlencode()

        # Selects
        ano_atual = date.today().year
        anos = list(range(2020, ano_atual + 1))
        meses = list(range(1, 13))

        contexto = {
            "page_obj": page_obj,
            "transacoes": page_obj.object_list,  # se você já usa "transacoes" no template
            "total_count": total_count,
            "per_page": per_page,
            "querystring": querystring,
            "categorias": Categoria.objects.filter(usuario=usuario).order_by("nome"),
            "formas_pagamento": FormaPagamento.objects.filter(usuario=usuario).order_by(
                "nome"
            ),
            "anos": anos,
            "meses": meses,
        }
        return render(request, self.template_name, contexto)
