"""
Views para gerenciamento de assinaturas (pagamentos recorrentes).
"""

from datetime import date
from dateutil.relativedelta import relativedelta

from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View

from core.models import Assinatura, Categoria, FormaPagamento
from core.services.assinatura_service import gerar_conta_da_assinatura


class AssinaturasListView(LoginRequiredMixin, View):
    """Lista todas as assinaturas do usuário."""

    def get(self, request):
        assinaturas = (
            Assinatura.objects.filter(usuario=request.user)
            .select_related("categoria", "forma_pagamento")
            .order_by("-ativa", "descricao")
        )

        return render(
            request,
            "cadastros/assinaturas.html",
            {
                "assinaturas": assinaturas,
            },
        )


class AssinaturaCreateView(LoginRequiredMixin, View):
    """Cria uma nova assinatura."""

    def get(self, request):
        categorias = Categoria.objects.filter(
            usuario=request.user,
            tipo__in=[Categoria.TIPO_DESPESA, Categoria.TIPO_RECEITA],
        )
        formas_pagamento = FormaPagamento.objects.filter(
            usuario=request.user, ativa=True
        )

        # Próxima geração padrão: próximo mês
        hoje = date.today()
        proxima = (hoje + relativedelta(months=1)).replace(day=1)

        return render(
            request,
            "assinatura_form.html",
            {
                "categorias": categorias,
                "formas_pagamento": formas_pagamento,
                "proxima_geracao": proxima.isoformat(),
                "is_edit": False,
            },
        )

    def post(self, request):
        try:
            dia = int(request.POST.get("dia_vencimento", 1))
            dia = max(1, min(31, dia))

            proxima_str = request.POST.get("proxima_geracao")
            proxima = date.fromisoformat(proxima_str) if proxima_str else date.today()

            Assinatura.objects.create(
                usuario=request.user,
                descricao=request.POST.get("descricao", "").strip(),
                valor=request.POST.get("valor", "0").replace(",", "."),
                tipo=request.POST.get("tipo", Assinatura.TIPO_DESPESA),
                dia_vencimento=dia,
                categoria_id=request.POST.get("categoria") or None,
                forma_pagamento_id=request.POST.get("forma_pagamento") or None,
                ativa=True,
                proxima_geracao=proxima,
            )
            return redirect("assinaturas")
        except Exception as e:
            return render(
                request,
                "assinatura_form.html",
                {
                    "error": str(e),
                    "is_edit": False,
                },
            )


class AssinaturaUpdateView(LoginRequiredMixin, View):
    """Edita uma assinatura existente."""

    def get(self, request, pk):
        assinatura = get_object_or_404(Assinatura, pk=pk, usuario=request.user)
        categorias = Categoria.objects.filter(
            usuario=request.user,
            tipo__in=[Categoria.TIPO_DESPESA, Categoria.TIPO_RECEITA],
        )
        formas_pagamento = FormaPagamento.objects.filter(
            usuario=request.user, ativa=True
        )

        return render(
            request,
            "assinatura_form.html",
            {
                "assinatura": assinatura,
                "categorias": categorias,
                "formas_pagamento": formas_pagamento,
                "is_edit": True,
            },
        )

    def post(self, request, pk):
        assinatura = get_object_or_404(Assinatura, pk=pk, usuario=request.user)
        try:
            dia = int(request.POST.get("dia_vencimento", 1))
            dia = max(1, min(31, dia))

            proxima_str = request.POST.get("proxima_geracao")
            if proxima_str:
                assinatura.proxima_geracao = date.fromisoformat(proxima_str)

            assinatura.descricao = request.POST.get("descricao", "").strip()
            assinatura.valor = request.POST.get("valor", "0").replace(",", ".")
            assinatura.tipo = request.POST.get("tipo", Assinatura.TIPO_DESPESA)
            assinatura.dia_vencimento = dia
            assinatura.categoria_id = request.POST.get("categoria") or None
            assinatura.forma_pagamento_id = request.POST.get("forma_pagamento") or None
            assinatura.ativa = request.POST.get("ativa") == "on"
            assinatura.save()

            return redirect("assinaturas")
        except Exception as e:
            return render(
                request,
                "assinatura_form.html",
                {
                    "assinatura": assinatura,
                    "error": str(e),
                    "is_edit": True,
                },
            )


class AssinaturaDeleteView(LoginRequiredMixin, View):
    """Remove uma assinatura."""

    def post(self, request, pk):
        assinatura = get_object_or_404(Assinatura, pk=pk, usuario=request.user)
        cartao_id = assinatura.cartao.id if assinatura.cartao else None
        assinatura.delete()

        if cartao_id:
            return redirect("cartao_despesas", pk=cartao_id)
        return redirect("assinaturas")


class AssinaturaGerarContaView(LoginRequiredMixin, View):
    """Gera manualmente uma conta a partir da assinatura."""

    def post(self, request, pk):
        assinatura = get_object_or_404(Assinatura, pk=pk, usuario=request.user)
        gerar_conta_da_assinatura(assinatura)
        return redirect("assinaturas")
