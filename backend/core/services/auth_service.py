"""Operações de ciclo de vida de sessão que atravessam mais de uma view.

Revogar as sessões de um usuário é necessário em três momentos distintos —
redefinição de senha, suspensão pelo administrador e logout de todos os
dispositivos — então a lógica não pertence a nenhuma view em particular.
"""

import logging

from rest_framework_simplejwt.token_blacklist.models import (
    BlacklistedToken,
    OutstandingToken,
)

logger = logging.getLogger("core")


def revogar_tokens_do_usuario(user) -> int:
    """Invalida todos os refresh tokens ativos de um usuário.

    Duas limitações, detalhadas em `docs/autenticacao.md`: tokens emitidos antes de o app
    `token_blacklist` existir não têm registro em `OutstandingToken` e expiram
    naturalmente; e o access token é stateless, seguindo válido por até 15 minutos — para
    suspensão isso não se aplica, porque o `JWTAuthentication` verifica `is_active` a cada
    requisição.

    Returns:
        int: Quantidade de tokens efetivamente revogados nesta chamada.
    """
    revogados = 0
    for token in OutstandingToken.objects.filter(user=user):
        _, criado = BlacklistedToken.objects.get_or_create(token=token)
        if criado:
            revogados += 1

    logger.info(
        "Sessões revogadas para o usuário %s: %d token(s).", user.pk, revogados
    )
    return revogados
