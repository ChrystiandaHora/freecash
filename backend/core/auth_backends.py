"""Backend de autenticação que aceita e-mail ou nome de usuário.

O produto nasceu com login por `username`, mas o e-mail é o identificador que as
pessoas esperam usar e o único que permite recuperar o acesso. Trocar
`AUTH_USER_MODEL` por um modelo com `USERNAME_FIELD = "email"` foi descartado: com
migrations aplicadas e chave estrangeira para o usuário em quase todo modelo, o
Django não suporta a troca — e `auth.User` sempre teve campo `email`.

Só é seguro porque o e-mail é único: `core/0002_email_unico_case_insensitive` cria
um índice único sobre `LOWER(email)`. Sem isso, resolver um endereço para um
usuário seria ambíguo.
"""

from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend


class EmailOuUsernameBackend(ModelBackend):
    """Autentica pelo e-mail e, se não houver correspondência, pelo nome de usuário.

    O fallback por `username` não é conveniência: é o que mantém funcionando as
    contas criadas antes desta mudança — inclusive o superusuário, que pode não ter
    e-mail cadastrado.
    """

    def authenticate(self, request, username=None, password=None, **kwargs):
        """Resolve o identificador informado e valida a senha.

        Returns:
            User | None: O usuário autenticado, ou None se as credenciais não conferem.
        """
        User = get_user_model()
        identificador = username or kwargs.get("email") or kwargs.get(
            User.USERNAME_FIELD
        )

        if not identificador or not password:
            return None

        identificador = identificador.strip()

        usuario = None
        if "@" in identificador:
            # O índice único garante no máximo um resultado; `filter().first()`
            # evita depender disso e nunca levanta MultipleObjectsReturned.
            usuario = (
                User.objects.filter(email__iexact=identificador)
                .order_by("pk")
                .first()
            )

        if usuario is None:
            usuario = (
                User.objects.filter(username__iexact=identificador)
                .order_by("pk")
                .first()
            )

        if usuario is None:
            # Executa o hash de uma senha mesmo sem usuário encontrado, para que o
            # tempo de resposta não revele se o identificador existe.
            User().set_password(password)
            return None

        if usuario.check_password(password) and self.user_can_authenticate(usuario):
            return usuario

        return None
