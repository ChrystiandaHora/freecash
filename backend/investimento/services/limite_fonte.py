"""Backoff global depois que o TradingView limita as consultas (403/429).

O bloqueio é do IP do servidor, então a pausa vale para todos os usuários e para os dois
caminhos que consultam a fonte: a sincronização do telão e o botão «Atualizar Cotações».
Sem isso, um botão manual insistindo durante a pausa agravaria o bloqueio que o telão
está respeitando.
"""

import datetime

from django.core.cache import caches

CHAVE_BACKOFF = "backoff"

# Espera mínima depois de um limite; um Retry-After maior prevalece, até o teto
BACKOFF_MINIMO = datetime.timedelta(minutes=30)
BACKOFF_MAXIMO = datetime.timedelta(hours=6)


def backoff_ativo_ate(agora: datetime.datetime) -> datetime.datetime | None:
    """Até quando a fonte está em pausa, ou None se não estiver."""
    ate = caches["mercado"].get(CHAVE_BACKOFF)
    return ate if ate and ate > agora else None


def registrar_backoff(retry_after: int | None, agora: datetime.datetime) -> datetime.datetime:
    """Grava a pausa global e devolve até quando ela vale.

    Args:
        retry_after: Segundos sugeridos pela fonte, quando vierem.
        agora: Instante de referência.
    """
    sugerida = datetime.timedelta(seconds=retry_after or 0)
    espera = min(max(sugerida, BACKOFF_MINIMO), BACKOFF_MAXIMO)
    ate = agora + espera
    caches["mercado"].set(CHAVE_BACKOFF, ate, timeout=int(espera.total_seconds()))
    return ate
