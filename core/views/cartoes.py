"""
Views para gerenciamento de Cartões de Crédito.
"""

from datetime import date, datetime
from dateutil.relativedelta import relativedelta
from decimal import Decimal, InvalidOperation
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views import View

from core.models import (
    CartaoCredito,
    Categoria,
    Conta,
)
from core.forms import CartaoCreditoForm, ContaForm
from core.services.fatura_service import (
    obter_ou_criar_fatura,
    atualizar_valor_fatura,
    despesa_pode_ser_editada,
    calcular_vencimento_fatura,
)


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
class CartoesListView(View):
    """Lista todos os cartões de crédito do usuário."""

    template_name = "core/cartoes/cartoes.html"

    def get(self, request):
        usuario = request.user
        hoje = timezone.localdate()

        cartoes = CartaoCredito.objects.filter(usuario=usuario, ativo=True).order_by(
            "nome"
        )

        # Calcular gasto total e do ciclo de cada cartão
        cartoes_com_gasto = []
        for cartao in cartoes:
            # Gasto TOTAL (não pago) = para calcular o limite disponível atual
            gasto_total = Conta.objects.filter(
                usuario=usuario,
                cartao=cartao,
                tipo=Conta.TIPO_DESPESA,
                transacao_realizada=False,
                eh_fatura_cartao=False,
            ).aggregate(total=Sum("valor"))["total"] or Decimal("0.00")

            # Gasto do CICLO (para exibir como "Gasto este mês" no template)
            # Se hoje > dia_vencimento, o "mês de referência" é o próximo
            if hoje.day > cartao.dia_vencimento:
                data_referencia = hoje + relativedelta(months=1)
            else:
                data_referencia = hoje

            gasto_ciclo = Conta.objects.filter(
                usuario=usuario,
                cartao=cartao,
                tipo=Conta.TIPO_DESPESA,
                data_prevista__year=data_referencia.year,
                data_prevista__month=data_referencia.month,
                eh_fatura_cartao=False,
            ).aggregate(total=Sum("valor"))["total"] or Decimal("0.00")

            cartoes_com_gasto.append(
                {
                    "cartao": cartao,
                    "gasto_mes": gasto_ciclo,
                    "limite_disponivel": (
                        cartao.limite - gasto_total if cartao.limite else None
                    ),
                    "percentual_usado": (
                        (gasto_ciclo / cartao.limite * 100) if cartao.limite else None
                    ),
                }
            )

        return render(
            request,
            self.template_name,
            {
                "cartoes": cartoes_com_gasto,
                "hoje": hoje,
            },
        )


@method_decorator(login_required, name="dispatch")
class CartaoCreateView(View):
    """Cria um novo cartão de crédito."""

    template_name = "core/cartoes/cartao_form.html"

    def get(self, request):
        form = CartaoCreditoForm()
        return render(
            request,
            self.template_name,
            {
                "modo": "create",
                "form": form,
                "bandeiras": CartaoCredito.BANDEIRA_CHOICES,
            },
        )

    def post(self, request):
        usuario = request.user
        form = CartaoCreditoForm(request.POST, usuario=usuario)

        if not form.is_valid():
            messages.error(request, "Erro ao validar o formulário. Verifique os dados.")
            return redirect("cartao_novo")

        cartao = form.save(commit=False)
        cartao.usuario = usuario
        cartao.save()

        messages.success(request, "Cartão cadastrado com sucesso!")
        return redirect("cartoes")


@method_decorator(login_required, name="dispatch")
class CartaoUpdateView(View):
    """Edita um cartão de crédito existente."""

    template_name = "core/cartoes/cartao_form.html"

    def get(self, request, pk):
        usuario = request.user
        cartao = get_object_or_404(CartaoCredito, pk=pk, usuario=usuario)
        form = CartaoCreditoForm(instance=cartao)

        return render(
            request,
            self.template_name,
            {
                "modo": "edit",
                "cartao": cartao,
                "form": form,
                "bandeiras": CartaoCredito.BANDEIRA_CHOICES,
            },
        )

    def post(self, request, pk):
        usuario = request.user
        cartao = get_object_or_404(CartaoCredito, pk=pk, usuario=usuario)

        form = CartaoCreditoForm(request.POST, instance=cartao, usuario=usuario)
        if not form.is_valid():
            messages.error(request, "Erro ao validar o formulário. Verifique os dados.")
            return redirect("cartao_editar", pk=pk)

        form.save()

        messages.success(request, "Cartão atualizado com sucesso!")
        return redirect("cartoes")


