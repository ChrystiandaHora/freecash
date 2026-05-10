from datetime import date, datetime
from decimal import Decimal

from django.views import View
from django.shortcuts import get_object_or_404, render, redirect
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.contrib import messages
from django.core.paginator import Paginator
from django.utils import timezone
from django.db.models import Sum, Q

from core.models import Conta, Categoria
from core.signals import atualizar_config
from core.forms import ContaForm


def parse_date_flexible(date_str: str) -> date | None:
    """Parse date string in DD/MM/YYYY or YYYY-MM-DD format."""
    if not date_str:
        return None
    # Try DD/MM/YYYY first (Flowbite format)
    for fmt in ("%d/%m/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(date_str, fmt).date()
        except ValueError:
            continue
    return None


def clamp_per_page(raw, default=5, min_v=5, max_v=50):
    try:
        v = int(raw)
    except (TypeError, ValueError):
        v = default
    return max(min_v, min(v, max_v))


@method_decorator(login_required, name="dispatch")
class ContasPagarView(View):
    template_name = "core/cadastros/contas.html"

    def get(self, request):
        usuario = request.user
        hoje = timezone.localdate()

        # Pendentes: despesas ainda não realizadas
        # Exclui despesas de cartão individuais (apenas faturas são mostradas)
        qs_pendentes = (
            Conta.objects.filter(
                usuario=usuario,
                tipo=Conta.TIPO_DESPESA,
                transacao_realizada=False,
            )
            .filter(
                # Apenas contas sem cartão OU faturas de cartão
                Q(cartao__isnull=True) | Q(eh_fatura_cartao=True)
            )
            .select_related("categoria", "cartao")
            .order_by("data_prevista", "id")
        )

        # Pagas: despesas realizadas
        # Exclui despesas de cartão individuais (apenas faturas são mostradas)
        qs_pagas = (
            Conta.objects.filter(
                usuario=usuario,
                tipo=Conta.TIPO_DESPESA,
                transacao_realizada=True,
            )
            .filter(
                # Apenas contas sem cartão OU faturas de cartão
                Q(cartao__isnull=True) | Q(eh_fatura_cartao=True)
            )
            .select_related("categoria", "cartao")
            .order_by("-data_realizacao", "-id")
        )

        # Filtros
        q = (request.GET.get("q") or "").strip()
        ano = (request.GET.get("ano") or "").strip()
        mes = (request.GET.get("mes") or "").strip()
        categoria_id = (request.GET.get("categoria") or "").strip()

        # Verificar se há filtros aplicados (para decidir KPI default)
        has_date_filter = ano.isdigit() or mes.isdigit()

        # Base filters
        if ano.isdigit():
            qs_pendentes = qs_pendentes.filter(data_prevista__year=int(ano))
            qs_pagas = qs_pagas.filter(data_realizacao__year=int(ano))
        elif not has_date_filter:
            # Default: mês atual para pendentes
            qs_pendentes = qs_pendentes.filter(data_prevista__year=hoje.year)
            qs_pagas = qs_pagas.filter(data_realizacao__year=hoje.year)

        if mes.isdigit():
            qs_pendentes = qs_pendentes.filter(data_prevista__month=int(mes))
            qs_pagas = qs_pagas.filter(data_realizacao__month=int(mes))
        elif not has_date_filter:
            # Default: mês atual
            qs_pendentes = qs_pendentes.filter(data_prevista__month=hoje.month)
            qs_pagas = qs_pagas.filter(data_realizacao__month=hoje.month)

        if categoria_id.isdigit():
            qs_pendentes = qs_pendentes.filter(categoria_id=int(categoria_id))
            qs_pagas = qs_pagas.filter(categoria_id=int(categoria_id))

        if q:
            qs_pendentes = qs_pendentes.filter(descricao__icontains=q)
            qs_pagas = qs_pagas.filter(descricao__icontains=q)

        # KPIs - Baseados nos querysets já filtrados
        total_pendente = qs_pendentes.aggregate(total=Sum("valor"))["total"] or Decimal(
            "0.00"
        )
        pendentes_count = qs_pendentes.count()
        pagas_count = qs_pagas.count()

        # Texto para label do período nos KPIs
        if ano.isdigit() and mes.isdigit():
            kpi_periodo = f"{int(mes):02d}/{ano}"
        elif ano.isdigit():
            kpi_periodo = ano
        elif mes.isdigit():
            kpi_periodo = f"{int(mes):02d}/{hoje.year}"
        else:
            kpi_periodo = hoje.strftime("%b/%Y")  # Default: mês atual

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

        # Querystring preservando filtro, mas removendo a página específica de cada paginator
        params = request.GET.copy()

        # Para pendentes
        p_pend = params.copy()
        p_pend.pop("page_pendentes", None)
        pendentes_qs = p_pend.urlencode()

        # Para pagas
        p_pagas = params.copy()
        p_pagas.pop("page_pagas", None)
        pagas_qs = p_pagas.urlencode()

        # Selects
        categorias = Categoria.objects.filter(
            usuario=usuario, tipo=Categoria.TIPO_DESPESA
        ).order_by("nome")

        anos = list(range(hoje.year - 5, hoje.year + 1))
        anos.reverse()
        meses = list(range(1, 13))

        contexto = {
            "pendentes_page": pendentes_page,
            "pagas_page": pagas_page,
            "pendentes_qs": pendentes_qs,
            "pagas_qs": pagas_qs,
            "categorias": categorias,
            "hoje": hoje,
            "anos": anos,
            "meses": meses,
            # KPIs
            "total_pendente": total_pendente,
            "pendentes_count": pendentes_count,
            "pagas_count": pagas_count,
            "kpi_periodo": kpi_periodo,
            "filtros": {
                "q": q,
                "ano": ano,
                "mes": mes,
                "categoria": categoria_id,
            },
        }
        return render(request, self.template_name, contexto)


@method_decorator(login_required, name="dispatch")
class ContasPagarKanbanView(View):
    template_name = "core/cadastros/contas_kanban.html"

    def get(self, request):
        usuario = request.user
        hoje = timezone.localdate()

        # Base Queryset: apenas despesas pendentes
        qs = (
            Conta.objects.filter(
                usuario=usuario,
                tipo=Conta.TIPO_DESPESA,
                transacao_realizada=False,
            )
            .filter(Q(cartao__isnull=True) | Q(eh_fatura_cartao=True))
            .select_related("categoria", "cartao")
        )

        # Filtros
        q = (request.GET.get("q") or "").strip()
        ano = (request.GET.get("ano") or "").strip()
        mes = (request.GET.get("mes") or "").strip()
        categoria_id = (request.GET.get("categoria") or "").strip()

        if ano.isdigit():
            qs = qs.filter(data_prevista__year=int(ano))
        if mes.isdigit():
            qs = qs.filter(data_prevista__month=int(mes))
        if categoria_id.isdigit():
            qs = qs.filter(categoria_id=int(categoria_id))
        if q:
            qs = qs.filter(descricao__icontains=q)

        # Agrupamento para Kanban
        atrasadas = qs.filter(data_prevista__lt=hoje).order_by("data_prevista")
        vence_hoje = qs.filter(data_prevista=hoje).order_by("id")
        proximas = qs.filter(data_prevista__gt=hoje).order_by("data_prevista")[:50]

        # Pagas recentemente (opcional, para feedback visual)
        pagas_recentemente = Conta.objects.filter(
            usuario=usuario,
            tipo=Conta.TIPO_DESPESA,
            transacao_realizada=True,
            data_realizacao__gte=hoje,
        ).order_by("-data_realizacao")[:10]

        # Dados para filtros
        categorias = Categoria.objects.filter(
            usuario=usuario, tipo=Categoria.TIPO_DESPESA
        ).order_by("nome")

        anos = list(range(hoje.year - 5, hoje.year + 1))
        anos.reverse()
        meses = list(range(1, 13))

        contexto = {
            "atrasadas": atrasadas,
            "vence_hoje": vence_hoje,
            "proximas": proximas,
            "pagas_recentemente": pagas_recentemente,
            "categorias": categorias,
            "anos": anos,
            "meses": meses,
            "hoje": hoje,
            "filtros": {
                "q": q,
                "ano": ano,
                "mes": mes,
                "categoria": categoria_id,
            },
        }
        return render(request, self.template_name, contexto)


@method_decorator(login_required, name="dispatch")
class CadastrarContaPagarView(View):
    def post(self, request):
        usuario = request.user

        form = ContaForm(request.POST, usuario=usuario, tipo=Conta.TIPO_DESPESA)
        if not form.is_valid():
            messages.error(
                request, "Erro na validação do formulário. Verifique os dados."
            )
            return redirect("contas_pagar")

        cd = form.cleaned_data
        pago = cd.get("pago", False)
        data_prevista = cd.get("data_prevista")

        conta = form.save(commit=False)
        conta.transacao_realizada = pago
        if pago and not conta.data_realizacao:
            conta.data_realizacao = data_prevista
        
        conta.save()

        messages.success(request, "Conta registrada com sucesso.")

        next_url = request.POST.get("next")
        if next_url:
            return redirect(next_url)
        return redirect("contas_pagar")


@method_decorator(login_required, name="dispatch")
class ContaCreateView(View):
    template_name = "core/financeiro/conta_form.html"

    def get(self, request):
        usuario = request.user
        form = ContaForm(usuario=usuario, tipo=Conta.TIPO_DESPESA)
        return render(
            request,
            self.template_name,
            {
                "form": form,
                "modo": "create",
                "tipo": "despesa",
                "next_url": request.GET.get("next"),
            },
        )

    def post(self, request):
        return CadastrarContaPagarView().post(request)


@method_decorator(login_required, name="dispatch")
class ContaUpdateView(View):
    template_name = "core/financeiro/conta_form.html"

    def get(self, request, conta_id):
        usuario = request.user
        conta = get_object_or_404(Conta, id=conta_id, usuario=usuario)

        form = ContaForm(instance=conta, usuario=usuario, tipo=conta.tipo)
        return render(
            request,
            self.template_name,
            {
                "form": form,
                "conta": conta,
                "modo": "edit",
                "tipo": "receita" if conta.tipo == Conta.TIPO_RECEITA else "despesa",
                "next_url": request.GET.get("next"),
            },
        )

    def post(self, request, conta_id):
        usuario = request.user
        conta = get_object_or_404(Conta, id=conta_id, usuario=usuario)

        # Captura os dados originais antes da edição
        descricao_antiga = conta.descricao
        valor_antigo = conta.valor
        data_antiga = conta.data_prevista
        dia_antigo = conta.data_prevista.day
        tipo_antigo = conta.tipo

        form = ContaForm(request.POST, instance=conta, usuario=usuario, tipo=conta.tipo)

        if not form.is_valid():
            messages.error(request, "Erros no formulário, não foi possível atualizar.")
            return redirect("conta_editar", conta_id=conta.id)

        cd = form.cleaned_data

        valor = cd.get("valor")
        data_prevista = cd.get("data_prevista")
        pago = cd.get("pago", False)

        conta = form.save(commit=False)
        conta.transacao_realizada = pago

        if pago and not conta.data_realizacao:
            conta.data_realizacao = data_prevista
        elif not pago:
            conta.data_realizacao = None

        conta.save()

        # ATUALIZAR FUTUROS SEMELHANTES
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
                )
                atualizar_config(usuario)
                msg_adicional = f" {count} lançamentos futuros também foram atualizados."

        messages.success(request, f"Conta atualizada com sucesso.{msg_adicional}")

        next_url = request.POST.get("next")
        if next_url:
            return redirect(next_url)
        return redirect("contas_pagar")


@method_decorator(login_required, name="dispatch")
class ApagarContaView(View):
    def post(self, request, conta_id):
        usuario = request.user
        conta = get_object_or_404(Conta, id=conta_id, usuario=usuario)
        conta.delete()
        messages.success(request, "Conta apagada com sucesso.")
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

        data_pagamento = (request.POST.get("data_pagamento") or "").strip()
        conta.transacao_realizada = True
        conta.data_realizacao = data_pagamento or hoje
        conta.atualizada_em = timezone.now()
        conta.save(
            update_fields=["transacao_realizada", "data_realizacao", "atualizada_em"]
        )

        messages.success(request, "Conta marcada como paga com sucesso.")

        next_url = request.POST.get("next") or request.GET.get("next")
        if next_url:
            return redirect(next_url)
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
        conta.atualizada_em = timezone.now()  # Força atualização para ordenação
        conta.save(
            update_fields=["transacao_realizada", "data_realizacao", "atualizada_em"]
        )

        messages.success(request, "Conta marcada como paga com sucesso.")

        next_url = request.POST.get("next") or request.GET.get("next")
        if next_url:
            return redirect(next_url)
        return redirect("contas_pagar")
