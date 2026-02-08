"""
Serviço de importação de relatórios Excel (.xlsx).
Permite ler, validar e importar movimentações de um arquivo de relatório exportado.
"""

import io
from datetime import datetime
from decimal import Decimal, InvalidOperation

from django.db import transaction
from openpyxl import load_workbook

from core.models import Conta, Categoria


def parse_date_br(date_str: str):
    """Parse date in dd/mm/yyyy format."""
    if not date_str:
        return None
    try:
        return datetime.strptime(date_str.strip(), "%d/%m/%Y").date()
    except ValueError:
        return None


def parse_valor(valor):
    """Parse valor from Excel (pode ser float ou string)."""
    if valor is None:
        return None
    if isinstance(valor, (int, float)):
        return Decimal(str(valor))
    try:
        # Remove formatação brasileira
        valor_str = str(valor).strip().replace(".", "").replace(",", ".")
        return Decimal(valor_str)
    except (InvalidOperation, ValueError):
        return None


def ler_excel_relatorio(arquivo) -> dict:
    """
    Lê arquivo Excel de relatório e retorna dados estruturados.

    Returns:
        dict com keys:
            - 'dados': lista de dicionários com os registros
            - 'resumo': dict com total_receitas, total_despesas, quantidade
            - 'erro': mensagem de erro se houver problema
    """
    try:
        # Lê o arquivo
        if hasattr(arquivo, "read"):
            content = arquivo.read()
            arquivo.seek(0)  # Reset para uso posterior
            wb = load_workbook(filename=io.BytesIO(content), read_only=True)
        else:
            wb = load_workbook(filename=io.BytesIO(arquivo), read_only=True)

        ws = wb.active

        # Encontra linha de cabeçalho (procura por "Data" na primeira coluna)
        header_row = None
        for row_num, row in enumerate(
            ws.iter_rows(min_row=1, max_row=10, values_only=True), 1
        ):
            if row and row[0] and str(row[0]).strip().upper() == "DATA":
                header_row = row_num
                break

        if header_row is None:
            return {"erro": "Formato inválido: cabeçalho 'Data' não encontrado."}

        # Valida colunas esperadas - extrai valores das células
        header_cells = list(
            ws.iter_rows(min_row=header_row, max_row=header_row, values_only=True)
        )[0]
        headers = [str(cell).strip() if cell else "" for cell in header_cells]
        expected = ["Data", "Tipo", "Descrição", "Categoria", "Valor (R$)", "Status"]

        # Verifica se as primeiras 6 colunas correspondem (case insensitive)
        for i, exp in enumerate(expected):
            if i >= len(headers):
                return {"erro": f"Formato inválido: coluna '{exp}' não encontrada."}
            if headers[i].upper() != exp.upper():
                # Aceita variações comuns
                if exp == "Valor (R$)" and "VALOR" in headers[i].upper():
                    continue
                return {
                    "erro": f"Formato inválido: esperado '{exp}', encontrado '{headers[i]}'."
                }

        # Lê os dados
        dados = []
        total_receitas = Decimal("0.00")
        total_despesas = Decimal("0.00")

        for row in ws.iter_rows(min_row=header_row + 1, values_only=True):
            # Ignora linhas vazias ou de resumo
            if not row or not row[0]:
                continue

            # Ignora linhas de resumo (Total Receitas, Total Despesas, Saldo)
            primeira_col = str(row[0]).strip() if row[0] else ""
            if primeira_col.upper() in [
                "TOTAL RECEITAS:",
                "TOTAL DESPESAS:",
                "SALDO:",
                "",
            ]:
                continue
            if any(x in primeira_col.upper() for x in ["TOTAL", "SALDO"]):
                continue

            # Parse data
            data = row[0]
            if isinstance(data, datetime):
                data = data.date()
            elif isinstance(data, str):
                data = parse_date_br(data)

            if not data:
                continue

            tipo_str = str(row[1]).strip() if row[1] else ""
            descricao = str(row[2]).strip() if row[2] else ""
            categoria_nome = str(row[3]).strip() if row[3] else ""
            valor = parse_valor(row[4])
            status_str = str(row[5]).strip() if row[5] else ""

            if not valor or valor <= 0:
                continue

            # Determina tipo
            tipo = (
                Conta.TIPO_RECEITA
                if tipo_str.upper() == "RECEITA"
                else Conta.TIPO_DESPESA
            )

            # Determina status
            realizada = status_str.upper() in [
                "REALIZADA",
                "OK",
                "PAGO",
                "PAGA",
                "SIM",
                "TRUE",
                "1",
            ]

            registro = {
                "data": data,
                "tipo": tipo,
                "tipo_label": tipo_str,
                "descricao": descricao,
                "categoria_nome": categoria_nome,
                "valor": valor,
                "realizada": realizada,
                "status_label": "Realizada" if realizada else "Pendente",
            }
            dados.append(registro)

            if tipo == Conta.TIPO_RECEITA:
                total_receitas += valor
            else:
                total_despesas += valor

        wb.close()

        return {
            "dados": dados,
            "resumo": {
                "total_receitas": total_receitas,
                "total_despesas": total_despesas,
                "saldo": total_receitas - total_despesas,
                "quantidade": len(dados),
            },
            "erro": None,
        }

    except Exception as e:
        return {"erro": f"Erro ao ler arquivo: {str(e)}"}


