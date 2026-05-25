"""Serviço de Processamento e Extração de Extratos Bancários (PDF Parser).

Este módulo utiliza a biblioteca `pdfplumber` e expressões regulares otimizadas
para abrir, decodificar e ler arquivos PDF de extratos bancários, mapeando dados
de data, descrição de despesas/receitas, valor monetário e tipo (Crédito/Débito)
para fins de conciliação.
"""

import re
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import List, Dict, Any
import pdfplumber


def parse_pdf_generico(pdf_path: str) -> List[Dict[str, Any]]:
    """Parser genérico de fallback para extratos bancários simples.

    Realiza uma varredura sequencial linha a linha no texto do arquivo PDF
    tentando localizar e decodificar os formatos mais habituais de datas e
    valores monetários brasileiros.

    Args:
        pdf_path (str): Caminho absoluto ou relativo do arquivo PDF no disco.

    Returns:
        List[Dict[str, Any]]: Lista contendo dicionários estruturados de transações,
        onde cada um possui as chaves: 'data' (date), 'descricao' (str), 'valor' (Decimal) e 'tipo' (str).
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
    """Parser altamente especializado no padrão de faturas e extratos em PDF do Nubank.

    Nubank usa a sintaxe característica de data abreviada sem ano (ex: '20 MAI')
    no início da linha. O parser calcula o ano dinamicamente e mapeia as saídas.

    Args:
        pdf_path (str): Caminho para o extrato em formato PDF.

    Returns:
        List[Dict[str, Any]]: Lista de dicionários de transações decodificadas.
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
    """Extrai informações estruturadas de uma única linha de texto bruto de extrato.

    Args:
        line (str): A string da linha extraída do PDF.
        date_patterns (list): Lista de expressões regulares de padrões de data.
        valor_pattern (str): Expressão regular do padrão monetário.

    Returns:
        Dict[str, Any] | None: Transação estruturada ou None caso a linha não corresponda aos padrões mínimos.
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


def parse_layout_colunas(pdf_path: str) -> List[Dict[str, Any]]:
    """Parser avançado para extratos com layout de colunas tabulares (ex: Santander).

    Procura por linhas estruturadas na ordem clássica contendo data (DD/MM),
    descrição e valor monetário com cifrão no final. Resolve anos com base na
    data de vencimento da fatura presente na capa do extrato.

    Args:
        pdf_path (str): Caminho para o extrato em formato PDF.

    Returns:
        List[Dict[str, Any]]: Lista de dicionários de transações.
    """
    linhas = []

    # Regex para capturar data DD/MM e valor monetário R$ X.XXX,XX
    line_pattern = (
        r"(?:\d+\s+)?(\d{2}/\d{2})\s+(.+?)\s+(?:R\$\s*)?(\d{1,3}(?:\.\d{3})*,\d{2})"
    )

    with pdfplumber.open(pdf_path) as pdf:
        # Tenta achar ano de vencimento na primeira página
        ano_fatura = datetime.now().year
        first_page_text = pdf.pages[0].extract_text()
        if first_page_text:
            vencimento_match = re.search(
                r"Vencimento\s+(\d{2}/\d{2}/(\d{4}))", first_page_text
            )
            if vencimento_match:
                ano_fatura = int(vencimento_match.group(2))

        for page in pdf.pages:
            text = page.extract_text()
            if not text:
                continue

            for line in text.split("\n"):
                match = re.search(line_pattern, line)
                if match:
                    try:
                        data_str = match.group(1)
                        descricao_raw = match.group(2)
                        valor_str = match.group(3)

                        # Limpa descrição
                        descricao = descricao_raw.strip()

                        # Parse Valor
                        valor_str_clean = valor_str.replace(".", "").replace(",", ".")
                        valor = Decimal(valor_str_clean)

                        # Parse Data
                        dia, mes = map(int, data_str.split("/"))

                        # Lógica de Ano:
                        ano_compra = ano_fatura

                        # Simplificação segura:
                        data = datetime(ano_compra, mes, dia).date()

                        # Se a data ficar no futuro em relação ao processamento
                        if data > datetime.now().date() + timedelta(days=30):
                            data = data.replace(year=data.year - 1)

                        linhas.append(
                            {
                                "data": data,
                                "descricao": descricao[:500],
                                "valor": valor,
                                "tipo": "D",  # Fatura de cartão é sempre débito/despesa
                            }
                        )
                    except (ValueError, InvalidOperation):
                        continue

    return list(linhas)


def processar_pdf(pdf_path: str, banco: str = "generico") -> List[Dict[str, Any]]:
    """Função controladora que coordena o processamento do extrato em PDF.

    Se o banco for especificado como 'generico', ela executa uma cascata de
    fallback testando seqüencialmente o parser genérico, o parser de colunas
    e o parser do Nubank para garantir a maior taxa de sucesso de leitura possível.

    Args:
        pdf_path (str): Caminho físico do arquivo no servidor.
        banco (str, optional): Instituição de origem ('nubank', 'santander', 'generico'). Defaults to "generico".

    Returns:
        List[Dict[str, Any]]: Lista consolidada de transações encontradas.
    """
    parsers = {
        "nubank": parse_pdf_nubank,
        "santander": parse_layout_colunas,
        "generico": parse_pdf_generico,
    }

    if banco == "generico":
        # Estratégia de Fallback: Tenta um por um até achar linhas
        # 1. Tenta parser genérico
        linhas = parse_pdf_generico(pdf_path)
        if linhas:
            return linhas

        # 2. Tenta parser de colunas
        linhas = parse_layout_colunas(pdf_path)
        if linhas:
            return linhas

        # 3. Tenta Nubank
        linhas = parse_pdf_nubank(pdf_path)
        return linhas

    parser = parsers.get(banco, parse_pdf_generico)
    return parser(pdf_path)

