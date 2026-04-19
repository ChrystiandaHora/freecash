from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import transaction

from investimento.models import Ativo, CarteiraHistorico, Cotacao, Transacao


@dataclass(frozen=True)
class HistoricoUpdateResult:
    created: int
    updated: int
    start_date: date | None
    end_date: date | None


class CarteiraHistoricoService:
    """
    Gera snapshots diários da carteira a partir de Transações + Cotações.
    """

    def __init__(self, user):
        self.user = user

    def atualizar(self, *, ate_data: date | None = None) -> HistoricoUpdateResult:
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
        """
        Série mensal (último ponto de cada mês), em ordem crescente.
        """
        qs = CarteiraHistorico.objects.filter(usuario=self.user).order_by("data").values(
            "data", "patrimonio", "rentabilidade_percentual"
        )

        last_by_month: dict[tuple[int, int], dict] = {}
        for row in qs:
            d: date = row["data"]
            last_by_month[(d.year, d.month)] = row

        rows = [last_by_month[k] for k in sorted(last_by_month.keys())]
        if meses is not None and len(rows) > meses:
            rows = rows[-meses:]

        return [
            {
                "data": r["data"].isoformat(),
                "patrimonio": float(r["patrimonio"] or 0),
                "rentabilidade_percentual": float(r["rentabilidade_percentual"] or 0),
            }
            for r in rows
        ]

    def series_anual(self, *, anos: int | None = 10) -> list[dict]:
        """
        Série anual (último ponto de cada ano), em ordem crescente.
        """
        qs = CarteiraHistorico.objects.filter(usuario=self.user).order_by("data").values(
            "data", "patrimonio", "rentabilidade_percentual"
        )

        last_by_year: dict[int, dict] = {}
        for row in qs:
            d: date = row["data"]
            last_by_year[d.year] = row

        rows = [last_by_year[k] for k in sorted(last_by_year.keys())]
        if anos is not None and len(rows) > anos:
            rows = rows[-anos:]

        return [
            {
                "data": r["data"].isoformat(),
                "patrimonio": float(r["patrimonio"] or 0),
                "rentabilidade_percentual": float(r["rentabilidade_percentual"] or 0),
            }
            for r in rows
        ]


def atualizar_historico_para_todos(*, ate_data: date | None = None) -> dict:
    User = get_user_model()
    results = {"users": 0, "created": 0, "updated": 0}
    for user in User.objects.all().iterator():
        svc = CarteiraHistoricoService(user)
        res = svc.atualizar(ate_data=ate_data)
        results["users"] += 1
        results["created"] += res.created
        results["updated"] += res.updated
    return results
