"""Comando Customizado do Django para Sincronização de Cotações a Mercado.

Interface CLI que consome a API do TradingView via scanner para atualizar as cotações
atuais de todos os ativos de renda variável custodiados no sistema.
"""

from django.core.management.base import BaseCommand
from investimento.services import atualizar_cotacoes


class Command(BaseCommand):
    """Classe executora do comando CLI de varredura e atualização de cotações a mercado.
    """
    help = "Atualiza cotações de ativos via TradingView Screener"

    def handle(self, *args, **options):
        """Gatilha a consulta e atualização em lote de cotações no TradingView Screener.

        Registra as cotações criadas com sucesso ou imprime erros ocorridos no canal stdout.

        Args:
            *args: Argumentos posicionais.
            **options: Opções do terminal.
        """
        self.stdout.write("Iniciando atualização de cotações...")
        count, errors = atualizar_cotacoes()

        for err in errors:
            self.stdout.write(self.style.ERROR(err))

        self.stdout.write(
            self.style.SUCCESS(f"Atualização concluída. {count} cotações salvas.")
        )

