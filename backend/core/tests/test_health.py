"""Testes do endpoint de verificação de saúde.

`/api/health/` é o que o healthcheck do docker-compose consulta para decidir se o
contêiner está apto. Duas características dele são fáceis de quebrar sem
perceber, e ambas têm consequência direta em produção:

**Precisa responder sem autenticação e sem throttle.** Se um dia um `IsAuthenticated`
global alcançar esta rota, o orquestrador passará a receber 401, marcará o
contêiner como não saudável e ficará reiniciando uma aplicação que está
funcionando perfeitamente.

**Precisa falhar quando o banco falha.** Um healthcheck que responde 200 sempre é
pior que nenhum: ele afirma que a instância pode atender tráfego enquanto toda
requisição real devolve erro.
"""

from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient


class HealthCheckAPITests(TestCase):
    """Verifica as duas respostas possíveis do healthcheck."""

    def setUp(self):
        """Usa um cliente sem credencial alguma, como faz o orquestrador."""
        self.client = APIClient()
        self.url = reverse("api-health")

    def test_responde_ok_sem_autenticacao(self):
        """Sem sessão nem token, a resposta é 200."""
        resposta = self.client.get(self.url)

        self.assertEqual(resposta.status_code, status.HTTP_200_OK)
        self.assertEqual(resposta.data, {"status": "ok"})

    def test_devolve_503_quando_o_banco_nao_responde(self):
        """Falha de banco tira a instância do balanceamento.

        O 503 é o que faz o orquestrador parar de mandar tráfego para cá, em vez
        de continuar entregando requisições que vão falhar uma a uma.
        """
        with patch("core.views.health.connection") as conexao:
            conexao.cursor.side_effect = OSError("conexão recusada")

            with self.assertLogs("core", level="ERROR"):
                resposta = self.client.get(self.url)

        self.assertEqual(resposta.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
        self.assertEqual(resposta.data, {"status": "indisponivel"})

    def test_falha_nao_expoe_detalhe_do_erro(self):
        """A resposta de falha não revela nada sobre a infraestrutura.

        O endpoint é público: a mensagem de erro do banco (host, porta, nome de
        base) não pode servir de mapa para quem estiver sondando o serviço.
        """
        with patch("core.views.health.connection") as conexao:
            conexao.cursor.side_effect = OSError(
                "could not connect to server: postgres:5432"
            )

            with self.assertLogs("core", level="ERROR"):
                resposta = self.client.get(self.url)

        self.assertNotIn("postgres", str(resposta.data))
        self.assertNotIn("5432", str(resposta.data))

    def test_a_falha_fica_registrada_no_log(self):
        """O motivo real da indisponibilidade precisa estar em algum lugar."""
        with patch("core.views.health.connection") as conexao:
            conexao.cursor.side_effect = OSError("conexão recusada")

            with self.assertLogs("core", level="ERROR") as capturado:
                self.client.get(self.url)

        self.assertTrue(
            any("Healthcheck falhou" in linha for linha in capturado.output)
        )

    def test_nao_aceita_metodos_de_escrita(self):
        """A rota é somente leitura."""
        self.assertEqual(
            self.client.post(self.url).status_code,
            status.HTTP_405_METHOD_NOT_ALLOWED,
        )
