"""
Serviço de exportação de relatórios em Excel e PDF.
"""

import io
from datetime import date
from decimal import Decimal

from django.db.models import Q
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
from openpyxl.utils import get_column_letter

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate,
    Table,
    TableStyle,
    Paragraph,
    Spacer,
    PageBreak,
)

from core.models import Conta
from investimento.models import Ativo, Transacao as TransacaoInvestimento


def get_movimentacoes(usuario, data_inicio: date, data_fim: date):
    """
    Busca todas as movimentações do usuário no período.
    Exclui despesas individuais de cartão (apenas faturas consolidadas).
    """
    qs = (
        Conta.objects.filter(
            usuario=usuario,
            data_prevista__gte=data_inicio,
            data_prevista__lte=data_fim,
        )
        .filter(
            # Apenas contas sem cartão OU faturas de cartão
            Q(cartao__isnull=True) | Q(eh_fatura_cartao=True)
        )
        .select_related("categoria", "forma_pagamento", "cartao")
        .order_by("data_prevista", "id")
    )
    return qs


def get_investimentos(usuario, data_inicio: date, data_fim: date):
    """
    Busca ativos do usuário que têm transações no período ou posição > 0.
    """
    # Ativos com posição > 0 ou com transações no período
    ativos_com_transacoes = TransacaoInvestimento.objects.filter(
        usuario=usuario,
        data__gte=data_inicio,
        data__lte=data_fim,
    ).values_list("ativo_id", flat=True)

    qs = (
        Ativo.objects.filter(
            Q(usuario=usuario) & (Q(quantidade__gt=0) | Q(id__in=ativos_com_transacoes))
        )
        .select_related("subcategoria__categoria__classe")
        .order_by("ticker")
    )
    return qs


def get_transacoes_investimento(usuario, data_inicio: date, data_fim: date):
    """
    Busca transações de investimento do usuário no período.
    """
    qs = (
        TransacaoInvestimento.objects.filter(
            usuario=usuario,
            data__gte=data_inicio,
            data__lte=data_fim,
        )
        .select_related("ativo")
        .order_by("data", "id")
    )
    return qs


