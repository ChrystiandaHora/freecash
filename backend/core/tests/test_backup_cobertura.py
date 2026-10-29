"""Garante que todo modelo do projeto esteja no backup ou fora dele por decisão explícita.

A descoberta automática de `get_backupable_models` só enxerga modelos com `usuario` e
`uuid`. Modelos que pertencem ao usuário por outro caminho (via meta, ativo ou extrato)
precisam de exportação manual — e esquecê-la não dá erro nenhum: a restauração devolve a
base sem os registros. Este teste transforma esse esquecimento em falha.
"""

from django.apps import apps
from django.contrib.auth.models import User
from django.test import TestCase

from core.services.export_service import coletar_dados_usuario

APPS_DO_PROJETO = ("core", "investimento")

# Cada exclusão diz por que o modelo não é dado do usuário.
FORA_DO_BACKUP = {
    "core.LogAcaoAdmin": "auditoria das ações da administração sobre a conta, não do usuário",
}


class CoberturaDoBackupTests(TestCase):
    """Todo modelo concreto dos apps do projeto precisa estar classificado."""

    def test_todo_modelo_do_projeto_esta_no_backup_ou_excluido(self):
        usuario = User.objects.create_user(username="cobertura", password="senha-forte-123")
        dados = coletar_dados_usuario(usuario)["data"]

        no_backup = {
            f"{app_label}.{nome_modelo}"
            for app_label, modelos in dados.items()
            for nome_modelo in modelos
        }
        faltando = [
            f"{app_label}.{modelo.__name__}"
            for app_label in APPS_DO_PROJETO
            for modelo in apps.get_app_config(app_label).get_models()
            if f"{app_label}.{modelo.__name__}" not in no_backup | FORA_DO_BACKUP.keys()
        ]

        self.assertEqual(
            faltando,
            [],
            "Modelos fora do backup sem exclusão explícita (ver docs/backup.md).",
        )
