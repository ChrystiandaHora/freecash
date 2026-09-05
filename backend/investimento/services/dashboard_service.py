"""Serviço de Agregações de Dashboard de Investimentos.

Este módulo realiza o processamento otimizado (prevenindo N+1 queries) das estatísticas,
séries de alocação de carteiras, top rentabilidades de ativos e histórico de ordens
para servir como barramento de dados principal para o Dashboard do investidor.
"""

from decimal import Decimal
from django.db.models import DecimalField, OuterRef, Subquery, Sum
from django.db.models.functions import Coalesce

from investimento.models import Ativo, Cotacao, PosicaoCarteira, Transacao
from investimento.services.carteira_historico_service import CarteiraHistoricoService


class DashboardInvestimentoService:
    """Serviço de inteligência para consolidação estatística de ativos.

    Minimiza acessos ao banco de dados agregando cotações e calculando de forma offline
    as distribuições de classes e rentabilidade líquida do portfólio.

    Com `carteira_id`, todos os números passam a ser os daquela custódia: a quantidade
    e o preço médio vêm de `PosicaoCarteira` em vez do consolidado do `Ativo`, e os
    agregados de ordens filtram pela carteira.
    """

    def __init__(self, user, carteira_id: int | None = None):
        """Inicializa o serviço de dashboard vinculando o investidor e a carteira em foco."""
        self.user = user
        self.carteira_id = carteira_id

    def obter_dados_dashboard(self) -> dict:
        """Coleta, processa e pagina as estatísticas completas de investimento do usuário.

        Returns:
            dict: Payload consolidado contendo séries, patrimônio, custos e proventos.
        """
        # 1. Obter a última cotação para cada ativo sem causar N+1 queries
        ultima_cotacao = Cotacao.objects.filter(ativo_id=OuterRef("pk")).order_by(
            "-data", "-criada_em"
        )

        # 2. Consultar os ativos e injetar a última cotação via Subquery
        ativos_qs = (
            Ativo.objects.filter(usuario=self.user, ativo=True)
            .select_related("subcategoria__categoria__classe")
            .annotate(cotacao_recente=Subquery(ultima_cotacao.values("valor")[:1]))
            .order_by("subcategoria__categoria__classe__nome", "ticker")
        )

        # 3. Sob filtro, quantidade e preço médio vêm da posição na custódia (Subquery,
        #    para não quebrar a promessa de uma consulta só)
        if self.carteira_id:
            posicao = PosicaoCarteira.objects.filter(
                ativo_id=OuterRef("pk"), carteira_id=self.carteira_id
            )
            ativos_qs = ativos_qs.filter(
                posicoes__carteira_id=self.carteira_id, posicoes__quantidade__gt=0
            ).annotate(
                quantidade_carteira=Coalesce(
                    Subquery(posicao.values("quantidade")[:1]),
                    Decimal(0),
                    output_field=DecimalField(max_digits=19, decimal_places=8),
                ),
                preco_medio_carteira=Coalesce(
                    Subquery(posicao.values("preco_medio")[:1]),
                    Decimal(0),
                    output_field=DecimalField(max_digits=19, decimal_places=4),
                ),
            )

        ativos = list(ativos_qs)

        total_patrimonio = Decimal(0)
        total_investido = Decimal(0)
        allocation_by_category = {}

        for a in ativos:
            # Sob filtro, a posição da carteira substitui o consolidado do ativo.
            if self.carteira_id:
                a.quantidade = a.quantidade_carteira
                a.preco_medio = a.preco_medio_carteira

            # Cálculos refeitos baseados nas cotações em cache para evitar queries nos properties do Model
            val_investido = (
                (a.quantidade * a.preco_medio)
                if a.quantidade and a.preco_medio
                else Decimal(0)
            )

            if a.cotacao_recente is not None:
                val_atual = a.quantidade * a.cotacao_recente
                a.cotacao_atual_cache = a.cotacao_recente
            else:
                val_atual = val_investido
                a.cotacao_atual_cache = None

            # Injetando propriedades para os templates
            a.cached_valor_atual = val_atual
            a.cached_rentabilidade = val_atual - val_investido

            if val_investido > 0:
                a.cached_rentabilidade_percentual = (
                    (val_atual - val_investido) / val_investido
                ) * 100
            else:
                a.cached_rentabilidade_percentual = Decimal(0)

            total_patrimonio += val_atual
            total_investido += val_investido

            # Agregação para os Gráficos de Alocação
            if (
                a.subcategoria
                and a.subcategoria.categoria
                and a.subcategoria.categoria.classe
            ):
                cat_name = a.subcategoria.categoria.nome
            else:
                cat_name = "Sem Categoria"

            allocation_by_category[cat_name] = allocation_by_category.get(
                cat_name, 0
            ) + float(val_atual)

        # Estruturação de dados para gráficos
        category_labels = list(allocation_by_category.keys())
        category_values = list(allocation_by_category.values())

        transacoes_qs = Transacao.objects.filter(usuario=self.user)
        if self.carteira_id:
            transacoes_qs = transacoes_qs.filter(carteira_id=self.carteira_id)

        # Rentabilidade Global otimizada (apenas 1 query agrupada).
        agregados = transacoes_qs.values("tipo").annotate(total=Sum("valor_total"))

        totais = {linha["tipo"]: (linha["total"] or Decimal(0)) for linha in agregados}
        total_compras = totais.get(Transacao.TIPO_COMPRA, Decimal(0))
        total_vendas = totais.get(Transacao.TIPO_VENDA, Decimal(0))
        total_dividendos = totais.get(Transacao.TIPO_DIVIDENDO, Decimal(0))
        transf_entrada = totais.get(Transacao.TIPO_TRANSF_ENTRADA, Decimal(0))
        transf_saida = totais.get(Transacao.TIPO_TRANSF_SAIDA, Decimal(0))

        # Capital posto *nesta* custódia. Ignorar as pernas da transferência dava lucro
        # fantasma dos dois lados; subtrair a saída mantém o consolidado intacto.
        capital_aportado = total_compras + transf_entrada - transf_saida

        total_rentabilidade = (
            total_patrimonio + total_vendas + total_dividendos
        ) - capital_aportado
        total_rentabilidade_percentual = 0
        if capital_aportado > 0:
            total_rentabilidade_percentual = (
                total_rentabilidade / capital_aportado
            ) * 100

        historico_service = CarteiraHistoricoService(self.user, self.carteira_id)
        historico_service.atualizar()
        performance_monthly = historico_service.series_mensal(meses=36)
        rentabilidade_mensal = historico_service.obter_rentabilidade_mensal_por_ano()

        carteira_labels, carteira_values = self._alocacao_por_carteira()

        return {
            "carteira_labels": carteira_labels,
            "carteira_values": carteira_values,
            "carteira_data": list(zip(carteira_labels, carteira_values)),
            "total_patrimonio": total_patrimonio,
            "total_investido": total_investido,
            "total_rentabilidade": float(total_rentabilidade),
            "total_rentabilidade_percentual": float(total_rentabilidade_percentual),
            "total_dividendos": float(total_dividendos),
            "category_labels": category_labels,
            "category_values": category_values,
            "category_data": list(zip(category_labels, category_values)),
            "performance_monthly": performance_monthly,
            "rentabilidade_mensal": rentabilidade_mensal,
        }

    def _alocacao_por_carteira(self) -> tuple[list[str], list[float]]:
        """Distribui o patrimônio a mercado entre as carteiras do usuário.

        Sai sempre do consolidado, mesmo sob filtro: é o gráfico que responde "quanto
        eu tenho em cada corretora", e com uma carteira só ele não teria o que dizer.

        Returns:
            tuple[list[str], list[float]]: Nomes das carteiras e o valor em cada uma.
        """
        ultima_cotacao = Cotacao.objects.filter(ativo_id=OuterRef("ativo_id")).order_by(
            "-data", "-criada_em"
        )
        posicoes = (
            PosicaoCarteira.objects.filter(usuario=self.user, quantidade__gt=0)
            .select_related("carteira")
            .annotate(cotacao_recente=Subquery(ultima_cotacao.values("valor")[:1]))
        )

        totais: dict[str, float] = {}
        for posicao in posicoes:
            cotacao = posicao.cotacao_recente
            valor = posicao.quantidade * (
                cotacao if cotacao is not None else posicao.preco_medio
            )
            nome = posicao.carteira.nome
            totais[nome] = totais.get(nome, 0.0) + float(valor)

        return list(totais.keys()), list(totais.values())

