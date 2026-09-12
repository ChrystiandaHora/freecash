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
from django.db.models import Sum

from investimento.models import Ativo, CarteiraHistorico, Cotacao, Transacao


@dataclass(frozen=True)
class HistoricoUpdateResult:
    """Estrutura representativa de dados de estatísticas de processamento de snapshots."""
    created: int
    updated: int
    start_date: date | None
    end_date: date | None


class CarteiraHistoricoService:
    """Serviço especializado na geração e emissão de snapshots diários de patrimônio.

    Coordena o processamento incremental e consolida balanços de compras, vendas e proventos.

    O snapshot é gravado **por carteira**. Na leitura, `carteira_id` restringe a série a
    uma custódia; sem ele, as séries somam as carteiras dia a dia. Guardar também uma
    linha "consolidada" seria uma segunda fonte de verdade para o mesmo número, que
    poderia divergir das partes sem que nada acusasse.
    """

    def __init__(self, user, carteira_id: int | None = None):
        """Inicializa o serviço de histórico atribuindo o investidor e a carteira em foco."""
        self.user = user
        self.carteira_id = carteira_id

    def atualizar(self, *, ate_data: date | None = None) -> HistoricoUpdateResult:
        """Gera e grava snapshots diários na base de dados de forma incremental.

        Calcula de forma atômica e linear o patrimônio a mercado, o somatório de custos
        de aquisição (compras), resgates (vendas), proventos e rentabilidade diária,
        uma série por carteira.

        Args:
            ate_data: Data limite de encerramento. Defaults to date.today().

        Returns:
            HistoricoUpdateResult: Estatísticas contendo criados, atualizados e limites temporais.
        """
        transacoes = list(
            Transacao.objects.filter(usuario=self.user)
            .select_related("ativo")
            .order_by("data", "criada_em")
        )
        if not transacoes:
            return HistoricoUpdateResult(0, 0, None, None)

        start_date = transacoes[0].data
        max_transacao_date = max(t.data for t in transacoes)
        end_date = ate_data or max(date.today(), max_transacao_date)

        ativos = list(Ativo.objects.filter(usuario=self.user))
        preco_medio_by_ativo = {a.id: (a.preco_medio or Decimal(0)) for a in ativos}

        cotacoes_by_date: dict[date, list[tuple[int, Decimal]]] = {}
        cotacoes_qs = (
            Cotacao.objects.filter(ativo__usuario=self.user, data__gte=start_date, data__lte=end_date)
            .values_list("data", "ativo_id", "valor")
            .order_by("data")
        )
        for d, ativo_id, valor in cotacoes_qs:
            cotacoes_by_date.setdefault(d, []).append((ativo_id, valor))

        existing = {
            (row["carteira_id"], row["data"]): row["id"]
            for row in CarteiraHistorico.objects.filter(
                usuario=self.user, data__gte=start_date, data__lte=end_date
            ).values("id", "carteira_id", "data")
        }

        # Indexa por carteira e, dentro dela, por data.
        por_carteira: dict[int, dict[date, list[Transacao]]] = {}
        for t in transacoes:
            por_carteira.setdefault(t.carteira_id, {}).setdefault(t.data, []).append(t)

        to_create: list[CarteiraHistorico] = []
        to_update: list[CarteiraHistorico] = []

        for carteira_id, transacoes_by_date in por_carteira.items():
            self._processar_carteira(
                carteira_id=carteira_id,
                transacoes_by_date=transacoes_by_date,
                cotacoes_by_date=cotacoes_by_date,
                preco_medio_by_ativo=preco_medio_by_ativo,
                start_date=start_date,
                end_date=end_date,
                existing=existing,
                to_create=to_create,
                to_update=to_update,
            )

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

    def _processar_carteira(
        self,
        *,
        carteira_id: int,
        transacoes_by_date: dict[date, list[Transacao]],
        cotacoes_by_date: dict[date, list[tuple[int, Decimal]]],
        preco_medio_by_ativo: dict[int, Decimal],
        start_date: date,
        end_date: date,
        existing: dict[tuple[int, date], int],
        to_create: list[CarteiraHistorico],
        to_update: list[CarteiraHistorico],
    ) -> None:
        """Percorre a janela dia a dia montando os snapshots de uma carteira.

        As pernas de transferência entram como aquisição (entrada) e alienação a custo
        (saída). Dentro da carteira isso mantém o custo coerente com a quantidade —
        um papel que chegou por portabilidade não é lucro. Somando as carteiras, a
        entrada e a saída se anulam, então o consolidado continua igual ao de antes de
        a transferência existir.
        """
        quantities: dict[int, Decimal] = {}
        # Custo por ativo nesta carteira: é o preço de fallback sem cotação. O PM
        # consolidado atribuiria à custódia um custo que não é o dela.
        custos: dict[int, Decimal] = {}
        last_price: dict[int, Decimal] = {}

        total_compras = Decimal(0)
        total_vendas = Decimal(0)
        total_dividendos = Decimal(0)

        cur = start_date
        one_day = timedelta(days=1)

        while cur <= end_date:
            for ativo_id, valor in cotacoes_by_date.get(cur, []):
                if valor is not None:
                    last_price[ativo_id] = Decimal(valor)

            for t in transacoes_by_date.get(cur, []):
                quantidade_atual = quantities.get(t.ativo_id, Decimal(0))
                custo_atual = custos.get(t.ativo_id, Decimal(0))

                if t.tipo in (Transacao.TIPO_COMPRA, Transacao.TIPO_TRANSF_ENTRADA):
                    quantities[t.ativo_id] = quantidade_atual + t.quantidade
                    custos[t.ativo_id] = custo_atual + (t.valor_total or Decimal(0))
                    total_compras += t.valor_total or Decimal(0)
                elif t.tipo in (Transacao.TIPO_VENDA, Transacao.TIPO_TRANSF_SAIDA):
                    quantities[t.ativo_id] = quantidade_atual - t.quantidade
                    if quantidade_atual > 0:
                        # Abate o custo na proporção vendida, como no preço médio.
                        custos[t.ativo_id] = custo_atual - (
                            t.quantidade * (custo_atual / quantidade_atual)
                        )
                    total_vendas += t.valor_total or Decimal(0)
                elif t.tipo == Transacao.TIPO_DIVIDENDO:
                    total_dividendos += t.valor_total or Decimal(0)

            patrimonio = Decimal(0)
            for ativo_id, qtd in quantities.items():
                if not qtd:
                    continue
                price = last_price.get(ativo_id)
                if price is None:
                    custo = custos.get(ativo_id)
                    price = (custo / qtd) if custo else preco_medio_by_ativo.get(ativo_id, Decimal(0))
                patrimonio += qtd * price

            rentabilidade = (patrimonio + total_vendas + total_dividendos) - total_compras
            rentabilidade_percentual = Decimal(0)
            if total_compras > 0:
                rentabilidade_percentual = (rentabilidade / total_compras) * Decimal(100)

            obj = CarteiraHistorico(
                usuario=self.user,
                carteira_id=carteira_id,
                data=cur,
                patrimonio=patrimonio,
                total_compras=total_compras,
                total_vendas=total_vendas,
                total_dividendos=total_dividendos,
                rentabilidade=rentabilidade,
                rentabilidade_percentual=rentabilidade_percentual,
            )

            existing_id = existing.get((carteira_id, cur))
            if existing_id:
                obj.id = existing_id
                to_update.append(obj)
            else:
                to_create.append(obj)

            cur += one_day

    def _linhas_diarias(self) -> list[dict]:
        """Devolve a série diária já no recorte pedido — uma carteira, ou a soma delas.

        Sem filtro, soma as carteiras por dia e **recalcula** a rentabilidade a partir
        dos totais somados. Somar a coluna `rentabilidade` das partes daria o mesmo
        número por acaso, mas o percentual não sobrevive a uma soma — ele precisa da
        base consolidada.

        Returns:
            list[dict]: Linhas ordenadas por data, com patrimônio, custos e rentabilidade.
        """
        qs = CarteiraHistorico.objects.filter(usuario=self.user)
        if self.carteira_id:
            return list(
                qs.filter(carteira_id=self.carteira_id)
                .order_by("data")
                .values(
                    "data", "patrimonio", "total_compras", "total_vendas",
                    "total_dividendos", "rentabilidade", "rentabilidade_percentual",
                )
            )

        agregado = (
            qs.values("data")
            .annotate(
                patrimonio=Sum("patrimonio"),
                total_compras=Sum("total_compras"),
                total_vendas=Sum("total_vendas"),
                total_dividendos=Sum("total_dividendos"),
            )
            .order_by("data")
        )

        linhas = []
        for row in agregado:
            compras = row["total_compras"] or Decimal(0)
            vendas = row["total_vendas"] or Decimal(0)
            dividendos = row["total_dividendos"] or Decimal(0)
            patrimonio = row["patrimonio"] or Decimal(0)
            rentabilidade = (patrimonio + vendas + dividendos) - compras
            row["rentabilidade"] = rentabilidade
            row["rentabilidade_percentual"] = (
                (rentabilidade / compras) * Decimal(100) if compras > 0 else Decimal(0)
            )
            linhas.append(row)
        return linhas

    def series_mensal(self, *, meses: int | None = 36) -> list[dict]:
        """Gera a série mensal consolidada em formato OHLC de patrimônio e investimentos.

        Agrupa os dados diários em janelas mensais para renderização de gráficos.

        Args:
            meses: Número limite de meses a retornar. Defaults to 36.

        Returns:
            list[dict]: Lista de dicionários contendo patrimônio, custo investido, dividendos acumulados e dividendos mensais.
        """
        qs = self._linhas_diarias()

        # Agrupar por (ano, mês)
        groups: dict[tuple[int, int], list[dict]] = {}
        for row in qs:
            d: date = row["data"]
            key = (d.year, d.month)
            if key not in groups:
                groups[key] = []
            groups[key].append(row)

        all_sorted_keys = sorted(groups.keys())

        # Pre-calcular dividendos mensais para todos os meses em ordem cronológica
        all_results = []
        prev_dividendos_acum = Decimal(0)

        for key in all_sorted_keys:
            rows = groups[key]
            # OHLC do Patrimônio
            o = float(rows[0]["patrimonio"] or 0)
            c = float(rows[-1]["patrimonio"] or 0)
            h = float(max(r["patrimonio"] or 0 for r in rows))
            l = float(min(r["patrimonio"] or 0 for r in rows))
            
            # Investimento Líquido (Custo) no final do mês
            investido = float((rows[-1]["total_compras"] or 0) - (rows[-1]["total_vendas"] or 0))
            dividendos_acum_dec = rows[-1]["total_dividendos"] or Decimal(0)
            dividendos_acumulados = float(dividendos_acum_dec)

            # Proventos recebidos especificamente neste mês
            dividendos_mes_dec = dividendos_acum_dec - prev_dividendos_acum
            if dividendos_mes_dec < Decimal(0):
                dividendos_mes_dec = Decimal(0)
            dividendos_mes = float(dividendos_mes_dec)

            prev_dividendos_acum = dividendos_acum_dec

            all_results.append({
                "data": rows[-1]["data"].isoformat(),
                "ohlc": [o, h, l, c],
                "investido": investido,
                "patrimonio": c,
                "total_dividendos": dividendos_acumulados,
                "total_dividendos_mes": dividendos_mes,
            })

        if meses and len(all_results) > meses:
            all_results = all_results[-meses:]

        return all_results

    def series_anual(self, *, anos: int | None = 10) -> list[dict]:
        """Gera a série anual consolidada em formato OHLC de patrimônio e investimentos.

        Args:
            anos: Número de anos de retrocesso histórico. Defaults to 10.

        Returns:
            list[dict]: Lista contendo dicionários com a evolução anual.
        """
        qs = self._linhas_diarias()

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

    def obter_rentabilidade_mensal_por_ano(self) -> dict[int, dict[int, float]]:
        """Gera um dicionário mapeando ano -> {mes: rentabilidade_mensal_percentual}.

        Calculado com base na variação de rentabilidade absoluta em relação à base de capital
        do início do mês ajustado pelas contribuições líquidas do próprio mês.
        """
        qs = self._linhas_diarias()

        # Agrupar por (ano, mês) e pegar o último registro de cada mês (fim do mês)
        groups = {}
        for row in qs:
            d = row["data"]
            groups[(d.year, d.month)] = row

        sorted_keys = sorted(groups.keys())
        matrix = {}

        for i, (year, month) in enumerate(sorted_keys):
            row_current = groups[(year, month)]
            
            # Obter snapshot do fim do mês anterior
            row_prev = None
            if i > 0:
                row_prev = groups[sorted_keys[i-1]]

            # Calcular variação de rentabilidade absoluta
            rent_current = row_current["rentabilidade"] or Decimal(0)
            rent_prev = row_prev["rentabilidade"] or Decimal(0) if row_prev else Decimal(0)
            delta_rentabilidade = rent_current - rent_prev

            # Calcular a base de capital do período:
            # Patrimônio no fim do mês anterior + aportes líquidos do mês
            patrimonio_prev = row_prev["patrimonio"] or Decimal(0) if row_prev else Decimal(0)
            
            compras_current = row_current["total_compras"] or Decimal(0)
            compras_prev = row_prev["total_compras"] or Decimal(0) if row_prev else Decimal(0)
            delta_compras = compras_current - compras_prev

            vendas_current = row_current["total_vendas"] or Decimal(0)
            vendas_prev = row_prev["total_vendas"] or Decimal(0) if row_prev else Decimal(0)
            delta_vendas = vendas_current - vendas_prev

            aportes_liquidos = delta_compras - delta_vendas
            if aportes_liquidos < 0:
                aportes_liquidos = Decimal(0)

            base_capital = patrimonio_prev + aportes_liquidos

            if base_capital > 0:
                retorno_mensal = (delta_rentabilidade / base_capital) * Decimal(100)
            else:
                retorno_mensal = Decimal(0)

            # Garantir formato de float com 4 casas decimais para manter leveza e precisão
            retorno_float = float(round(retorno_mensal, 4))

            if year not in matrix:
                matrix[year] = {}
            matrix[year][month] = retorno_float

        return matrix


def atualizar_historico_para_todos(*, ate_data: date | None = None) -> dict:
    """Sincroniza atomaticamente os snapshots históricos de todos os usuários do sistema.

    Args:
        ate_data: Data limite de atualização. Defaults to None (hoje).

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

