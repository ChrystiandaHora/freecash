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

from core.models import Conta, Categoria, FormaPagamento, CategoriaCartao
from core.signals import atualizar_config
from core.services.cotacao_service import converter_para_brl
from core.services.conta_service import (
    criar_contas_multiplicadas,
    criar_contas_parceladas,
)
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
            .select_related("categoria", "forma_pagamento", "cartao")
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
            .select_related("categoria", "forma_pagamento", "cartao")
            .order_by("-data_realizacao", "-id")
        )

        # Filtros
        q = (request.GET.get("q") or "").strip()
        ano = (request.GET.get("ano") or "").strip()
        mes = (request.GET.get("mes") or "").strip()
        categoria_id = (request.GET.get("categoria") or "").strip()
        forma_id = (request.GET.get("forma_pagamento") or "").strip()

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
        if forma_id.isdigit():
            qs_pendentes = qs_pendentes.filter(forma_pagamento_id=int(forma_id))
            qs_pagas = qs_pagas.filter(forma_pagamento_id=int(forma_id))
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
        # Para que ao mudar de pagina em um, não perca os filtros gerais.
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
        formas = FormaPagamento.objects.filter(usuario=usuario).order_by("nome")

        anos = list(range(hoje.year - 5, hoje.year + 1))
        anos.reverse()
        meses = list(range(1, 13))

        contexto = {
            "pendentes_page": pendentes_page,
            "pagas_page": pagas_page,
            "pendentes_qs": pendentes_qs,
            "pagas_qs": pagas_qs,
            "categorias": categorias,
            "formas": formas,
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
                "forma_pagamento": forma_id,
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
            .select_related("categoria", "forma_pagamento", "cartao")
        )

        # Filtros
        q = (request.GET.get("q") or "").strip()
        ano = (request.GET.get("ano") or "").strip()
        mes = (request.GET.get("mes") or "").strip()
        categoria_id = (request.GET.get("categoria") or "").strip()
        forma_id = (request.GET.get("forma_pagamento") or "").strip()

        if ano.isdigit():
            qs = qs.filter(data_prevista__year=int(ano))
        if mes.isdigit():
            qs = qs.filter(data_prevista__month=int(mes))
        if categoria_id.isdigit():
            qs = qs.filter(categoria_id=int(categoria_id))
        if forma_id.isdigit():
            qs = qs.filter(forma_pagamento_id=int(forma_id))
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
        formas = FormaPagamento.objects.filter(usuario=usuario, ativa=True).order_by(
            "nome"
        )

        anos = list(range(hoje.year - 5, hoje.year + 1))
        anos.reverse()
        meses = list(range(1, 13))

        contexto = {
            "atrasadas": atrasadas,
            "vence_hoje": vence_hoje,
            "proximas": proximas,
            "pagas_recentemente": pagas_recentemente,
            "categorias": categorias,
            "formas": formas,
            "anos": anos,
            "meses": meses,
            "hoje": hoje,
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
        descricao = cd.get("descricao")
        valor_total = cd.get("valor")
        data_prevista = cd.get("data_prevista")
        forma_pagamento = cd.get("forma_pagamento")
        categoria = cd.get("categoria")
        categoria_cartao = cd.get("categoria_cartao")

        parcelado = cd.get("parcelado")
        numero_parcelas = cd.get("numero_parcelas", 2)
        multiplicar = cd.get("multiplicar")
        numero_multiplicacoes = cd.get("numero_multiplicacoes", 2)
        data_limite_repeticao = cd.get("data_limite_repeticao")
        pago = cd.get("pago", False)
        moeda = cd.get("moeda", "BRL")

        if valor_total <= 0:
            messages.error(request, "O valor precisa ser maior que zero.")
            return redirect("contas_pagar")

        valor_brl, taxa_cambio = converter_para_brl(valor_total, moeda, data_prevista)

        # 1) MULTIPLICAR (criar N contas iguais, vencimentos mensais)
        if multiplicar:
            n = numero_multiplicacoes
            if not data_limite_repeticao and (n < 2 or n > 120):
                messages.error(request, "Quantidade deve ser entre 2 e 120.")
                return redirect("contas_pagar")

            criar_contas_multiplicadas(
                n=n,
                usuario=usuario,
                tipo=Conta.TIPO_DESPESA,
                descricao=descricao,
                valor_total=valor_total,
                data_prevista=data_prevista,
                pago=pago,
                categoria=categoria,
                forma_pagamento=forma_pagamento,
                categoria_cartao=categoria_cartao,
                data_limite=data_limite_repeticao,
            )

            messages.success(request, f"Conta registrada {n} vezes.")
            return redirect("contas_pagar")

        # 2) PARCELAR
        if parcelado:
            n = numero_parcelas
            if n < 2 or n > 12:
                messages.error(request, "Número de parcelas deve ser entre 2 e 12.")
                return redirect("contas_pagar")

            criar_contas_parceladas(
                n=n,
                usuario=usuario,
                tipo=Conta.TIPO_DESPESA,
                descricao=descricao,
                valor_total=valor_total,
                data_prevista=data_prevista,
                pago=pago,
                categoria=categoria,
                forma_pagamento=forma_pagamento,
                categoria_cartao=categoria_cartao,
            )

            messages.success(request, f"Conta registrada em {n} parcelas.")
            return redirect("contas_pagar")

        # 3) NORMAL
        Conta.objects.create(
            usuario=usuario,
            tipo=Conta.TIPO_DESPESA,
            descricao=descricao,
            valor=valor_total,
            moeda=moeda,
            valor_brl=valor_brl,
            taxa_cambio=taxa_cambio,
            data_prevista=data_prevista,
            transacao_realizada=pago,
            data_realizacao=data_prevista if pago else None,
            categoria=categoria,
            forma_pagamento=forma_pagamento,
            categoria_cartao=categoria_cartao,
            eh_parcelada=False,
            parcela_numero=None,
            parcela_total=None,
            grupo_parcelamento=None,
        )

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
                "categorias_cartao": CategoriaCartao.objects.all(),
                "modo": "create",
                "tipo": "despesa",
                "next_url": request.GET.get("next"),
            },
        )

    def post(self, request):
        # aqui você reutiliza exatamente o corpo do seu CadastrarContaPagarView.post
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
                "categorias_cartao": CategoriaCartao.objects.all(),
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
        dia_antigo = conta.data_prevista.day

        form = ContaForm(request.POST, instance=conta, usuario=usuario, tipo=conta.tipo)

        if not form.is_valid():
            messages.error(request, "Erros no formulário, não foi possível atualizar.")
            return redirect("conta_editar", conta_id=conta.id)

        cd = form.cleaned_data
        aplicar_grupo = request.POST.get("aplicar_grupo") == "1"

        # Update specific fields controlled outside normal save logic if needed
        valor_total = cd.get("valor")
        moeda = cd.get("moeda", "BRL")
        data_prevista = cd.get("data_prevista")
        pago = cd.get("pago", False)

        valor_brl, taxa_cambio = converter_para_brl(valor_total, moeda, data_prevista)

        conta = form.save(commit=False)
        conta.moeda = moeda
        conta.valor_brl = valor_brl
        conta.taxa_cambio = taxa_cambio
        conta.transacao_realizada = pago

        if pago and not conta.data_realizacao:
            conta.data_realizacao = data_prevista
        elif not pago:
            conta.data_realizacao = None

        conta.save()

        if aplicar_grupo and conta.eh_parcelada and conta.grupo_parcelamento:
            Conta.objects.filter(
                usuario=usuario, grupo_parcelamento=conta.grupo_parcelamento
            ).update(
                descricao=conta.descricao,
                categoria=conta.categoria,
                forma_pagamento=conta.forma_pagamento,
                categoria_cartao=conta.categoria_cartao,
            )

        # 4) ATUALIZAR FUTUROS SEMELHANTES
        atualizar_futuros = cd.get("atualizar_futuros")
        msg_adicional = ""
        if atualizar_futuros:
            contas_futuras = Conta.objects.filter(
                usuario=usuario,
                tipo=conta.tipo,
                data_prevista__gt=conta.data_prevista,
                data_prevista__day=dia_antigo,
                descricao__iexact=descricao_antiga,
                valor=valor_antigo,
            )
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

        # opcional: apagar grupo de parcelas se usuário escolher
        apagar_grupo = (request.POST.get("apagar_grupo") or "").strip() == "1"

        if apagar_grupo and conta.eh_parcelada and conta.grupo_parcelamento:
            Conta.objects.filter(
                usuario=usuario,
                eh_parcelada=True,
                grupo_parcelamento=conta.grupo_parcelamento,
            ).delete()
            messages.success(request, "Grupo de parcelas apagado com sucesso.")
        else:
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
