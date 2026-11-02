"""Calendário de pregões da B3: feriados sem sessão e dias de horário especial.

Conferido contra o calendário oficial de 2026 (b3.com.br, "Calendário de negociação da
B3", publicado em 09/01/2026). As datas móveis saem da Páscoa: Carnaval (segunda e
terça), Sexta-feira Santa e Corpus Christi. A B3 funciona nos feriados municipais de
São Paulo (25/01 e 09/07) e não abre em 24/12 nem em 31/12.

A B3 pode mudar o calendário; quando mudar, é aqui que se ajusta.
"""

import datetime
from functools import lru_cache

FERIADOS_FIXOS = {
    (1, 1): "Confraternização Universal",
    (4, 21): "Tiradentes",
    (5, 1): "Dia do Trabalho",
    (9, 7): "Independência do Brasil",
    (10, 12): "Nossa Senhora Aparecida",
    (11, 2): "Finados",
    (11, 15): "Proclamação da República",
    (11, 20): "Dia Nacional de Zumbi e da Consciência Negra",
    (12, 24): "Véspera de Natal",
    (12, 25): "Natal",
    (12, 31): "Véspera de Ano Novo",
}

ABERTURA_PADRAO = datetime.time(9, 55)
# Quarta-feira de Cinzas: pré-abertura às 12h45 e negociação a partir das 13h
ABERTURA_QUARTA_DE_CINZAS = datetime.time(12, 55)


def pascoa(ano: int) -> datetime.date:
    """Domingo de Páscoa pelo algoritmo gregoriano anônimo (Meeus/Jones/Butcher)."""
    a = ano % 19
    b, c = divmod(ano, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    l = (32 + 2 * e + 2 * i - h - k) % 7  # noqa: E741
    m = (a + 11 * h + 22 * l) // 451
    mes, dia = divmod(h + l - 7 * m + 114, 31)
    return datetime.date(ano, mes, dia + 1)


@lru_cache(maxsize=8)
def feriados_b3(ano: int) -> dict[datetime.date, str]:
    """Dias sem pregão no ano, com o nome do feriado."""
    domingo = pascoa(ano)
    moveis = {
        domingo - datetime.timedelta(days=48): "Carnaval",
        domingo - datetime.timedelta(days=47): "Carnaval",
        domingo - datetime.timedelta(days=2): "Sexta-feira Santa",
        domingo + datetime.timedelta(days=60): "Corpus Christi",
    }
    fixos = {datetime.date(ano, mes, dia): nome for (mes, dia), nome in FERIADOS_FIXOS.items()}
    return {**fixos, **moveis}


def feriado_b3(data: datetime.date) -> str | None:
    """Nome do feriado sem pregão em `data`, ou None se não for feriado."""
    return feriados_b3(data.year).get(data)


def eh_dia_de_pregao(data: datetime.date) -> bool:
    """Dia útil que não é feriado da B3."""
    return data.weekday() < 5 and feriado_b3(data) is None


def abertura_do_dia(data: datetime.date) -> datetime.time:
    """Horário a partir do qual vale consultar cotações naquele dia de pregão."""
    quarta_de_cinzas = pascoa(data.year) - datetime.timedelta(days=46)
    return ABERTURA_QUARTA_DE_CINZAS if data == quarta_de_cinzas else ABERTURA_PADRAO
