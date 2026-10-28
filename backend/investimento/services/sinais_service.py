"""Monta, a partir do banco, os sinais de rebalanceamento de cada posição.

A regra mora em `investimento.sinais`, sem I/O. Aqui ficam só as consultas que a
alimentam: posição com a última cotação, total a mercado por carteira e o valor já
vendido de ações no mês. Ver docs/proposta-sinais-realizacao.md.
"""

import datetime
from decimal import Decimal

from django.db.models import DecimalField, F, OuterRef, Subquery, Sum
from django.utils import timezone

from investimento.models import Cotacao, PosicaoCarteira, Transacao
from investimento.sinais import (
    PosicaoAvaliada,
    Sinal,
    TipoFiscal,
    avaliar_posicao,
)


def vendas_de_acoes_no_mes(usuario, hoje: datetime.date | None = None) -> Decimal:
    """Soma o valor vendido de ações no mês corrente, em todas as carteiras.

    A isenção é por CPF e sobre o valor de alienação (quantidade × preço), não sobre o
    lucro nem sobre o líquido das taxas.

    Returns:
        Decimal: Valor bruto vendido de ações do primeiro dia do mês até hoje.
    """
    hoje = hoje or timezone.localdate()
    total = Transacao.objects.filter(
        usuario=usuario,
        tipo=Transacao.TIPO_VENDA,
        ativo__tipo_fiscal=TipoFiscal.ACAO,
        data__gte=hoje.replace(day=1),
        data__lte=hoje,
    ).aggregate(
        total=Sum(
            F("quantidade") * F("preco_unitario"),
            output_field=DecimalField(max_digits=28, decimal_places=12),
        )
    )["total"]
    return total or Decimal(0)


def avaliar_posicoes(
    usuario,
    carteira_id: int | None = None,
    vendas_acoes_no_mes: Decimal | None = None,
) -> list[tuple[PosicaoCarteira, Sinal]]:
    """Avalia todas as posições abertas do usuário, ou só as de uma carteira.

    A cotação vem anotada por subconsulta: `Ativo.cotacao_atual` faria uma consulta
    por posição.

    Args:
        usuario: Dono das posições.
        carteira_id: Restringe a uma carteira; None avalia todas.
        vendas_acoes_no_mes: Valor já vendido de ações no mês; None consulta o banco.

    Returns:
        list[tuple[PosicaoCarteira, Sinal]]: Cada posição com o seu sinal, inclusive
            as `SEM_SINAL`.
    """
    ultima_cotacao = (
        Cotacao.objects.filter(ativo=OuterRef("ativo"))
        .order_by("-data", "-criada_em")
        .values("valor")[:1]
    )
    posicoes = (
        PosicaoCarteira.objects.filter(usuario=usuario, ativo__ativo=True, quantidade__gt=0)
        .select_related("ativo", "carteira")
        .annotate(cotacao_mercado=Subquery(ultima_cotacao))
        .order_by("carteira__ordem", "carteira__nome", "ativo__ticker")
    )
    if carteira_id:
        posicoes = posicoes.filter(carteira_id=carteira_id)
    posicoes = list(posicoes)

    if vendas_acoes_no_mes is None:
        vendas_acoes_no_mes = vendas_de_acoes_no_mes(usuario)
    totais = _total_a_mercado_por_carteira(posicoes)

    return [
        (
            posicao,
            avaliar_posicao(
                PosicaoAvaliada(
                    quantidade=posicao.quantidade,
                    preco_medio=posicao.ativo.preco_medio,
                    cotacao=posicao.cotacao_mercado,
                    meta_porcentagem=posicao.meta_porcentagem,
                    tipo_fiscal=posicao.ativo.tipo_fiscal,
                ),
                total_mercado_carteira=totais[posicao.carteira_id],
                vendas_acoes_no_mes=vendas_acoes_no_mes,
            ),
        )
        for posicao in posicoes
    ]


def sinal_para_dict(sinal: Sinal) -> dict:
    """Converte o sinal no formato da API, com números em float como no balanceamento.

    Returns:
        dict: Os campos do `Sinal`, prontos para JSON.
    """
    return {
        "tipo": sinal.tipo,
        "queda_relevante": sinal.queda_relevante,
        "peso_mercado": float(sinal.peso_mercado),
        "banda": float(sinal.banda),
        "variacao_preco_medio": _float_ou_none(sinal.variacao_preco_medio),
        "cotas_a_vender": float(sinal.cotas_a_vender),
        "valor_venda": float(sinal.valor_venda),
        "resultado_venda": float(sinal.resultado_venda),
        "isencao": sinal.isencao,
        "cotas_dentro_isencao": _float_ou_none(sinal.cotas_dentro_isencao),
    }


def _total_a_mercado_por_carteira(posicoes: list[PosicaoCarteira]) -> dict[int, Decimal]:
    # Sem cotação, a posição entra pelo custo — o mesmo fallback de `valor_total_atual`
    totais: dict[int, Decimal] = {}
    for posicao in posicoes:
        preco = posicao.cotacao_mercado or posicao.preco_medio
        totais[posicao.carteira_id] = (
            totais.get(posicao.carteira_id, Decimal(0)) + posicao.quantidade * preco
        )
    return totais


def _float_ou_none(valor: Decimal | None) -> float | None:
    return None if valor is None else float(valor)
