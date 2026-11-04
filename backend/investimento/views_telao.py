"""Endpoints do telão de investimentos (tela cheia com atualização periódica).

O telão lê os KPIs e a alocação de `/api/investimentos/dashboard/` e os sinais de
`/api/investimentos/sinais/`. Aqui ficam só o que eles não dão: a tabela de ativos com
a variação do dia e o pedido de sincronização, que o servidor filtra para não fazer o
IP ser bloqueado pela fonte (ver `services/sincronizacao_mercado.py`).
"""

from decimal import Decimal

from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from core.throttles import AuthScopedRateThrottle
from investimento.services.dashboard_service import DashboardInvestimentoService
from investimento.services.sincronizacao_mercado import (
    sincronizar_mercado,
    ultima_atualizacao_cotacoes,
)
from investimento.views_api import carteira_do_request


def _categoria(ativo) -> str:
    subcategoria = ativo.subcategoria
    if subcategoria and subcategoria.categoria:
        return subcategoria.categoria.nome
    return "Sem Categoria"


def _variacao_percentual(atual: Decimal | None, anterior: Decimal | None) -> float | None:
    if atual is None or not anterior:
        return None
    return float((atual - anterior) / anterior * 100)


def linhas_telao(ativos) -> list[dict]:
    """Monta as linhas da tabela do telão, da maior posição para a menor.

    Sem cotação, o valor cai para o custo (quantidade × preço médio), como no dashboard,
    e a variação do dia fica nula.

    Args:
        ativos: Saída de `DashboardInvestimentoService.ativos_a_mercado(com_cotacao_anterior=True)`.

    Returns:
        list[dict]: Uma linha por ativo com posição aberta, com o peso no total.
    """
    linhas = []
    for a in ativos:
        if not a.quantidade or a.quantidade <= 0:
            continue
        cotacao = a.cotacao_recente
        valor = a.quantidade * (cotacao if cotacao is not None else (a.preco_medio or Decimal(0)))
        linhas.append({
            "id": a.pk,
            "ticker": a.ticker,
            "nome": a.nome,
            "categoria": _categoria(a),
            "preco_medio": float(a.preco_medio or 0),
            "cotacao": float(cotacao) if cotacao is not None else None,
            "cotacao_anterior": float(a.cotacao_anterior) if a.cotacao_anterior is not None else None,
            "cotacao_data": a.cotacao_data.isoformat() if a.cotacao_data else None,
            "variacao_dia_pct": _variacao_percentual(cotacao, a.cotacao_anterior),
            "valor": valor,
        })

    total = sum((linha["valor"] for linha in linhas), Decimal(0))
    for linha in linhas:
        linha["peso_pct"] = float(linha["valor"] / total * 100) if total else 0.0
        linha["valor"] = float(linha["valor"])

    return sorted(linhas, key=lambda linha: linha["valor"], reverse=True)


class TelaoAPIView(APIView):
    """Tabela de ativos do telão: cotação, variação do dia, valor e peso.

    Só lê o banco. Quem traz cotação nova é `TelaoSincronizarAPIView`.
    """

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request) -> Response:
        """Devolve as linhas da tabela e quando as cotações foram gravadas por último."""
        carteira_id = carteira_do_request(request)
        ativos = DashboardInvestimentoService(request.user, carteira_id).ativos_a_mercado(
            com_cotacao_anterior=True
        )
        atualizado_em = ultima_atualizacao_cotacoes(request.user)
        return Response({
            "ativos": linhas_telao(ativos),
            "cotacoes_atualizadas_em": atualizado_em.isoformat() if atualizado_em else None,
            "carteira_filtrada": carteira_id,
        }, status=status.HTTP_200_OK)


class TelaoSincronizarAPIView(APIView):
    """Pedido de sincronização do telão; o servidor decide se vai à fonte.

    Responde 200 mesmo quando nada é consultado: o `status` no corpo diz o que houve e
    `proxima_em` diz quando vale pedir de novo.
    """

    permission_classes = [permissions.IsAuthenticated]
    throttle_classes = [AuthScopedRateThrottle]
    throttle_scope = "telao_sincronizar"

    def post(self, request) -> Response:
        """Sincroniza as cotações do usuário se as guardas permitirem."""
        resultado = sincronizar_mercado(request.user)
        return Response(resultado.como_payload(), status=status.HTTP_200_OK)
