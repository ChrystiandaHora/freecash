"""Paginação da API REST do FreeCash.

Ativada por requisição: sem o parâmetro `page`, a resposta continua sendo um array
puro. Ligar o envelope `{count, next, previous, results}` globalmente mudaria o
formato de ~20 pontos de consumo do frontend de uma vez, e um deles não atualizado
mostraria os primeiros 100 lançamentos como se fossem o total — conclusão
financeira errada, sem sinal de que faltam dados. Truncar em silêncio é pior do
que não paginar.

Endpoints novos, como os do painel administrativo, nascem pedindo `page`.
"""

from rest_framework.pagination import PageNumberPagination


class PadraoPageNumberPagination(PageNumberPagination):
    """Paginação por número de página, ativada apenas quando o cliente a solicita.

    Atributos:
        page_size: Itens por página quando `page` é informado sem `page_size`.
    """

    page_size = 100
    page_size_query_param = "page_size"
    max_page_size = 500

    def paginate_queryset(self, queryset, request, view=None):
        """Pagina somente se a requisição trouxer o parâmetro `page`.

        Returns:
            list | None: A página solicitada, ou None para que o DRF serialize a
                lista completa sem envelope, preservando o contrato histórico.
        """
        if self.page_query_param not in request.query_params:
            return None
        return super().paginate_queryset(queryset, request, view)
