"""Management command to idempotently provision an administrative superuser.

Designed for automated container and cloud environments (Render, AWS, Fly.io, etc.)
where interactive terminal sessions are unavailable or inconvenient during CD/deploy.
Safely provisions or elevates an administrative user (is_staff and is_superuser)
from environment variables or CLI arguments.
"""

import os
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from core.models import ConfigUsuario
from core.services.criar_usuario import criar_usuario_com_ecosistema
from core.services.email_service import normalizar_email

User = get_user_model()


class Command(BaseCommand):
    """Ensures that an administrative superuser exists and is active."""

    help = (
        "Idempotently provisions or elevates a superuser account using "
        "environment variables (ADMIN_USERNAME, ADMIN_EMAIL, ADMIN_PASSWORD) "
        "or command-line arguments."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--username",
            dest="username",
            default=None,
            help="Superuser username.",
        )
        parser.add_argument(
            "--email",
            dest="email",
            default=None,
            help="Superuser email address.",
        )
        parser.add_argument(
            "--password",
            dest="password",
            default=None,
            help="Superuser password.",
        )

    def handle(self, *args, **options):
        username = (
            options.get("username")
            or os.getenv("ADMIN_USERNAME")
            or os.getenv("DJANGO_SUPERUSER_USERNAME")
            or ""
        ).strip()

        email = (
            options.get("email")
            or os.getenv("ADMIN_EMAIL")
            or os.getenv("DJANGO_SUPERUSER_EMAIL")
            or ""
        ).strip()

        password = (
            options.get("password")
            or os.getenv("ADMIN_PASSWORD")
            or os.getenv("DJANGO_SUPERUSER_PASSWORD")
            or ""
        ).strip()

        if not username or not password:
            self.stdout.write(
                self.style.WARNING(
                    "ADMIN_USERNAME or ADMIN_PASSWORD not configured. "
                    "Skipping automated superuser provisioning."
                )
            )
            return

        with transaction.atomic():
            user = User.objects.filter(username=username).first()

            if user is None:
                # Create user with initial financial ecosystem (default categories & config)
                user = criar_usuario_com_ecosistema(
                    username=username, senha=password, email=email
                )
                user.is_staff = True
                user.is_superuser = True
                user.is_active = True
                user.save(update_fields=["is_staff", "is_superuser", "is_active"])

                config, _ = ConfigUsuario.objects.get_or_create(usuario=user)
                config.email_verificado = True
                config.email_verificado_em = timezone.now()
                config.save(update_fields=["email_verificado", "email_verificado_em"])

                self.stdout.write(
                    self.style.SUCCESS(
                        f"Superuser '{username}' successfully created with active administrative privileges."
                    )
                )
            else:
                # Elevate existing account to superuser and sync credentials if changed
                has_changes = False
                if not user.is_staff:
                    user.is_staff = True
                    has_changes = True
                if not user.is_superuser:
                    user.is_superuser = True
                    has_changes = True
                if not user.is_active:
                    user.is_active = True
                    has_changes = True
                if email and user.email != normalizar_email(email):
                    user.email = normalizar_email(email)
                    has_changes = True
                if password and not user.check_password(password):
                    user.set_password(password)
                    has_changes = True

                if has_changes:
                    user.save()

                config, _ = ConfigUsuario.objects.get_or_create(usuario=user)
                if not config.email_verificado:
                    config.email_verificado = True
                    config.email_verificado_em = timezone.now()
                    config.save(update_fields=["email_verificado", "email_verificado_em"])

                self.stdout.write(
                    self.style.SUCCESS(
                        f"User '{username}' verified and ensured as active superuser."
                    )
                )