@method_decorator(login_required, name="dispatch")
class CartaoDeleteView(View):
    """Desativa um cartão de crédito."""

    def post(self, request, pk):
        usuario = request.user
        cartao = get_object_or_404(CartaoCredito, pk=pk, usuario=usuario)

        cartao.ativo = False
        cartao.save(update_fields=["ativo", "atualizada_em"])

        messages.success(request, "Cartão removido com sucesso!")
        return redirect("cartoes")


@method_decorator(login_required, name="dispatch")
class CartaoDespesasView(View):
    """Lista despesas de um cartão específico."""

    template_name = "core/cartoes/cartao_despesas.html"

    def get(self, request, pk):
        usuario = request.user
        cartao = get_object_or_404(CartaoCredito, pk=pk, usuario=usuario)
        hoje = timezone.localdate()

        # Filtros
        ano = (request.GET.get("ano") or str(hoje.year)).strip()
        mes = (request.GET.get("mes") or str(hoje.month)).strip()
        filtro_data = (request.GET.get("filtro_data") or "vencimento").strip()

        qs = (
            Conta.objects.filter(
                usuario=usuario,
                cartao=cartao,
                tipo=Conta.TIPO_DESPESA,
            )
            .select_related("categoria")
            .order_by("-data_prevista", "-id")
        )

        # Excluir faturas da lista de despesas (elas são mostradas separadamente)
        qs = qs.filter(eh_fatura_cartao=False)

        # Aplicar filtro pelo tipo de data escolhido
        if filtro_data == "compra":
            # Filtrar por data_compra
            if ano.isdigit():
                qs = qs.filter(data_compra__year=int(ano))
            if mes.isdigit():
                qs = qs.filter(data_compra__month=int(mes))
        else:
            # Filtrar por data_prevista (vencimento) - padrão
            if ano.isdigit():
                qs = qs.filter(data_prevista__year=int(ano))
            if mes.isdigit():
                qs = qs.filter(data_prevista__month=int(mes))

        total_mes = qs.aggregate(total=Sum("valor"))["total"] or Decimal("0.00")

        # Buscar a fatura do mês/ano selecionado
        fatura = Conta.objects.filter(
            usuario=usuario,
            cartao=cartao,
            eh_fatura_cartao=True,
            data_prevista__year=int(ano) if ano.isdigit() else hoje.year,
            data_prevista__month=int(mes) if mes.isdigit() else hoje.month,
        ).first()

        paginator = Paginator(qs, 10)
        page = paginator.get_page(request.GET.get("page") or 1)

        return render(
            request,
            self.template_name,
            {
                "cartao": cartao,
                "despesas_page": page,
                "paginator": paginator,
                "total_mes": total_mes,
                "hoje": hoje,
                "anos": reversed(range(2020, 2031)),
                "meses": range(1, 13),
                "filtros": {
                    "ano": ano,
                    "mes": mes,
                },
                "fatura": fatura,
            },
        )


