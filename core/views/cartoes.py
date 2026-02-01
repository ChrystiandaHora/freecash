"""
Views para gerenciamento de Cartões de Crédito.
"""

from datetime import date, datetime, timedelta
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
    CategoriaCartao,
    Conta,
    Assinatura,
)
from core.services.fatura_service import (
    obter_ou_criar_fatura,
    atualizar_valor_fatura,
    despesa_pode_ser_editada,
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

    template_name = "cartoes.html"

    def get(self, request):
        usuario = request.user
        hoje = timezone.localdate()

        cartoes = CartaoCredito.objects.filter(usuario=usuario, ativo=True).order_by(
            "nome"
        )

        # Calcular gasto total de cada cartão no mês atual
        cartoes_com_gasto = []
        for cartao in cartoes:
            gasto_mes = Conta.objects.filter(
                usuario=usuario,
                cartao=cartao,
                tipo=Conta.TIPO_DESPESA,
                data_prevista__year=hoje.year,
                data_prevista__month=hoje.month,
            ).aggregate(total=Sum("valor"))["total"] or Decimal("0.00")

            cartoes_com_gasto.append(
                {
                    "cartao": cartao,
                    "gasto_mes": gasto_mes,
                    "limite_disponivel": (
                        cartao.limite - gasto_mes if cartao.limite else None
                    ),
                    "percentual_usado": (
                        (gasto_mes / cartao.limite * 100) if cartao.limite else None
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

    template_name = "cartao_form.html"

    def get(self, request):
        return render(
            request,
            self.template_name,
            {
                "modo": "create",
                "bandeiras": CartaoCredito.BANDEIRA_CHOICES,
            },
        )

    def post(self, request):
        usuario = request.user

        nome = (request.POST.get("nome") or "").strip()
        bandeira = (request.POST.get("bandeira") or "OUTRO").strip()
        ultimos_digitos = (request.POST.get("ultimos_digitos") or "").strip()[:4]
        limite_raw = (request.POST.get("limite") or "").strip()
        dia_fechamento = (request.POST.get("dia_fechamento") or "1").strip()
        dia_vencimento = (request.POST.get("dia_vencimento") or "10").strip()

        if not nome:
            messages.error(request, "O nome do cartão é obrigatório.")
            return redirect("cartao_novo")

        # Parse limite
        limite = None
        if limite_raw:
            try:
                limite_raw = (
                    limite_raw.replace(".", "").replace(",", ".")
                    if "," in limite_raw
                    else limite_raw
                )
                limite = Decimal(limite_raw).quantize(Decimal("0.01"))
            except (InvalidOperation, ValueError):
                messages.error(request, "Limite inválido.")
                return redirect("cartao_novo")

        # Dias
        try:
            dia_fechamento = max(1, min(31, int(dia_fechamento)))
            dia_vencimento = max(1, min(31, int(dia_vencimento)))
        except ValueError:
            dia_fechamento = 1
            dia_vencimento = 10

        CartaoCredito.objects.create(
            usuario=usuario,
            nome=nome,
            bandeira=bandeira,
            ultimos_digitos=ultimos_digitos,
            limite=limite,
            dia_fechamento=dia_fechamento,
            dia_vencimento=dia_vencimento,
        )

        messages.success(request, "Cartão cadastrado com sucesso!")
        return redirect("cartoes")


@method_decorator(login_required, name="dispatch")
class CartaoUpdateView(View):
    """Edita um cartão de crédito existente."""

    template_name = "cartao_form.html"

    def get(self, request, pk):
        usuario = request.user
        cartao = get_object_or_404(CartaoCredito, pk=pk, usuario=usuario)

        return render(
            request,
            self.template_name,
            {
                "modo": "edit",
                "cartao": cartao,
                "bandeiras": CartaoCredito.BANDEIRA_CHOICES,
            },
        )

    def post(self, request, pk):
        usuario = request.user
        cartao = get_object_or_404(CartaoCredito, pk=pk, usuario=usuario)

        nome = (request.POST.get("nome") or "").strip()
        bandeira = (request.POST.get("bandeira") or "OUTRO").strip()
        ultimos_digitos = (request.POST.get("ultimos_digitos") or "").strip()[:4]
        limite_raw = (request.POST.get("limite") or "").strip()
        dia_fechamento = (request.POST.get("dia_fechamento") or "1").strip()
        dia_vencimento = (request.POST.get("dia_vencimento") or "10").strip()

        if not nome:
            messages.error(request, "O nome do cartão é obrigatório.")
            return redirect("cartao_editar", pk=pk)

        # Parse limite
        limite = None
        if limite_raw:
            try:
                limite_raw = (
                    limite_raw.replace(".", "").replace(",", ".")
                    if "," in limite_raw
                    else limite_raw
                )
                limite = Decimal(limite_raw).quantize(Decimal("0.01"))
            except (InvalidOperation, ValueError):
                messages.error(request, "Limite inválido.")
                return redirect("cartao_editar", pk=pk)

        # Dias
        try:
            dia_fechamento = max(1, min(31, int(dia_fechamento)))
            dia_vencimento = max(1, min(31, int(dia_vencimento)))
        except ValueError:
            dia_fechamento = 1
            dia_vencimento = 10

        cartao.nome = nome
        cartao.bandeira = bandeira
        cartao.ultimos_digitos = ultimos_digitos
        cartao.limite = limite
        cartao.dia_fechamento = dia_fechamento
        cartao.dia_vencimento = dia_vencimento
        cartao.save()

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

    template_name = "cartao_despesas.html"

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
            .select_related("categoria_cartao")
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

        categorias_cartao = CategoriaCartao.objects.all()
        assinaturas = Assinatura.objects.filter(
            usuario=usuario, cartao=cartao, ativa=True
        ).order_by("dia_vencimento")

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
                "categorias_cartao": categorias_cartao,
                "fatura": fatura,
                "assinaturas": assinaturas,
            },
        )


@method_decorator(login_required, name="dispatch")
class CartaoDespesaCreateView(View):
    """Cria uma nova despesa no cartão, com suporte a parcelamento."""

    def post(self, request, pk):
        import calendar

        usuario = request.user
        cartao = get_object_or_404(CartaoCredito, pk=pk, usuario=usuario)

        descricao = (request.POST.get("descricao") or "").strip()
        valor_raw = (request.POST.get("valor") or "").strip()
        data_raw = (
            request.POST.get("data_compra") or request.POST.get("data_prevista") or ""
        ).strip()
        categoria_cartao_id = (request.POST.get("categoria_cartao") or "").strip()

        # Parcelamento
        parcelado = (request.POST.get("parcelado") or "") == "1"
        numero_parcelas_raw = (request.POST.get("numero_parcelas") or "2").strip()

        # Recorrente (Assinatura)
        recorrente = request.POST.get("recorrente") == "on"

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

        # Categoria MCC
        categoria_cartao = None
        if categoria_cartao_id.isdigit():
            categoria_cartao = CategoriaCartao.objects.filter(
                id=int(categoria_cartao_id)
            ).first()

        def add_months(d: date, months: int) -> date:
            y = d.year + (d.month - 1 + months) // 12
            m = (d.month - 1 + months) % 12 + 1
            last_day = calendar.monthrange(y, m)[1]
            day = min(d.day, last_day)
            return date(y, m, day)

        def calcular_vencimento_fatura(
            data_compra: date, dia_fechamento: int, dia_vencimento: int
        ) -> date:
            """
            Calcula a data de vencimento da fatura baseado na data da compra.

            Lógica:
            1. Primeiro, determina a qual ciclo de fechamento a compra pertence:
               - Se comprou ATÉ o dia de fechamento: pertence ao fechamento do mês atual
               - Se comprou DEPOIS do dia de fechamento: pertence ao fechamento do próximo mês

            2. Depois, calcula quando essa fatura vence:
               - Se dia_vencimento > dia_fechamento: vence no MESMO mês do fechamento
               - Se dia_vencimento <= dia_fechamento: vence no MÊS SEGUINTE ao fechamento

            Exemplo 1 (fecha 10, vence 15):
            - Compra 05/01: fechamento Jan → vence 15/01
            - Compra 15/01: fechamento Fev → vence 15/02

            Exemplo 2 (fecha 20, vence 5):
            - Compra 05/01: fechamento Jan → vence 05/02
            - Compra 25/01: fechamento Fev → vence 05/03
            """
            ano = data_compra.year
            mes = data_compra.month
            dia = data_compra.day

            # Passo 1: Determinar mês de fechamento
            if dia <= dia_fechamento:
                # Pertence ao fechamento deste mês
                mes_fechamento = mes
                ano_fechamento = ano
            else:
                # Pertence ao fechamento do próximo mês
                if mes == 12:
                    mes_fechamento = 1
                    ano_fechamento = ano + 1
                else:
                    mes_fechamento = mes + 1
                    ano_fechamento = ano

            # Passo 2: Calcular data de vencimento
            if dia_vencimento > dia_fechamento:
                # Vencimento é no mesmo mês do fechamento
                mes_vencimento = mes_fechamento
                ano_vencimento = ano_fechamento
            else:
                # Vencimento é no mês seguinte ao fechamento
                if mes_fechamento == 12:
                    mes_vencimento = 1
                    ano_vencimento = ano_fechamento + 1
                else:
                    mes_vencimento = mes_fechamento + 1
                    ano_vencimento = ano_fechamento

            # Ajustar dia de vencimento se o mês não tiver tantos dias
            ultimo_dia_mes = calendar.monthrange(ano_vencimento, mes_vencimento)[1]
            dia_venc = min(dia_vencimento, ultimo_dia_mes)

            return date(ano_vencimento, mes_vencimento, dia_venc)

        def cents_to_decimal(cents: int) -> Decimal:
            return (Decimal(cents) / Decimal(100)).quantize(Decimal("0.01"))

        # Calcular data de vencimento da primeira parcela
        data_vencimento = calcular_vencimento_fatura(
            data_compra, cartao.dia_fechamento, cartao.dia_vencimento
        )

        # Se parcelado
        if parcelado:
            try:
                n = int(numero_parcelas_raw)
            except ValueError:
                n = 2

            if n < 2 or n > 24:
                messages.error(request, "Número de parcelas deve ser entre 2 e 24.")
                return redirect("cartao_despesas", pk=pk)

            total_cents = int((valor_total * 100).to_integral_value())
            base = total_cents // n
            resto = total_cents % n

            from django.db import transaction

            with transaction.atomic():
                # Coletar todas as faturas que precisam ser atualizadas
                faturas_afetadas = set()

                cents_1 = base + (1 if 1 <= resto else 0)

                # Obter fatura para a primeira parcela
                fatura_1 = obter_ou_criar_fatura(usuario, cartao, data_vencimento)
                faturas_afetadas.add(fatura_1.id)

                primeira = Conta.objects.create(
                    usuario=usuario,
                    tipo=Conta.TIPO_DESPESA,
                    descricao=descricao,
                    valor=cents_to_decimal(cents_1),
                    data_compra=data_compra,
                    data_prevista=data_vencimento,
                    cartao=cartao,
                    categoria_cartao=categoria_cartao,
                    eh_parcelada=True,
                    parcela_numero=1,
                    parcela_total=n,
                    grupo_parcelamento=None,
                    fatura=fatura_1,
                )

                gid = primeira.id
                primeira.grupo_parcelamento = gid
                primeira.save(update_fields=["grupo_parcelamento", "atualizada_em"])

                # Criar demais parcelas
                for i in range(2, n + 1):
                    cents = base + (1 if i <= resto else 0)
                    # Cada parcela vence um mês depois da anterior
                    venc = add_months(data_vencimento, i - 1)

                    # Obter fatura para esta parcela
                    fatura_i = obter_ou_criar_fatura(usuario, cartao, venc)
                    faturas_afetadas.add(fatura_i.id)

                    Conta.objects.create(
                        usuario=usuario,
                        tipo=Conta.TIPO_DESPESA,
                        descricao=descricao,
                        valor=cents_to_decimal(cents),
                        data_compra=data_compra,
                        data_prevista=venc,
                        cartao=cartao,
                        categoria_cartao=categoria_cartao,
                        eh_parcelada=True,
                        parcela_numero=i,
                        parcela_total=n,
                        grupo_parcelamento=gid,
                        fatura=fatura_i,
                    )

                # Atualizar todas as faturas afetadas
                for fatura_id in faturas_afetadas:
                    fatura_obj = Conta.objects.get(id=fatura_id)
                    atualizar_valor_fatura(fatura_obj)

            messages.success(request, f"Compra parcelada em {n}x adicionada ao cartão!")
            return redirect("cartao_despesas", pk=pk)

        # Obter ou criar a fatura para este cartão/vencimento
        fatura = obter_ou_criar_fatura(usuario, cartao, data_vencimento)

        # Compra normal (sem parcelamento)
        Conta.objects.create(
            usuario=usuario,
            tipo=Conta.TIPO_DESPESA,
            descricao=descricao,
            valor=valor_total,
            data_compra=data_compra,
            data_prevista=data_vencimento,
            cartao=cartao,
            categoria_cartao=categoria_cartao,
            fatura=fatura,
        )

        # Atualizar valor total da fatura
        atualizar_valor_fatura(fatura)

        messages.success(request, "Despesa adicionada ao cartão!")

        if recorrente:
            try:
                cat_geral = None
                if categoria_cartao:
                    cat_geral = Categoria.objects.filter(
                        usuario=usuario, nome__iexact=categoria_cartao.nome
                    ).first()

                Assinatura.objects.create(
                    usuario=usuario,
                    descricao=descricao,
                    valor=valor_total,
                    tipo=Assinatura.TIPO_DESPESA,
                    dia_vencimento=data_compra.day,
                    categoria=cat_geral,
                    ativa=True,
                    proxima_geracao=data_compra + relativedelta(months=1),
                    cartao=cartao,
                )
                messages.info(request, "Assinatura recorrente criada com sucesso!")
            except Exception as e:
                messages.warning(request, f"Erro ao criar assinatura: {e}")

        return redirect("cartao_despesas", pk=pk)


@method_decorator(login_required, name="dispatch")
class CartaoDespesaUpdateView(View):
    """Edita uma despesa do cartão."""

    template_name = "cartao_despesa_form.html"

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

        categorias_cartao = CategoriaCartao.objects.all()

        return render(
            request,
            self.template_name,
            {
                "cartao": cartao,
                "despesa": despesa,
                "categorias_cartao": categorias_cartao,
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
        categoria_cartao_id = (request.POST.get("categoria_cartao") or "").strip()

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

        # Categoria MCC
        categoria_cartao = None
        if categoria_cartao_id.isdigit():
            categoria_cartao = CategoriaCartao.objects.filter(
                id=int(categoria_cartao_id)
            ).first()

        # Guardar referência à fatura antiga
        fatura_antiga = despesa.fatura

        # Atualizar despesa
        despesa.descricao = descricao
        despesa.valor = valor
        despesa.data_prevista = data_prevista
        despesa.categoria_cartao = categoria_cartao
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

        # Coletar faturas afetadas antes de excluir
        faturas_para_atualizar = set()

        # Se for parcelada, perguntar se quer apagar todas
        apagar_grupo = (request.POST.get("apagar_grupo") or "").strip() == "1"

        if apagar_grupo and despesa.eh_parcelada and despesa.grupo_parcelamento:
            # Coletar faturas de todas as parcelas
            parcelas = Conta.objects.filter(
                usuario=usuario,
                cartao=cartao,
                eh_parcelada=True,
                grupo_parcelamento=despesa.grupo_parcelamento,
            )
            for parcela in parcelas:
                if parcela.fatura_id:
                    faturas_para_atualizar.add(parcela.fatura_id)

            parcelas.delete()
            messages.success(request, "Todas as parcelas foram excluídas!")
        else:
            if despesa.fatura_id:
                faturas_para_atualizar.add(despesa.fatura_id)
            despesa.delete()
            messages.success(request, "Despesa excluída com sucesso!")

        # Recalcular todas as faturas afetadas
        for fatura_id in faturas_para_atualizar:
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
