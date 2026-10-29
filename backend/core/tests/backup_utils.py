"""Atalhos compartilhados pelos testes de backup."""

import io

from core.services.export_service import gerar_backup_zip
from core.services.import_service import ler_backup_zip

SENHA_DE_TESTE = "senha-de-teste-bem-longa"


def exportar_e_ler(usuario) -> dict:
    """Gera o ZIP do usuário e o lê de volta, pelo mesmo caminho da importação real.

    Returns:
        dict: O conteúdo de `dados.json`, pronto para `restaurar_dados_usuario`.
    """
    return ler_backup_zip(io.BytesIO(gerar_backup_zip(usuario, SENHA_DE_TESTE)), SENHA_DE_TESTE)
