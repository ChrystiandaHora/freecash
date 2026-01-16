import calendar
from datetime import date
from decimal import Decimal, InvalidOperation

from django.views import View
from django.shortcuts import get_object_or_404, render, redirect
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.contrib import messages
from django.core.paginator import Paginator
from django.utils import timezone
from django.db import transaction

from core.models import Conta, Categoria, FormaPagamento


def clamp_per_page(raw, default=5, min_v=5, max_v=50):
    try:
        v = int(raw)
    except (TypeError, ValueError):
        v = default
    return max(min_v, min(v, max_v))


@method_decorator(login_required, name="dispatch")
class ContasPagarView(View):
    template_name = "contas.html"

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

        # Filtros
        q = (request.GET.get("q") or "").strip()
        ano = (request.GET.get("ano") or "").strip()
        mes = (request.GET.get("mes") or "").strip()
        categoria_id = (request.GET.get("categoria") or "").strip()
        forma_id = (request.GET.get("forma_pagamento") or "").strip()

        # Base filters
        if ano.isdigit():
            qs_pendentes = qs_pendentes.filter(data_prevista__year=int(ano))
            qs_pagas = qs_pagas.filter(data_realizacao__year=int(ano))
        if mes.isdigit():
            qs_pendentes = qs_pendentes.filter(data_prevista__month=int(mes))
            qs_pagas = qs_pagas.filter(data_realizacao__month=int(mes))
        if categoria_id.isdigit():
            qs_pendentes = qs_pendentes.filter(categoria_id=int(categoria_id))
            qs_pagas = qs_pagas.filter(categoria_id=int(categoria_id))
        if forma_id.isdigit():
            qs_pendentes = qs_pendentes.filter(forma_pagamento_id=int(forma_id))
            qs_pagas = qs_pagas.filter(forma_pagamento_id=int(forma_id))
        if q:
            qs_pendentes = qs_pendentes.filter(descricao__icontains=q)
            qs_pagas = qs_pagas.filter(descricao__icontains=q)

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

        descricao = (request.POST.get("descricao") or "").strip()
        valor_raw = (request.POST.get("valor") or "").strip()
        data_prevista_raw = (request.POST.get("data_prevista") or "").strip()
        forma_pagamento_id = (request.POST.get("forma_pagamento") or "").strip()

        parcelado = (request.POST.get("parcelado") or "").strip() == "1"
        numero_parcelas_raw = (request.POST.get("numero_parcelas") or "").strip()

        multiplicar = (request.POST.get("multiplicar") or "").strip() == "1"
        numero_multiplicacoes_raw = (
            request.POST.get("numero_multiplicacoes") or ""
        ).strip()

        if not descricao or not valor_raw or not data_prevista_raw:
            messages.error(request, "Preencha todos os campos obrigatórios.")
            return redirect("contas_pagar")

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
            return redirect("contas_pagar")

        if valor_total <= 0:
            messages.error(request, "O valor precisa ser maior que zero.")
            return redirect("contas_pagar")

        # Data
        try:
            data_prevista = date.fromisoformat(data_prevista_raw)
        except ValueError:
            messages.error(request, "Data de vencimento inválida.")
            return redirect("contas_pagar")

        # Não permitir as duas opções ao mesmo tempo
        if parcelado and multiplicar:
            messages.error(
                request, "Escolha apenas uma opção: parcelar ou multiplicar."
            )
            return redirect("contas_pagar")

        # FK forma pagamento
        forma_pagamento = (
            FormaPagamento.objects.filter(
                id=forma_pagamento_id, usuario=usuario
            ).first()
            if forma_pagamento_id.isdigit()
            else None
        )

        categoria_padrao = Categoria.objects.filter(
            usuario=usuario, tipo=Categoria.TIPO_DESPESA
        ).first()

        def add_months(d: date, months: int) -> date:
            y = d.year + (d.month - 1 + months) // 12
            m = (d.month - 1 + months) % 12 + 1
            last_day = calendar.monthrange(y, m)[1]
            day = min(d.day, last_day)
            return date(y, m, day)

        def cents_to_decimal(cents: int) -> Decimal:
            return (Decimal(cents) / Decimal(100)).quantize(Decimal("0.01"))

        # 1) MULTIPLICAR (criar N contas iguais, vencimentos mensais)
        if multiplicar:
            try:
                n = int(numero_multiplicacoes_raw or "2")
            except ValueError:
                n = 2

            if n < 2 or n > 12:
                messages.error(request, "Quantidade deve ser entre 2 e 12.")
                return redirect("contas_pagar")

            with transaction.atomic():
                contas = []
                for i in range(1, n + 1):
                    venc = add_months(data_prevista, i - 1)
                    contas.append(
                        Conta(
                            usuario=usuario,
                            tipo=Conta.TIPO_DESPESA,
                            descricao=descricao,
                            valor=valor_total,
                            data_prevista=venc,
                            transacao_realizada=False,
                            data_realizacao=None,
                            categoria=categoria_padrao,
                            forma_pagamento=forma_pagamento,
                            # não é parcelado
                            eh_parcelada=False,
                            parcela_numero=None,
                            parcela_total=None,
                            grupo_parcelamento=None,
                        )
                    )
                Conta.objects.bulk_create(contas)

            messages.success(request, f"Conta registrada {n} vezes.")
            return redirect("contas_pagar")

        # 2) PARCELAR
        if parcelado:
            try:
                n = int(numero_parcelas_raw or "2")
            except ValueError:
                n = 2

            if n < 2 or n > 12:
                messages.error(request, "Número de parcelas deve ser entre 2 e 12.")
                return redirect("contas_pagar")

            total_cents = int((valor_total * 100).to_integral_value())
            base = total_cents // n
            resto = total_cents % n

            with transaction.atomic():
                cents_1 = base + (1 if 1 <= resto else 0)

                primeira = Conta.objects.create(
                    usuario=usuario,
                    tipo=Conta.TIPO_DESPESA,
                    descricao=descricao,
                    valor=cents_to_decimal(cents_1),
                    data_prevista=data_prevista,
                    transacao_realizada=False,
                    data_realizacao=None,
                    categoria=categoria_padrao,
                    forma_pagamento=forma_pagamento,
                    eh_parcelada=True,
                    parcela_numero=1,
                    parcela_total=n,
                    grupo_parcelamento=None,
                )

                gid = primeira.id
                primeira.grupo_parcelamento = gid
                primeira.save(update_fields=["grupo_parcelamento", "atualizada_em"])

                contas = []
                for i in range(2, n + 1):
                    cents = base + (1 if i <= resto else 0)
                    venc = add_months(data_prevista, i - 1)

                    contas.append(
                        Conta(
                            usuario=usuario,
                            tipo=Conta.TIPO_DESPESA,
                            descricao=descricao,
                            valor=cents_to_decimal(cents),
                            data_prevista=venc,
                            transacao_realizada=False,
                            data_realizacao=None,
                            categoria=categoria_padrao,
                            forma_pagamento=forma_pagamento,
                            eh_parcelada=True,
                            parcela_numero=i,
                            parcela_total=n,
                            grupo_parcelamento=gid,
                        )
                    )

                if contas:
                    Conta.objects.bulk_create(contas)

            messages.success(request, f"Conta registrada em {n} parcelas.")
            return redirect("contas_pagar")

        # 3) NORMAL
        Conta.objects.create(
            usuario=usuario,
            tipo=Conta.TIPO_DESPESA,
            descricao=descricao,
            valor=valor_total,
            data_prevista=data_prevista,
            transacao_realizada=False,
            data_realizacao=None,
            categoria=categoria_padrao,
            forma_pagamento=forma_pagamento,
            eh_parcelada=False,
            parcela_numero=None,
            parcela_total=None,
            grupo_parcelamento=None,
        )

        messages.success(request, "Conta registrada com sucesso.")
        return redirect("contas_pagar")


