"""Paginação da API REST do FreeCash.

Nenhum endpoint de listagem era paginado: cada requisição devolvia a tabela
inteira do usuário. Em uso pessoal isso passa despercebido, mas com anos de
transações acumuladas a resposta cresce sem limite.

A paginação aqui é **opt-in por requisição**: sem o parâmetro `page`, a resposta
continua sendo um array puro, exatamente como antes. Essa escolha é deliberada.
Ativar o envelope `{count, next, previous, results}` globalmente mudaria o formato
de ~20 pontos de consumo no frontend de uma vez; qualquer um deles não atualizado
passaria a renderizar uma tabela vazia — ou, pior, mostraria os primeiros 100
lançamentos como se fossem o total, levando o usuário a conclusões financeiras
erradas sem nenhum sinal de que faltam dados.

Truncar silenciosamente uma lista financeira é pior do que não paginar. Portanto,
o envelope só aparece quando o cliente pede, e a migração das telas que realmente
precisam de paginação (extrato, contas a pagar, receitas, compras de cartão e
transações de investimento) exige trabalho de interface e é tarefa própria.

Endpoints novos — como os do painel administrativo — nascem paginados, pedindo
`page` explicitamente.
"""

from rest_framework.pagination import PageNumberPagination


class PadraoPageNumberPagination(PageNumberPagination):
    """Paginação por número de página, ativada apenas quando o cliente a solicita.

    Atributos:
        page_size (int): Itens por página quando `page` é informado sem `page_size`.
        page_size_query_param (str): Parâmetro que permite ajustar o tamanho da página.
        max_page_size (int): Teto rígido, para que `page_size` não sirva de brecha
            para reintroduzir respostas ilimitadas.
    """

    page_size = 100
    page_size_query_param = "page_size"
    max_page_size = 500

    def paginate_queryset(self, queryset, request, view=None):
        """Pagina somente se a requisição trouxer o parâmetro `page`.

        Args:
            queryset (QuerySet): Conjunto de resultados a paginar.
            request (Request): Requisição em processamento.
            view (APIView | None): View que originou a listagem.

        Returns:
            list | None: A página solicitada, ou None para que o DRF serialize a
                lista completa sem envelope, preservando o contrato histórico.
        """
        if self.page_query_param not in request.query_params:
            return None
        return super().paginate_queryset(queryset, request, view)
