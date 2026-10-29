"""Planilhas CSV e LEIA-ME do backup em ZIP — a parte do backup feita para pessoas.

A importação lê só o `dados.json`; estes arquivos existem para quem quer abrir os
próprios dados no Excel, Numbers ou LibreOffice, inclusive depois de sair do freecash.
Tudo é derivado do mesmo dicionário do `dados.json`, então um modelo novo no backup
ganha planilha e documentação sem mudança aqui.
"""

import csv
import io
import uuid
from datetime import date, datetime
from decimal import Decimal

from django.apps import apps
from django.core.exceptions import FieldDoesNotExist
from django.utils import timezone
from django.utils.text import slugify

# Só onde o `verbose_name_plural` do modelo não serve como nome de arquivo
NOMES_DAS_PLANILHAS = {
    "core.Conta": "lancamentos",
    "core.ConfigUsuario": "configuracoes",
    "investimento.Cotacao": "cotacoes",
    "investimento.Transacao": "transacoes-de-investimento",
    "investimento.CarteiraHistorico": "historico-das-carteiras",
}

# Campo que identifica um registro para uma pessoa, na ordem de preferência
CAMPOS_DE_ROTULO = ("nome", "ticker", "descricao", "arquivo_nome")

SUFIXO_DE_VINCULO = "_uuid"


def montar_planilhas(dados: dict) -> dict[str, str]:
    """Monta uma planilha CSV por entidade com registros.

    Returns:
        dict[str, str]: Caminho dentro do ZIP (`planilhas/<nome>.csv`) → conteúdo.
    """
    rotulos = _indice_de_rotulos(dados["data"])
    planilhas = {}
    for app_label, modelos in dados["data"].items():
        for nome_modelo, linhas in modelos.items():
            if linhas:
                caminho = f"planilhas/{_nome_da_planilha(app_label, nome_modelo)}.csv"
                planilhas[caminho] = _csv(linhas, rotulos)
    return planilhas


def montar_leia_me(dados: dict, planilhas: dict[str, str]) -> str:
    """Escreve o LEIA-ME: como abrir o ZIP, o que é cada arquivo e o que é cada coluna.

    Returns:
        str: Texto puro em português.
    """
    gerado_em = timezone.localtime().strftime("%d/%m/%Y às %H:%M")
    partes = [
        "freecash — seus dados",
        f"Gerado em {gerado_em} para {dados['metadata'].get('username', '')}.",
        "",
        "COMO ABRIR",
        "Este arquivo é um ZIP protegido com criptografia AES-256. Para abrir, use o 7-Zip",
        "ou o WinRAR (Windows), o Keka ou o The Unarchiver (macOS), ou o app Arquivos",
        "(Android), e informe a senha escolhida na exportação. O descompactador nativo do",
        "Windows e do macOS não abre esse tipo de ZIP.",
        "",
        "O QUE TEM AQUI",
        "- dados.json: todos os seus dados num só arquivo, em JSON. É ele que o freecash lê",
        "  para importar o backup de volta (Ferramentas > Importar). As relações entre",
        "  registros usam os campos terminados em _uuid.",
        "- planilhas/: uma planilha CSV por tipo de dado, para Excel, Numbers ou LibreOffice.",
        "  Separador ponto e vírgula, vírgula decimal e datas no formato AAAA-MM-DD. Ao lado",
        "  de cada coluna _uuid há uma coluna com o nome do registro referenciado.",
        "",
        "PLANILHAS",
    ]
    for app_label, modelos in dados["data"].items():
        for nome_modelo, linhas in modelos.items():
            caminho = f"planilhas/{_nome_da_planilha(app_label, nome_modelo)}.csv"
            if caminho in planilhas:
                partes.extend(_secao_da_planilha(app_label, nome_modelo, caminho, linhas))
    return "\n".join(partes) + "\n"


