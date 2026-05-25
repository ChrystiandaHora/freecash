"""Comando Customizado do Django para Atualização de Snapshots Históricos.

Varre linearmente todas as carteiras ativas consolidando e gravando a rentabilidade
e custos diários históricos para exibição do gráfico de evolução patrimonial no React.
"""

from django.core.management.base import BaseCommand

from investimento.services.carteira_historico_service import atualizar_historico_para_todos


class Command(BaseCommand):
    """Classe que encapsula o gatilho CLI para atualização de snapshots da carteira.
    """
    help = "Gera/atualiza o histórico (snapshots) de performance da carteira"

    def handle(self, *args, **options):
        """Invoca o serviço de snapshots históricos consolidando o patrimônio diário dos usuários.

        Args:
            *args: Argumentos posicionais.
            **options: Opções de comando.
        """
        self.stdout.write("Atualizando histórico da carteira...")
        res = atualizar_historico_para_todos()
        self.stdout.write(
            self.style.SUCCESS(
                f"Concluído. Usuários: {res['users']}, criados: {res['created']}, atualizados: {res['updated']}."
            )
        )
