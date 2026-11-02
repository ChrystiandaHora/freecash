"""Sincronização de cotações acionada pelo telão, com guardas contra bloqueio na fonte.

O telão pede uma sincronização a cada 15 minutos, mas quem decide se a fonte externa é
consultada é o servidor. Várias telas, abas ou recarregamentos não multiplicam as
requisições ao TradingView, e um 429 faz todo o servidor recuar.

As guardas, na ordem em que são avaliadas:

1. **Pregão.** Fora de dia de pregão (fim de semana ou feriado da B3, ver
   `services/calendario_b3.py`) ou fora da janela das 09:55 às 18:30 (horário de
   Brasília) o preço não muda, e nada é consultado.
2. **Backoff global.** Depois de um 403/429 o servidor inteiro espera: o bloqueio é do
   IP, então recuar só o usuário que tomou o erro não adiantaria. A pausa vale também
   para o botão manual (ver `services/limite_fonte.py`).
3. **Cooldown por usuário.** Uma consulta a cada `INTERVALO_SINCRONIZACAO`.
4. **Single-flight.** Duas telas que chegam juntas não disparam duas consultas.

A consulta em si é a mesma do botão «Atualizar Cotações», com duas diferenças: a CVM
roda no máximo uma vez por dia (o informe diário é D-1 e vem num ZIP mensal pesado), e
o Yahoo fica de fora (uma requisição por ticker, e a série histórica não muda ao longo
do pregão).

O estado das guardas vive no cache `mercado` (DatabaseCache), compartilhado entre os
workers do gunicorn. As comparações usam o instante gravado, e não só a expiração da
chave, para que `agora` possa ser injetado nos testes.
"""

import datetime
import logging
from dataclasses import dataclass, field, replace

from django.core.cache import caches
from django.db.models import Max
from django.utils import timezone

from investimento.calculators import _atualizar_b3, _atualizar_cvm, ativos_para_cotar
from investimento.models import Cotacao
from investimento.services.calendario_b3 import abertura_do_dia, eh_dia_de_pregao, feriado_b3
from investimento.services.limite_fonte import backoff_ativo_ate
from investimento.services.tradingview_screener import TradingViewLimitado

logger = logging.getLogger(__name__)

INTERVALO_SINCRONIZACAO = datetime.timedelta(minutes=15)

# Falha de rede ou 5xx não prende o ciclo inteiro: tenta de novo antes, sem martelar
RETENTATIVA_APOS_FALHA = datetime.timedelta(minutes=5)

# Cobre o pior caso de TradingView + download da CVM sem prender o lock para sempre
LOCK_TTL_SEGUNDOS = 120

# Inclui o after-market, quando o último preço ainda muda; a abertura vem do calendário
FECHAMENTO_PREGAO = datetime.time(18, 30)

ATUALIZADO = "atualizado"
EM_CACHE = "em_cache"
FORA_DO_PREGAO = "fora_do_pregao"
LIMITADO = "limitado"
FALHOU = "falhou"


@dataclass(frozen=True)
class ResultadoSincronizacao:
    """Desfecho de um pedido de sincronização.

    Atributos:
        status: Um de `ATUALIZADO`, `EM_CACHE`, `FORA_DO_PREGAO`, `LIMITADO` ou `FALHOU`.
        proxima_em: A partir de quando um novo pedido pode ir à fonte.
        atualizado_em: Quando uma cotação do usuário foi gravada pela última vez.
        count: Cotações gravadas nesta chamada.
        errors: Erros por ativo, escopados ao usuário.
        motivo: Por que o pregão está fechado (ex.: "Finados"), só em `FORA_DO_PREGAO`.
    """

    status: str
    proxima_em: datetime.datetime
    atualizado_em: datetime.datetime | None
    count: int = 0
    errors: tuple[str, ...] = field(default_factory=tuple)
    motivo: str | None = None

    def como_payload(self) -> dict:
        """Serializa para a resposta da API."""
        return {
            "status": self.status,
            "proxima_em": self.proxima_em.isoformat(),
            "atualizado_em": self.atualizado_em.isoformat() if self.atualizado_em else None,
            "count": self.count,
            "errors": list(self.errors),
            "motivo": self.motivo,
        }


def motivo_pregao_fechado(agora: datetime.datetime) -> str | None:
    """Por que não há negociação em `agora`, ou None se o pregão estiver aberto."""
    local = timezone.localtime(agora)
    dia = local.date()
    if dia.weekday() >= 5:
        return "Fim de semana"
    feriado = feriado_b3(dia)
    if feriado:
        return feriado
    if not abertura_do_dia(dia) <= local.time() <= FECHAMENTO_PREGAO:
        return "Fora do horário de negociação"
    return None


