import pandas as pd
from django.db import transaction
from core.models import LogImportacao
from core.services.import_planilha import importar_backup_excel, importar_planilha_excel


def eh_backup_moderno(xls: pd.ExcelFile) -> bool:
    abas_modernas = {
        "transacoes",
        "categorias",
        "formas_pagamento",
        "contas_pagar",
        "resumo_mensal",
        "config_usuario",
    }

    return any(aba.lower() in abas_modernas for aba in xls.sheet_names)


def eh_planilha_legado(xls: pd.ExcelFile) -> bool:
    # procura abas com nomes de anos, ex: 2024, 2025
    for aba in xls.sheet_names:
        try:
            ano = int(aba)
            if 1900 < ano < 2100:
                return True
        except Exception:
            pass
    return False


@transaction.atomic
def importar_planilha_unificada(arquivo, usuario):
    xls = pd.ExcelFile(arquivo)

    try:
        # É backup moderno?
        if eh_backup_moderno(xls):
            importar_backup_excel(arquivo, usuario)

            LogImportacao.objects.create(
                usuario=usuario,
                tipo=LogImportacao.TIPO_BACKUP,
                sucesso=True,
                mensagem="Backup restaurado com sucesso.",
            )
            return True

        # É planilha legado?
        if eh_planilha_legado(xls):
            importar_planilha_excel(arquivo, usuario)

            LogImportacao.objects.create(
                usuario=usuario,
                tipo=LogImportacao.TIPO_LEGADO,
                sucesso=True,
                mensagem="Planilha legado importada com sucesso.",
            )
            return True

        # Arquivo não reconhecido
        raise ValueError(
            "O arquivo enviado não corresponde a um backup nem ao formato legado."
        )

    except Exception as e:
        # REGISTRA O ERRO
        LogImportacao.objects.create(
            usuario=usuario,
            tipo="backup",
            sucesso=False,
            mensagem=str(e),
        )
        raise
