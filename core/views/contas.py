from django.views import View
from django.shortcuts import get_object_or_404, render, redirect
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.contrib import messages
from django.core.paginator import Paginator
from datetime import date

from core.models import ContaPagar, Categoria, FormaPagamento, Transacao


@method_decorator(login_required, name="dispatch")
class ContasPagarView(View):
    template_name = "contas_pagar.html"

    def get(self, request):
        usuario = request.user
        hoje = date.today()

        qs_pendentes = ContaPagar.objects.filter(
            usuario=usuario, status=ContaPagar.STATUS_PENDENTE
        ).order_by("data_vencimento")

        qs_pagas = ContaPagar.objects.filter(
            usuario=usuario, status=ContaPagar.STATUS_PAGO
        ).order_by("-data_vencimento", "-id")

        # Quantidade por página (opcional)
        try:
            per_page_pendentes = int(request.GET.get("per_page_pendentes", 5))
        except ValueError:
            per_page_pendentes = 5

        try:
            per_page_pagas = int(request.GET.get("per_page_pagas", 5))
        except ValueError:
            per_page_pagas = 5

        per_page_pendentes = max(5, min(per_page_pendentes, 50))
        per_page_pagas = max(5, min(per_page_pagas, 50))

        paginator_pendentes = Paginator(qs_pendentes, per_page_pendentes)
        paginator_pagas = Paginator(qs_pagas, per_page_pagas)

        page_pendentes = request.GET.get("page_pendentes") or 1
        page_pagas = request.GET.get("page_pagas") or 1

        pendentes_page = paginator_pendentes.get_page(page_pendentes)
        pagas_page = paginator_pagas.get_page(page_pagas)

        # Querystring para preservar estado (mantém os params, remove só o page da tabela)
        params_pendentes = request.GET.copy()
        params_pendentes.pop("page_pendentes", None)
        pendentes_qs = params_pendentes.urlencode()

        params_pagas = request.GET.copy()
        params_pagas.pop("page_pagas", None)
        pagas_qs = params_pagas.urlencode()

        categorias = (
            Categoria.objects.filter(usuario=usuario)
            .exclude(tipo=Categoria.TIPO_RECEITA)
            .order_by("nome")
        )
        formas = FormaPagamento.objects.filter(usuario=usuario).order_by("nome")

        contexto = {
            "pendentes_page": pendentes_page,
            "pagas_page": pagas_page,
            "pendentes_qs": pendentes_qs,
            "pagas_qs": pagas_qs,
            "categorias": categorias,
            "formas": formas,
            "hoje": hoje,
        }
        return render(request, self.template_name, contexto)


@method_decorator(login_required, name="dispatch")
class CadastrarContaPagarView(View):
    def post(self, request):
        usuario = request.user

        descricao = request.POST.get("descricao")
        valor = request.POST.get("valor")
        data_vencimento = request.POST.get("data_vencimento")
        categoria_id = request.POST.get("categoria")
        forma_pagamento_id = request.POST.get("forma_pagamento")

        if not descricao or not valor or not data_vencimento:
            messages.error(request, "Preencha todos os campos obrigatórios.")
            return redirect("contas_pagar")

        categoria = (
            Categoria.objects.filter(id=categoria_id, usuario=usuario).first()
            if categoria_id
            else None
        )
        forma_pagamento = (
            FormaPagamento.objects.filter(
                id=forma_pagamento_id, usuario=usuario
            ).first()
            if forma_pagamento_id
            else None
        )

        ContaPagar.objects.create(
            usuario=usuario,
            descricao=descricao,
            valor=valor,
            data_vencimento=data_vencimento,
            categoria=categoria,
            forma_pagamento=forma_pagamento,
        )

        messages.success(request, "Conta registrada com sucesso.")
        return redirect("contas_pagar")


@method_decorator(login_required, name="dispatch")
class MarcarContaPagaView(View):
    def get(self, request, conta_id):
        usuario = request.user
        conta = get_object_or_404(ContaPagar, id=conta_id, usuario=usuario)

        if conta.status != ContaPagar.STATUS_PENDENTE:
            messages.warning(
                request, "Esta conta já está paga ou não pode ser alterada."
            )
            return redirect("contas_pagar")

        conta.status = ContaPagar.STATUS_PAGO
        conta.save(update_fields=["status"])

        Transacao.objects.create(
            usuario=usuario,
            tipo=Transacao.TIPO_DESPESA,
            valor=conta.valor,
            data=date.today(),
            categoria=conta.categoria,
            forma_pagamento=conta.forma_pagamento,
            descricao=f"Pagamento da conta: {conta.descricao}",
        )

        messages.success(request, "Conta marcada como paga com sucesso.")
        return redirect("contas_pagar")