def validar_dados_relatorio(dados: list, usuario) -> list:
    """
    Valida os dados do relatório contra o banco de dados.
    Retorna lista de dados com informações de validação adicionadas.

    Adiciona aos registros:
        - 'categoria_id': ID da categoria encontrada ou None
        - 'categoria_existe': bool
        - 'existe_duplicado': bool (se já existe conta com mesma data/descrição/valor)
        - 'conta_existente_id': ID da conta existente ou None
    """
    # Busca categorias do usuário
    categorias = {c.nome.upper(): c for c in Categoria.objects.filter(usuario=usuario)}

    # Busca contas existentes para verificar duplicados
    contas_existentes = {
        (c.data_prevista, c.descricao.upper(), c.valor): c
        for c in Conta.objects.filter(usuario=usuario)
    }

    for registro in dados:
        cat_nome = registro["categoria_nome"].upper()

        # Verifica categoria
        if cat_nome in categorias:
            registro["categoria_id"] = categorias[cat_nome].id
            registro["categoria_existe"] = True
        elif cat_nome == "SEM CATEGORIA" or not cat_nome:
            registro["categoria_id"] = None
            registro["categoria_existe"] = True
        else:
            registro["categoria_id"] = None
            registro["categoria_existe"] = False

        # Verifica duplicado
        chave = (registro["data"], registro["descricao"].upper(), registro["valor"])
        if chave in contas_existentes:
            registro["existe_duplicado"] = True
            registro["conta_existente_id"] = contas_existentes[chave].id
        else:
            registro["existe_duplicado"] = False
            registro["conta_existente_id"] = None

    return dados


@transaction.atomic
def importar_dados_relatorio(dados: list, usuario, modo: str = "criar") -> dict:
    """
    Importa os dados do relatório no banco de dados.

    Args:
        dados: Lista de registros a importar (já validados)
        usuario: Usuário dono dos registros
        modo: 'criar' para criar novos, 'sobrescrever' para atualizar existentes

    Returns:
        dict com keys:
            - 'criados': quantidade de registros criados
            - 'atualizados': quantidade de registros atualizados
            - 'ignorados': quantidade de registros ignorados
            - 'erro': mensagem de erro se houver
    """
    criados = 0
    atualizados = 0
    ignorados = 0

    try:
        for registro in dados:
            # Se existe duplicado
            if registro.get("existe_duplicado"):
                if modo == "sobrescrever":
                    # Atualiza registro existente
                    conta = Conta.objects.get(id=registro["conta_existente_id"])
                    conta.tipo = registro["tipo"]
                    conta.descricao = registro["descricao"]
                    conta.valor = registro["valor"]
                    conta.categoria_id = registro.get("categoria_id")
                    conta.transacao_realizada = registro["realizada"]
                    if registro["realizada"] and not conta.data_realizacao:
                        conta.data_realizacao = registro["data"]
                    conta.save()
                    atualizados += 1
                else:
                    # Ignora duplicado
                    ignorados += 1
                continue

            # Cria novo registro
            Conta.objects.create(
                usuario=usuario,
                tipo=registro["tipo"],
                descricao=registro["descricao"],
                valor=registro["valor"],
                data_prevista=registro["data"],
                categoria_id=registro.get("categoria_id"),
                transacao_realizada=registro["realizada"],
                data_realizacao=registro["data"] if registro["realizada"] else None,
            )
            criados += 1

        return {
            "criados": criados,
            "atualizados": atualizados,
            "ignorados": ignorados,
            "erro": None,
        }

    except Exception as e:
        return {
            "criados": criados,
            "atualizados": atualizados,
            "ignorados": ignorados,
            "erro": str(e),
        }
