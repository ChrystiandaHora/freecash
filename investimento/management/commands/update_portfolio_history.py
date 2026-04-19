from django.core.management.base import BaseCommand

from investimento.services.carteira_historico_service import atualizar_historico_para_todos


class Command(BaseCommand):
    help = "Gera/atualiza o histórico (snapshots) de performance da carteira"

    def handle(self, *args, **options):
        self.stdout.write("Atualizando histórico da carteira...")
        res = atualizar_historico_para_todos()
        self.stdout.write(
            self.style.SUCCESS(
                f"Concluído. Usuários: {res['users']}, criados: {res['created']}, atualizados: {res['updated']}."
            )
        )

