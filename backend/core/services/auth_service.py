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

    Duas limitações que valem ser conhecidas, e que estão documentadas em
    `docs/autenticacao.md`:

    1. Tokens emitidos antes de o app `token_blacklist` ser instalado não têm
       registro em `OutstandingToken` e portanto não são alcançáveis aqui. Eles
       expiram naturalmente dentro da validade do refresh token.
    2. O **access token** é stateless e continua válido até expirar (15 minutos),
       mesmo depois desta chamada. Essa janela é inerente a JWT sem introspecção.
       Para suspensão de conta ela não se aplica, porque o `JWTAuthentication`
       verifica `is_active` a cada requisição.

    Args:
        user (User): Usuário cujas sessões devem ser encerradas.

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
