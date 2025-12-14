from django.views import View
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.db.models import Q
from datetime import date

from core.models import Transacao, Categoria, FormaPagamento


@method_decorator(login_required, name="dispatch")
class TransacoesView(View):
    template_name = "transacoes.html"

    def get(self, request):
        usuario = request.user

        # Filtros
        ano = request.GET.get("ano")
        mes = request.GET.get("mes")
        tipo = request.GET.get("tipo")
        categoria = request.GET.get("categoria")
        forma_pagamento = request.GET.get("forma_pagamento")

        transacoes = Transacao.objects.filter(usuario=usuario).order_by("-data", "-id")

        # Aplicando filtros
        if ano:
            transacoes = transacoes.filter(data__year=ano)

        if mes:
            transacoes = transacoes.filter(data__month=mes)

        if tipo:
            transacoes = transacoes.filter(tipo=tipo)

        if categoria:
            transacoes = transacoes.filter(categoria_id=categoria)

        if forma_pagamento:
            transacoes = transacoes.filter(forma_pagamento_id=forma_pagamento)

        # ---- Dados para os filtros (SELECTs) ----
        ano_atual = date.today().year

        anos = list(range(2020, ano_atual + 1))
        meses = list(range(1, 13))

        contexto = {
            "transacoes": transacoes,
            # filtros
            "categorias": Categoria.objects.filter(usuario=usuario),
            "formas_pagamento": FormaPagamento.objects.filter(usuario=usuario),
            # selects
            "anos": anos,
            "meses": meses,
            # manter valores atuais (opcional, para selected)
            "ano_selecionado": ano,
            "mes_selecionado": mes,
            "tipo_selecionado": tipo,
            "categoria_selecionada": categoria,
            "forma_selecionada": forma_pagamento,
        }

        return render(request, self.template_name, contexto)