@method_decorator(login_required, name="dispatch")
class CartaoDespesaCreateView(View):
    """Cria uma nova despesa no cartão."""

    def post(self, request, pk):
        usuario = request.user
        cartao = get_object_or_404(CartaoCredito, pk=pk, usuario=usuario)

        descricao = (request.POST.get("descricao") or "").strip()
        valor_raw = (request.POST.get("valor") or "").strip()
        data_raw = (
            request.POST.get("data_compra") or request.POST.get("data_prevista") or ""
        ).strip()

        if not descricao or not valor_raw or not data_raw:
            messages.error(request, "Preencha todos os campos obrigatórios.")
            return redirect("cartao_despesas", pk=pk)

        # Valor
        try:
            valor_raw = (
                valor_raw.replace(".", "").replace(",", ".")
                if "," in valor_raw
                else valor_raw
            )
            valor_total = Decimal(valor_raw).quantize(Decimal("0.01"))
        except (InvalidOperation, ValueError):
            messages.error(request, "Valor inválido.")
            return redirect("cartao_despesas", pk=pk)

        if valor_total <= 0:
            messages.error(request, "O valor precisa ser maior que zero.")
            return redirect("cartao_despesas", pk=pk)

        # Data da compra
        data_compra = parse_date_flexible(data_raw)
        if not data_compra:
            messages.error(request, "Data inválida.")
            return redirect("cartao_despesas", pk=pk)

        data_vencimento = calcular_vencimento_fatura(
            data_compra, cartao.dia_fechamento, cartao.dia_vencimento
        )

        # Obter ou criar a fatura para este cartão/vencimento
        fatura = obter_ou_criar_fatura(usuario, cartao, data_vencimento)

        # Validar se a fatura já está paga
        if fatura.transacao_realizada:
            messages.error(
                request,
                f"Não é possível adicionar despesas a uma fatura já paga ({data_vencimento.strftime('%m/%Y')}).",
            )
            return redirect("cartao_despesas", pk=pk)

        # Buscar categoria padrão de despesa
        default_cat = Categoria.objects.filter(
            usuario=usuario, tipo=Categoria.TIPO_DESPESA, is_default=True
        ).first()

        # Compra normal
        Conta.objects.create(
            usuario=usuario,
            tipo=Conta.TIPO_DESPESA,
            descricao=descricao,
            valor=valor_total,
            data_compra=data_compra,
            data_prevista=data_vencimento,
            cartao=cartao,
            fatura=fatura,
            categoria=default_cat,
        )

        # Atualizar valor total da fatura
        atualizar_valor_fatura(fatura)

        messages.success(request, "Despesa adicionada ao cartão!")
        return redirect("cartao_despesas", pk=pk)


@method_decorator(login_required, name="dispatch")
class CartaoDespesaUpdateView(View):
    """Edita uma despesa do cartão."""

    template_name = "core/cartoes/cartao_despesa_form.html"

    def get(self, request, pk, despesa_id):
        usuario = request.user
        cartao = get_object_or_404(CartaoCredito, pk=pk, usuario=usuario)
        despesa = get_object_or_404(
            Conta, id=despesa_id, cartao=cartao, usuario=usuario, eh_fatura_cartao=False
        )

        # Bloquear edição se a fatura já foi paga
        if not despesa_pode_ser_editada(despesa):
            messages.error(
                request, "Esta despesa não pode ser editada pois a fatura já foi paga."
            )
            return redirect("cartao_despesas", pk=pk)

        return render(
            request,
            self.template_name,
            {
                "cartao": cartao,
                "despesa": despesa,
            },
        )

    def post(self, request, pk, despesa_id):
        usuario = request.user
        cartao = get_object_or_404(CartaoCredito, pk=pk, usuario=usuario)
        despesa = get_object_or_404(
            Conta, id=despesa_id, cartao=cartao, usuario=usuario, eh_fatura_cartao=False
        )

        # Bloquear edição se a fatura já foi paga
        if not despesa_pode_ser_editada(despesa):
            messages.error(
                request, "Esta despesa não pode ser editada pois a fatura já foi paga."
            )
            return redirect("cartao_despesas", pk=pk)

        descricao = (request.POST.get("descricao") or "").strip()
        valor_raw = (request.POST.get("valor") or "").strip()
        data_raw = (request.POST.get("data_prevista") or "").strip()

        if not descricao or not valor_raw or not data_raw:
            messages.error(request, "Preencha todos os campos obrigatórios.")
            return redirect("cartao_despesa_editar", pk=pk, despesa_id=despesa_id)

        # Valor
        try:
            valor_raw = (
                valor_raw.replace(".", "").replace(",", ".")
                if "," in valor_raw
                else valor_raw
            )
            valor = Decimal(valor_raw).quantize(Decimal("0.01"))
        except (InvalidOperation, ValueError):
            messages.error(request, "Valor inválido.")
            return redirect("cartao_despesa_editar", pk=pk, despesa_id=despesa_id)

        if valor <= 0:
            messages.error(request, "O valor precisa ser maior que zero.")
            return redirect("cartao_despesa_editar", pk=pk, despesa_id=despesa_id)

        # Data
        data_prevista = parse_date_flexible(data_raw)
        if not data_prevista:
            messages.error(request, "Data inválida.")
            return redirect("cartao_despesa_editar", pk=pk, despesa_id=despesa_id)

        # Guardar referência à fatura antiga
        fatura_antiga = despesa.fatura

        # Atualizar despesa
        despesa.descricao = descricao
        despesa.valor = valor
        despesa.data_prevista = data_prevista
        despesa.save()

        # Recalcular valor da fatura
        if fatura_antiga:
            atualizar_valor_fatura(fatura_antiga)

        messages.success(request, "Despesa atualizada com sucesso!")
        return redirect("cartao_despesas", pk=pk)