def gerar_excel(usuario, data_inicio: date, data_fim: date) -> bytes:
    """
    Gera arquivo Excel com as movimentações, investimentos e transações do período.
    Retorna bytes do arquivo.
    """
    movimentacoes = get_movimentacoes(usuario, data_inicio, data_fim)
    investimentos = get_investimentos(usuario, data_inicio, data_fim)
    transacoes_invest = get_transacoes_investimento(usuario, data_inicio, data_fim)

    wb = Workbook()
    wb.properties.title = f"Relatório Financeiro {data_inicio.strftime('%d-%m-%Y')} a {data_fim.strftime('%d-%m-%Y')}"
    wb.properties.creator = "FreeCash"

    # Estilos comuns
    header_font = Font(bold=True, color="FFFFFF")
    header_fill = PatternFill(
        start_color="10B981", end_color="10B981", fill_type="solid"
    )
    header_fill_blue = PatternFill(
        start_color="3B82F6", end_color="3B82F6", fill_type="solid"
    )
    header_alignment = Alignment(horizontal="center", vertical="center")
    thin_border = Border(
        left=Side(style="thin"),
        right=Side(style="thin"),
        top=Side(style="thin"),
        bottom=Side(style="thin"),
    )

    # =====================
    # ABA 1: MOVIMENTAÇÕES
    # =====================
    ws = wb.active
    ws.title = "Movimentações"

    # Título
    ws.merge_cells("A1:F1")
    ws["A1"] = (
        f"Relatório de Movimentações - {data_inicio.strftime('%d/%m/%Y')} a {data_fim.strftime('%d/%m/%Y')}"
    )
    ws["A1"].font = Font(bold=True, size=14)
    ws["A1"].alignment = Alignment(horizontal="center")

    # Cabeçalhos
    headers = ["Data", "Tipo", "Descrição", "Categoria", "Valor (R$)", "Status"]
    for col, header in enumerate(headers, 1):
        cell = ws.cell(row=3, column=col, value=header)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = header_alignment
        cell.border = thin_border

    # Dados
    total_receitas = Decimal("0.00")
    total_despesas = Decimal("0.00")

    for row_num, mov in enumerate(movimentacoes, 4):
        tipo_label = "Receita" if mov.tipo == Conta.TIPO_RECEITA else "Despesa"
        categoria_nome = mov.categoria.nome if mov.categoria else "Sem categoria"
        status = "Realizada" if mov.transacao_realizada else "Pendente"

        if mov.tipo == Conta.TIPO_RECEITA:
            total_receitas += mov.valor
        else:
            total_despesas += mov.valor

        data = [
            mov.data_prevista.strftime("%d/%m/%Y"),
            tipo_label,
            mov.descricao,
            categoria_nome,
            float(mov.valor),
            status,
        ]

        for col, value in enumerate(data, 1):
            cell = ws.cell(row=row_num, column=col, value=value)
            cell.border = thin_border
            if col == 5:  # Coluna de valor
                cell.number_format = "#,##0.00"
                cell.alignment = Alignment(horizontal="right")

    # Resumo
    last_row = ws.max_row + 2
    ws.cell(row=last_row, column=4, value="Total Receitas:").font = Font(bold=True)
    ws.cell(
        row=last_row, column=5, value=float(total_receitas)
    ).number_format = "#,##0.00"

    ws.cell(row=last_row + 1, column=4, value="Total Despesas:").font = Font(bold=True)
    ws.cell(
        row=last_row + 1, column=5, value=float(total_despesas)
    ).number_format = "#,##0.00"

    saldo = total_receitas - total_despesas
    ws.cell(row=last_row + 2, column=4, value="Saldo:").font = Font(bold=True)
    saldo_cell = ws.cell(row=last_row + 2, column=5, value=float(saldo))
    saldo_cell.number_format = "#,##0.00"
    saldo_cell.font = Font(bold=True, color="10B981" if saldo >= 0 else "EF4444")

    # Ajustar largura das colunas
    column_widths = [12, 10, 40, 20, 15, 12]
    for i, width in enumerate(column_widths, 1):
        ws.column_dimensions[get_column_letter(i)].width = width

    # =====================
    # ABA 2: INVESTIMENTOS
    # =====================
    ws_invest = wb.create_sheet("Investimentos")

    # Título
    ws_invest.merge_cells("A1:H1")
    ws_invest["A1"] = f"Carteira de Investimentos - {data_fim.strftime('%d/%m/%Y')}"
    ws_invest["A1"].font = Font(bold=True, size=14)
    ws_invest["A1"].alignment = Alignment(horizontal="center")

    # Cabeçalhos
    invest_headers = [
        "Ticker",
        "Nome",
        "Classe",
        "Categoria",
        "Subcategoria",
        "Quantidade",
        "Preço Médio",
        "Valor Investido",
        "Rentabilidade",
        "Valor Mercado",
    ]
    for col, header in enumerate(invest_headers, 1):
        cell = ws_invest.cell(row=3, column=col, value=header)
        cell.font = header_font
        cell.fill = header_fill_blue
        cell.alignment = header_alignment
        cell.border = thin_border

    # Dados
    total_investido = Decimal("0.00")
    total_mercado = Decimal("0.00")
    row_num = 4

    for ativo in investimentos:
        classe = ""
        categoria = ""
        subcategoria = ""

        if ativo.subcategoria:
            subcategoria = ativo.subcategoria.nome
            categoria = ativo.subcategoria.categoria.nome
            classe = ativo.subcategoria.categoria.classe.nome

        valor_investido = ativo.valor_investido
        total_investido += valor_investido
        valor_mercado = ativo.valor_total_atual
        total_mercado += valor_mercado
        rentabilidade = ativo.rentabilidade

        data = [
            ativo.ticker,
            ativo.nome or "",
            classe,
            categoria,
            subcategoria,
            float(ativo.quantidade),
            float(ativo.preco_medio),
            float(valor_investido),
            float(rentabilidade),
            float(valor_mercado),
        ]

        for col, value in enumerate(data, 1):
            cell = ws_invest.cell(row=row_num, column=col, value=value)
            cell.border = thin_border
            if col in [6, 7, 8, 9, 10]:  # Colunas numéricas
                cell.number_format = "#,##0.00" if col != 6 else "#,##0.00000000"
                cell.alignment = Alignment(horizontal="right")

        row_num += 1

    # Total da carteira
    if investimentos.exists():
        ws_invest.cell(row=row_num + 1, column=7, value="Total Investido:").font = Font(
            bold=True
        )
        total_inv_cell = ws_invest.cell(
            row=row_num + 1, column=8, value=float(total_investido)
        )
        total_inv_cell.number_format = "#,##0.00"
        total_inv_cell.font = Font(bold=True)

        ws_invest.cell(row=row_num + 2, column=7, value="Total Mercado:").font = Font(
            bold=True
        )
        total_merc_cell = ws_invest.cell(
            row=row_num + 2, column=8, value=float(total_mercado)
        )
        total_merc_cell.number_format = "#,##0.00"
        total_merc_cell.font = Font(bold=True, color="3B82F6")

        rent_total = total_mercado - total_investido
        ws_invest.cell(row=row_num + 3, column=7, value="Rentabilidade:").font = Font(
            bold=True
        )
        rent_cell = ws_invest.cell(row=row_num + 3, column=8, value=float(rent_total))
        rent_cell.number_format = "#,##0.00"
        rent_cell.font = Font(
            bold=True, color="10B981" if rent_total >= 0 else "EF4444"
        )

    # Ajustar largura das colunas
    invest_widths = [12, 30, 15, 15, 15, 15, 15, 18, 15, 18]
    for i, width in enumerate(invest_widths, 1):
        ws_invest.column_dimensions[get_column_letter(i)].width = width

    # ================================
    # ABA 3: TRANSAÇÕES INVESTIMENTO
    # ================================
    ws_trans = wb.create_sheet("Transações Invest.")

    # Título
    ws_trans.merge_cells("A1:G1")
    ws_trans["A1"] = (
        f"Transações de Investimento - {data_inicio.strftime('%d/%m/%Y')} a {data_fim.strftime('%d/%m/%Y')}"
    )
    ws_trans["A1"].font = Font(bold=True, size=14)
    ws_trans["A1"].alignment = Alignment(horizontal="center")

    # Cabeçalhos
    trans_headers = [
        "Data",
        "Ticker",
        "Tipo",
        "Quantidade",
        "Preço Unit.",
        "Taxas",
        "Valor Total",
    ]
    for col, header in enumerate(trans_headers, 1):
        cell = ws_trans.cell(row=3, column=col, value=header)
        cell.font = header_font
        cell.fill = header_fill_blue
        cell.alignment = header_alignment
        cell.border = thin_border

    # Dados
    row_num = 4
    total_compras = Decimal("0.00")
    total_vendas = Decimal("0.00")
    total_proventos = Decimal("0.00")

    for trans in transacoes_invest:
        tipo_label = trans.get_tipo_display()

        if trans.tipo == TransacaoInvestimento.TIPO_COMPRA:
            total_compras += trans.valor_total
        elif trans.tipo == TransacaoInvestimento.TIPO_VENDA:
            total_vendas += trans.valor_total
        else:
            total_proventos += trans.valor_total

        data = [
            trans.data.strftime("%d/%m/%Y"),
            trans.ativo.ticker,
            tipo_label,
            float(trans.quantidade),
            float(trans.preco_unitario),
            float(trans.taxas),
            float(trans.valor_total),
        ]

        for col, value in enumerate(data, 1):
            cell = ws_trans.cell(row=row_num, column=col, value=value)
            cell.border = thin_border
            if col >= 4:  # Colunas numéricas
                cell.number_format = "#,##0.00" if col != 4 else "#,##0.00000000"
                cell.alignment = Alignment(horizontal="right")

        row_num += 1

    # Resumo
    if transacoes_invest.exists():
        ws_trans.cell(row=row_num + 1, column=6, value="Total Compras:").font = Font(
            bold=True
        )
        ws_trans.cell(
            row=row_num + 1, column=7, value=float(total_compras)
        ).number_format = "#,##0.00"

        ws_trans.cell(row=row_num + 2, column=6, value="Total Vendas:").font = Font(
            bold=True
        )
        ws_trans.cell(
            row=row_num + 2, column=7, value=float(total_vendas)
        ).number_format = "#,##0.00"

        ws_trans.cell(row=row_num + 3, column=6, value="Total Proventos:").font = Font(
            bold=True
        )
        ws_trans.cell(
            row=row_num + 3, column=7, value=float(total_proventos)
        ).number_format = "#,##0.00"

    # Ajustar largura das colunas
    trans_widths = [12, 12, 18, 15, 15, 12, 18]
    for i, width in enumerate(trans_widths, 1):
        ws_trans.column_dimensions[get_column_letter(i)].width = width

    # Salvar em bytes
    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    return output.getvalue()


