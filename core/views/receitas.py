import calendar
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
from django.db import transaction

from core.models import Conta, Categoria, FormaPagamento


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
    template_name = "receitas.html"

    def get(self, request):
        usuario = request.user

        q = (request.GET.get("q") or "").strip()
        ano = (request.GET.get("ano") or "").strip()
        mes = (request.GET.get("mes") or "").strip()
        categoria_id = (request.GET.get("categoria") or "").strip()
        forma_id = (request.GET.get("forma_pagamento") or "").strip()

        qs = Conta.objects.filter(
            usuario=usuario,
            tipo=Conta.TIPO_RECEITA,
            transacao_realizada=True,
        ).select_related("categoria", "forma_pagamento")

        if ano.isdigit():
            qs = qs.filter(data_realizacao__year=int(ano))
        if mes.isdigit():
            qs = qs.filter(data_realizacao__month=int(mes))
        if categoria_id.isdigit():
            qs = qs.filter(categoria_id=int(categoria_id))
        if forma_id.isdigit():
            qs = qs.filter(forma_pagamento_id=int(forma_id))
        if q:
            qs = qs.filter(descricao__icontains=q)

        qs = qs.order_by("data_realizacao", "id")

        categorias = Categoria.objects.filter(
            usuario=usuario,
            tipo=Categoria.TIPO_RECEITA,
        ).order_by("nome")
        formas = FormaPagamento.objects.filter(usuario=usuario, ativa=True).order_by(
            "nome"
        )

        hoje = timezone.localdate()
        ano_ref = int(ano) if ano.isdigit() else hoje.year
        mes_ref = int(mes) if mes.isdigit() else hoje.month

        # opção A (como você tinha): total do mês/ano ref, independente dos filtros
        total_periodo = (
            Conta.objects.filter(
                usuario=usuario,
                tipo=Conta.TIPO_RECEITA,
                transacao_realizada=True,
                data_realizacao__year=ano_ref,
                data_realizacao__month=mes_ref,
            ).aggregate(total=Sum("valor"))["total"]
            or 0
        )

        # opção B (se preferir): total considerando exatamente os filtros aplicados
        # total_periodo = qs.aggregate(total=Sum("valor"))["total"] or 0

        anos = list(range(hoje.year - 5, hoje.year + 1))
        anos.reverse()
        meses = list(range(1, 13))

        per_page = clamp_per_page(request.GET.get("per_page"), default=4, max_v=200)
        paginator = Paginator(qs, per_page)
        page_obj = paginator.get_page(request.GET.get("page") or 1)

        total_count = paginator.count  # mais barato/consistente do que qs.count()

        params = request.GET.copy()
        params.pop("page", None)
        querystring = params.urlencode()

        contexto = {
            "page_obj": page_obj,
            "receitas": page_obj.object_list,
            "per_page": per_page,
            "total_count": total_count,
            "querystring": querystring,
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


@method_decorator(login_required, name="dispatch")
class ReceitaCreateView(View):
    template_name = "conta_form.html"

    def get(self, request):
        usuario = request.user
        categorias = Categoria.objects.filter(
            usuario=usuario,
            tipo=Categoria.TIPO_RECEITA,
        ).order_by("nome")
        formas = FormaPagamento.objects.filter(usuario=usuario, ativa=True).order_by(
            "nome"
        )

        return render(
            request,
            self.template_name,
            {
                "categorias": categorias,
                "formas": formas,
                "modo": "create",
                "titulo": "Nova Receita",
                # Passamos um objeto vazio ou dicionario para evitar erro no template se ele tentar acessar conta
                "conta": None,
                "is_receita": True,  # Flag util se precisarmos customizar o texto no template
            },
        )

    def post(self, request):
        usuario = request.user

        descricao = (request.POST.get("descricao") or "").strip()
        valor_raw = (request.POST.get("valor") or "").strip()
        data_input = request.POST.get("data_prevista") or ""

        # Campos de recorrência (Multiplicar)
        multiplicar = (request.POST.get("multiplicar") or "").strip() == "1"
        numero_multiplicacoes_raw = (
            request.POST.get("numero_multiplicacoes") or ""
        ).strip()

        # Campos de Parcelamento
        parcelado = (request.POST.get("parcelado") or "").strip() == "1"
        numero_parcelas_raw = (request.POST.get("numero_parcelas") or "").strip()

        if parcelado and multiplicar:
            messages.error(
                request, "Escolha apenas uma opção: parcelar ou multiplicar."
            )
            return redirect("receita_nova")

        if not descricao or not valor_raw or not data_input:
            messages.error(request, "Preencha todos os campos obrigatórios.")
            return redirect("receita_nova")

        try:
            valor_norm = (
                valor_raw.replace(".", "").replace(",", ".")
                if "," in valor_raw
                else valor_raw
            )
            valor = Decimal(valor_norm)
        except (InvalidOperation, TypeError):
            messages.error(request, "Valor inválido.")
            return redirect("receita_nova")

        # Se for receita, data_prevista = data_realizacao (pois já entra como realizado)
        data_date = parse_date_flexible(data_input)
        if not data_date:
            messages.error(request, "Data inválida.")
            return redirect("receita_nova")

        categoria_id = (request.POST.get("categoria") or "").strip()
        forma_id = (request.POST.get("forma_pagamento") or "").strip()

        categoria = (
            Categoria.objects.filter(usuario=usuario, id=categoria_id).first()
            if categoria_id.isdigit()
            else None
        )
        forma_pagamento = (
            FormaPagamento.objects.filter(usuario=usuario, id=forma_id).first()
            if forma_id.isdigit()
            else None
        )

        def add_months(d: date, months: int) -> date:
            y = d.year + (d.month - 1 + months) // 12
            m = (d.month - 1 + months) % 12 + 1
            last_day = calendar.monthrange(y, m)[1]
            day = min(d.day, last_day)
            return date(y, m, day)

        # Lógica de Multiplicar
        if multiplicar:
            try:
                n = int(numero_multiplicacoes_raw or "2")
            except ValueError:
                n = 2

            if n < 2 or n > 12:
                messages.error(request, "Quantidade deve ser entre 2 e 12.")
                return redirect("receita_nova")

            with transaction.atomic():
                receitas = []
                for i in range(1, n + 1):
                    # Calcula data para cada mês
                    venc = add_months(data_date, i - 1)

                    receitas.append(
                        Conta(
                            usuario=usuario,
                            tipo=Conta.TIPO_RECEITA,
                            descricao=descricao,
                            valor=valor,
                            data_prevista=venc,
                            transacao_realizada=True,
                            data_realizacao=venc,
                            categoria=categoria,
                            forma_pagamento=forma_pagamento,
                        )
                    )
                Conta.objects.bulk_create(receitas)

            messages.success(request, f"Receita registrada {n} vezes.")
            return redirect("receitas")

        def cents_to_decimal(cents: int) -> Decimal:
            return (Decimal(cents) / Decimal(100)).quantize(Decimal("0.01"))

        # Lógica de Parcelar
        if parcelado:
            try:
                n = int(numero_parcelas_raw or "2")
            except ValueError:
                n = 2

            if n < 2 or n > 12:
                messages.error(request, "Número de parcelas deve ser entre 2 e 12.")
                return redirect("receita_nova")

            total_cents = int((valor * 100).to_integral_value())
            base = total_cents // n
            resto = total_cents % n

            with transaction.atomic():
                cents_1 = base + (1 if 1 <= resto else 0)

                # Cria a primeira para gerar o ID do grupo
                primeira = Conta.objects.create(
                    usuario=usuario,
                    tipo=Conta.TIPO_RECEITA,
                    descricao=descricao,
                    valor=cents_to_decimal(cents_1),
                    data_prevista=data_date,
                    transacao_realizada=True,
                    data_realizacao=data_date,
                    categoria=categoria,
                    forma_pagamento=forma_pagamento,
                    eh_parcelada=True,
                    parcela_numero=1,
                    parcela_total=n,
                    grupo_parcelamento=None,
                )

                gid = primeira.id
                primeira.grupo_parcelamento = gid
                primeira.save(update_fields=["grupo_parcelamento"])

                receitas = []
                for i in range(2, n + 1):
                    cents = base + (1 if i <= resto else 0)
                    venc = add_months(data_date, i - 1)

                    receitas.append(
                        Conta(
                            usuario=usuario,
                            tipo=Conta.TIPO_RECEITA,
                            descricao=descricao,
                            valor=cents_to_decimal(cents),
                            data_prevista=venc,
                            transacao_realizada=True,
                            data_realizacao=venc,
                            categoria=categoria,
                            forma_pagamento=forma_pagamento,
                            eh_parcelada=True,
                            parcela_numero=i,
                            parcela_total=n,
                            grupo_parcelamento=gid,
                        )
                    )
                if receitas:
                    Conta.objects.bulk_create(receitas)

            messages.success(request, f"Receita registrada em {n} parcelas.")
            return redirect("receitas")

        # Criação Unitária (Padrão)
        Conta.objects.create(
            usuario=usuario,
            tipo=Conta.TIPO_RECEITA,
            descricao=descricao,
            valor=valor,
            data_prevista=data_input,
            transacao_realizada=True,
            data_realizacao=data_input,
            categoria=categoria,
            forma_pagamento=forma_pagamento,
            eh_parcelada=False,
            parcela_numero=None,
            parcela_total=None,
            grupo_parcelamento=None,
        )

        messages.success(request, "Receita registrada!")
        return redirect("receitas")


@method_decorator(login_required, name="dispatch")
class ReceitaUpdateView(View):
    template_name = "conta_form.html"

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

        return render(
            request,
            self.template_name,
            {
                "conta": conta,
                "categorias": categorias,
                "formas": formas,
                "modo": "edit",
                "titulo": "Editar Receita",
            },
        )

    def post(self, request, pk):
        usuario = request.user
        conta = get_object_or_404(
            Conta, id=pk, usuario=usuario, tipo=Conta.TIPO_RECEITA
        )

        descricao = (request.POST.get("descricao") or "").strip()
        valor_raw = (request.POST.get("valor") or "").strip()

        # Tenta pegar data de data_prevista (padrao form) ou data_realizacao
        data_input = (
            request.POST.get("data_prevista")
            or request.POST.get("data_realizacao")
            or ""
        )

        try:
            valor_norm = (
                valor_raw.replace(".", "").replace(",", ".")
                if "," in valor_raw
                else valor_raw
            )
            valor = Decimal(valor_norm)
        except (InvalidOperation, TypeError):
            messages.error(request, "Valor inválido.")
            return redirect("receita_editar", pk=conta.id)

        categoria_id = (request.POST.get("categoria") or "").strip()
        forma_id = (request.POST.get("forma_pagamento") or "").strip()

        categoria = (
            Categoria.objects.filter(usuario=usuario, id=categoria_id).first()
            if categoria_id.isdigit()
            else None
        )
        forma_pagamento = (
            FormaPagamento.objects.filter(usuario=usuario, id=forma_id).first()
            if forma_id.isdigit()
            else None
        )

        # Atualiza
        conta.descricao = descricao
        conta.valor = valor

        # Para receitas, usamos data_prevista = data_realizacao
        if data_input:
            conta.data_prevista = data_input
            conta.data_realizacao = data_input

        conta.transacao_realizada = True
        conta.categoria = categoria
        conta.forma_pagamento = forma_pagamento
        conta.save()

        messages.success(request, "Receita atualizada.")
        return redirect("receitas")