@method_decorator(login_required, name="dispatch")
class CartaoDespesaDeleteView(View):
    """Exclui uma despesa do cartão."""

    def post(self, request, pk, despesa_id):
        usuario = request.user
        cartao = get_object_or_404(CartaoCredito, pk=pk, usuario=usuario)
        despesa = get_object_or_404(
            Conta, id=despesa_id, cartao=cartao, usuario=usuario, eh_fatura_cartao=False
        )

        # Bloquear exclusão se a fatura já foi paga
        if not despesa_pode_ser_editada(despesa):
            messages.error(
                request, "Esta despesa não pode ser excluída pois a fatura já foi paga."
            )
            return redirect("cartao_despesas", pk=pk)

        fatura_id = despesa.fatura_id
        despesa.delete()
        messages.success(request, "Despesa excluída com sucesso!")

        # Recalcular fatura afetada
        if fatura_id:
            try:
                fatura_obj = Conta.objects.get(id=fatura_id)
                atualizar_valor_fatura(fatura_obj)
            except Conta.DoesNotExist:
                pass

        return redirect("cartao_despesas", pk=pk)


@method_decorator(login_required, name="dispatch")
class FaturaPagarView(View):
    """Marca uma fatura como paga."""

    def post(self, request, pk, fatura_id):
        from core.services.fatura_service import pagar_fatura, desfazer_pagamento_fatura

        usuario = request.user
        cartao = get_object_or_404(CartaoCredito, pk=pk, usuario=usuario)
        fatura = get_object_or_404(
            Conta, id=fatura_id, cartao=cartao, usuario=usuario, eh_fatura_cartao=True
        )

        acao = (request.POST.get("acao") or "pagar").strip()

        if acao == "desfazer":
            desfazer_pagamento_fatura(fatura)
            messages.success(request, "Pagamento da fatura desfeito!")
        else:
            pagar_fatura(fatura)
            messages.success(
                request, f"Fatura paga com sucesso! Valor: R$ {fatura.valor}"
            )

        return redirect("cartao_despesas", pk=pk)


@method_decorator(login_required, name="dispatch")
class FaturaPagarView(View):
    """Marca uma fatura como paga."""

    def post(self, request, pk, fatura_id):
        from core.services.fatura_service import pagar_fatura, desfazer_pagamento_fatura

        usuario = request.user
        cartao = get_object_or_404(CartaoCredito, pk=pk, usuario=usuario)
        fatura = get_object_or_404(
            Conta, id=fatura_id, cartao=cartao, usuario=usuario, eh_fatura_cartao=True
        )

        acao = (request.POST.get("acao") or "pagar").strip()

        if acao == "desfazer":
            desfazer_pagamento_fatura(fatura)
            messages.success(request, "Pagamento da fatura desfeito!")
        else:
            pagar_fatura(fatura)
            messages.success(
                request, f"Fatura paga com sucesso! Valor: R$ {fatura.valor}"
            )

        return redirect("cartao_despesas", pk=pk)
