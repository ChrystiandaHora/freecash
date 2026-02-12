from django.core.management.base import BaseCommand
from investimento.services import atualizar_cotacoes


class Command(BaseCommand):
    help = "Atualiza cotações de ativos via Yahoo Finance"

    def handle(self, *args, **options):
        self.stdout.write("Iniciando atualização de cotações...")
        count, errors = atualizar_cotacoes()

        for err in errors:
            self.stdout.write(self.style.ERROR(err))

        self.stdout.write(
            self.style.SUCCESS(f"Atualização concluída. {count} cotações salvas.")
        )
