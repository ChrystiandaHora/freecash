from datetime import date
from decimal import Decimal, InvalidOperation

from django.views import View
from django.shortcuts import get_object_or_404, render, redirect
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.contrib import messages
from django.core.paginator import Paginator
from django.utils import timezone

from core.models import Conta, Categoria, FormaPagamento


def clamp_per_page(raw, default=5, min_v=5, max_v=50):
    try:
        v = int(raw)
    except (TypeError, ValueError):
        v = default
    return max(min_v, min(v, max_v))


@method_decorator(login_required, name="dispatch")
class ContasPagarView(View):
    template_name = "contas_pagar.html"

    def get(self, request):
        usuario = request.user
        hoje = timezone.localdate()

        # Pendentes: despesas ainda não realizadas
        qs_pendentes = (
            Conta.objects.filter(
                usuario=usuario,
                tipo=Conta.TIPO_DESPESA,
                transacao_realizada=False,
            )
            .select_related("categoria", "forma_pagamento")
            .order_by("data_prevista", "id")
        )

        # Pagas: despesas realizadas
        qs_pagas = (
            Conta.objects.filter(
                usuario=usuario,
                tipo=Conta.TIPO_DESPESA,
                transacao_realizada=True,
            )
            .select_related("categoria", "forma_pagamento")
            .order_by("-data_realizacao", "-id")
        )

        per_page_pendentes = clamp_per_page(
            request.GET.get("per_page_pendentes"), default=5, max_v=50
        )
        per_page_pagas = clamp_per_page(
            request.GET.get("per_page_pagas"), default=5, max_v=50
        )

        pendentes_page = Paginator(qs_pendentes, per_page_pendentes).get_page(
            request.GET.get("page_pendentes") or 1
        )
        pagas_page = Paginator(qs_pagas, per_page_pagas).get_page(
            request.GET.get("page_pagas") or 1
        )

        # Querystring preservando estado
        params_pendentes = request.GET.copy()
        params_pendentes.pop("page_pendentes", None)
        pendentes_qs = params_pendentes.urlencode()

        params_pagas = request.GET.copy()
        params_pagas.pop("page_pagas", None)
        pagas_qs = params_pagas.urlencode()

        # selects
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

        descricao = (request.POST.get("descricao") or "").strip()
        valor_raw = (request.POST.get("valor") or "").strip()
        data_prevista = (
            request.POST.get("data_vencimento") or ""
        ).strip()  # mantém o name do form
        categoria_id = (request.POST.get("categoria") or "").strip()
        forma_pagamento_id = (request.POST.get("forma_pagamento") or "").strip()

        if not descricao or not valor_raw or not data_prevista:
            messages.error(request, "Preencha todos os campos obrigatórios.")
            return redirect("contas_pagar")

        try:
            # aceita "10,50" ou "10.50"
            valor_raw = (
                valor_raw.replace(".", "").replace(",", ".")
                if "," in valor_raw
                else valor_raw
            )
            valor = Decimal(valor_raw)
        except (InvalidOperation, ValueError):
            messages.error(request, "Valor inválido.")
            return redirect("contas_pagar")

        categoria = (
            Categoria.objects.filter(id=categoria_id, usuario=usuario).first()
            if categoria_id.isdigit()
            else None
        )
        forma_pagamento = (
            FormaPagamento.objects.filter(
                id=forma_pagamento_id, usuario=usuario
            ).first()
            if forma_pagamento_id.isdigit()
            else None
        )

        Conta.objects.create(
            usuario=usuario,
            tipo=Conta.TIPO_DESPESA,
            descricao=descricao,
            valor=valor,
            data_prevista=data_prevista,
            transacao_realizada=False,
            data_realizacao=None,
            categoria=categoria,
            forma_pagamento=forma_pagamento,
        )

        messages.success(request, "Conta registrada com sucesso.")
        return redirect("contas_pagar")


@method_decorator(login_required, name="dispatch")
class MarcarContaPagaView(View):
    def post(self, request, conta_id):
        usuario = request.user
        hoje = timezone.localdate()

        conta = get_object_or_404(
            Conta,
            id=conta_id,
            usuario=usuario,
            tipo=Conta.TIPO_DESPESA,
        )

        if conta.transacao_realizada:
            messages.warning(request, "Esta conta já está marcada como paga.")
            return redirect("contas_pagar")

        # permite escolher a data de pagamento, se você quiser no form
        data_pagamento = (request.POST.get("data_pagamento") or "").strip()
        conta.transacao_realizada = True
        conta.data_realizacao = data_pagamento or hoje
        conta.save(
            update_fields=["transacao_realizada", "data_realizacao", "atualizada_em"]
        )

        messages.success(request, "Conta marcada como paga com sucesso.")
        return redirect("contas_pagar")
