"""Testes do tratamento centralizado de exceções da API.

`freecash_exception_handler` é o `EXCEPTION_HANDLER` global: decide o corpo de toda
resposta de erro. Uma regressão aqui quebra todos os endpoints ao mesmo tempo, e de
forma silenciosa. Duas garantias: erro previsto mantém o formato do DRF (senão toda
mensagem por campo desaparece do frontend) e erro imprevisto não vaza a mensagem
original, que pode conter nome de tabela, SQL ou caminho de arquivo.
"""

import re

from django.test import TestCase
from rest_framework import status
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.test import APIRequestFactory

from core.exception_handler import freecash_exception_handler


class _ViewFalsa:
    """Substituto de view para preencher o contexto exigido pelo handler."""


class ExceptionHandlerTests(TestCase):
    """Verifica o que o cliente recebe em cada classe de erro."""

    def setUp(self):
        """Monta um contexto equivalente ao que o DRF passa ao handler."""
        self.contexto = {
            "view": _ViewFalsa(),
            "request": APIRequestFactory().get("/api/financeiro/contas-pagar/"),
        }

    def test_erro_de_validacao_mantem_o_formato_do_drf(self):
        """Erros por campo chegam intactos ao frontend."""
        resposta = freecash_exception_handler(
            ValidationError({"valor": ["Informe um número positivo."]}), self.contexto
        )

        self.assertEqual(resposta.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(resposta.data, {"valor": ["Informe um número positivo."]})

    def test_erro_de_permissao_mantem_status_403(self):
        """Recusa de permissão não é convertida em erro interno."""
        resposta = freecash_exception_handler(PermissionDenied(), self.contexto)

        self.assertEqual(resposta.status_code, status.HTTP_403_FORBIDDEN)

    def test_nao_encontrado_mantem_status_404(self):
        """404 continua sendo 404, com a mensagem do DRF."""
        resposta = freecash_exception_handler(NotFound(), self.contexto)

        self.assertEqual(resposta.status_code, status.HTTP_404_NOT_FOUND)

    def test_excecao_inesperada_vira_500_generico(self):
        """Exceção fora do vocabulário do DRF recebe resposta padronizada."""
        with self.assertLogs("core", level="ERROR"):
            resposta = freecash_exception_handler(
                ValueError("coluna core_conta.saldo_secreto não existe"), self.contexto
            )

        self.assertEqual(resposta.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertEqual(
            resposta.data["detail"], "Erro interno ao processar a requisição."
        )

    def test_excecao_inesperada_nao_vaza_a_mensagem_original(self):
        """O detalhe interno não chega ao cliente.

        Este é o teste que impede a volta do padrão antigo, que devolvia `str(e)`
        no corpo da resposta.
        """
        segredo = "coluna core_conta.saldo_secreto não existe"

        with self.assertLogs("core", level="ERROR"):
            resposta = freecash_exception_handler(ValueError(segredo), self.contexto)

        self.assertNotIn(segredo, str(resposta.data))

    def test_codigo_de_correlacao_liga_resposta_e_log(self):
        """O código devolvido ao cliente é o mesmo registrado no log.

        Sem essa correspondência o código seria decorativo: o usuário informaria
        um identificador que não localiza nada no servidor.
        """
        with self.assertLogs("core", level="ERROR") as capturado:
            resposta = freecash_exception_handler(ValueError("falhou"), self.contexto)

        codigo = resposta.data["codigo"]
        self.assertRegex(codigo, re.compile(r"^[0-9a-f]{12}$"))
        self.assertTrue(any(codigo in linha for linha in capturado.output))

    def test_log_registra_metodo_e_caminho_da_requisicao(self):
        """O log guarda o contexto necessário para reproduzir a falha."""
        with self.assertLogs("core", level="ERROR") as capturado:
            freecash_exception_handler(ValueError("falhou"), self.contexto)

        registro = "\n".join(capturado.output)
        self.assertIn("GET", registro)
        self.assertIn("/api/financeiro/contas-pagar/", registro)

    def test_codigos_de_erros_distintos_nao_se_repetem(self):
        """Cada ocorrência recebe seu próprio código."""
        with self.assertLogs("core", level="ERROR"):
            primeira = freecash_exception_handler(ValueError("a"), self.contexto)
            segunda = freecash_exception_handler(ValueError("b"), self.contexto)

        self.assertNotEqual(primeira.data["codigo"], segunda.data["codigo"])
