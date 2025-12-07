import openpyxl
from openpyxl.workbook import Workbook
from django.http import HttpResponse
from datetime import datetime

from core.models import (
    Transacao,
    Categoria,
    FormaPagamento,
    ResumoMensal,
    ConfigUsuario,
)


def gerar_backup_excel(usuario):
    wb = Workbook()
    ws_trans = wb.active
    ws_trans.title = "transacoes"

    # Aba 1: Transações
    ws_trans.append(
        [
            "id",
            "data",
            "tipo",
            "valor",
            "descricao",
            "categoria",
            "forma_pagamento",
            "is_legacy",
            "origem_ano",
            "origem_mes",
            "origem_linha",
        ]
    )

    transacoes = Transacao.objects.filter(usuario=usuario).order_by("data", "id")

    for t in transacoes:
        ws_trans.append(
            [
                t.id,
                t.data.strftime("%Y-%m-%d"),
                t.get_tipo_display(),
                float(t.valor),
                t.descricao,
                t.categoria.nome if t.categoria else "",
                t.forma_pagamento.nome if t.forma_pagamento else "",
                t.is_legacy,
                t.origem_ano,
                t.origem_mes,
                t.origem_linha,
            ]
        )

    # Aba 2: Categorias
    ws_cat = wb.create_sheet("categorias")
    ws_cat.append(["id", "nome", "tipo", "is_default"])

    for c in Categoria.objects.filter(usuario=usuario).order_by("id"):
        ws_cat.append(
            [
                c.id,
                c.nome,
                c.get_tipo_display(),
                c.is_default,
            ]
        )

    # Aba 3: Formas de pagamento
    ws_fp = wb.create_sheet("formas_pagamento")
    ws_fp.append(["id", "nome"])

    for fp in FormaPagamento.objects.filter(usuario=usuario).order_by("id"):
        ws_fp.append(
            [
                fp.id,
                fp.nome,
            ]
        )

    # Aba 4: Resumo mensal
    ws_rm = wb.create_sheet("resumo_mensal")
    ws_rm.append(["ano", "mes", "receita", "outras_receitas", "gastos", "total"])

    resumos = ResumoMensal.objects.filter(usuario=usuario).order_by("ano", "mes")

    for r in resumos:
        ws_rm.append(
            [
                r.ano,
                r.mes,
                float(r.receita),
                float(r.outras_receitas),
                float(r.gastos),
                float(r.total),
            ]
        )

    # Aba 5: Config usuário
    ws_conf = wb.create_sheet("configuracoes")
    ws_conf.append(["moeda_padrao", "ultimo_export_em"])

    config = ConfigUsuario.objects.filter(usuario=usuario).first()
    if config:
        ws_conf.append(
            [
                config.moeda_padrao,
                config.ultimo_export_em.strftime("%Y-%m-%d %H:%M:%S")
                if config.ultimo_export_em
                else "",
            ]
        )

    # Gera resposta HTTP com o arquivo
    response = HttpResponse(
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

    nome_arquivo = f"backup_financeiro_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    response["Content-Disposition"] = f'attachment; filename="{nome_arquivo}"'

    wb.save(response)

    if config:
        config.ultimo_export_em = datetime.now()
        config.save()

    return response
