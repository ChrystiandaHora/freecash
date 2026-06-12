"""Serviço de Consulta de Cotações de Fundos via Dados Abertos da CVM.

Este módulo implementa o download e parsing dos informes diários de fundos de investimento
publicados pela CVM (Comissão de Valores Mobiliários), permitindo atualizar as cotações
de ativos multimercado, cambiais, de ações e de renda fixa de forma automatizada por CNPJ.
"""

import urllib.request
import zipfile
import io
import csv
from datetime import datetime, date
from decimal import Decimal
from typing import Iterable


def format_cnpj(cnpj: str) -> str:
    """Formata um CNPJ puramente numérico no padrão oficial brasileiro (XX.XXX.XXX/XXXX-XX).

    Args:
        cnpj (str): CNPJ limpo apenas com dígitos (ex: "12987743000186").

    Returns:
        str: CNPJ formatado ou o valor original se não tiver 14 caracteres.
    """
    if len(cnpj) != 14:
        return cnpj
    return f"{cnpj[:2]}.{cnpj[2:5]}.{cnpj[5:8]}/{cnpj[8:12]}-{cnpj[12:]}"


def fetch_cvm_quotes(cnpjs: Iterable[str], *, timeout_seconds: int = 15) -> dict[str, tuple[Decimal, date]]:
    """Baixa o arquivo de cotações mensais da CVM e filtra as cotações mais recentes para os CNPJs indicados.

    Aplica um fallback automático de mês: caso o arquivo do mês corrente não seja encontrado
    (ex: início do mês em que a CVM ainda não gerou o relatório), tenta baixar o do mês anterior.

    Args:
        cnpjs (Iterable[str]): Lista de CNPJs limpos (apenas números).
        timeout_seconds (int, optional): Timeout da requisição HTTP. Defaults to 15.

    Returns:
        dict[str, tuple[Decimal, date]]: Dicionário mapeando CNPJ limpo -> (Cotação Decimal, Data do Fechamento).
    """
    clean_cnpjs = [c for c in cnpjs if c]
    if not clean_cnpjs:
        return {}

    # Mapeamento CNPJ formatado -> CNPJ limpo
    cnpj_map = {format_cnpj(c): c for c in clean_cnpjs}

    hoje = datetime.today()
    # Tenta o mês atual e o mês anterior como fallback
    meses_tentativas = [
        (hoje.year, hoje.month),
        (hoje.year - 1 if hoje.month == 1 else hoje.year, 12 if hoje.month == 1 else hoje.month - 1)
    ]

    zip_data = None
    for ano, mes in meses_tentativas:
        url = f"https://dados.cvm.gov.br/dados/FI/DOC/INF_DIARIO/DADOS/inf_diario_fi_{ano}{mes:02d}.zip"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (compatible; freecash/1.0)'})
        try:
            with urllib.request.urlopen(req, timeout=timeout_seconds) as resp:
                if resp.status == 200:
                    zip_data = resp.read()
                    break
        except Exception:
            continue

    if not zip_data:
        raise RuntimeError("Não foi possível conectar ou baixar os dados do portal da CVM (tempo limite ou arquivo indisponível).")

    results: dict[str, tuple[Decimal, date]] = {}

    try:
        with zipfile.ZipFile(io.BytesIO(zip_data)) as z:
            csv_name = z.namelist()[0]
            with z.open(csv_name) as f:
                # O arquivo da CVM é codificado em utf-8 ou iso-8859-1 e delimitado por ponto e vírgula (;)
                text_stream = io.TextIOWrapper(f, encoding='utf-8')
                reader = csv.DictReader(text_stream, delimiter=';')
                
                for row in reader:
                    cnpj_fundo = row.get('CNPJ_FUNDO_CLASSE')
                    if cnpj_fundo in cnpj_map:
                        clean_cnpj = cnpj_map[cnpj_fundo]
                        dt_comptc_str = row.get('DT_COMPTC')
                        vl_quota_str = row.get('VL_QUOTA')

                        if not dt_comptc_str or not vl_quota_str:
                            continue

                        try:
                            dt_comptc = datetime.strptime(dt_comptc_str, "%Y-%m-%d").date()
                            vl_quota = Decimal(vl_quota_str)
                            
                            # Atualiza apenas se for uma data mais recente para este CNPJ
                            if clean_cnpj not in results or dt_comptc > results[clean_cnpj][1]:
                                results[clean_cnpj] = (vl_quota, dt_comptc)
                        except Exception:
                            # Ignora erros individuais de linha corrompida ou valores inválidos
                            continue
    except Exception as e:
        raise RuntimeError(f"Erro ao descompactar ou processar arquivo CSV da CVM: {str(e)}") from e

    return results
