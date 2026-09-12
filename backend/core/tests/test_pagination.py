"""Testes da paginação padrão da API.

`PadraoPageNumberPagination` pagina **apenas** quando o cliente pede `page`; sem
ele, a listagem continua sendo um array puro. É o que permite que ~20 pontos de
consumo do frontend sigam funcionando sem alteração. Se alguém "corrigir" a classe
para paginar sempre, as telas não migradas mostrariam os primeiros 100 lançamentos
como se fossem o total. Este arquivo existe para que isso quebre um teste em vez de
um número na tela. O teto de `max_page_size` fecha a outra ponta.
"""

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.exceptions import NotFound
from rest_framework.request import Request
from rest_framework.test import APIRequestFactory

from core.pagination import PadraoPageNumberPagination

User = get_user_model()


class PadraoPageNumberPaginationTests(TestCase):
    """Verifica quando a paginação age e quais limites respeita."""

    @classmethod
    def setUpTestData(cls):
        """Cria registros suficientes para atravessar mais de uma página."""
        User.objects.bulk_create(
            [
                User(username=f"usuario{indice:03d}", email=f"u{indice:03d}@x.com")
                for indice in range(150)
            ]
        )

    def setUp(self):
        """Instancia a paginação e a fábrica de requisições."""
        self.paginacao = PadraoPageNumberPagination()
        self.factory = APIRequestFactory()
        self.queryset = User.objects.order_by("pk")

    def _requisicao(self, query: str = ""):
        """Monta uma Request do DRF com a query string informada.

        Args:
            query: Query string sem o '?' inicial.

        Returns:
            Request: Requisição pronta para `paginate_queryset`.
        """
        return Request(self.factory.get(f"/api/admin/usuarios/?{query}"))

    def test_sem_parametro_page_nao_pagina(self):
        """Ausência de `page` preserva o contrato histórico de array puro.

        Retornar None é o que faz o DRF serializar a lista completa, sem envelope.
        """
        self.assertIsNone(
            self.paginacao.paginate_queryset(self.queryset, self._requisicao())
        )

    def test_com_parametro_page_devolve_a_pagina(self):
        """Com `page`, a resposta é limitada ao tamanho padrão."""
        pagina = self.paginacao.paginate_queryset(self.queryset, self._requisicao("page=1"))

        self.assertEqual(len(pagina), 100)

    def test_envelope_traz_contagem_e_navegacao(self):
        """O envelope informa o total e como chegar à próxima página."""
        self.paginacao.paginate_queryset(self.queryset, self._requisicao("page=1"))
        corpo = self.paginacao.get_paginated_response([]).data

        self.assertEqual(corpo["count"], 150)
        self.assertIsNotNone(corpo["next"])
        self.assertIsNone(corpo["previous"])
        self.assertIn("results", corpo)

    def test_ultima_pagina_traz_o_resto(self):
        """A página final contém apenas os registros restantes."""
        pagina = self.paginacao.paginate_queryset(self.queryset, self._requisicao("page=2"))

        self.assertEqual(len(pagina), 50)

    def test_page_size_ajusta_o_tamanho(self):
        """O cliente pode pedir páginas menores."""
        pagina = self.paginacao.paginate_queryset(
            self.queryset, self._requisicao("page=1&page_size=10")
        )

        self.assertEqual(len(pagina), 10)

    def test_page_size_respeita_o_teto(self):
        """Um `page_size` acima do máximo é limitado, não atendido.

        Sem esse teto, `page_size=99999` reintroduziria a resposta ilimitada que a
        paginação existe para evitar.
        """
        pagina = self.paginacao.paginate_queryset(
            self.queryset, self._requisicao("page=1&page_size=99999")
        )

        self.assertEqual(len(pagina), 150)
        self.assertEqual(self.paginacao.max_page_size, 500)

    def test_pagina_inexistente_resulta_em_404(self):
        """Pedir uma página além do fim é erro do cliente, não lista vazia."""
        with self.assertRaises(NotFound):
            self.paginacao.paginate_queryset(self.queryset, self._requisicao("page=99"))

    def test_pagina_nao_numerica_resulta_em_404(self):
        """Valor inválido em `page` não derruba a requisição com erro interno."""
        with self.assertRaises(NotFound):
            self.paginacao.paginate_queryset(
                self.queryset, self._requisicao("page=abacaxi")
            )
