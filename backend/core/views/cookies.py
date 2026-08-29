"""Gravação e remoção do cookie HttpOnly que transporta o refresh token JWT.

Este módulo existe para que haja um único lugar no projeto decidindo os atributos
do cookie de sessão. Antes, a chamada de `set_cookie` estava copiada em três views
(login, refresh e registro), com `secure=False` fixo no código e `max_age` escrito
à mão — o que significava que o token de sessão trafegaria em claro em produção e
que o tempo de vida do cookie podia divergir silenciosamente do configurado em
`SIMPLE_JWT["REFRESH_TOKEN_LIFETIME"]`.
"""

from django.conf import settings


def _max_age_refresh() -> int:
    """Calcula o tempo de vida do cookie a partir da configuração do SimpleJWT.

    Derivar do setting evita a divergência silenciosa entre o cookie e o token: se
    `REFRESH_TOKEN_LIFETIME` mudar, o cookie acompanha.

    Returns:
        int: Tempo de vida do cookie em segundos.
    """
    return int(settings.SIMPLE_JWT["REFRESH_TOKEN_LIFETIME"].total_seconds())


def set_refresh_cookie(response, refresh_token: str):
    """Grava o refresh token em cookie HttpOnly na resposta informada.

    Returns:
        Response: A mesma resposta, para permitir encadeamento.
    """
    response.set_cookie(
        key=settings.AUTH_COOKIE_NAME,
        value=str(refresh_token),
        httponly=True,
        secure=settings.AUTH_COOKIE_SECURE,
        samesite=settings.AUTH_COOKIE_SAMESITE,
        max_age=_max_age_refresh(),
        path=settings.AUTH_COOKIE_PATH,
    )
    return response


def clear_refresh_cookie(response):
    """Remove o cookie do refresh token da resposta informada.

    O `path` e o `samesite` precisam coincidir com os usados na gravação, senão o
    navegador ignora a instrução de remoção e o cookie permanece.

    Returns:
        Response: A mesma resposta, para permitir encadeamento.
    """
    response.delete_cookie(
        settings.AUTH_COOKIE_NAME,
        path=settings.AUTH_COOKIE_PATH,
        samesite=settings.AUTH_COOKIE_SAMESITE,
    )
    return response