def pregao_aberto(agora: datetime.datetime) -> bool:
    """Diz se `agora` cai na janela de negociação da B3, feriados incluídos."""
    return motivo_pregao_fechado(agora) is None


def proxima_abertura(agora: datetime.datetime) -> datetime.datetime:
    """Próximo instante de abertura do pregão, estritamente depois de `agora`."""
    local = timezone.localtime(agora)
    dia = local.date()
    while True:
        if eh_dia_de_pregao(dia):
            abertura = abertura_do_dia(dia)
            candidato = local.replace(
                year=dia.year, month=dia.month, day=dia.day,
                hour=abertura.hour, minute=abertura.minute, second=0, microsecond=0,
            )
            if candidato > local:
                return candidato
        dia += datetime.timedelta(days=1)


def ultima_atualizacao_cotacoes(usuario) -> datetime.datetime | None:
    """Quando uma cotação de algum ativo do usuário foi gravada pela última vez."""
    return Cotacao.objects.filter(
        ativo__usuario=usuario, ativo__ativo=True
    ).aggregate(ultima=Max("atualizada_em"))["ultima"]


def _chave(nome: str, usuario) -> str:
    return f"{nome}:{usuario.pk}"


def sincronizar_mercado(usuario, agora: datetime.datetime | None = None) -> ResultadoSincronizacao:
    """Atualiza as cotações do usuário se as guardas permitirem.

    Args:
        usuario: Dono dos ativos; a consulta e os erros ficam restritos a ele.
        agora: Instante de referência (injetável nos testes). Padrão: `timezone.now()`.

    Returns:
        ResultadoSincronizacao: O que aconteceu e quando vale pedir de novo.
    """
    agora = agora or timezone.now()
    cache = caches["mercado"]

    def resultado(status: str, proxima_em: datetime.datetime, count=0, errors=()):
        return ResultadoSincronizacao(
            status=status,
            proxima_em=proxima_em,
            atualizado_em=ultima_atualizacao_cotacoes(usuario),
            count=count,
            errors=tuple(errors),
        )

    motivo = motivo_pregao_fechado(agora)
    if motivo:
        return replace(resultado(FORA_DO_PREGAO, proxima_abertura(agora)), motivo=motivo)

    backoff_ate = backoff_ativo_ate(agora)
    if backoff_ate:
        return resultado(LIMITADO, backoff_ate)

    ultima = cache.get(_chave("ultima", usuario))
    if ultima and agora - ultima < INTERVALO_SINCRONIZACAO:
        return resultado(EM_CACHE, ultima + INTERVALO_SINCRONIZACAO)

    chave_lock = _chave("lock", usuario)
    if not cache.add(chave_lock, True, timeout=LOCK_TTL_SEGUNDOS):
        # Outra tela já está consultando; o resultado dela aparece no próximo ciclo
        return resultado(EM_CACHE, agora + datetime.timedelta(minutes=1))

    try:
        return _consultar_fontes(usuario, agora, cache, resultado)
    finally:
        cache.delete(chave_lock)


def _consultar_fontes(usuario, agora, cache, resultado) -> ResultadoSincronizacao:
    """Executa a consulta propriamente dita, já com o lock do usuário em mãos."""
    errors: list[str] = []
    base = ativos_para_cotar(usuario)

    try:
        count, quotes_by_symbol, fonte_ok = _atualizar_b3(
            base, errors, propagar_limite=True, agora=agora
        )
    except TradingViewLimitado:
        # `_atualizar_b3` já gravou a pausa global
        backoff_ate = backoff_ativo_ate(agora) or agora + RETENTATIVA_APOS_FALHA
        logger.warning("TradingView limitou as consultas; recuando até %s", backoff_ate.isoformat())
        return resultado(LIMITADO, backoff_ate)

    # A CVM publica D-1: uma vez por dia basta, mesmo que a consulta falhe
    hoje = timezone.localdate(agora)
    chave_cvm = _chave("cvm", usuario)
    if cache.get(chave_cvm) != hoje:
        cache.set(chave_cvm, hoje, timeout=int(datetime.timedelta(days=1).total_seconds()))
        count += _atualizar_cvm(base, quotes_by_symbol, errors)

    if not fonte_ok:
        # Sem gravar o cooldown: o próximo pedido, um pouco adiante, tenta de novo
        return resultado(FALHOU, agora + RETENTATIVA_APOS_FALHA, count, errors)

    cache.set(
        _chave("ultima", usuario), agora, timeout=int(INTERVALO_SINCRONIZACAO.total_seconds())
    )
    return resultado(ATUALIZADO, agora + INTERVALO_SINCRONIZACAO, count, errors)
