"""Endpoints de planejamento: horizonte de saldos e calendário de pagamentos.

As duas telas respondem à mesma necessidade por ângulos diferentes: o horizonte
mostra *para onde o saldo vai* nos próximos meses; o calendário mostra *o que
acontece nesta semana*. Nenhum dos dois cria lançamento — só o calendário
escreve, e apenas para liquidar o que já existe.

O cálculo vive em `core/services/projecao_service.py`. Estas views validam
parâmetros e delegam.
"""

import logging
from datetime import date
from decimal import Decimal, InvalidOperation

from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from core.models import Conta
from core.services.projecao_service import (
    MESES_MAXIMO,
    MESES_PADRAO,
    calendario_mes,
    horizonte_saldos,
)

logger = logging.getLogger("core")


class HorizonteSaldosAPIView(APIView):
    """Projeta o saldo acumulado dia a dia para os próximos meses."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request) -> Response:
        """Devolve a projeção diária agrupada por mês.

        Args:
            request (Request): Aceita `meses` (tamanho da janela) e
                `limite_atencao` (saldo abaixo do qual o dia é sinalizado).

        Returns:
            Response: 200 com a projeção, ou 400 se `limite_atencao` não for número.
        """
        try:
            meses = int(request.query_params.get("meses", MESES_PADRAO))
        except (TypeError, ValueError):
            meses = MESES_PADRAO

        # Teto no serviço, mas repetido aqui para que a resposta não dependa de
        # um parâmetro absurdo chegar até a camada de cálculo.
        meses = max(1, min(meses, MESES_MAXIMO))

        limite_bruto = request.query_params.get("limite_atencao")
        limite = None
        if limite_bruto not in (None, ""):
            try:
                limite = Decimal(limite_bruto)
            except (InvalidOperation, TypeError, ValueError):
                return Response(
                    {"limite_atencao": ["Informe um valor numérico."]},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        dados = horizonte_saldos(
            request.user, date.today(), meses=meses, limite_atencao=limite
        )
        return Response(dados, status=status.HTTP_200_OK)


class CalendarioPagamentosAPIView(APIView):
    """Lista os pagamentos e recebimentos previstos de um mês, dia a dia."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request) -> Response:
        """Devolve a grade do mês com os lançamentos de cada dia.

        Args:
            request (Request): Aceita `ano` e `mes`; sem eles, usa o mês corrente.

        Returns:
            Response: 200 com a grade, ou 400 se o período for inválido.
        """
        hoje = date.today()
        try:
            ano = int(request.query_params.get("ano", hoje.year))
            mes = int(request.query_params.get("mes", hoje.month))
        except (TypeError, ValueError):
            return Response(
                {"detail": "Ano e mês devem ser números."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not 1 <= mes <= 12:
            return Response(
                {"mes": ["Informe um mês entre 1 e 12."]},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Faixa defensiva: `date(ano, mes, 1)` estoura fora dela, e o erro chegaria
        # como 500 em vez de uma recusa clara.
        if not 1900 <= ano <= 2999:
            return Response(
                {"ano": ["Informe um ano válido."]},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            calendario_mes(request.user, ano, mes), status=status.HTTP_200_OK
        )


class _LiquidacaoBase(APIView):
    """Base das ações de liquidar e desfazer a partir do calendário.

    A ação `pagar` do `ContasPagarViewSet` cobre apenas despesas, porque aquela
    tela só lista despesas. O calendário mostra pagamentos **e** recebimentos, e
    precisa de uma ação que sirva aos dois tipos.

    O escopo por usuário é a única barreira de autorização aqui, e por isso é
    explícito: um lançamento de outra pessoa devolve 404, nunca 403 — a resposta
    não deve confirmar que aquele identificador existe.

    Atributos:
        marcar (bool): Se a ação liquida (True) ou desfaz a liquidação (False).
    """

    permission_classes = [permissions.IsAuthenticated]
    marcar = True

    def post(self, request, pk) -> Response:
        """Aplica a mudança de estado ao lançamento informado.

        Args:
            request (Request): Requisição autenticada. Aceita `data` na liquidação.
            pk (int): Identificador do lançamento.

        Returns:
            Response: 200 com o novo estado, ou 404 se o lançamento não for do
                usuário autenticado.
        """
        conta = Conta.objects.filter(pk=pk, usuario=request.user).first()
        if conta is None:
            return Response(
                {"detail": "Lançamento não encontrado."},
                status=status.HTTP_404_NOT_FOUND,
            )

        if self.marcar:
            data_liquidacao = None
            bruto = request.data.get("data")
            if bruto:
                try:
                    data_liquidacao = date.fromisoformat(bruto)
                except (TypeError, ValueError):
                    return Response(
                        {"data": ["Use o formato AAAA-MM-DD."]},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
            # Idempotente no modelo: chamar duas vezes não altera a data original.
            conta.marcar_realizada(data_liquidacao)
        else:
            conta.desmarcar_realizada()

        return Response(
            {
                "id": conta.id,
                "realizado": conta.transacao_realizada,
                "data_realizacao": (
                    conta.data_realizacao.isoformat()
                    if conta.data_realizacao else None
                ),
            },
            status=status.HTTP_200_OK,
        )


class LiquidarLancamentoAPIView(_LiquidacaoBase):
    """Marca um lançamento como pago ou recebido."""

    marcar = True


class DesfazerLiquidacaoAPIView(_LiquidacaoBase):
    """Devolve um lançamento liquidado ao estado pendente."""

    marcar = False
