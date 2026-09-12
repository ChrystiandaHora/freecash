"""Serviço de cálculo e gerenciamento de metas financeiras baseadas em renda e custo de vida."""

from decimal import Decimal

from dateutil.relativedelta import relativedelta
from django.db import transaction
from django.db.models import OuterRef, Subquery, Sum
from django.utils import timezone

from core.models import MetaFinanceira
from core.services.dashboard_helper import (
    month_start,
    next_month_start,
    totals_for_range_competencia,
)

METAS_PADRAO = (
    {
        "tipo": MetaFinanceira.TIPO_PATRIMONIO_RENDA,
        "nome": "Patrimônio para viver de renda",
        "natureza": MetaFinanceira.NATUREZA_ACUMULO,
        "base_calculo": MetaFinanceira.BASE_RENDA,
        "multiplicador": Decimal("200"),
        "ordem": 1,
        "origem_acumulado": MetaFinanceira.ORIGEM_CARTEIRA,
        "observacao": (
            "Referência de quanto acumular para viver da renda dos seus "
            "investimentos no futuro."
        ),
    },
    {
        "tipo": MetaFinanceira.TIPO_APORTE_MENSAL,
        "nome": "Meta mensal investimento",
        "natureza": MetaFinanceira.NATUREZA_ACUMULO,
        "base_calculo": MetaFinanceira.BASE_RENDA,
        "multiplicador": Decimal("0.1"),
        "ordem": 2,
        "origem_acumulado": MetaFinanceira.ORIGEM_APORTES_MES,
        "observacao": (
            "10% da renda mensal para aportar todo mês e construir patrimônio."
        ),
    },
    {
        "tipo": MetaFinanceira.TIPO_RESERVA_EMERGENCIA,
        "nome": "Reserva de emergência",
        "natureza": MetaFinanceira.NATUREZA_ACUMULO,
        "base_calculo": MetaFinanceira.BASE_CUSTO_VIDA,
        "multiplicador": Decimal("6"),
        "ordem": 3,
        "observacao": (
            "Dinheiro aplicado com segurança e liquidez diária, para imprevistos."
        ),
    },
    {
        "tipo": MetaFinanceira.TIPO_GASTO_ESSENCIAL,
        "nome": "Limite de gastos essenciais",
        "natureza": MetaFinanceira.NATUREZA_TETO,
        "base_calculo": MetaFinanceira.BASE_RENDA,
        "multiplicador": Decimal("0.6"),
        "ordem": 4,
        "observacao": (
            "Teto mensal para moradia, alimentação, transporte e demais custos fixos."
        ),
    },
)


def medias_mensais(usuario, meses: int = 3) -> tuple[float, float]:
    """Calcula a média de receitas e despesas por mês na janela especificada."""
    meses = max(int(meses or 1), 1)
    inicio_janela = month_start(timezone.localdate()) - relativedelta(months=meses - 1)

    total_receitas = 0.0
    total_despesas = 0.0
    cursor = inicio_janela
    for _ in range(meses):
        proximo = next_month_start(cursor)
        receitas, despesas = totals_for_range_competencia(usuario, cursor, proximo)
        total_receitas += receitas
        total_despesas += despesas
        cursor = proximo

    return round(total_receitas / meses, 2), round(total_despesas / meses, 2)


def gasto_essencial_do_mes(usuario) -> float:
    """Retorna o total de despesas da competência corrente."""
    inicio = month_start(timezone.localdate())
    _, despesas = totals_for_range_competencia(usuario, inicio, next_month_start(inicio))
    return despesas


def patrimonio_carteira(usuario) -> Decimal:
    """Calcula o valor total de mercado da carteira de investimentos ativa do usuário."""
    from investimento.models import Ativo, Cotacao

    ultima_cotacao = Cotacao.objects.filter(ativo_id=OuterRef("pk")).order_by(
        "-data", "-criada_em"
    )
    ativos = (
        Ativo.objects.filter(usuario=usuario, ativo=True)
        .annotate(cotacao_recente=Subquery(ultima_cotacao.values("valor")[:1]))
        .values_list("quantidade", "preco_medio", "cotacao_recente")
    )

    total = Decimal("0")
    for quantidade, preco_medio, cotacao_recente in ativos:
        quantidade = quantidade or Decimal("0")
        referencia = cotacao_recente if cotacao_recente is not None else (preco_medio or Decimal("0"))
        total += quantidade * referencia

    return total.quantize(Decimal("0.01"))


def aportes_do_mes(usuario) -> Decimal:
    """Soma as compras de ativos executadas no mês corrente."""
    from investimento.models import Transacao

    inicio = month_start(timezone.localdate())
    total = Transacao.objects.filter(
        usuario=usuario,
        tipo=Transacao.TIPO_COMPRA,
        data__gte=inicio,
        data__lt=next_month_start(inicio),
    ).aggregate(total=Sum("valor_total"))["total"] or Decimal("0")

    return Decimal(total).quantize(Decimal("0.01"))


def valores_externos(usuario) -> dict:
    """Retorna mapa de origens automáticas de progresso acumulado."""
    return {
        MetaFinanceira.ORIGEM_CARTEIRA: patrimonio_carteira(usuario),
        MetaFinanceira.ORIGEM_APORTES_MES: aportes_do_mes(usuario),
    }


def calcular_valor_alvo(definicao: dict, renda: Decimal | None, custo_vida: Decimal | None) -> Decimal:
    """Aplica o multiplicador da meta sobre a base correspondente."""
    base_map = {
        MetaFinanceira.BASE_RENDA: renda,
        MetaFinanceira.BASE_CUSTO_VIDA: custo_vida,
    }
    base = base_map.get(definicao.get("base_calculo"))
    multiplicador = definicao.get("multiplicador")

    if base is None or multiplicador is None:
        return Decimal("0.00")

    return (Decimal(base) * Decimal(multiplicador)).quantize(Decimal("0.01"))


@transaction.atomic
def gerar_metas_padrao(usuario, plano) -> list[MetaFinanceira]:
    """Gera ou recalcula as metas padrão do usuário a partir do plano."""
    existentes = {
        meta.tipo: meta
        for meta in MetaFinanceira.objects.filter(
            usuario=usuario, tipo__in=[d["tipo"] for d in METAS_PADRAO]
        )
    }

    metas = []
    for definicao in METAS_PADRAO:
        meta = existentes.get(definicao["tipo"])

        if meta is None:
            meta = MetaFinanceira.objects.create(
                usuario=usuario,
                tipo=definicao["tipo"],
                nome=definicao["nome"],
                natureza=definicao["natureza"],
                base_calculo=definicao["base_calculo"],
                multiplicador=definicao["multiplicador"],
                valor_alvo=calcular_valor_alvo(
                    definicao, plano.renda_mensal, plano.custo_vida_mensal
                ),
                ordem=definicao["ordem"],
                observacao=definicao["observacao"],
                origem_acumulado=definicao.get(
                    "origem_acumulado", MetaFinanceira.ORIGEM_MANUAL
                ),
            )
        else:
            meta.valor_alvo = calcular_valor_alvo(
                {
                    "base_calculo": meta.base_calculo,
                    "multiplicador": meta.multiplicador,
                },
                plano.renda_mensal,
                plano.custo_vida_mensal,
            )
            meta.save(update_fields=["valor_alvo", "atualizada_em"])

        metas.append(meta)

    return metas


def multiplicadores_padrao() -> dict:
    """Retorna os multiplicadores originais de fábrica de cada meta padrão."""
    return {d["tipo"]: str(d["multiplicador"]) for d in METAS_PADRAO}

