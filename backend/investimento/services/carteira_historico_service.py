"""Serviço de Processamento de Snapshots Históricos de Carteira de Investimentos.

Este módulo gera e atualiza snapshots diários da carteira do investidor com base
no histórico de transações e cotações coletadas. Também constrói séries mensais
e anuais agregadas em formato de gráfico de vela (OHLC) e custos históricos para
alimentar a interface do React.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import transaction

from investimento.models import Ativo, CarteiraHistorico, Cotacao, Transacao


@dataclass(frozen=True)
class HistoricoUpdateResult:
    """Estrutura representativa de dados de estatísticas de processamento de snapshots.

    Atributos:
        created (int): Quantidade de snapshots diários criados.
        updated (int): Quantidade de snapshots diários atualizados.
        start_date (date): Data de início do processamento de snapshots.
        end_date (date): Data de encerramento do processamento de snapshots.
    """
    created: int
    updated: int
    start_date: date | None
    end_date: date | None


class CarteiraHistoricoService:
    """Serviço especializado na geração e emissão de snapshots diários de patrimônio.

    Coordena o processamento incremental e consolida balanços de compras, vendas e proventos.
    """

    def __init__(self, user):
        """Inicializa o serviço de histórico atribuindo o investidor correspondente.

        Args:
            user (User): Instância do usuário Django proprietário da carteira.
        """
        self.user = user

    def atualizar(self, *, ate_data: date | None = None) -> HistoricoUpdateResult:
        """Gera e grava snapshots diários na base de dados de forma incremental.

        Calcula de forma atômica e linear o patrimônio a mercado, o somatório de custos
        de aquisição (compras), resgates (vendas), proventos e rentabilidade diária.

        Args:
            ate_data (date, optional): Data limite de encerramento. Defaults to date.today().

        Returns:
            HistoricoUpdateResult: Estatísticas contendo criados, atualizados e limites temporais.
        """
        end_date = ate_data or date.today()

        transacoes = list(
            Transacao.objects.filter(usuario=self.user)
            .select_related("ativo")
            .order_by("data", "criada_em")
        )
        if not transacoes:
            return HistoricoUpdateResult(0, 0, None, None)

        start_date = transacoes[0].data

        ativos = list(Ativo.objects.filter(usuario=self.user))
        preco_medio_by_ativo = {a.id: (a.preco_medio or Decimal(0)) for a in ativos}

        # Indexa eventos por data para processar em ordem
        transacoes_by_date: dict[date, list[Transacao]] = {}
        for t in transacoes:
            transacoes_by_date.setdefault(t.data, []).append(t)

        cotacoes_by_date: dict[date, list[tuple[int, Decimal]]] = {}
        cotacoes_qs = (
            Cotacao.objects.filter(ativo__usuario=self.user, data__gte=start_date, data__lte=end_date)
            .values_list("data", "ativo_id", "valor")
            .order_by("data")
        )
        for d, ativo_id, valor in cotacoes_qs:
            cotacoes_by_date.setdefault(d, []).append((ativo_id, valor))

        existing = {
            row["data"]: row["id"]
            for row in CarteiraHistorico.objects.filter(
                usuario=self.user, data__gte=start_date, data__lte=end_date
            ).values("id", "data")
        }

        quantities: dict[int, Decimal] = {}
        last_price: dict[int, Decimal] = {}

        total_compras = Decimal(0)
        total_vendas = Decimal(0)
        total_dividendos = Decimal(0)

        to_create: list[CarteiraHistorico] = []
        to_update: list[CarteiraHistorico] = []

        cur = start_date
        one_day = timedelta(days=1)

        while cur <= end_date:
            for ativo_id, valor in cotacoes_by_date.get(cur, []):
                if valor is not None:
                    last_price[ativo_id] = Decimal(valor)

            for t in transacoes_by_date.get(cur, []):
                if t.tipo == Transacao.TIPO_COMPRA:
                    quantities[t.ativo_id] = quantities.get(t.ativo_id, Decimal(0)) + t.quantidade
                    total_compras += t.valor_total or Decimal(0)
                elif t.tipo == Transacao.TIPO_VENDA:
                    quantities[t.ativo_id] = quantities.get(t.ativo_id, Decimal(0)) - t.quantidade
                    total_vendas += t.valor_total or Decimal(0)
                elif t.tipo == Transacao.TIPO_DIVIDENDO:
                    total_dividendos += t.valor_total or Decimal(0)

            patrimonio = Decimal(0)
            for ativo_id, qtd in quantities.items():
                if not qtd:
                    continue
                price = last_price.get(ativo_id)
                if price is None:
                    price = preco_medio_by_ativo.get(ativo_id, Decimal(0))
                patrimonio += qtd * price

            rentabilidade = (patrimonio + total_vendas + total_dividendos) - total_compras
            rentabilidade_percentual = Decimal(0)
            if total_compras > 0:
                rentabilidade_percentual = (rentabilidade / total_compras) * Decimal(100)

            obj = CarteiraHistorico(
                usuario=self.user,
                data=cur,
                patrimonio=patrimonio,
                total_compras=total_compras,
                total_vendas=total_vendas,
                total_dividendos=total_dividendos,
                rentabilidade=rentabilidade,
                rentabilidade_percentual=rentabilidade_percentual,
            )

            existing_id = existing.get(cur)
            if existing_id:
                obj.id = existing_id
                to_update.append(obj)
            else:
                to_create.append(obj)

            cur += one_day

        with transaction.atomic():
            if to_create:
                CarteiraHistorico.objects.bulk_create(to_create, batch_size=500)
            if to_update:
                CarteiraHistorico.objects.bulk_update(
                    to_update,
                    fields=[
                        "patrimonio",
                        "total_compras",
                        "total_vendas",
                        "total_dividendos",
                        "rentabilidade",
                        "rentabilidade_percentual",
                    ],
                    batch_size=500,
                )

        return HistoricoUpdateResult(
            created=len(to_create),
            updated=len(to_update),
            start_date=start_date,
            end_date=end_date,
        )

    def series_mensal(self, *, meses: int | None = 36) -> list[dict]:
        """Gera a série mensal consolidada em formato OHLC de patrimônio e investimentos.

        Agrupa os dados diários em janelas mensais para renderização de gráficos.

        Args:
            meses (int, optional): Número limite de meses a retornar. Defaults to 36.

        Returns:
            list[dict]: Lista de dicionários com 'data', 'ohlc' (lista de floats) e 'investido'.
        """
        qs = CarteiraHistorico.objects.filter(usuario=self.user).order_by("data").values(
            "data", "patrimonio", "total_compras", "total_vendas"
        )

        # Agrupar por (ano, mês)
        groups: dict[tuple[int, int], list[dict]] = {}
        for row in qs:
            d: date = row["data"]
            key = (d.year, d.month)
            if key not in groups:
                groups[key] = []
            groups[key].append(row)

        sorted_keys = sorted(groups.keys())
        if meses and len(sorted_keys) > meses:
            sorted_keys = sorted_keys[-meses:]

        results = []
        for key in sorted_keys:
            rows = groups[key]
            # OHLC do Patrimônio
            o = float(rows[0]["patrimonio"] or 0)
            c = float(rows[-1]["patrimonio"] or 0)
            h = float(max(r["patrimonio"] or 0 for r in rows))
            l = float(min(r["patrimonio"] or 0 for r in rows))
            
            # Investimento Líquido (Custo) no final do mês
            investido = float((rows[-1]["total_compras"] or 0) - (rows[-1]["total_vendas"] or 0))

            results.append({
                "data": rows[-1]["data"].isoformat(),
                "ohlc": [o, h, l, c],
                "investido": investido,
                "patrimonio": c,
            })
        return results

    def series_anual(self, *, anos: int | None = 10) -> list[dict]:
        """Gera a série anual consolidada em formato OHLC de patrimônio e investimentos.

        Args:
            anos (int, optional): Número de anos de retrocesso histórico. Defaults to 10.

        Returns:
            list[dict]: Lista contendo dicionários com a evolução anual.
        """
        qs = CarteiraHistorico.objects.filter(usuario=self.user).order_by("data").values(
            "data", "patrimonio", "total_compras", "total_vendas"
        )

        groups: dict[int, list[dict]] = {}
        for row in qs:
            d: date = row["data"]
            key = d.year
            if key not in groups:
                groups[key] = []
            groups[key].append(row)

        sorted_keys = sorted(groups.keys())
        if anos and len(sorted_keys) > anos:
            sorted_keys = sorted_keys[-anos:]

        results = []
        for key in sorted_keys:
            rows = groups[key]
            o = float(rows[0]["patrimonio"] or 0)
            c = float(rows[-1]["patrimonio"] or 0)
            h = float(max(r["patrimonio"] or 0 for r in rows))
            l = float(min(r["patrimonio"] or 0 for r in rows))
            investido = float((rows[-1]["total_compras"] or 0) - (rows[-1]["total_vendas"] or 0))

            results.append({
                "data": rows[-1]["data"].isoformat(),
                "ohlc": [o, h, l, c],
                "investido": investido,
                "patrimonio": c,
            })
        return results


def atualizar_historico_para_todos(*, ate_data: date | None = None) -> dict:
    """Sincroniza atomaticamente os snapshots históricos de todos os usuários do sistema.

    Args:
        ate_data (date, optional): Data limite de atualização. Defaults to None (hoje).

    Returns:
        dict: Estatísticas de processamento global com chaves 'users', 'created' e 'updated'.
    """
    User = get_user_model()
    results = {"users": 0, "created": 0, "updated": 0}
    for user in User.objects.all().iterator():
        svc = CarteiraHistoricoService(user)
        res = svc.atualizar(ate_data=ate_data)
        results["users"] += 1
        results["created"] += res.created
        results["updated"] += res.updated
    return results

