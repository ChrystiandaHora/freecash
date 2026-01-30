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
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer

from core.models import Conta


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


def gerar_excel(usuario, data_inicio: date, data_fim: date) -> bytes:
    """
    Gera arquivo Excel com as movimentações do período.
    Retorna bytes do arquivo.
    """
    movimentacoes = get_movimentacoes(usuario, data_inicio, data_fim)

    wb = Workbook()
    ws = wb.active
    ws.title = "Movimentações"

    # Estilos
    header_font = Font(bold=True, color="FFFFFF")
    header_fill = PatternFill(
        start_color="10B981", end_color="10B981", fill_type="solid"
    )
    header_alignment = Alignment(horizontal="center", vertical="center")
    thin_border = Border(
        left=Side(style="thin"),
        right=Side(style="thin"),
        top=Side(style="thin"),
        bottom=Side(style="thin"),
    )

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

    # Salvar em bytes
    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    return output.getvalue()


def gerar_pdf(usuario, data_inicio: date, data_fim: date) -> bytes:
    """
    Gera arquivo PDF com as movimentações do período.
    Retorna bytes do arquivo.
    """
    movimentacoes = get_movimentacoes(usuario, data_inicio, data_fim)

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=15 * mm,
        leftMargin=15 * mm,
        topMargin=15 * mm,
        bottomMargin=15 * mm,
    )

    elements = []
    styles = getSampleStyleSheet()

    # Título
    title_style = ParagraphStyle(
        "Title",
        parent=styles["Heading1"],
        fontSize=16,
        spaceAfter=20,
        alignment=1,  # Center
    )
    title = Paragraph(
        f"Relatório de Movimentações<br/>{data_inicio.strftime('%d/%m/%Y')} a {data_fim.strftime('%d/%m/%Y')}",
        title_style,
    )
    elements.append(title)
    elements.append(Spacer(1, 10 * mm))

    # Tabela de dados
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

        # Truncar descrição se muito longa
        descricao = (
            mov.descricao[:30] + "..." if len(mov.descricao) > 30 else mov.descricao
        )

        table_data.append(
            [
                mov.data_prevista.strftime("%d/%m"),
                tipo_label,
                descricao,
                categoria_nome[:15],
                f"R$ {mov.valor:,.2f}".replace(",", "X")
                .replace(".", ",")
                .replace("X", "."),
                status,
            ]
        )

    # Adicionar resumo
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

    # Criar tabela
    col_widths = [45, 50, 120, 80, 70, 40]
    table = Table(table_data, colWidths=col_widths)

    table_style = TableStyle(
        [
            # Header
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#10B981")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, 0), 9),
            ("ALIGN", (0, 0), (-1, 0), "CENTER"),
            # Body
            ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
            ("FONTSIZE", (0, 1), (-1, -1), 8),
            ("ALIGN", (4, 1), (4, -1), "RIGHT"),  # Valores à direita
            ("ALIGN", (5, 1), (5, -1), "CENTER"),  # Status centralizado
            # Grid
            ("GRID", (0, 0), (-1, -5), 0.5, colors.grey),
            # Alternating rows
            (
                "ROWBACKGROUNDS",
                (0, 1),
                (-1, -5),
                [colors.white, colors.HexColor("#F0FDF4")],
            ),
            # Summary styling
            ("FONTNAME", (3, -3), (4, -1), "Helvetica-Bold"),
            ("ALIGN", (3, -3), (3, -1), "RIGHT"),
        ]
    )
    table.setStyle(table_style)

    elements.append(table)

    # Build PDF
    doc.build(elements)
    buffer.seek(0)
    return buffer.getvalue()
