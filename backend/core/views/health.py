"""Verificação de saúde da aplicação.

Antes deste endpoint, o único healthcheck do projeto era o `pg_isready` do
docker-compose — que confirma que o Postgres aceita conexões, mas nada diz sobre a
aplicação: o Django podia estar em laço de erro de configuração, sem migrations
aplicadas ou incapaz de consultar o banco, e o contêiner continuaria "saudável".

O endpoint é intencionalmente magro. Ele responde à única pergunta que um
orquestrador precisa fazer antes de mandar tráfego: este processo consegue atender
uma requisição e falar com o banco?
"""

import logging

from django.db import connection
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

logger = logging.getLogger("core")


class HealthCheckAPIView(APIView):
    """Informa se a aplicação está apta a atender requisições.

    Deliberadamente não exige autenticação: o orquestrador precisa consultá-la antes
    de haver qualquer sessão. Em compensação, não expõe nenhum detalhe de ambiente
    (versão, configuração, nome de banco) que ajudasse a orientar um ataque.
    """

    permission_classes = [permissions.AllowAny]
    authentication_classes = []
    # Um healthcheck estrangulado derrubaria o serviço em vez de protegê-lo.
    throttle_classes = []

    def get(self, request) -> Response:
        """Executa uma consulta trivial ao banco e reporta o resultado.

        Returns:
            Response: 200 com `{"status": "ok"}` quando o banco responde, ou 503
                quando não — o que faz o orquestrador tirar esta instância do
                balanceamento em vez de continuar enviando tráfego para ela.
        """
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()
        except Exception:
            logger.exception("Healthcheck falhou ao consultar o banco de dados.")
            return Response(
                {"status": "indisponivel"},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        return Response({"status": "ok"}, status=status.HTTP_200_OK)
