from datetime import datetime
from django.http import HttpResponse
from django.utils import timezone

from openpyxl import Workbook

from core.models import Categoria, Conta, FormaPagamento, ResumoMensal, ConfigUsuario


def gerar_backup_excel(usuario):
    wb = Workbook()

    # =========================
    # Aba 0: Metadata
    # =========================
    ws_meta = wb.active
    ws_meta.title = "metadata"
    ws_meta.append(["chave", "valor"])
    ws_meta.append(["backup_version", "1"])
    ws_meta.append(["generated_at", timezone.now().strftime("%Y-%m-%d %H:%M:%S")])
    ws_meta.append(["usuario_id", str(usuario.id)])
    ws_meta.append(["username", usuario.get_username()])

    # =========================
    # Aba 1: Contas (tudo em um)
    # =========================
    ws_contas = wb.create_sheet("contas")
    ws_contas.append(
        [
            "id",
            "tipo",  # R/D/I (valor do campo)
            "descricao",
            "valor",
            "data_prevista",
            "transacao_realizada",
            "data_realizacao",
            "categoria_id",
            "forma_pagamento_id",
            "is_legacy",
            "origem_ano",
            "origem_mes",
            "origem_linha",
            "criada_em",
            "atualizada_em",
        ]
    )

    contas = (
        Conta.objects.filter(usuario=usuario)
        .select_related("categoria", "forma_pagamento")
        .order_by("data_prevista", "id")
    )

    for c in contas:
        ws_contas.append(
            [
                c.id,
                c.tipo,
                c.descricao or "",
                float(c.valor),
                c.data_prevista.strftime("%Y-%m-%d") if c.data_prevista else "",
                bool(c.transacao_realizada),
                c.data_realizacao.strftime("%Y-%m-%d") if c.data_realizacao else "",
                c.categoria_id or "",
                c.forma_pagamento_id or "",
                bool(getattr(c, "is_legacy", False)),
                getattr(c, "origem_ano", None),
                getattr(c, "origem_mes", None),
                getattr(c, "origem_linha", "") or "",
                c.criada_em.strftime("%Y-%m-%d %H:%M:%S")
                if getattr(c, "criada_em", None)
                else "",
                c.atualizada_em.strftime("%Y-%m-%d %H:%M:%S")
                if getattr(c, "atualizada_em", None)
                else "",
            ]
        )

    # =========================
    # Aba 2: Categorias
    # =========================
    ws_cat = wb.create_sheet("categorias")
    ws_cat.append(["id", "nome", "tipo", "is_default", "criada_em", "atualizada_em"])

    for cat in Categoria.objects.filter(usuario=usuario).order_by("id"):
        ws_cat.append(
            [
                cat.id,
                cat.nome,
                cat.tipo,  # exporta valor estável
                bool(getattr(cat, "is_default", False)),
                cat.criada_em.strftime("%Y-%m-%d %H:%M:%S")
                if getattr(cat, "criada_em", None)
                else "",
                cat.atualizada_em.strftime("%Y-%m-%d %H:%M:%S")
                if getattr(cat, "atualizada_em", None)
                else "",
            ]
        )

    # =========================
    # Aba 3: Formas de pagamento
    # =========================
    ws_fp = wb.create_sheet("formas_pagamento")
    ws_fp.append(["id", "nome", "ativa", "criada_em", "atualizada_em"])

    for fp in FormaPagamento.objects.filter(usuario=usuario).order_by("id"):
        ws_fp.append(
            [
                fp.id,
                fp.nome,
                bool(getattr(fp, "ativa", True)),
                fp.criada_em.strftime("%Y-%m-%d %H:%M:%S")
                if getattr(fp, "criada_em", None)
                else "",
                fp.atualizada_em.strftime("%Y-%m-%d %H:%M:%S")
                if getattr(fp, "atualizada_em", None)
                else "",
            ]
        )

    # =========================
    # Aba 4: Resumo mensal
    # =========================
    ws_rm = wb.create_sheet("resumo_mensal")
    ws_rm.append(
        [
            "id",
            "ano",
            "mes",
            "receita",
            "outras_receitas",
            "gastos",
            "total",
            "is_legacy",
        ]
    )

    for r in ResumoMensal.objects.filter(usuario=usuario).order_by("ano", "mes"):
        ws_rm.append(
            [
                r.id,
                r.ano,
                r.mes,
                float(r.receita),
                float(r.outras_receitas),
                float(r.gastos),
                float(r.total),
                bool(getattr(r, "is_legacy", False)),
            ]
        )

    # =========================
    # Aba 5: Configurações
    # =========================
    ws_conf = wb.create_sheet("configuracoes")
    ws_conf.append(["moeda_padrao", "ultimo_export_em"])

    config = ConfigUsuario.objects.filter(usuario=usuario).first()
    ws_conf.append(
        [
            getattr(config, "moeda_padrao", "BRL") if config else "BRL",
            config.ultimo_export_em.strftime("%Y-%m-%d %H:%M:%S")
            if config and config.ultimo_export_em
            else "",
        ]
    )

    # =========================
    # Response
    # =========================
    response = HttpResponse(
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    nome_arquivo = f"backup_freecash_{usuario.get_username()}_{timezone.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    response["Content-Disposition"] = f'attachment; filename="{nome_arquivo}"'

    wb.save(response)

    # Atualiza config
    if config:
        config.ultimo_export_em = timezone.now()
        config.save(update_fields=["ultimo_export_em"])

    return response
