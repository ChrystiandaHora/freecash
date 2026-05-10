"""
Views para cadastro em lote de Contas e Receitas.
"""

from datetime import datetime
from decimal import Decimal, InvalidOperation

from django.views import View
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.contrib import messages
from django.db import transaction

from core.models import Conta, Categoria


def parse_date_flexible(date_str: str):
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
class ContaLoteCreateView(View):
    """View para cadastro em lote de despesas."""

    template_name = "core/financeiro/conta_lote_form.html"

    def get(self, request):
        usuario = request.user
        quantidade = int(request.GET.get("qtd", 5))

        # Limitar entre 1 e 20
        quantidade = max(1, min(quantidade, 20))

        return render(
            request,
            self.template_name,
            {
                "tipo": "despesa",
                "titulo": "Cadastro em Lote - Contas",
                "subtitulo": "Registre várias despesas de uma só vez",
                "quantidade": quantidade,
                "linhas": range(quantidade),
                "url_voltar": "contas_pagar",
            },
        )

    def post(self, request):
        usuario = request.user

        # Coletar dados do formulário
        descricoes = request.POST.getlist("descricao[]")
        valores = request.POST.getlist("valor[]")
        datas = request.POST.getlist("data[]")
        todas_pagas = request.POST.get("todas_pagas") == "on"

        # Buscar categoria padrão de despesa
        default_cat = Categoria.objects.filter(
            usuario=usuario, tipo=Categoria.TIPO_DESPESA, is_default=True
        ).first()

        # Validar e preparar lançamentos
        contas_para_criar = []
        erros = []

        for i, (desc, val, dt) in enumerate(
            zip(descricoes, valores, datas), 1
        ):
            desc = desc.strip()
            val = val.strip()
            dt = dt.strip()

            # Pular linhas vazias
            if not desc and not val and not dt:
                continue

            # Validar campos obrigatórios
            if not desc:
                erros.append(f"Linha {i}: Descrição é obrigatória")
                continue
            if not val:
                erros.append(f"Linha {i}: Valor é obrigatório")
                continue
            if not dt:
                erros.append(f"Linha {i}: Data é obrigatória")
                continue

            # Parsear valor
            try:
                val_norm = val.replace(".", "").replace(",", ".") if "," in val else val
                valor = Decimal(val_norm).quantize(Decimal("0.01"))
                if valor <= 0:
                    erros.append(f"Linha {i}: Valor deve ser maior que zero")
                    continue
            except (InvalidOperation, ValueError):
                erros.append(f"Linha {i}: Valor inválido")
                continue

            # Parsear data
            data_parsed = parse_date_flexible(dt)
            if not data_parsed:
                erros.append(f"Linha {i}: Data inválida")
                continue

            contas_para_criar.append(
                Conta(
                    usuario=usuario,
                    tipo=Conta.TIPO_DESPESA,
                    descricao=desc,
                    valor=valor,
                    data_prevista=data_parsed,
                    categoria=default_cat,
                    transacao_realizada=todas_pagas,
                    data_realizacao=data_parsed if todas_pagas else None,
                )
            )

        if erros:
            for erro in erros:
                messages.error(request, erro)
            return redirect("conta_lote")

        if not contas_para_criar:
            messages.warning(request, "Nenhum lançamento preenchido.")
            return redirect("conta_lote")

        # Criar em lote
        with transaction.atomic():
            Conta.objects.bulk_create(contas_para_criar)

        messages.success(
            request, f"{len(contas_para_criar)} conta(s) registrada(s) com sucesso!"
        )
        return redirect("contas_pagar")


@method_decorator(login_required, name="dispatch")
class ReceitaLoteCreateView(View):
    """View para cadastro em lote de receitas."""

    template_name = "core/financeiro/conta_lote_form.html"

    def get(self, request):
        usuario = request.user
        quantidade = int(request.GET.get("qtd", 5))

        # Limitar entre 1 e 20
        quantidade = max(1, min(quantidade, 20))

        return render(
            request,
            self.template_name,
            {
                "tipo": "receita",
                "titulo": "Cadastro em Lote - Receitas",
                "subtitulo": "Registre várias receitas de uma só vez",
                "quantidade": quantidade,
                "linhas": range(quantidade),
                "url_voltar": "receitas",
            },
        )

    def post(self, request):
        usuario = request.user

        # Coletar dados do formulário
        descricoes = request.POST.getlist("descricao[]")
        valores = request.POST.getlist("valor[]")
        datas = request.POST.getlist("data[]")

        # Buscar categoria padrão de receita
        default_cat = Categoria.objects.filter(
            usuario=usuario, tipo=Categoria.TIPO_RECEITA, is_default=True
        ).first()

        # Validar e preparar lançamentos
        receitas_para_criar = []
        erros = []

        for i, (desc, val, dt) in enumerate(
            zip(descricoes, valores, datas), 1
        ):
            desc = desc.strip()
            val = val.strip()
            dt = dt.strip()

            # Pular linhas vazias
            if not desc and not val and not dt:
                continue

            # Validar campos obrigatórios
            if not desc:
                erros.append(f"Linha {i}: Descrição é obrigatória")
                continue
            if not val:
                erros.append(f"Linha {i}: Valor é obrigatório")
                continue
            if not dt:
                erros.append(f"Linha {i}: Data é obrigatória")
                continue

            # Parsear valor
            try:
                val_norm = val.replace(".", "").replace(",", ".") if "," in val else val
                valor = Decimal(val_norm).quantize(Decimal("0.01"))
                if valor <= 0:
                    erros.append(f"Linha {i}: Valor deve ser maior que zero")
                    continue
            except (InvalidOperation, ValueError):
                erros.append(f"Linha {i}: Valor inválido")
                continue

            # Parsear data
            data_parsed = parse_date_flexible(dt)
            if not data_parsed:
                erros.append(f"Linha {i}: Data inválida")
                continue

            receitas_para_criar.append(
                Conta(
                    usuario=usuario,
                    tipo=Conta.TIPO_RECEITA,
                    descricao=desc,
                    valor=valor,
                    data_prevista=data_parsed,
                    categoria=default_cat,
                    transacao_realizada=True,  # Receitas já entram como realizadas
                    data_realizacao=data_parsed,
                )
            )

        if erros:
            for erro in erros:
                messages.error(request, erro)
            return redirect("receita_lote")

        if not receitas_para_criar:
            messages.warning(request, "Nenhum lançamento preenchido.")
            return redirect("receita_lote")

        # Criar em lote
        with transaction.atomic():
            Conta.objects.bulk_create(receitas_para_criar)

        messages.success(
            request, f"{len(receitas_para_criar)} receita(s) registrada(s) com sucesso!"
        )
        return redirect("receitas")
