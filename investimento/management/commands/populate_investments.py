from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from investimento.signals import criar_classificacao_padrao

User = get_user_model()


class Command(BaseCommand):
    help = "Populate default investment classes for all users"

    def handle(self, *args, **options):
        users = User.objects.all()
        for user in users:
            self.stdout.write(f"Processing user: {user.username}")
            # We call the signal handler manually
            # But we need to ensure we don't duplicate if they already have them?
            # The signal does strictly create(). If run twice, it errors or creates duplicates?
            # The models have unique_together constraint. So it will error if exists.
            # We wrap in try/except or just run it and let unique constraints handle it (ignoring or checking).

            # Simple check: if has no classes?
            if user.classes_ativos.exists():
                self.stdout.write("  User already has classes. Skipping.")
                continue

            criar_classificacao_padrao(sender=User, instance=user, created=True)
            self.stdout.write("  Classes created.")
