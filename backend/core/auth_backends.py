"""Backend de autenticação que aceita e-mail ou nome de usuário.

O sistema nasceu com login por `username` e o campo `email` sem uso. Para um
produto público, o e-mail é o identificador que as pessoas esperam usar e o único
que permite recuperar o acesso.

A alternativa seria trocar `AUTH_USER_MODEL` por um modelo com `USERNAME_FIELD =
"email"`. Isso foi descartado: as migrations iniciais de `core` e `investimento` já
declaram dependência *swappable* de `auth.User`, e há chave estrangeira para o
usuário em praticamente todos os modelos. Trocar o modelo com migrations aplicadas
exigiria copiar a tabela preservando as chaves primárias, reapontar as referências
e reconstruir os tipos de conteúdo — um procedimento que a própria documentação do
Django descreve como não suportado. O ganho seria nulo, já que `auth.User` sempre
teve um campo `email`.

Este backend só é seguro porque o e-mail é único: a migration
`core/0010_email_unico_case_insensitive` cria um índice único sobre `LOWER(email)`.
Sem essa garantia, resolver um endereço para um usuário seria ambíguo.
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

        Args:
            request (HttpRequest | None): Requisição em curso, se houver.
            username (str | None): Identificador informado — e-mail ou nome de usuário.
            password (str | None): Senha em texto plano.
            **kwargs: Campos alternativos, incluindo `email`.

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