def _nome_da_planilha(app_label: str, nome_modelo: str) -> str:
    chave = f"{app_label}.{nome_modelo}"
    if chave in NOMES_DAS_PLANILHAS:
        return NOMES_DAS_PLANILHAS[chave]
    return slugify(apps.get_model(app_label, nome_modelo)._meta.verbose_name_plural)


def _indice_de_rotulos(data: dict) -> dict[str, str]:
    """Mapeia o UUID de cada registro do backup para o texto que o identifica."""
    rotulos = {}
    for modelos in data.values():
        for linhas in modelos.values():
            for linha in linhas:
                rotulo = next((linha[c] for c in CAMPOS_DE_ROTULO if linha.get(c)), None)
                if linha.get("uuid") and rotulo:
                    rotulos[str(linha["uuid"])] = str(rotulo)
    return rotulos


def _colunas(linhas: list[dict]) -> list[str]:
    """União das chaves das linhas, na ordem de aparição, com o rótulo após cada vínculo."""
    colunas = []
    for linha in linhas:
        for chave in linha:
            if chave in colunas:
                continue
            colunas.append(chave)
            if _eh_vinculo(chave) and _rotulo_do_vinculo(chave) not in linha:
                colunas.append(_rotulo_do_vinculo(chave))
    return colunas


def _csv(linhas: list[dict], rotulos: dict[str, str]) -> str:
    colunas = _colunas(linhas)
    saida = io.StringIO()
    escritor = csv.writer(saida, delimiter=";")
    escritor.writerow(colunas)
    for linha in linhas:
        completa = dict(linha)
        for chave, valor in linha.items():
            if _eh_vinculo(chave) and valor:
                completa.setdefault(_rotulo_do_vinculo(chave), rotulos.get(str(valor), ""))
        escritor.writerow([_celula(completa.get(coluna)) for coluna in colunas])
    # BOM: sem ele o Excel em português abre o UTF-8 com acentos quebrados
    return "﻿" + saida.getvalue()


def _celula(valor) -> str:
    if valor is None:
        return ""
    if isinstance(valor, bool):
        return "sim" if valor else "não"
    if isinstance(valor, (Decimal, float)):
        # Via Decimal para não virar notação científica (1e-05) nem perder casas
        return format(Decimal(str(valor)), "f").replace(".", ",")
    if isinstance(valor, (date, datetime)):
        return valor.isoformat()
    if isinstance(valor, uuid.UUID):
        return str(valor)
    return str(valor)


def _eh_vinculo(coluna: str) -> bool:
    return coluna.endswith(SUFIXO_DE_VINCULO) and coluna != "uuid"


def _rotulo_do_vinculo(coluna: str) -> str:
    return coluna[: -len(SUFIXO_DE_VINCULO)]


def _secao_da_planilha(app_label: str, nome_modelo: str, caminho: str, linhas: list) -> list[str]:
    modelo = apps.get_model(app_label, nome_modelo)
    total = len(linhas)
    secao = ["", f"{caminho} — {modelo._meta.verbose_name_plural} ({total} registro{'s' if total != 1 else ''})"]
    for coluna in _colunas(linhas):
        secao.append(f"  {coluna}: {_descricao_da_coluna(modelo, coluna)}")
    return secao


def _descricao_da_coluna(modelo, coluna: str) -> str:
    if coluna == "uuid":
        return "identificador único do registro"
    if _eh_vinculo(coluna):
        return f"identificador de {_nome_do_campo(modelo, _rotulo_do_vinculo(coluna))}"
    try:
        campo = modelo._meta.get_field(coluna)
    except FieldDoesNotExist:
        return coluna.replace("_", " ")
    if campo.is_relation:
        return f"nome de {campo.verbose_name}"
    return str(campo.verbose_name)


def _nome_do_campo(modelo, nome: str) -> str:
    try:
        return str(modelo._meta.get_field(nome).verbose_name)
    except FieldDoesNotExist:
        return nome.replace("_", " ")
