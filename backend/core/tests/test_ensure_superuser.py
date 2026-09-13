"""Automated tests for ensure_superuser management command."""

import io
import os
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase

from core.models import ConfigUsuario

User = get_user_model()


class EnsureSuperuserTestCase(TestCase):
    """Verifies creation and elevation of admin accounts via ensure_superuser command."""

    def test_skips_gracefully_when_credentials_not_set(self):
        """When credentials are not supplied, command exits cleanly without modifying database."""
        out = io.StringIO()
        with patch.dict(os.environ, {}, clear=True):
            call_command("ensure_superuser", stdout=out)
        self.assertIn("not configured", out.getvalue())
        self.assertEqual(User.objects.filter(is_staff=True).count(), 0)

    def test_provisions_new_superuser_successfully(self):
        """Creates a new user with staff, superuser, active status and verified email."""
        out = io.StringIO()
        env = {
            "ADMIN_USERNAME": "opsadmin",
            "ADMIN_EMAIL": "ops@freecash.local",
            "ADMIN_PASSWORD": "ProductionSecurePassword2026!",
        }
        with patch.dict(os.environ, env, clear=True):
            call_command("ensure_superuser", stdout=out)

        user = User.objects.filter(username="opsadmin").first()
        self.assertIsNotNone(user)
        self.assertTrue(user.is_staff)
        self.assertTrue(user.is_superuser)
        self.assertTrue(user.is_active)
        self.assertEqual(user.email, "ops@freecash.local")
        self.assertTrue(user.check_password("ProductionSecurePassword2026!"))

        config = ConfigUsuario.objects.get(usuario=user)
        self.assertTrue(config.email_verificado)
        self.assertIn("successfully created", out.getvalue())

    def test_elevates_existing_regular_user(self):
        """Elevates an existing regular user account to superuser privileges."""
        user = User.objects.create_user(
            username="manager", email="manager@freecash.local", password="InitialPassword123!"
        )
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)

        out = io.StringIO()
        call_command(
            "ensure_superuser",
            username="manager",
            password="DummyPassword",
            stdout=out,
        )

        user.refresh_from_db()
        self.assertTrue(user.is_staff)
        self.assertTrue(user.is_superuser)
        self.assertTrue(user.is_active)
        self.assertTrue(user.check_password("DummyPassword"))
        self.assertIn("ensured as active superuser", out.getvalue())

    def test_syncs_updated_password_for_existing_superuser(self):
        """When the password in environment changes, existing superuser password is synchronized."""
        user = User.objects.create_user(
            username="chief", email="chief@freecash.local", password="OldPassword123!"
        )
        user.is_staff = True
        user.is_superuser = True
        user.save()

        env = {
            "ADMIN_USERNAME": "chief",
            "ADMIN_PASSWORD": "NewRotatedPassword456!",
        }
        with patch.dict(os.environ, env, clear=True):
            call_command("ensure_superuser")

        user.refresh_from_db()
        self.assertTrue(user.check_password("NewRotatedPassword456!"))
        self.assertFalse(user.check_password("OldPassword123!"))
