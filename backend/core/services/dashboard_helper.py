"""
Módulo de Agregações Estatísticas e Apoio do Dashboard.

Isola funções de cálculo aritmético, comparação de períodos, e projeção de fluxo
de caixa mensal para manter as views de API limpas e focadas em contratos REST.
"""

import calendar
from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from dateutil.relativedelta import relativedelta

from decimal import Decimal

from django.db.models import Sum, Q
from django.db.models.functions import TruncDay, TruncMonth

from core.models import Conta


@dataclass(frozen=True)
class Periodo:
    """
    Representa um período de tempo (ex: mês corrente) com datas limites
    e metadados para fins de filtragem de competência de lançamentos.
    """
    idx: int
    label: str
    inicio: date
    fim: date
    inicio_prev: date
    ultimo_dia: int


def totals_for_range_competencia(usuario, inicio: date, fim: date) -> tuple[float, float]:
    """Calcula a soma total de receitas e despesas com vencimento previsto (competência)
    dentro do intervalo de datas informado.

    Filtra lançamentos de despesas vinculadas a faturas para evitar duplicidades
    (só inclui compras individuais sem cartão ou a fatura de cartão consolidada).

    Args:
        inicio: Data de início do intervalo (inclusive).
        fim: Data de fim do intervalo (exclusive).

    Returns:
        tuple[float, float]: Uma tupla contendo (total_receitas, total_despesas).
    """
    qs = Conta.objects.filter(
        usuario=usuario,
        data_prevista__gte=inicio,
        data_prevista__lt=fim,
    ).filter(Q(cartao__isnull=True) | Q(eh_fatura_cartao=True))
    receitas = (
        qs.filter(tipo=Conta.TIPO_RECEITA).aggregate(total=Sum("valor"))["total"] or 0
    )
    despesas = (
        qs.filter(tipo=Conta.TIPO_DESPESA).aggregate(total=Sum("valor"))["total"] or 0
    )
    return float(receitas), float(despesas)


def strip_tz(v) -> date:
    """Normaliza valores de data removendo timezone ou convertendo datetimes em dates.

    Args:
        v: O objeto de data a ser normalizado.

    Returns:
        date: A representação simplificada contendo apenas ano, mês e dia.
    """
    return v.date() if hasattr(v, "date") else v


def serie_por_dia_competencia(usuario, tipo: str, inicio: date, fim: date, ultimo_dia: int) -> tuple[list[str], list[float]]:
    """Gera uma série temporal diária agrupando valores previstos para um determinado
    tipo de lançamento (Receitas ou Despesas) ao longo de um mês específico.

    Args:
        tipo: Tipo de lançamento (ex: Conta.TIPO_RECEITA ou Conta.TIPO_DESPESA).

    Returns:
        tuple[list[str], list[float]]: Tupla contendo a lista de labels ("01", "02"...) e os valores acumulados por dia.
    """
    qs = (
        Conta.objects.filter(
            usuario=usuario,
            tipo=tipo,
            data_prevista__gte=inicio,
            data_prevista__lt=fim,
        )
        .filter(Q(cartao__isnull=True) | Q(eh_fatura_cartao=True))
        .annotate(dia=TruncDay("data_prevista"))
        .values("dia")
        .annotate(total=Sum("valor"))
        .order_by("dia")
    )

    mapa = {strip_tz(row["dia"]): float(row["total"] or 0) for row in qs}

    labels, valores = [], []
    for d in range(1, ultimo_dia + 1):
        dt = date(inicio.year, inicio.month, d)
        labels.append(f"{d:02d}")
        valores.append(mapa.get(dt, 0.0))
    return labels, valores


def serie_6m_competencia(usuario, tipo: str, inicio_ref: date, fim_ref: date) -> tuple[list[str], list[float]]:
    """Série mensal dos 6 meses anteriores.

    Returns:
        tuple[list[str], list[float]]: Labels formatados como "Mês/Ano" e seus valores acumulados.
    """
    inicio_janela = inicio_ref - relativedelta(months=5)

    qs = (
        Conta.objects.filter(
            usuario=usuario,
            tipo=tipo,
            data_prevista__gte=inicio_janela,
            data_prevista__lt=fim_ref,
        )
        .filter(Q(cartao__isnull=True) | Q(eh_fatura_cartao=True))
        .annotate(mes=TruncMonth("data_prevista"))
        .values("mes")
        .annotate(total=Sum("valor"))
        .order_by("mes")
    )

    mapa = {strip_tz(row["mes"]).replace(day=1): float(row["total"] or 0) for row in qs}

    labels, values = [], []
    for i in range(5, -1, -1):
        ref = (inicio_ref - relativedelta(months=i)).replace(day=1)
        labels.append(ref.strftime("%b/%Y"))
        values.append(mapa.get(ref, 0.0))
    return labels, values


