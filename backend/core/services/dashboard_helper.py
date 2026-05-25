"""
Módulo de Agregações Estatísticas e Apoio do Dashboard.

Isola funções de cálculo aritmético, comparação de períodos, e projeção de fluxo
de caixa mensal para manter as views de API limpas e focadas em contratos REST.
"""

import calendar
from dataclasses import dataclass
from datetime import date
from dateutil.relativedelta import relativedelta

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
    """
    Calcula a soma total de receitas e despesas com vencimento previsto (competência)
    dentro do intervalo de datas informado.

    Filtra lançamentos de despesas vinculadas a faturas para evitar duplicidades
    (só inclui compras individuais sem cartão ou a fatura de cartão consolidada).

    Args:
        usuario (User): Instância do usuário autenticado no Django.
        inicio (date): Data de início do intervalo (inclusive).
        fim (date): Data de fim do intervalo (exclusive).

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
    """
    Normaliza valores de data removendo timezone ou convertendo datetimes em dates.

    Args:
        v (datetime | date): O objeto de data a ser normalizado.

    Returns:
        date: A representação simplificada contendo apenas ano, mês e dia.
    """
    return v.date() if hasattr(v, "date") else v


def serie_por_dia_competencia(usuario, tipo: str, inicio: date, fim: date, ultimo_dia: int) -> tuple[list[str], list[float]]:
    """
    Gera uma série temporal diária agrupando valores previstos para um determinado
    tipo de lançamento (Receitas ou Despesas) ao longo de um mês específico.

    Args:
        usuario (User): Instância do usuário autenticado.
        tipo (str): Tipo de lançamento (ex: Conta.TIPO_RECEITA ou Conta.TIPO_DESPESA).
        inicio (date): Data de início do mês de referência.
        fim (date): Data de fim do mês de referência.
        ultimo_dia (int): Quantidade total de dias no mês.

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
    """
    Gera uma série temporal histórica mensal de 6 meses retroativos para análises financeiras.

    Args:
        usuario (User): Instância do usuário autenticado.
        tipo (str): Tipo de lançamento (Receitas ou Despesas).
        inicio_ref (date): Data inicial do mês mais recente de referência.
        fim_ref (date): Data final do mês mais recente de referência.

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
    """
    Calcula a projeção mensal de fluxo de caixa em uma janela de 6 meses
    (2 meses anteriores, mês atual, e 3 meses subsequentes de projeção).

    Args:
        usuario (User): Instância do usuário autenticado.
        tipo (str): Tipo de lançamento (Receitas ou Despesas).
        inicio_ref (date): Data inicial do mês de referência atual.

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


def breakdown_despesas_competencia(usuario, inicio: date, fim: date, total_despesas: float, top_n: int = 4) -> tuple[list[dict], dict]:
    """
    Realiza o detalhamento de gastos agrupados por categoria dentro de um período,
    isolando as 'N' categorias mais caras e agrupando o restante em "Outros".

    Args:
        usuario (User): Instância do usuário autenticado.
        inicio (date): Início do período (inclusive).
        fim (date): Fim do período (exclusive).
        total_despesas (float): Valor total de despesas consolidadas no período.
        top_n (int, opcional): Quantidade de categorias principais a listar. Padrão 4.

    Returns:
        tuple[list[dict], dict]: Lista de despesas formatadas com porcentagens e dicionário da maior categoria.
    """
    qs = (
        Conta.objects.filter(
            usuario=usuario,
            tipo=Conta.TIPO_DESPESA,
            data_prevista__gte=inicio,
            data_prevista__lt=fim,
        )
        .filter(Q(cartao__isnull=True) | Q(eh_fatura_cartao=True))
        .values("categoria__nome")
        .annotate(total=Sum("valor"))
        .order_by("-total")
    )

    itens = [
        {
            "nome": (row["categoria__nome"] or "Sem categoria"),
            "valor": float(row["total"] or 0),
        }
        for row in qs
    ]

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
    """
    Limita e sanitiza um valor inteiro contido em uma string dentro de limites mínimo e máximo.

    Args:
        value (str): A string a ser convertida em inteiro.
        default (int): O valor padrão de retorno se a conversão falhar.
        min_v (int): O limite mínimo aceitável.
        max_v (int): O limite máximo aceitável.

    Returns:
        int: O número inteiro sanitizado e restrito ao intervalo.
    """
    value = (value or "").strip()
    if not value.isdigit():
        return default
    return max(min(int(value), max_v), min_v)


