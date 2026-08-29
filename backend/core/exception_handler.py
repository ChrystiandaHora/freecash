"""Tratamento centralizado de exceções da API REST do FreeCash.

O padrão anterior era `try/except Exception` dentro de cada view, devolvendo 500
com `str(e)` no corpo — o que expõe detalhes internos (nomes de tabela, trechos de
SQL, caminhos de arquivo) a qualquer cliente. Este handler concentra a decisão num
único lugar: erros previstos pelo DRF seguem o formato normal, e qualquer exceção
não tratada é registrada com contexto no log e respondida com mensagem genérica.
"""

import logging
import uuid

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler

logger = logging.getLogger("core")


def freecash_exception_handler(exc, context):
    """Converte exceções em respostas da API, sem vazar detalhes internos.

    Args:
        exc (Exception): Exceção levantada durante o processamento da requisição.
        context (dict): Contexto do DRF, contendo ao menos a view e a requisição.

    Returns:
        Response: Resposta tratada pelo DRF quando a exceção é prevista (validação,
            permissão, autenticação, 404), ou uma resposta 500 genérica acompanhada
            de um código de correlação para localizar o traceback no log.
    """
    resposta = drf_exception_handler(exc, context)

    if resposta is not None:
        return resposta

    # Exceção não prevista pelo DRF: o cliente recebe um código opaco e o traceback
    # completo fica no log, associado ao mesmo código.
    codigo = uuid.uuid4().hex[:12]
    view = context.get("view")
    request = context.get("request")
    logger.exception(
        "Erro não tratado [%s] em %s %s (view=%s)",
        codigo,
        getattr(request, "method", "?"),
        getattr(request, "path", "?"),
        type(view).__name__ if view is not None else "?",
    )

    return Response(
        {
            "detail": "Erro interno ao processar a requisição.",
            "codigo": codigo,
        },
        status=status.HTTP_500_INTERNAL_SERVER_ERROR,
    )
