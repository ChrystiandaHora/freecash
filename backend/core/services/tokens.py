"""Geradores de token para os fluxos de identidade enviados por e-mail.

Nenhum destes tokens é armazenado. Todos são HMAC assinados com a `SECRET_KEY`,
carregando o instante de emissão, no mesmo desenho que o Django usa para
redefinição de senha. A alternativa — uma tabela de tokens — custaria migration,
código de "já utilizado" e uma rotina periódica de limpeza que exigiria o
agendador que o projeto não possui.

O ponto central do desenho está em `_make_hash_value`: os campos incluídos no hash
determinam quando o token morre. Ao incluir um dado que a própria ação altera, o
token passa a ser de uso único sem precisar registrar nada em lugar algum.
"""

from django.conf import settings
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.utils.crypto import constant_time_compare
from django.utils.http import base36_to_int


class EmailVerificationTokenGenerator(PasswordResetTokenGenerator):
    """Gera e valida tokens de confirmação de endereço de e-mail.

    O hash inclui o e-mail atual e o estado de verificação: concluir a verificação
    invalida o token na hora, tornando-o de uso único sem tabela de controle, e trocar o
    endereço derruba qualquer link pendente do anterior.

    O hash **não** inclui a senha, diferente da redefinição: confirmar o e-mail não deve
    parar de funcionar porque o usuário trocou a senha enquanto a mensagem estava na
    caixa de entrada.
    """

    key_salt = "core.services.tokens.EmailVerificationTokenGenerator"

    def _make_hash_value(self, user, timestamp: int) -> str:
        """Compõe o valor assinado do token.

        Args:
            timestamp: Instante de emissão, em segundos desde a época interna.

        Returns:
            str: Valor a ser assinado, combinando identidade, endereço e estado.
        """
        verificado = bool(
            getattr(getattr(user, "config", None), "email_verificado", False)
        )
        return f"{user.pk}{user.email}{verificado}{timestamp}"

    def _timeout_segundos(self) -> int:
        """Informa a janela de validade deste tipo de token.

        Returns:
            int: Validade em segundos, vinda de `EMAIL_VERIFICATION_TIMEOUT`.
        """
        return settings.EMAIL_VERIFICATION_TIMEOUT

    def check_token(self, user, token: str) -> bool:
        """Valida o token respeitando a janela própria de verificação de e-mail.

        A implementação do Django compara a idade do token com
        `settings.PASSWORD_RESET_TIMEOUT`, que aqui governa apenas a redefinição de
        senha. Confirmar uma conta é menos urgente que recuperar o acesso a ela, e
        merece uma janela mais longa — daí a reimplementação.

        A verificação de integridade percorre `secret_fallbacks` da mesma forma que
        o Django, para que uma rotação de `SECRET_KEY` não invalide de imediato os
        links já enviados.

        Returns:
            bool: True se o token é válido, íntegro e ainda está no prazo.
        """
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
    """Gera e valida tokens de confirmação de **troca** de endereço de e-mail.

    Separado de `EmailVerificationTokenGenerator` por correção, não organização: aquele
    assina o endereço vigente, e aqui o que precisa ser provado é a posse do endereço
    **pendente**. Reaproveitar o outro deixaria um link de verificação comum confirmar
    uma troca de e-mail, e vice-versa.

    O hash inclui `email_pendente` e o `email` atual, então concluir a troca invalida o
    token na hora (uso único, sem tabela de controle) e pedir uma nova troca derruba o
    link anterior.
    """

    key_salt = "core.services.tokens.EmailChangeTokenGenerator"

    def _make_hash_value(self, user, timestamp: int) -> str:
        """Compõe o valor assinado do token.

        Args:
            timestamp: Instante de emissão, em segundos desde a época interna.

        Returns:
            str: Valor a ser assinado, ligando a identidade ao par de endereços.
        """
        pendente = getattr(getattr(user, "config", None), "email_pendente", "") or ""
        return f"{user.pk}{user.email}{pendente}{timestamp}"

    def _timeout_segundos(self) -> int:
        """Informa a janela de validade deste tipo de token.

        Returns:
            int: Validade em segundos, a mesma da verificação de conta.
        """
        return settings.EMAIL_VERIFICATION_TIMEOUT

    check_token = EmailVerificationTokenGenerator.check_token


email_change_token = EmailChangeTokenGenerator()