def serie_fluxo_projetado_competencia(usuario, tipo: str, inicio_ref: date) -> tuple[list[str], list[float]]:
    """Calcula a projeção mensal de fluxo de caixa em uma janela de 6 meses
    (2 meses anteriores, mês atual, e 3 meses subsequentes de projeção).

    Returns:
        tuple[list[str], list[float]]: Labels dos 6 meses de janela e valores correspondentes.
    """
    inicio_janela = inicio_ref - relativedelta(months=2)
    fim_janela = inicio_ref + relativedelta(months=4)

    qs = (
        Conta.objects.filter(
            usuario=usuario,
            tipo=tipo,
            data_prevista__gte=inicio_janela,
            data_prevista__lt=fim_janela,
        )
        .filter(Q(cartao__isnull=True) | Q(eh_fatura_cartao=True))
        .annotate(mes=TruncMonth("data_prevista"))
        .values("mes")
        .annotate(total=Sum("valor"))
        .order_by("mes")
    )

    mapa = {strip_tz(row["mes"]).replace(day=1): float(row["total"] or 0) for row in qs}

    labels, values = [], []
    for i in range(-2, 4):
        ref = (inicio_ref + relativedelta(months=i)).replace(day=1)
        labels.append(ref.strftime("%b/%Y"))
        values.append(mapa.get(ref, 0.0))

    return labels, values


SEM_CATEGORIA = "Sem categoria"


def _explodir_fatura_por_categoria(fatura: Conta) -> dict[str, Decimal]:
    """Distribui o valor de uma fatura de cartão entre as categorias de suas compras.

    A fatura consolidada é só o pagamento agregado; o gasto real está nas compras
    vinculadas a ela (mesmo usuário, cartão e `data_prevista`). Compras não classificadas
    entram como "Cartão de Crédito", não como "Sem categoria".

    Se o valor da fatura divergir da soma das compras — fatura liquidada tem valor
    congelado, e há ajuste manual — a diferença é rateada proporcionalmente, para o
    detalhamento continuar somando o total exibido no painel.

    Returns:
        dict[str, Decimal]: Valor da fatura por nome de categoria.
    """
    from core.services.fatura_service import CATEGORIA_CARTAO_NOME

    parcelas: dict[str, Decimal] = defaultdict(Decimal)
    compras = (
        Conta.objects.filter(
            usuario_id=fatura.usuario_id,
            cartao_id=fatura.cartao_id,
            eh_fatura_cartao=False,
            data_prevista=fatura.data_prevista,
        )
        .values("categoria__nome")
        .annotate(total=Sum("valor"))
    )
    for row in compras:
        nome = row["categoria__nome"] or CATEGORIA_CARTAO_NOME
        parcelas[nome] += row["total"] or Decimal("0")

    valor_fatura = fatura.valor or Decimal("0")
    soma_compras = sum(parcelas.values(), Decimal("0"))

    # Fatura sem compras vinculadas (lançada à mão): fica com a própria categoria
    if soma_compras <= 0:
        nome = fatura.categoria.nome if fatura.categoria else CATEGORIA_CARTAO_NOME
        return {nome: valor_fatura}

    if soma_compras == valor_fatura:
        return dict(parcelas)

    fator = valor_fatura / soma_compras
    return {nome: valor * fator for nome, valor in parcelas.items()}


def despesas_por_categoria(usuario, inicio: date, fim: date, campo_data: str, **extra_filtros) -> list[dict]:
    """Agrupa as despesas de um período por categoria, detalhando os gastos de cartão.

    Despesas comuns entram com a própria categoria. Faturas de cartão, que nos
    totais do painel representam todo o gasto do cartão no período, são abertas
    nas categorias das compras que as compõem — assim a classificação que o
    usuário faz em cada compra chega até o gráfico de "Maiores Gastos".

    Args:
        inicio: Início do período (inclusive).
        fim: Fim do período (exclusive).

    Returns:
        list[dict]: Itens `{"nome", "valor"}` ordenados do maior para o menor valor.
    """
    filtros = {
        "usuario": usuario,
        "tipo": Conta.TIPO_DESPESA,
        f"{campo_data}__gte": inicio,
        f"{campo_data}__lt": fim,
        **extra_filtros,
    }

    totais: dict[str, Decimal] = defaultdict(Decimal)

    despesas_comuns = (
        Conta.objects.filter(cartao__isnull=True, **filtros)
        .values("categoria__nome")
        .annotate(total=Sum("valor"))
    )
    for row in despesas_comuns:
        nome = row["categoria__nome"] or SEM_CATEGORIA
        totais[nome] += row["total"] or Decimal("0")

    faturas = Conta.objects.filter(
        eh_fatura_cartao=True, cartao__isnull=False, **filtros
    ).select_related("categoria")
    for fatura in faturas:
        for nome, valor in _explodir_fatura_por_categoria(fatura).items():
            totais[nome] += valor

    itens = [{"nome": nome, "valor": float(valor)} for nome, valor in totais.items()]
    itens.sort(key=lambda item: item["valor"], reverse=True)
    return itens


