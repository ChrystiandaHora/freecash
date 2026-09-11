"""Teste de regressão do isolamento na atualização em lote de cotações.

`POST /api/investimentos/ativos/atualizar-cotacoes/` chamava `atualizar_cotacoes()`
sem argumento, percorrendo os ativos de toda a base. Daí duas consequências:
escrita entre inquilinos, com um usuário gravando cotações nos ativos dos outros; e
vazamento, porque a lista `errors` devolvida é montada com o ticker do ativo — quem
acionasse o endpoint recebia a composição de carteira de terceiros.

Segue o padrão de `test_security.py`: um usuário age, e verifica-se que o dado do
outro não é alcançado.
"""

from unittest import mock

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from investimento.models import Ativo

User = get_user_model()


def sem_rede():
    """Neutraliza as duas fontes remotas do lote, deixando só o recorte sob teste.

    O completamento de histórico faz um GET por ticker descoberto — sem este mock a
    suíte sairia para a internet, e o que está em teste aqui é a fronteira de
    usuário, não a integração.
    """
    return (
        mock.patch("investimento.calculators.fetch_quotes_brazil", return_value={}),
        mock.patch("investimento.calculators.fetch_historico_yahoo", return_value=[]),
    )


class AtualizarCotacoesIsolamentoTests(APITestCase):
    """Verifica que a atualização em lote não atravessa a fronteira de usuário."""

    def setUp(self):
        """Cria dois usuários, cada um com um ativo de ticker distinto."""
        self.maria = User.objects.create_user(
            username="maria", password="senha-bem-comprida-123",
            email="maria@exemplo.com",
        )
        self.joao = User.objects.create_user(
            username="joao", password="senha-bem-comprida-123",
            email="joao@exemplo.com",
        )

        # `subcategoria` é opcional no modelo, e a classificação não participa do
        # que está sob teste: o recorte por usuário.
        self.ativo_maria = Ativo.objects.create(
            usuario=self.maria,
            nome="Ativo secreto da Maria", ticker="SEGREDO11", ativo=True,
        )
        self.ativo_joao = Ativo.objects.create(
            usuario=self.joao,
            nome="Ativo do João", ticker="JOAO3", ativo=True,
        )

        self.url = reverse("api-ativo-atualizar-cotacoes")

    def test_lote_so_percorre_os_ativos_de_quem_pediu(self):
        """A varredura precisa parar na fronteira do usuário autenticado."""
        self.client.force_authenticate(user=self.joao)

        patch_tv, patch_yahoo = sem_rede()
        with patch_tv as fetch, patch_yahoo:
            self.client.post(self.url)

        self.assertEqual(fetch.call_count, 1)
        tickers_consultados = fetch.call_args.args[0]

        self.assertIn("JOAO3", tickers_consultados)
        self.assertNotIn(
            "SEGREDO11",
            tickers_consultados,
            "O ticker de outro usuário entrou na consulta em lote.",
        )

    def test_resposta_nao_vaza_ticker_de_outro_usuario(self):
        """A lista de erros é devolvida ao cliente e não pode citar terceiros."""
        self.client.force_authenticate(user=self.joao)

        patch_tv, patch_yahoo = sem_rede()
        with patch_tv, patch_yahoo:
            resposta = self.client.post(self.url)

        self.assertEqual(resposta.status_code, status.HTTP_200_OK)
        corpo = str(resposta.data)
        self.assertNotIn(
            "SEGREDO11",
            corpo,
            "A resposta expôs o ticker de outro usuário.",
        )

    def test_nenhuma_cotacao_de_outro_usuario_e_gravada(self):
        """Escrita entre inquilinos: o ativo alheio não pode receber cotação."""
        from investimento.models import Cotacao

        self.client.force_authenticate(user=self.joao)

        patch_tv, patch_yahoo = sem_rede()
        with patch_tv, patch_yahoo:
            self.client.post(self.url)

        self.assertFalse(
            Cotacao.objects.filter(ativo=self.ativo_maria).exists(),
            "Foi gravada cotação em ativo de outro usuário.",
        )
