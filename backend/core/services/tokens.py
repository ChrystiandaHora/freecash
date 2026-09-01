"""Geradores de tokens HMAC stateless para fluxos de verificação e troca de e-mail.

Os tokens embutem o estado relevante no hash, tornando-se de uso único automaticamente
quando a ação correspondente é concluída, sem necessidade de tabela em banco de dados.
"""

from django.conf import settings
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.utils.crypto import constant_time_compare
from django.utils.http import base36_to_int


class EmailVerificationTokenGenerator(PasswordResetTokenGenerator):
    """Gera e valida tokens de uso único para confirmação de e-mail."""

    key_salt = "core.services.tokens.EmailVerificationTokenGenerator"

    def _make_hash_value(self, user, timestamp: int) -> str:
        verificado = bool(
            getattr(getattr(user, "config", None), "email_verificado", False)
        )
        return f"{user.pk}{user.email}{verificado}{timestamp}"

    def _timeout_segundos(self) -> int:
        return settings.EMAIL_VERIFICATION_TIMEOUT

    def check_token(self, user, token: str) -> bool:
        """Valida o token respeitando a janela configurada em EMAIL_VERIFICATION_TIMEOUT."""
        if not (user and token):
            return False

        try:
            ts_b36, _ = token.split("-")
            ts = base36_to_int(ts_b36)
        except ValueError:
            return False

        for secret in [self.secret, *self.secret_fallbacks]:
            if constant_time_compare(
                self._make_token_with_timestamp(user, ts, secret), token
            ):
                break
        else:
            return False

        if (self._num_seconds(self._now()) - ts) > self._timeout_segundos():
            return False

        return True


email_verification_token = EmailVerificationTokenGenerator()


class EmailChangeTokenGenerator(PasswordResetTokenGenerator):
    """Gera e valida tokens de confirmação de alteração de e-mail (valida email_pendente)."""

    key_salt = "core.services.tokens.EmailChangeTokenGenerator"

    def _make_hash_value(self, user, timestamp: int) -> str:
        pendente = getattr(getattr(user, "config", None), "email_pendente", "") or ""
        return f"{user.pk}{user.email}{pendente}{timestamp}"

    def _timeout_segundos(self) -> int:
        return settings.EMAIL_VERIFICATION_TIMEOUT

    check_token = EmailVerificationTokenGenerator.check_token


email_change_token = EmailChangeTokenGenerator()