def breakdown_despesas_competencia(usuario, inicio: date, fim: date, total_despesas: float, top_n: int = 4) -> tuple[list[dict], dict]:
    """Realiza o detalhamento de gastos agrupados por categoria dentro de um período,
    isolando as 'N' categorias mais caras e agrupando o restante em "Outros".

    Args:
        inicio: Início do período (inclusive).
        fim: Fim do período (exclusive).
        top_n: Quantidade de categorias principais a listar. Padrão 4.

    Returns:
        tuple[list[dict], dict]: Lista de despesas formatadas com porcentagens e dicionário da maior categoria.
    """
    itens = despesas_por_categoria(usuario, inicio, fim, "data_prevista")

    if not itens or total_despesas <= 0:
        return [], {"nome": "Sem dados", "valor": 0.0, "pct": 0.0}

    top = itens[:top_n]
    soma_top = sum(i["valor"] for i in top)
    outros = max(total_despesas - soma_top, 0.0)

    out = [
        {
            "nome": i["nome"],
            "valor": i["valor"],
            "pct": (i["valor"] / total_despesas) * 100.0,
        }
        for i in top
    ]

    if outros > 0:
        out.append(
            {
                "nome": "Outros",
                "valor": outros,
                "pct": (outros / total_despesas) * 100.0,
            }
        )

    if out:
        total_pct = sum(x["pct"] for x in out)
        out[-1]["pct"] = max(0.0, out[-1]["pct"] - (total_pct - 100.0))

    top1 = out[0] if out else {"nome": "Sem dados", "valor": 0.0, "pct": 0.0}
    return out, top1


def clamp_int(value: str, default: int = 0, min_v: int = 0, max_v: int = 2) -> int:
    """Converte a string para inteiro, preso entre os limites informados.

    Args:
        default: O valor padrão de retorno se a conversão falhar.
        min_v: O limite mínimo aceitável.
        max_v: O limite máximo aceitável.

    Returns:
        int: O número inteiro sanitizado e restrito ao intervalo.
    """
    value = (value or "").strip()
    if not value.isdigit():
        return default
    return max(min(int(value), max_v), min_v)


def month_start(d: date) -> date:
    """Retorna a data correspondente ao primeiro dia do mês da data informada.

    Returns:
        date: A data normalizada para o primeiro dia do mesmo mês.
    """
    return d.replace(day=1)


def next_month_start(d: date) -> date:
    """Calcula e retorna o primeiro dia do mês subsequente à data informada.

    Returns:
        date: A data correspondente ao primeiro dia do próximo mês.
    """
    return (d.replace(day=28) + relativedelta(days=4)).replace(day=1)


def make_periodo(hoje: date, periodo_idx: int) -> Periodo:
    """Gera as datas de controle para um período baseado em um índice de deslocamento
    (0 = mês atual, 1 = mês anterior, 2 = próximo mês).

    Returns:
        Periodo: A instância de Periodo estruturada contendo os limites de datas.
    """
    labels = {0: "Mês atual", 1: "Mês anterior", 2: "Próximo mês"}

    if periodo_idx == 0:
        inicio = month_start(hoje)
    elif periodo_idx == 1:
        inicio = month_start(hoje) - relativedelta(months=1)
    elif periodo_idx == 2:
        inicio = month_start(hoje) + relativedelta(months=1)
    else:
        inicio = month_start(hoje)

    fim = next_month_start(inicio)
    inicio_prev = inicio - relativedelta(months=1)

    ultimo_dia = calendar.monthrange(inicio.year, inicio.month)[1]

    return Periodo(
        idx=periodo_idx,
        label=labels.get(periodo_idx, "Mês atual"),
        inicio=inicio,
        fim=fim,
        inicio_prev=inicio_prev,
        ultimo_dia=ultimo_dia,
    )


