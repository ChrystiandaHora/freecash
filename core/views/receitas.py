from datetime import date
from decimal import Decimal, InvalidOperation

from django.views import View
from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.db.models import Sum, Q

from core.models import Transacao, Categoria, FormaPagamento


@method_decorator(login_required, name="dispatch")
class ReceitasView(View):
    template_name = "receitas.html"

    def get(self, request):
        usuario = request.user

        # filtros
        q = (request.GET.get("q") or "").strip()
        ano = request.GET.get("ano") or ""
        mes = request.GET.get("mes") or ""
        categoria_id = request.GET.get("categoria") or ""
        forma_id = request.GET.get("forma_pagamento") or ""

        receitas = Transacao.objects.filter(
            usuario=usuario, tipo=Transacao.TIPO_RECEITA
        )

        if ano.isdigit():
            receitas = receitas.filter(data__year=int(ano))
        if mes.isdigit():
            receitas = receitas.filter(data__month=int(mes))
        if categoria_id.isdigit():
            receitas = receitas.filter(categoria_id=int(categoria_id))
        if forma_id.isdigit():
            receitas = receitas.filter(forma_pagamento_id=int(forma_id))
        if q:
            receitas = receitas.filter(descricao__icontains=q)

        receitas = receitas.order_by("-data", "-id")

        # combos para selects
        categorias = (
            Categoria.objects.filter(usuario=usuario)
            .filter(Q(tipo=Categoria.TIPO_RECEITA) | Q(tipo=Categoria.TIPO_AMBOS))
            .order_by("nome")
        )

        formas = FormaPagamento.objects.filter(usuario=usuario, ativa=True).order_by(
            "nome"
        )

        # Referência para resumo (se não veio filtro, usa mês atual)
        hoje = date.today()
        ano_ref = int(ano) if ano.isdigit() else hoje.year
        mes_ref = int(mes) if mes.isdigit() else hoje.month

        total_periodo = (
            Transacao.objects.filter(
                usuario=usuario,
                tipo=Transacao.TIPO_RECEITA,
                data__year=ano_ref,
                data__month=mes_ref,
            ).aggregate(Sum("valor"))["valor__sum"]
            or 0
        )

        # listas para os selects
        anos = list(range(hoje.year - 5, hoje.year + 1))
        anos.reverse()
        meses = list(range(1, 13))

        contexto = {
            "receitas": receitas[:200],
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
        data_str = request.POST.get("data") or ""
        valor_str = request.POST.get("valor") or ""
        categoria_id = request.POST.get("categoria") or ""
        forma_id = request.POST.get("forma_pagamento") or ""

        if not data_str or not valor_str:
            messages.error(request, "Preencha data e valor.")
            return redirect("receitas")

        try:
            valor = Decimal(valor_str)
        except (InvalidOperation, TypeError):
            messages.error(request, "Valor inválido.")
            return redirect("receitas")

        categoria = None
        if categoria_id.isdigit():
            categoria = Categoria.objects.filter(
                usuario=usuario, id=int(categoria_id)
            ).first()

        forma_pagamento = None
        if forma_id.isdigit():
            forma_pagamento = FormaPagamento.objects.filter(
                usuario=usuario, id=int(forma_id)
            ).first()

        Transacao.objects.create(
            usuario=usuario,
            tipo=Transacao.TIPO_RECEITA,
            data=data_str,
            descricao=descricao,
            valor=valor,
            categoria=categoria,
            forma_pagamento=forma_pagamento,
        )

        messages.success(request, "Receita registrada!")
        return redirect("receitas")