def month_start(d: date) -> date:
    """
    Retorna a data correspondente ao primeiro dia do mês da data informada.

    Args:
        d (date): A data de referência.

    Returns:
        date: A data normalizada para o primeiro dia do mesmo mês.
    """
    return d.replace(day=1)


def next_month_start(d: date) -> date:
    """
    Calcula e retorna o primeiro dia do mês subsequente à data informada.

    Args:
        d (date): A data de referência.

    Returns:
        date: A data correspondente ao primeiro dia do próximo mês.
    """
    return (d.replace(day=28) + relativedelta(days=4)).replace(day=1)


def make_periodo(hoje: date, periodo_idx: int) -> Periodo:
    """
    Gera as datas de controle para um período baseado em um índice de deslocamento
    (0 = mês atual, 1 = mês anterior, 2 = próximo mês).

    Args:
        hoje (date): Data atual (hoje).
        periodo_idx (int): O índice representativo do período.

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
    """
    Gera as datas de controle para um mês e ano específicos definidos pelo usuário.

    Args:
        ano (int): O ano de referência (ex: 2026).
        mes (int): O mês de referência (1 a 12).

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
    """
    Calcula a variação percentual entre o valor atual e o valor do período anterior.

    Args:
        atual (float): O valor consolidado no mês de referência.
        anterior (float): O valor consolidado no mês anterior.

    Returns:
        float | None: A variação percentual calculada ou None caso o valor anterior seja nulo.
    """
    if not anterior:
        return None
    return float(((atual - anterior) / anterior) * 100.0)


def totals_for_range_realizadas(usuario, inicio: date, fim: date) -> tuple[float, float]:
    """
    Calcula a soma de receitas e despesas efetuadas (regime de caixa) com base na data de realização.

    Args:
        usuario (User): Instância do usuário autenticado.
        inicio (date): Data de início da realização (inclusive).
        fim (date): Data de fim da realização (exclusive).

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


def serie_por_dia_realizadas(usuario, tipo: str, inicio: date, fim: date, ultimo_dia: int) -> tuple[list[str], list[float]]:
    """
    Gera uma série diária agregando lançamentos realizados (regime de caixa) dentro de um mês.

    Args:
        usuario (User): Instância do usuário.
        tipo (str): Tipo de lançamento (Receitas/Despesas).
        inicio (date): Início do mês.
        fim (date): Fim do mês.
        ultimo_dia (int): Quantidade de dias no mês.

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
    """
    Gera o histórico mensal de 6 meses de contas realizadas (caixa).

    Args:
        usuario (User): Instância do usuário.
        tipo (str): Tipo de lançamento (Receitas/Despesas).
        inicio_ref (date): Início do mês atual.
        fim_ref (date): Fim do mês atual.

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
    """
    Gera o breakdown detalhado de despesas realizadas por categoria.

    Args:
        usuario (User): Instância do usuário.
        inicio (date): Início do período.
        fim (date): Fim do período.
        total_despesas (float): Soma total de despesas realizadas.
        top_n (int, opcional): Quantidade de categorias principais. Padrão 4.

    Returns:
        tuple[list[dict], dict]: Breakdown detalhado e maior categoria encontrada.
    """
    qs = (
        Conta.objects.filter(
            usuario=usuario,
            tipo=Conta.TIPO_DESPESA,
            transacao_realizada=True,
            data_realizacao__gte=inicio,
            data_realizacao__lt=fim,
        )
        .filter(Q(cartao__isnull=True) | Q(eh_fatura_cartao=True))
        .values("categoria__nome")
        .annotate(total=Sum("valor"))
        .order_by("-total")
    )

    itens = [
        {
            "nome": (row["categoria__nome"] or "Sem categoria"),
            "valor": float(row["total"] or 0),
        }
        for row in qs
    ]

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
    """
    Gera o painel comparativo financeiro consolidado dos últimos 3 meses
    (do mais recente para o mais antigo) baseado em competência.

    Args:
        usuario (User): Instância do usuário autenticado.
        inicio_ref (date): Data inicial do mês de referência mais recente.

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