def make_periodo_custom(ano: int, mes: int) -> Periodo:
    """Gera as datas de controle para um mês e ano específicos definidos pelo usuário.

    Returns:
        Periodo: A instância de Periodo estruturada contendo os limites e o label traduzido.
    """
    inicio = date(ano, mes, 1)
    fim = next_month_start(inicio)
    inicio_prev = inicio - relativedelta(months=1)
    ultimo_dia = calendar.monthrange(ano, mes)[1]

    meses_pt = {
        1: "Janeiro", 2: "Fevereiro", 3: "Março", 4: "Abril",
        5: "Maio", 6: "Junho", 7: "Julho", 8: "Agosto",
        9: "Setembro", 10: "Outubro", 11: "Novembro", 12: "Dezembro"
    }
    label = f"{meses_pt.get(mes, '')} de {ano}"

    return Periodo(
        idx=-1,
        label=label,
        inicio=inicio,
        fim=fim,
        inicio_prev=inicio_prev,
        ultimo_dia=ultimo_dia,
    )


def pct_change(atual: float, anterior: float) -> float | None:
    """Calcula a variação percentual entre o valor atual e o valor do período anterior.

    Returns:
        float | None: A variação percentual calculada ou None caso o valor anterior seja nulo.
    """
    if not anterior:
        return None
    return float(((atual - anterior) / anterior) * 100.0)


def totals_for_range_realizadas(usuario, inicio: date, fim: date) -> tuple[float, float]:
    """Soma receitas e despesas efetuadas, por data de realização (regime de caixa).

    Args:
        inicio: Data de início da realização (inclusive).
        fim: Data de fim da realização (exclusive).

    Returns:
        tuple[float, float]: Uma tupla contendo (receitas_realizadas, despesas_realizadas).
    """
    qs = Conta.objects.filter(
        usuario=usuario,
        transacao_realizada=True,
        data_realizacao__gte=inicio,
        data_realizacao__lt=fim,
    ).filter(Q(cartao__isnull=True) | Q(eh_fatura_cartao=True))

    receitas = (
        qs.filter(tipo=Conta.TIPO_RECEITA).aggregate(total=Sum("valor"))["total"] or 0
    )
    despesas = (
        qs.filter(tipo=Conta.TIPO_DESPESA).aggregate(total=Sum("valor"))["total"] or 0
    )
    return float(receitas), float(despesas)


def saldo_liquidez_ate(usuario, ate: date) -> float:
    """Calcula a liquidez acumulada — o dinheiro efetivamente em caixa — até uma data.

    Diferente de `totals_for_range_realizadas`, a soma é aberta no início: percorre todo
    o histórico realizado até `ate`. É o saldo que ancora a projeção do simulador; sem
    ele a curva partiria de zero e mediria fluxo líquido, não saldo.

    O filtro de cartão é obrigatório: sem ele a compra individual somaria junto da fatura
    consolidada e o caixa apareceria menor do que é.

    Args:
        ate: Data limite da realização (inclusive).

    Returns:
        float: Receitas menos despesas realizadas até `ate`. A subtração é feita em
            Decimal para o valor não chegar à tela com ruído de ponto flutuante.
    """
    qs = Conta.objects.filter(
        usuario=usuario,
        transacao_realizada=True,
        data_realizacao__lte=ate,
    ).filter(Q(cartao__isnull=True) | Q(eh_fatura_cartao=True))

    receitas = (
        qs.filter(tipo=Conta.TIPO_RECEITA).aggregate(total=Sum("valor"))["total"] or 0
    )
    despesas = (
        qs.filter(tipo=Conta.TIPO_DESPESA).aggregate(total=Sum("valor"))["total"] or 0
    )
    return round(float(Decimal(receitas) - Decimal(despesas)), 2)


def serie_por_dia_realizadas(usuario, tipo: str, inicio: date, fim: date, ultimo_dia: int) -> tuple[list[str], list[float]]:
    """Série diária dos lançamentos realizados no mês (regime de caixa).

    Returns:
        tuple[list[str], list[float]]: Labels diários e valores acumulados.
    """
    qs = (
        Conta.objects.filter(
            usuario=usuario,
            tipo=tipo,
            transacao_realizada=True,
            data_realizacao__gte=inicio,
            data_realizacao__lt=fim,
        )
        .filter(Q(cartao__isnull=True) | Q(eh_fatura_cartao=True))
        .annotate(dia=TruncDay("data_realizacao"))
        .values("dia")
        .annotate(total=Sum("valor"))
        .order_by("dia")
    )

    mapa = {strip_tz(row["dia"]): float(row["total"] or 0) for row in qs}

    labels, valores = [], []
    for d in range(1, ultimo_dia + 1):
        dt = date(inicio.year, inicio.month, d)
        labels.append(f"{d:02d}")
        valores.append(mapa.get(dt, 0.0))
    return labels, valores


