"""
Serviço para parsing de extratos bancários em PDF.
"""

import re
from datetime import datetime
from decimal import Decimal
from typing import List, Dict, Any
import pdfplumber


def parse_pdf_generico(pdf_path: str) -> List[Dict[str, Any]]:
    """
    Parser genérico para extratos bancários.
    Tenta identificar padrões comuns de data, descrição e valor.

    Returns:
        Lista de dicionários com: data, descricao, valor, tipo
    """
    linhas = []

    # Padrões comuns de data
    date_patterns = [
        r"(\d{2}/\d{2}/\d{4})",  # DD/MM/YYYY
        r"(\d{2}/\d{2}/\d{2})",  # DD/MM/YY
        r"(\d{2}-\d{2}-\d{4})",  # DD-MM-YYYY
    ]

    # Padrão de valor monetário
    valor_pattern = r"R?\$?\s*(-?\d{1,3}(?:\.\d{3})*,\d{2})"

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if not text:
                continue

            for line in text.split("\n"):
                linha_data = _extrair_linha(line, date_patterns, valor_pattern)
                if linha_data:
                    linhas.append(linha_data)

    return linhas


def parse_pdf_nubank(pdf_path: str) -> List[Dict[str, Any]]:
    """
    Parser específico para extratos do Nubank.
    """
    linhas = []

    # Nubank usa formato: DD MMM - Descrição - Valor
    date_pattern = r"(\d{2}\s+\w{3})"
    valor_pattern = r"R?\$?\s*(-?\d{1,3}(?:\.\d{3})*,\d{2})"

    meses = {
        "jan": 1,
        "fev": 2,
        "mar": 3,
        "abr": 4,
        "mai": 5,
        "jun": 6,
        "jul": 7,
        "ago": 8,
        "set": 9,
        "out": 10,
        "nov": 11,
        "dez": 12,
    }

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if not text:
                continue

            for line in text.split("\n"):
                # Tenta extrair data no formato Nubank
                date_match = re.search(date_pattern, line, re.IGNORECASE)
                valor_match = re.search(valor_pattern, line)

                if date_match and valor_match:
                    try:
                        # Parse da data
                        date_str = date_match.group(1)
                        parts = date_str.split()
                        dia = int(parts[0])
                        mes_nome = parts[1].lower()[:3]
                        mes = meses.get(mes_nome, 1)
                        ano = datetime.now().year
                        data = datetime(ano, mes, dia).date()

                        # Parse do valor
                        valor_str = valor_match.group(1)
                        valor_str = valor_str.replace(".", "").replace(",", ".")
                        valor = abs(Decimal(valor_str))

                        # Descrição
                        descricao = line
                        descricao = re.sub(date_pattern, "", descricao)
                        descricao = re.sub(valor_pattern, "", descricao)
                        descricao = descricao.strip(" -")

                        # Tipo
                        is_negativo = valor_match.group(1).startswith("-")
                        tipo = "D" if is_negativo else "C"

                        if descricao and valor > 0:
                            linhas.append(
                                {
                                    "data": data,
                                    "descricao": descricao[:500],
                                    "valor": valor,
                                    "tipo": tipo,
                                }
                            )
                    except (ValueError, IndexError):
                        continue

    return linhas


def _extrair_linha(
    line: str, date_patterns: list, valor_pattern: str
) -> Dict[str, Any] | None:
    """
    Tenta extrair dados de uma linha de texto.
    """
    data = None

    # Tentar encontrar data
    for pattern in date_patterns:
        match = re.search(pattern, line)
        if match:
            date_str = match.group(1)
            # Tenta diferentes formatos
            for fmt in ["%d/%m/%Y", "%d/%m/%y", "%d-%m-%Y"]:
                try:
                    data = datetime.strptime(date_str, fmt).date()
                    break
                except ValueError:
                    continue
            break

    if not data:
        return None

    # Tentar encontrar valor
    valor_match = re.search(valor_pattern, line)
    if not valor_match:
        return None

    try:
        valor_str = valor_match.group(1)
        is_negativo = valor_str.startswith("-")
        valor_str = valor_str.replace(".", "").replace(",", ".").replace("-", "")
        valor = Decimal(valor_str)

        if valor <= 0:
            return None

        # Limpar descrição
        descricao = line
        for pattern in date_patterns:
            descricao = re.sub(pattern, "", descricao)
        descricao = re.sub(valor_pattern, "", descricao)
        descricao = descricao.strip(" -|")

        if not descricao or len(descricao) < 3:
            return None

        tipo = "D" if is_negativo else "C"

        return {
            "data": data,
            "descricao": descricao[:500],
            "valor": valor,
            "tipo": tipo,
        }
    except (ValueError, TypeError):
        return None


def processar_pdf(pdf_path: str, banco: str = "generico") -> List[Dict[str, Any]]:
    """
    Processa um PDF de extrato bancário.

    Args:
        pdf_path: Caminho para o arquivo PDF
        banco: Tipo de banco (nubank, generico, etc)

    Returns:
        Lista de transações extraídas
    """
    parsers = {
        "nubank": parse_pdf_nubank,
        "generico": parse_pdf_generico,
    }

    parser = parsers.get(banco, parse_pdf_generico)
    return parser(pdf_path)
