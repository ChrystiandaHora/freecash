from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from django.core.paginator import Paginator
from django.views import View
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.db.models import Sum

from core.models import Conta, Categoria, FormaPagamento
from core.signals import atualizar_config
from core.services.cotacao_service import converter_para_brl
from core.services.conta_service import (
    criar_contas_multiplicadas,
    criar_contas_parceladas,
)
from core.forms import ContaForm


def clamp_per_page(raw, default=5, min_v=5, max_v=200):
    try:
        v = int(raw)
    except (TypeError, ValueError):
        v = default
    return max(min_v, min(v, max_v))


def parse_date_flexible(date_str: str) -> date | None:
    """Parse date string in DD/MM/YYYY or YYYY-MM-DD format."""
    if not date_str:
        return None
    for fmt in ("%d/%m/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(date_str, fmt).date()
        except ValueError:
            continue
    return None


@method_decorator(login_required, name="dispatch")
class ReceitasView(View):
    template_name = "core/financeiro/receitas.html"

    def get(self, request):
        usuario = request.user
        hoje = timezone.localdate()

        q = (request.GET.get("q") or "").strip()
        ano = (request.GET.get("ano") or "").strip()
        mes = (request.GET.get("mes") or "").strip()
        categoria_id = (request.GET.get("categoria") or "").strip()
        forma_id = (request.GET.get("forma_pagamento") or "").strip()

        # Verificar se há filtros de data aplicados
        has_date_filter = ano.isdigit() or mes.isdigit()

        qs = Conta.objects.filter(
            usuario=usuario,
            tipo=Conta.TIPO_RECEITA,
            transacao_realizada=True,
        ).select_related("categoria", "forma_pagamento")

        # Aplicar filtros - com default para mês atual se não houver filtro de data
        if ano.isdigit():
            qs = qs.filter(data_realizacao__year=int(ano))
        elif not has_date_filter:
            qs = qs.filter(data_realizacao__year=hoje.year)

        if mes.isdigit():
            qs = qs.filter(data_realizacao__month=int(mes))
        elif not has_date_filter:
            qs = qs.filter(data_realizacao__month=hoje.month)

        if categoria_id.isdigit():
            qs = qs.filter(categoria_id=int(categoria_id))
        if forma_id.isdigit():
            qs = qs.filter(forma_pagamento_id=int(forma_id))
        if q:
            qs = qs.filter(descricao__icontains=q)

        qs = qs.order_by("-data_realizacao", "-id")

        # KPIs - Baseados nos querysets já filtrados
        total_receitas = qs.aggregate(total=Sum("valor"))["total"] or Decimal("0.00")
        receitas_count = qs.count()

        # Texto para label do período nos KPIs
        if ano.isdigit() and mes.isdigit():
            kpi_periodo = f"{int(mes):02d}/{ano}"
        elif ano.isdigit():
            kpi_periodo = ano
        elif mes.isdigit():
            kpi_periodo = f"{int(mes):02d}/{hoje.year}"
        else:
            kpi_periodo = hoje.strftime("%b/%Y")  # Default: mês atual

        categorias = Categoria.objects.filter(
            usuario=usuario,
            tipo=Categoria.TIPO_RECEITA,
        ).order_by("nome")
        formas = FormaPagamento.objects.filter(usuario=usuario, ativa=True).order_by(
            "nome"
        )

        anos = list(range(hoje.year - 5, hoje.year + 1))
        anos.reverse()
        meses = list(range(1, 13))

        per_page = clamp_per_page(request.GET.get("per_page"), default=10, max_v=200)
        paginator = Paginator(qs, per_page)
        page_obj = paginator.get_page(request.GET.get("page") or 1)

        params = request.GET.copy()
        params.pop("page", None)
        querystring = params.urlencode()

        contexto = {
            "page_obj": page_obj,
            "receitas": page_obj.object_list,
            "per_page": per_page,
            "querystring": querystring,
            "categorias": categorias,
            "formas": formas,
            "hoje": hoje,
            "anos": anos,
            "meses": meses,
            # KPIs
            "total_receitas": total_receitas,
            "receitas_count": receitas_count,
            "kpi_periodo": kpi_periodo,
            "filtros": {
                "q": q,
                "ano": ano,
                "mes": mes,
                "categoria": categoria_id,
                "forma_pagamento": forma_id,
            },
        }
        return render(request, self.template_name, contexto)


@method_decorator(login_required, name="dispatch")
class ReceitaCreateView(View):
    template_name = "core/financeiro/conta_form.html"

    def get(self, request):
        usuario = request.user
        categorias = Categoria.objects.filter(
            usuario=usuario,
            tipo=Categoria.TIPO_RECEITA,
        ).order_by("nome")
        formas = FormaPagamento.objects.filter(usuario=usuario, ativa=True).order_by(
            "nome"
        )

        form = ContaForm(usuario=usuario, tipo=Conta.TIPO_RECEITA)
        return render(
            request,
            self.template_name,
            {
                "categorias": categorias,
                "formas": formas,
                "form": form,
                "modo": "create",
                "titulo": "Nova Receita",
                "conta": None,
                "is_receita": True,
                "tipo": "receita",
                "next_url": request.GET.get("next"),
            },
        )

    def post(self, request):
        usuario = request.user

        form = ContaForm(request.POST, usuario=usuario, tipo=Conta.TIPO_RECEITA)
        if not form.is_valid():
            messages.error(
                request, "Erro na validação do formulário. Verifique os dados."
            )
            return redirect("receita_nova")

        cd = form.cleaned_data
        descricao = cd.get("descricao")
        valor = cd.get("valor")
        data_date = cd.get("data_prevista")
        forma_pagamento = cd.get("forma_pagamento")
        categoria = cd.get("categoria")

        parcelado = cd.get("parcelado")
        numero_parcelas = cd.get("numero_parcelas", 2)
        multiplicar = cd.get("multiplicar")
        numero_multiplicacoes = cd.get("numero_multiplicacoes", 2)

        # Lógica de Multiplicar
        if multiplicar:
            n = numero_multiplicacoes

            if n < 2 or n > 12:
                messages.error(request, "Quantidade deve ser entre 2 e 12.")
                return redirect("receita_nova")

            criar_contas_multiplicadas(
                n=n,
                usuario=usuario,
                tipo=Conta.TIPO_RECEITA,
                descricao=descricao,
                valor_total=valor,
                data_prevista=data_date,
                pago=True,
                categoria=categoria,
                forma_pagamento=forma_pagamento,
                categoria_cartao=None,
            )

            messages.success(request, f"Receita registrada {n} vezes.")
            return redirect("receitas")

        # Lógica de Parcelar
        if parcelado:
            n = numero_parcelas

            if n < 2 or n > 12:
                messages.error(request, "Número de parcelas deve ser entre 2 e 12.")
                return redirect("receita_nova")

            criar_contas_parceladas(
                n=n,
                usuario=usuario,
                tipo=Conta.TIPO_RECEITA,
                descricao=descricao,
                valor_total=valor,
                data_prevista=data_date,
                pago=True,
                categoria=categoria,
                forma_pagamento=forma_pagamento,
                categoria_cartao=None,
            )

            messages.success(request, f"Receita registrada em {n} parcelas.")
            return redirect("receitas")

        # Criação Unitária (Padrão)
        Conta.objects.create(
            usuario=usuario,
            tipo=Conta.TIPO_RECEITA,
            descricao=descricao,
            valor=valor,
            data_prevista=data_date,
            transacao_realizada=True,
            data_realizacao=data_date,
            categoria=categoria,
            forma_pagamento=forma_pagamento,
            eh_parcelada=False,
            parcela_numero=None,
            parcela_total=None,
            grupo_parcelamento=None,
        )

        messages.success(request, "Receita registrada!")

        next_url = request.POST.get("next")
        if next_url:
            return redirect(next_url)
        return redirect("receitas")


@method_decorator(login_required, name="dispatch")
class ReceitaUpdateView(View):
    template_name = "core/financeiro/conta_form.html"

    def get(self, request, pk):
        usuario = request.user
        # Garante que é Receita
        conta = get_object_or_404(
            Conta, id=pk, usuario=usuario, tipo=Conta.TIPO_RECEITA
        )

        categorias = Categoria.objects.filter(
            usuario=usuario,
            tipo=Categoria.TIPO_RECEITA,
        ).order_by("nome")

        formas = FormaPagamento.objects.filter(usuario=usuario, ativa=True).order_by(
            "nome"
        )

        form = ContaForm(instance=conta, usuario=usuario, tipo=Conta.TIPO_RECEITA)

        return render(
            request,
            self.template_name,
            {
                "conta": conta,
                "categorias": categorias,
                "formas": formas,
                "form": form,
                "modo": "edit",
                "titulo": "Editar Receita",
                "is_receita": True,
                "tipo": "receita",
                "next_url": request.GET.get("next"),
            },
        )

    def post(self, request, pk):
        usuario = request.user
        conta = get_object_or_404(
            Conta, id=pk, usuario=usuario, tipo=Conta.TIPO_RECEITA
        )

        # Captura os dados originais antes da edição
        descricao_antiga = conta.descricao
        valor_antigo = conta.valor
        data_antiga = conta.data_prevista
        dia_antigo = conta.data_prevista.day
        tipo_antigo = conta.tipo

        form = ContaForm(
            request.POST, instance=conta, usuario=usuario, tipo=Conta.TIPO_RECEITA
        )
        if not form.is_valid():
            messages.error(request, "Erros no formulário.")
            return redirect("receita_editar", pk=conta.id)

        cd = form.cleaned_data
        
        valor_total = cd.get("valor")
        moeda = cd.get("moeda", "BRL")
        data_prevista_nova = cd.get("data_prevista")
        pago = cd.get("pago")

        # Recalcula BRL e taxas para manter consistência
        valor_brl, taxa_cambio = converter_para_brl(valor_total, moeda, data_prevista_nova)

        conta = form.save(commit=False)
        conta.moeda = moeda
        conta.valor_brl = valor_brl
        conta.taxa_cambio = taxa_cambio
        
        if data_prevista_nova:
            conta.data_realizacao = data_prevista_nova if pago else None

        conta.transacao_realizada = pago
        conta.save()

        # 4) ATUALIZAR FUTUROS SEMELHANTES
        atualizar_futuros = cd.get("atualizar_futuros")
        msg_adicional = ""
        if atualizar_futuros:
            contas_futuras = Conta.objects.filter(
                usuario=usuario,
                tipo=tipo_antigo,
                data_prevista__gt=data_antiga,
                data_prevista__day=dia_antigo,
                descricao__iexact=descricao_antiga,
                valor=valor_antigo,
            ).exclude(id=conta.id)
            count = contas_futuras.count()
            if count > 0:
                contas_futuras.update(
                    descricao=conta.descricao,
                    valor=conta.valor,
                    valor_brl=conta.valor_brl,
                    taxa_cambio=conta.taxa_cambio,
                )
                atualizar_config(usuario)
                msg_adicional = f" {count} lançamentos futuros também foram atualizados."

        messages.success(request, f"Receita atualizada.{msg_adicional}")

        next_url = request.POST.get("next")
        if next_url:
            return redirect(next_url)
        return redirect("receitas")
