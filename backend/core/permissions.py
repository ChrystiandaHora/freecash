"""Classes de permissão específicas do FreeCash."""

from rest_framework import permissions


class IsAdminPlataforma(permissions.BasePermission):
    """Restringe o acesso aos administradores da plataforma.

    Usa `is_staff` do próprio `auth.User` em vez de um modelo de papéis: para dois
    níveis, um modelo novo só somaria uma tabela a manter e um segundo lugar onde a
    autorização poderia divergir.

    O papel é lido do banco a cada requisição, nunca de claim do JWT — com
    `ROTATE_REFRESH_TOKENS` o payload sobrevive à rotação, e um administrador rebaixado
    seguiria administrador por sete dias. `is_active` é checado à parte para a suspensão
    ter efeito imediato.
    """

    message = "Esta área é restrita aos administradores da plataforma."

    def has_permission(self, request, view) -> bool:
        """Decide se a requisição parte de um administrador ativo.

        Returns:
            bool: True apenas para usuário autenticado, ativo e com `is_staff`.
        """
        usuario = request.user
        return bool(
            usuario
            and usuario.is_authenticated
            and usuario.is_active
            and usuario.is_staff
        )