@method_decorator(login_required, name="dispatch")
class ContaCreateView(View):
    template_name = "conta_form.html"

    def get(self, request):
        usuario = request.user
        categorias = Categoria.objects.filter(
            usuario=usuario, tipo=Categoria.TIPO_DESPESA
        ).order_by("nome")
        formas = FormaPagamento.objects.filter(usuario=usuario).order_by("nome")
        return render(
            request,
            self.template_name,
            {"categorias": categorias, "formas": formas, "modo": "create"},
        )

    def post(self, request):
        # aqui você reutiliza exatamente o corpo do seu CadastrarContaPagarView.post
        return CadastrarContaPagarView().post(request)


@method_decorator(login_required, name="dispatch")
class ContaUpdateView(View):
    template_name = "conta_form.html"

    def get(self, request, conta_id):
        usuario = request.user
        conta = get_object_or_404(Conta, id=conta_id, usuario=usuario)

        categorias = Categoria.objects.filter(usuario=usuario).order_by("nome")
        formas = FormaPagamento.objects.filter(usuario=usuario).order_by("nome")

        return render(
            request,
            self.template_name,
            {
                "conta": conta,
                "categorias": categorias,
                "formas": formas,
                "modo": "edit",
            },
        )

    def post(self, request, conta_id):
        usuario = request.user
        conta = get_object_or_404(Conta, id=conta_id, usuario=usuario)

        aplicar_grupo = (request.POST.get("aplicar_grupo") or "").strip() == "1"

        descricao = (request.POST.get("descricao") or "").strip()

        # valor
        valor_raw = (request.POST.get("valor") or "").strip()
        try:
            valor_raw = (
                valor_raw.replace(".", "").replace(",", ".")
                if "," in valor_raw
                else valor_raw
            )
            valor = Decimal(valor_raw).quantize(Decimal("0.01"))
        except (InvalidOperation, ValueError):
            messages.error(request, "Valor inválido.")
            return redirect("conta_editar", conta_id=conta.id)

        if valor <= 0:
            messages.error(request, "O valor precisa ser maior que zero.")
            return redirect("conta_editar", conta_id=conta.id)

        # data prevista
        data_prevista_raw = (request.POST.get("data_prevista") or "").strip()
        try:
            data_prevista = date.fromisoformat(data_prevista_raw)
        except ValueError:
            messages.error(request, "Data de vencimento inválida.")
            return redirect("conta_editar", conta_id=conta.id)

        # categoria
        cat_id = (request.POST.get("categoria") or "").strip()
        categoria = (
            Categoria.objects.filter(id=cat_id, usuario=usuario).first()
            if cat_id.isdigit()
            else None
        )

        # forma de pagamento
        forma_id = (request.POST.get("forma_pagamento") or "").strip()
        forma_pagamento = (
            FormaPagamento.objects.filter(id=forma_id, usuario=usuario).first()
            if forma_id.isdigit()
            else None
        )

        # Se marcou aplicar no grupo, e a conta é parcelada, atualiza o grupo inteiro
        if aplicar_grupo and conta.eh_parcelada and conta.grupo_parcelamento:
            gid = conta.grupo_parcelamento

            # group edit seguro: só campos compartilháveis
            Conta.objects.filter(usuario=usuario, grupo_parcelamento=gid).update(
                descricao=descricao,
                categoria=categoria,
                forma_pagamento=forma_pagamento,
            )

            # individual edit: mantém o resto só para a parcela atual
            conta.valor = valor
            conta.data_prevista = data_prevista
            conta.save(update_fields=["valor", "data_prevista", "atualizada_em"])

            messages.success(
                request,
                "Grupo atualizado (descrição, categoria e forma). Esta parcela teve valor e vencimento atualizados individualmente.",
            )
            return redirect("contas_pagar")

        # Edição individual normal
        conta.descricao = descricao
        conta.valor = valor
        conta.data_prevista = data_prevista
        conta.categoria = categoria
        conta.forma_pagamento = forma_pagamento
        conta.save()

        messages.success(request, "Conta atualizada com sucesso.")
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
        conta.save(
            update_fields=["transacao_realizada", "data_realizacao", "atualizada_em"]
        )

        messages.success(request, "Conta marcada como paga com sucesso.")
        return redirect("contas_pagar")
