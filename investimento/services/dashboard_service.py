from decimal import Decimal
from datetime import date, timedelta
from django.core.paginator import Paginator
from django.db.models import OuterRef, Subquery, Sum

from investimento.models import Ativo, Transacao, Cotacao


class DashboardInvestimentoService:
    def __init__(self, user):
        self.user = user

    def obter_dados_dashboard(self, page_number=1):
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

        ativos = list(ativos_qs)

        total_patrimonio = Decimal(0)
        total_investido = Decimal(0)
        allocation_by_class = {}
        allocation_by_category = {}

        for a in ativos:
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
                class_name = a.subcategoria.categoria.classe.nome
                cat_name = a.subcategoria.categoria.nome
            else:
                class_name = "Sem Classe"
                cat_name = "Sem Categoria"

            allocation_by_class[class_name] = allocation_by_class.get(
                class_name, 0
            ) + float(val_atual)
            allocation_by_category[cat_name] = allocation_by_category.get(
                cat_name, 0
            ) + float(val_atual)

        # Estruturação de dados para gráficos
        allocation_labels = list(allocation_by_class.keys())
        allocation_values = list(allocation_by_class.values())
        category_labels = list(allocation_by_category.keys())
        category_values = list(allocation_by_category.values())

        # Top 5 ativos por valor
        ativos_with_value = list(ativos)
        ativos_with_value.sort(key=lambda x: x.cached_valor_atual, reverse=True)
        top_5_ativos = ativos_with_value[:5]

        for a in top_5_ativos:
            if total_patrimonio > 0:
                a.percentual = (
                    float(a.cached_valor_atual) / float(total_patrimonio)
                ) * 100
            else:
                a.percentual = 0

        # Top 5 ativos por rentabilidade
        ativos_by_rent = list(ativos)
        ativos_by_rent.sort(key=lambda x: x.cached_rentabilidade, reverse=True)
        top_rentabilidade = ativos_by_rent[:5]

        # Última transação
        ultima_transacao = (
            Transacao.objects.filter(ativo__usuario=self.user).order_by("-data").first()
        )

        # Próximos vencimentos de Renda Fixa
        hoje = date.today()
        limite_dias = hoje + timedelta(days=90)
        proximos_vencimentos = (
            Ativo.objects.filter(
                usuario=self.user,
                ativo=True,
                data_vencimento__gte=hoje,
                data_vencimento__lte=limite_dias,
            )
            .select_related("subcategoria__categoria__classe")
            .order_by("data_vencimento")[:5]
        )

        # Paginação
        paginator = Paginator(ativos, 5)
        ativos_page = paginator.get_page(page_number)

        # Rentabilidade Global otimizada (apenas 1 query agrupada)
        agregados = (
            Transacao.objects.filter(usuario=self.user)
            .values("tipo")
            .annotate(total=Sum("valor_total"))
        )

        total_compras = Decimal(0)
        total_vendas = Decimal(0)
        total_dividendos = Decimal(0)

        for agg in agregados:
            if agg["tipo"] == Transacao.TIPO_COMPRA:
                total_compras = agg["total"] or Decimal(0)
            elif agg["tipo"] == Transacao.TIPO_VENDA:
                total_vendas = agg["total"] or Decimal(0)
            elif agg["tipo"] == Transacao.TIPO_DIVIDENDO:
                total_dividendos = agg["total"] or Decimal(0)

        total_rentabilidade = (
            total_patrimonio + total_vendas + total_dividendos
        ) - total_compras
        total_rentabilidade_percentual = 0
        if total_compras > 0:
            total_rentabilidade_percentual = (total_rentabilidade / total_compras) * 100

        return {
            "ativos": ativos,
            "ativos_page": ativos_page,
            "total_patrimonio": total_patrimonio,
            "total_investido": total_investido,
            "total_rentabilidade": float(total_rentabilidade),
            "total_rentabilidade_percentual": float(total_rentabilidade_percentual),
            "total_dividendos": float(total_dividendos),
            "allocation_labels": allocation_labels,
            "allocation_values": allocation_values,
            "allocation_data": list(zip(allocation_labels, allocation_values)),
            "category_labels": category_labels,
            "category_values": category_values,
            "category_data": list(zip(category_labels, category_values)),
            "top_5_ativos": top_5_ativos,
            "top_rentabilidade": top_rentabilidade,
            "ultima_transacao": ultima_transacao,
            "proximos_vencimentos": proximos_vencimentos,
        }
