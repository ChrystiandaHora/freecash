"""
Serviço para gestão de faturas de cartão de crédito.

Responsabilidades:
- Criar/obter fatura para um cartão e data de vencimento
- Atualizar valor total da fatura baseado nas despesas vinculadas
- Sincronizar status de pagamento entre fatura e despesas
"""

from datetime import date
from decimal import Decimal

from django.db import transaction
from django.db.models import Sum

from core.models import Conta


def obter_ou_criar_fatura(usuario, cartao, data_vencimento: date) -> Conta:
    """
    Obtém ou cria uma fatura para o cartão na data de vencimento especificada.

    A fatura é uma Conta especial marcada com eh_fatura_cartao=True.
    A descrição segue o padrão "Fatura {nome_cartao} - {mes}/{ano}".
    """
    mes = data_vencimento.month
    ano = data_vencimento.year

    # Buscar fatura existente para este cartão/mês/ano
    fatura = Conta.objects.filter(
        usuario=usuario,
        cartao=cartao,
        eh_fatura_cartao=True,
        data_prevista__year=ano,
        data_prevista__month=mes,
    ).first()

    if fatura:
        return fatura

    # Criar nova fatura
    descricao = f"Fatura {cartao.nome} - {mes:02d}/{ano}"

    fatura = Conta.objects.create(
        usuario=usuario,
        tipo=Conta.TIPO_DESPESA,
        descricao=descricao,
        valor=Decimal("0.00"),
        data_prevista=data_vencimento,
        cartao=cartao,
        eh_fatura_cartao=True,
    )

    return fatura


def atualizar_valor_fatura(fatura: Conta) -> None:
    """
    Recalcula o valor total da fatura baseado nas despesas vinculadas.
    Não atualiza se a fatura já foi paga.
    """
    if fatura.transacao_realizada:
        return

    # Somar todas as despesas vinculadas a esta fatura
    total = Conta.objects.filter(
        fatura=fatura,
        eh_fatura_cartao=False,
    ).aggregate(total=Sum("valor"))["total"] or Decimal("0.00")

    fatura.valor = total
    fatura.save(update_fields=["valor", "atualizada_em"])


@transaction.atomic
def pagar_fatura(fatura: Conta, data_pagamento: date = None) -> None:
    """
    Marca a fatura como paga e também todas as despesas vinculadas.

    Args:
        fatura: A fatura a ser paga
        data_pagamento: Data do pagamento (usa hoje se não informada)
    """
    from django.utils import timezone

    if data_pagamento is None:
        data_pagamento = timezone.localdate()

    # Marcar fatura como paga
    fatura.transacao_realizada = True
    fatura.data_realizacao = data_pagamento
    fatura.save(
        update_fields=["transacao_realizada", "data_realizacao", "atualizada_em"]
    )

    # Marcar todas as despesas vinculadas como pagas
    Conta.objects.filter(
        fatura=fatura,
        eh_fatura_cartao=False,
    ).update(
        transacao_realizada=True,
        data_realizacao=data_pagamento,
    )


@transaction.atomic
def desfazer_pagamento_fatura(fatura: Conta) -> None:
    """
    Desfaz o pagamento da fatura e de todas as despesas vinculadas.
    """
    # Desmarcar fatura
    fatura.transacao_realizada = False
    fatura.data_realizacao = None
    fatura.save(
        update_fields=["transacao_realizada", "data_realizacao", "atualizada_em"]
    )

    # Desmarcar todas as despesas vinculadas
    Conta.objects.filter(
        fatura=fatura,
        eh_fatura_cartao=False,
    ).update(
        transacao_realizada=False,
        data_realizacao=None,
    )


def fatura_pode_ser_editada(fatura: Conta) -> bool:
    """
    Verifica se a fatura pode ser editada (não está paga).
    """
    return not fatura.transacao_realizada


def despesa_pode_ser_editada(despesa: Conta) -> bool:
    """
    Verifica se uma despesa de cartão pode ser editada.
    Retorna False se a fatura à qual pertence já foi paga.
    """
    if despesa.fatura and despesa.fatura.transacao_realizada:
        return False
    return True
