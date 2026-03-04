"""
Serviço para gestão de faturas de cartão de crédito.

Responsabilidades:
- Criar/obter fatura para um cartão e data de vencimento
- Atualizar valor total da fatura baseado nas despesas vinculadas
- Sincronizar status de pagamento entre fatura e despesas
"""

from datetime import date
from decimal import Decimal
import calendar

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


def add_months(d: date, months: int) -> date:
    """Adiciona n meses a uma data, lidando com o fim do mês corretamente."""
    y = d.year + (d.month - 1 + months) // 12
    m = (d.month - 1 + months) % 12 + 1
    last_day = calendar.monthrange(y, m)[1]
    day = min(d.day, last_day)
    return date(y, m, day)


def calcular_vencimento_fatura(
    data_compra: date, dia_fechamento: int, dia_vencimento: int
) -> date:
    """Calcula a data de vencimento da fatura baseado na data da compra."""
    ano = data_compra.year
    mes = data_compra.month
    dia = data_compra.day

    if dia <= dia_fechamento:
        mes_fechamento = mes
        ano_fechamento = ano
    else:
        if mes == 12:
            mes_fechamento = 1
            ano_fechamento = ano + 1
        else:
            mes_fechamento = mes + 1
            ano_fechamento = ano

    if dia_vencimento > dia_fechamento:
        mes_vencimento = mes_fechamento
        ano_vencimento = ano_fechamento
    else:
        if mes_fechamento == 12:
            mes_vencimento = 1
            ano_vencimento = ano_fechamento + 1
        else:
            mes_vencimento = mes_fechamento + 1
            ano_vencimento = ano_fechamento

    ultimo_dia_mes = calendar.monthrange(ano_vencimento, mes_vencimento)[1]
    dia_venc = min(dia_vencimento, ultimo_dia_mes)

    return date(ano_vencimento, mes_vencimento, dia_venc)


def cents_to_decimal(cents: int) -> Decimal:
    """Converte centavos (int) para Decimal monetário."""
    return (Decimal(cents) / Decimal(100)).quantize(Decimal("0.01"))
