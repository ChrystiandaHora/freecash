"""Métricas de plataforma para o painel administrativo.

Este módulo é separado de `dashboard_helper.py` por uma razão estrutural, não
organizacional: todos os auxiliares de lá são escopados por usuário
(`totals_for_range_competencia(usuario, ...)`, `serie_6m_*(usuario, ...)`) porque
respondem "como estão as finanças desta pessoa". As métricas aqui respondem "como
está a plataforma" — agregam sobre todos os usuários e nunca tocam valores
financeiros.

**Limite deliberado:** nada aqui devolve dado financeiro. O painel administrativo
mostra quantidade de lançamentos, nunca soma de valores, nunca saldo, nunca ativo.
Administrar a plataforma não exige ver as finanças de ninguém, e o produto guarda
informação financeira pessoal.
"""

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db.models import Count, Q
from django.db.models.functions import TruncDate
from django.utils import timezone

User = get_user_model()


def _serie_cadastros(dias: int) -> list[dict]:
    """Conta os cadastros por dia nos últimos N dias.

    Args:
        dias: Tamanho da janela, em dias.

    Returns:
        list[dict]: Itens `{"data": "YYYY-MM-DD", "total": int}` em ordem crescente,
            incluindo os dias sem cadastro — uma série com lacunas produziria um
            gráfico que sugere continuidade onde não há dado.
    """
    inicio = timezone.localdate() - timedelta(days=dias - 1)

    contagem = dict(
        User.objects.filter(date_joined__date__gte=inicio)
        .annotate(dia=TruncDate("date_joined"))
        .values_list("dia")
        .annotate(total=Count("id"))
    )

    serie = []
    for deslocamento in range(dias):
        dia = inicio + timedelta(days=deslocamento)
        serie.append({"data": dia.isoformat(), "total": contagem.get(dia, 0)})
    return serie


def coletar_metricas(dias_serie: int = 30) -> dict:
    """Reúne os indicadores de uso da plataforma.

    Todas as contagens saem de `aggregate`, numa única consulta: iterar os usuários
    em Python para contá-los degradaria linearmente com o crescimento da base,
    exatamente no painel usado para acompanhar esse crescimento.

    Args:
        dias_serie: Tamanho da janela da série de cadastros, em dias.

    Returns:
        dict: Indicadores de contas, verificação de e-mail e atividade recente.
    """
    agora = timezone.now()
    limite_7d = agora - timedelta(days=7)
    limite_30d = agora - timedelta(days=30)

    contas = User.objects.aggregate(
        total=Count("id"),
        ativas=Count("id", filter=Q(is_active=True)),
        suspensas=Count("id", filter=Q(is_active=False)),
        administradores=Count("id", filter=Q(is_staff=True)),
        com_email=Count("id", filter=~Q(email="")),
        verificadas=Count("id", filter=Q(config__email_verificado=True)),
        novas_7d=Count("id", filter=Q(date_joined__gte=limite_7d)),
        novas_30d=Count("id", filter=Q(date_joined__gte=limite_30d)),
        ativos_7d=Count("id", filter=Q(last_login__gte=limite_7d)),
        ativos_30d=Count("id", filter=Q(last_login__gte=limite_30d)),
        nunca_acessaram=Count("id", filter=Q(last_login__isnull=True)),
    )

    total = contas["total"] or 0
    verificadas = contas["verificadas"] or 0

    return {
        "contas": contas,
        # Percentual calculado no servidor para que todo consumidor mostre o mesmo
        # número, com o mesmo arredondamento.
        "percentual_verificado": round(verificadas * 100 / total, 1) if total else 0.0,
        "cadastros_por_dia": _serie_cadastros(dias_serie),
        "gerado_em": agora.isoformat(),
    }