def serie_6m_realizadas(usuario, tipo: str, inicio_ref: date, fim_ref: date) -> tuple[list[str], list[float]]:
    """Gera o histórico mensal de 6 meses de contas realizadas (caixa).

    Returns:
        tuple[list[str], list[float]]: Labels e valores da série mensal de caixa.
    """
    inicio_janela = inicio_ref - relativedelta(months=5)

    qs = (
        Conta.objects.filter(
            usuario=usuario,
            tipo=tipo,
            transacao_realizada=True,
            data_realizacao__gte=inicio_janela,
            data_realizacao__lt=fim_ref,
        )
        .filter(Q(cartao__isnull=True) | Q(eh_fatura_cartao=True))
        .annotate(mes=TruncMonth("data_realizacao"))
        .values("mes")
        .annotate(total=Sum("valor"))
        .order_by("mes")
    )

    mapa = {strip_tz(row["mes"]).replace(day=1): float(row["total"] or 0) for row in qs}

    labels, values = [], []
    for i in range(5, -1, -1):
        ref = (inicio_ref - relativedelta(months=i)).replace(day=1)
        labels.append(ref.strftime("%b/%Y"))
        values.append(mapa.get(ref, 0.0))
    return labels, values


def breakdown_despesas_realizadas(usuario, inicio: date, fim: date, total_despesas: float, top_n: int = 4) -> tuple[list[dict], dict]:
    """Gera o breakdown detalhado de despesas realizadas por categoria.

    Args:
        top_n: Quantidade de categorias principais. Padrão 4.

    Returns:
        tuple[list[dict], dict]: Breakdown detalhado e maior categoria encontrada.
    """
    itens = despesas_por_categoria(
        usuario, inicio, fim, "data_realizacao", transacao_realizada=True
    )

    if not itens or total_despesas <= 0:
        return [], {"nome": "Sem dados", "valor": 0.0, "pct": 0.0}

    top = itens[:top_n]
    soma_top = sum(i["valor"] for i in top)
    outros = max(total_despesas - soma_top, 0.0)

    out = []
    for i in top:
        out.append(
            {
                "nome": i["nome"],
                "valor": i["valor"],
                "pct": (i["valor"] / total_despesas) * 100.0,
            }
        )

    if outros > 0:
        out.append(
            {
                "nome": "Outros",
                "valor": outros,
                "pct": (outros / total_despesas) * 100.0,
            }
        )

    if out:
        total_pct = sum(x["pct"] for x in out)
        out[-1]["pct"] = max(0.0, out[-1]["pct"] - (total_pct - 100.0))

    top1 = out[0] if out else {"nome": "Sem dados", "valor": 0.0, "pct": 0.0}
    return out, top1


def resumo_ultimos_3_meses_competencia(usuario, inicio_ref: date) -> list[dict]:
    """Gera o painel comparativo financeiro consolidado dos últimos 3 meses
    (do mais recente para o mais antigo) baseado em competência.

    Returns:
        list[dict]: Lista de dicionários contendo o fechamento mensal agrupado.
    """
    itens = []

    for i in range(0, 3):
        inicio_mes = (inicio_ref - relativedelta(months=i)).replace(day=1)
        fim_mes = (inicio_mes + relativedelta(months=1)).replace(day=1)

        qs = Conta.objects.filter(
            usuario=usuario,
            data_prevista__gte=inicio_mes,
            data_prevista__lt=fim_mes,
        ).filter(Q(cartao__isnull=True) | Q(eh_fatura_cartao=True))

        receita = (
            qs.filter(tipo=Conta.TIPO_RECEITA).aggregate(total=Sum("valor"))["total"]
            or 0
        )
        gastos = (
            qs.filter(tipo=Conta.TIPO_DESPESA).aggregate(total=Sum("valor"))["total"]
            or 0
        )

        itens.append(
            {
                "ano": inicio_mes.year,
                "mes": inicio_mes.month,
                "receita": float(receita),
                "outras_receitas": 0.0,
                "gastos": float(gastos),
                "total": float(receita) - float(gastos),
            }
        )

    return itens