def gerar_pdf(usuario, data_inicio: date, data_fim: date) -> bytes:
    """
    Gera arquivo PDF com as movimentações, investimentos e transações do período.
    Retorna bytes do arquivo.
    """
    movimentacoes = get_movimentacoes(usuario, data_inicio, data_fim)
    investimentos = get_investimentos(usuario, data_inicio, data_fim)
    transacoes_invest = get_transacoes_investimento(usuario, data_inicio, data_fim)

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=10 * mm,
        leftMargin=10 * mm,
        topMargin=10 * mm,
        bottomMargin=10 * mm,
        title=f"Relatório Financeiro {data_inicio.strftime('%d-%m-%Y')} a {data_fim.strftime('%d-%m-%Y')}",
        author="FreeCash",
    )

    elements = []
    styles = getSampleStyleSheet()

    # Estilo de título
    title_style = ParagraphStyle(
        "Title",
        parent=styles["Heading1"],
        fontSize=16,
        spaceAfter=20,
        alignment=1,  # Center
    )

    # Estilo de seção
    section_style = ParagraphStyle(
        "Section",
        parent=styles["Heading2"],
        fontSize=12,
        spaceAfter=10,
        spaceBefore=15,
        textColor=colors.HexColor("#1F2937"),
    )

    # =====================
    # SEÇÃO 1: MOVIMENTAÇÕES
    # =====================
    title = Paragraph(
        f"Relatório Financeiro<br/>{data_inicio.strftime('%d/%m/%Y')} a {data_fim.strftime('%d/%m/%Y')}",
        title_style,
    )
    elements.append(title)
    elements.append(Spacer(1, 5 * mm))

    section_mov = Paragraph("📊 Movimentações", section_style)
    elements.append(section_mov)

    # Tabela de movimentações
    table_data = [["Data", "Tipo", "Descrição", "Categoria", "Valor", "Status"]]

    total_receitas = Decimal("0.00")
    total_despesas = Decimal("0.00")

    for mov in movimentacoes:
        tipo_label = "Receita" if mov.tipo == Conta.TIPO_RECEITA else "Despesa"
        categoria_nome = mov.categoria.nome if mov.categoria else "Sem cat."
        status = "OK" if mov.transacao_realizada else "Pend."

        if mov.tipo == Conta.TIPO_RECEITA:
            total_receitas += mov.valor
        else:
            total_despesas += mov.valor

        descricao = (
            mov.descricao[:30] + "..." if len(mov.descricao) > 30 else mov.descricao
        )

        table_data.append(
            [
                mov.data_prevista.strftime("%d/%m/%Y"),
                tipo_label,
                descricao,
                categoria_nome[:15],
                f"R$ {mov.valor:,.2f}".replace(",", "X")
                .replace(".", ",")
                .replace("X", "."),
                status,
            ]
        )

    # Resumo de movimentações
    table_data.append(["", "", "", "", "", ""])
    table_data.append(
        [
            "",
            "",
            "",
            "Total Receitas:",
            f"R$ {total_receitas:,.2f}".replace(",", "X")
            .replace(".", ",")
            .replace("X", "."),
            "",
        ]
    )
    table_data.append(
        [
            "",
            "",
            "",
            "Total Despesas:",
            f"R$ {total_despesas:,.2f}".replace(",", "X")
            .replace(".", ",")
            .replace("X", "."),
            "",
        ]
    )
    saldo = total_receitas - total_despesas
    table_data.append(
        [
            "",
            "",
            "",
            "Saldo:",
            f"R$ {saldo:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."),
            "",
        ]
    )

    col_widths = [50, 60, 180, 100, 85, 60]
    table = Table(table_data, colWidths=col_widths)

    table_style = TableStyle(
        [
            ("BOTTOMPADDING", (0, 0), (-1, 0), 2 * mm),
            ("TOPPADDING", (0, 0), (-1, 0), 2 * mm),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#10B981")),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, 0), 10),
            ("ALIGN", (0, 0), (-1, 0), "CENTER"),
            ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
            ("FONTSIZE", (0, 1), (-1, -1), 8),
            ("ALIGN", (4, 1), (4, -1), "RIGHT"),
            ("ALIGN", (5, 1), (5, -1), "CENTER"),
            ("LINEBELOW", (0, 0), (-1, 0), 1, colors.HexColor("#10B981")),
            ("LINEBELOW", (0, 1), (-1, -1), 0.1, colors.grey),
            (
                "ROWBACKGROUNDS",
                (0, 1),
                (-1, -1),
                [colors.white, colors.HexColor("#e5e5e5")],
            ),
            ("FONTNAME", (3, -3), (4, -1), "Helvetica-Bold"),
            ("ALIGN", (3, -3), (3, -1), "RIGHT"),
        ]
    )
    table.setStyle(table_style)
    elements.append(table)

    # =====================
    # SEÇÃO 2: INVESTIMENTOS
    # =====================
    if investimentos.exists():
        elements.append(PageBreak())
        section_invest = Paragraph("📈 Carteira de Investimentos", section_style)
        elements.append(section_invest)

        invest_data = [["Ticker", "Nome", "Qtd", "PM", "Rentab.", "Mercado"]]
        total_investido = Decimal("0.00")
        total_mercado = Decimal("0.00")

        for ativo in investimentos:
            valor_investido = ativo.valor_investido
            total_investido += valor_investido
            valor_mercado = ativo.valor_total_atual
            total_mercado += valor_mercado
            rentabilidade = ativo.rentabilidade

            nome = (
                ativo.nome[:20] + "..."
                if ativo.nome and len(ativo.nome) > 20
                else (ativo.nome or "")
            )

            invest_data.append(
                [
                    ativo.ticker,
                    nome,
                    f"{ativo.quantidade:,.2f}".replace(",", "X")
                    .replace(".", ",")
                    .replace("X", "."),
                    f"R$ {ativo.preco_medio:,.2f}".replace(",", "X")
                    .replace(".", ",")
                    .replace("X", "."),
                    f"R$ {rentabilidade:,.2f}".replace(",", "X")
                    .replace(".", ",")
                    .replace("X", "."),
                    f"R$ {valor_mercado:,.2f}".replace(",", "X")
                    .replace(".", ",")
                    .replace("X", "."),
                ]
            )

        # Totais
        invest_data.append(["", "", "", "", "", ""])
        invest_data.append(
            [
                "",
                "",
                "",
                "Total Investido:",
                "",
                f"R$ {total_investido:,.2f}".replace(",", "X")
                .replace(".", ",")
                .replace("X", "."),
            ]
        )
        invest_data.append(
            [
                "",
                "",
                "",
                "Total Mercado:",
                "",
                f"R$ {total_mercado:,.2f}".replace(",", "X")
                .replace(".", ",")
                .replace("X", "."),
            ]
        )
        rent_total = total_mercado - total_investido
        invest_data.append(
            [
                "",
                "",
                "",
                "Rentabilidade:",
                "",
                f"R$ {rent_total:,.2f}".replace(",", "X")
                .replace(".", ",")
                .replace("X", "."),
            ]
        )

        invest_widths = [70, 145, 80, 80, 80, 80]
        invest_table = Table(invest_data, colWidths=invest_widths)

        invest_style = TableStyle(
            [
                ("BOTTOMPADDING", (0, 0), (-1, 0), 2 * mm),
                ("TOPPADDING", (0, 0), (-1, 0), 2 * mm),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#3B82F6")),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, 0), 10),
                ("ALIGN", (0, 0), (-1, 0), "CENTER"),
                ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
                ("FONTSIZE", (0, 1), (-1, -1), 8),
                ("ALIGN", (2, 1), (5, -1), "RIGHT"),
                ("LINEBELOW", (0, 0), (-1, 0), 1, colors.HexColor("#3B82F6")),
                ("LINEBELOW", (0, 1), (-1, -1), 0.1, colors.grey),
                (
                    "ROWBACKGROUNDS",
                    (0, 1),
                    (-1, -1),
                    [colors.white, colors.HexColor("#e5e5e5")],
                ),
                ("FONTNAME", (3, -3), (5, -1), "Helvetica-Bold"),
            ]
        )
        invest_table.setStyle(invest_style)
        elements.append(invest_table)

    # ================================
    # SEÇÃO 3: TRANSAÇÕES INVESTIMENTO
    # ================================
    if transacoes_invest.exists():
        elements.append(PageBreak())
        section_trans = Paragraph("💰 Transações de Investimento", section_style)
        elements.append(section_trans)

        trans_data = [["Data", "Ticker", "Tipo", "Qtd", "Preço", "Total"]]
        total_compras = Decimal("0.00")
        total_vendas = Decimal("0.00")
        total_proventos = Decimal("0.00")

        for trans in transacoes_invest:
            tipo_label = trans.get_tipo_display()

            if trans.tipo == TransacaoInvestimento.TIPO_COMPRA:
                total_compras += trans.valor_total
            elif trans.tipo == TransacaoInvestimento.TIPO_VENDA:
                total_vendas += trans.valor_total
            else:
                total_proventos += trans.valor_total

            trans_data.append(
                [
                    trans.data.strftime("%d/%m/%Y"),
                    trans.ativo.ticker,
                    tipo_label[:10],
                    f"{trans.quantidade:,.2f}".replace(",", "X")
                    .replace(".", ",")
                    .replace("X", "."),
                    f"R$ {trans.preco_unitario:,.2f}".replace(",", "X")
                    .replace(".", ",")
                    .replace("X", "."),
                    f"R$ {trans.valor_total:,.2f}".replace(",", "X")
                    .replace(".", ",")
                    .replace("X", "."),
                ]
            )

        # Resumo
        trans_data.append(["", "", "", "", "", ""])
        trans_data.append(
            [
                "",
                "",
                "",
                "",
                "Compras:",
                f"R$ {total_compras:,.2f}".replace(",", "X")
                .replace(".", ",")
                .replace("X", "."),
            ]
        )
        trans_data.append(
            [
                "",
                "",
                "",
                "",
                "Vendas:",
                f"R$ {total_vendas:,.2f}".replace(",", "X")
                .replace(".", ",")
                .replace("X", "."),
            ]
        )
        trans_data.append(
            [
                "",
                "",
                "",
                "",
                "Proventos:",
                f"R$ {total_proventos:,.2f}".replace(",", "X")
                .replace(".", ",")
                .replace("X", "."),
            ]
        )

        trans_widths = [60, 70, 95, 100, 100, 110]
        trans_table = Table(trans_data, colWidths=trans_widths)

        trans_style = TableStyle(
            [
                ("BOTTOMPADDING", (0, 0), (-1, 0), 2 * mm),
                ("TOPPADDING", (0, 0), (-1, 0), 2 * mm),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#8B5CF6")),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, 0), 10),
                ("ALIGN", (0, 0), (-1, 0), "CENTER"),
                ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
                ("FONTSIZE", (0, 1), (-1, -1), 8),
                ("ALIGN", (3, 1), (5, -1), "RIGHT"),
                ("LINEBELOW", (0, 0), (-1, 0), 1, colors.HexColor("#8B5CF6")),
                ("LINEBELOW", (0, 1), (-1, -1), 0.1, colors.grey),
                (
                    "ROWBACKGROUNDS",
                    (0, 1),
                    (-1, -1),
                    [colors.white, colors.HexColor("#e5e5e5")],
                ),
                ("FONTNAME", (4, -3), (5, -1), "Helvetica-Bold"),
            ]
        )
        trans_table.setStyle(trans_style)
        elements.append(trans_table)

    # Build PDF
    doc.build(elements)
    buffer.seek(0)
    return buffer.getvalue()
