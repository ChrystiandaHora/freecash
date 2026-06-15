"""Serviço de Gestão e Processamento de Faturas de Cartão de Crédito.

Este módulo concentra as regras de negócio de consolidação de faturas, cálculo
de datas de fechamento e vencimento de gastos, além da coordenação atômica de
pagamentos e estornos das compras parceladas e individuais do cartão de crédito.
"""

from datetime import date
from decimal import Decimal
import calendar

from django.db import transaction
from django.db.models import Sum

from core.models import Conta


def obter_ou_criar_fatura(usuario, cartao, data_vencimento: date) -> Conta:
    """Obtém ou cria uma fatura consolidada para o cartão na data de vencimento especificada.

    A fatura é representada como uma entidade 'Conta' especial marcada com a
    flag 'eh_fatura_cartao=True' e isolada por usuário.

    Args:
        usuario (User): Instância do usuário proprietário.
        cartao (CartaoCredito): Instância do cartão de crédito correspondente.
        data_vencimento (date): Data de vencimento prevista da fatura.

    Returns:
        Conta: A instância de fatura existente ou recém-criada.
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
    """Recalcula e salva o valor total consolidado da fatura com base nas despesas vinculadas.

    Soma de forma segura os valores de todas as compras individuais associadas à
    fatura, desde que a fatura ainda não esteja liquidada (paga).

    Args:
        fatura (Conta): Instância da fatura que receberá a atualização.
    """
    if fatura.transacao_realizada:
        return

    # Somar todas as despesas vinculadas a esta fatura
    total = Conta.objects.filter(
        usuario=fatura.usuario,
        cartao=fatura.cartao,
        eh_fatura_cartao=False,
        data_prevista=fatura.data_prevista
    ).aggregate(total=Sum("valor"))["total"] or Decimal("0.00")

    fatura.valor = total
    fatura.save(update_fields=["valor", "atualizada_em"])


@transaction.atomic
def pagar_fatura(fatura: Conta, data_pagamento: date = None) -> None:
    """Realiza a liquidação atômica da fatura e de todas as suas compras individuais vinculadas.

    Args:
        fatura (Conta): Instância da fatura a ser paga.
        data_pagamento (date, optional): Data de realização do pagamento. Defaults to timezone.localdate().
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
        usuario=fatura.usuario,
        cartao=fatura.cartao,
        eh_fatura_cartao=False,
        data_prevista=fatura.data_prevista
    ).update(
        transacao_realizada=True,
        data_realizacao=data_pagamento,
    )


@transaction.atomic
def desfazer_pagamento_fatura(fatura: Conta) -> None:
    """Desfaz atomaticamente o pagamento da fatura e de todas as despesas vinculadas.

    Retorna a fatura e seus lançamentos de despesa associados para o estado pendente.

    Args:
        fatura (Conta): Instância da fatura.
    """
    # Desmarcar fatura
    fatura.transacao_realizada = False
    fatura.data_realizacao = None
    fatura.save(
        update_fields=["transacao_realizada", "data_realizacao", "atualizada_em"]
    )

    # Desmarcar todas as despesas vinculadas
    Conta.objects.filter(
        usuario=fatura.usuario,
        cartao=fatura.cartao,
        eh_fatura_cartao=False,
        data_prevista=fatura.data_prevista
    ).update(
        transacao_realizada=False,
        data_realizacao=None,
    )


def fatura_pode_ser_editada(fatura: Conta) -> bool:
    """Verifica se a fatura consolidada pode sofrer modificações.

    Args:
        fatura (Conta): Instância da fatura analisada.

    Returns:
        bool: True se a fatura estiver aberta (não liquidada), False caso contrário.
    """
    return not fatura.transacao_realizada


def despesa_pode_ser_editada(despesa: Conta) -> bool:
    """Verifica se uma despesa individual atrelada a cartão pode ser alterada.

    Args:
        despesa (Conta): Lançamento de despesa analisado.

    Returns:
        bool: False se a despesa pertencer a uma fatura já liquidada/paga.
    """
    if despesa.cartao:
        fatura = Conta.objects.filter(
            usuario=despesa.usuario,
            cartao=despesa.cartao,
            eh_fatura_cartao=True,
            data_prevista=despesa.data_prevista
        ).first()
        if fatura and fatura.transacao_realizada:
            return False
    return True


def add_months(d: date, months: int) -> date:
    """Adiciona um número inteiro de meses a uma data com tratamento de dias de fim de mês.

    Lida corretamente com anos bissextos e transições de viradas de ano.

    Args:
        d (date): Data de referência.
        months (int): Quantidade de meses a adicionar (positivo ou negativo).

    Returns:
        date: A data final calculada.
    """
    y = d.year + (d.month - 1 + months) // 12
    m = (d.month - 1 + months) % 12 + 1
    last_day = calendar.monthrange(y, m)[1]
    day = min(d.day, last_day)
    return date(y, m, day)


def calcular_vencimento_fatura(
    data_compra: date, dia_fechamento: int, dia_vencimento: int
) -> date:
    """Calcula a data correta de vencimento da fatura do cartão baseado na data de compra.

    Utiliza as definições de dia de fechamento do cartão do usuário para decidir se a
    compra cai na fatura atual ou se passa para o mês seguinte (compra pós-fechamento).

    Args:
        data_compra (date): Data de ocorrência da compra física.
        dia_fechamento (int): Dia do mês que fecha a fatura do cartão.
        dia_vencimento (int): Dia do mês que vence a fatura do cartão.

    Returns:
        date: A data de vencimento da fatura na qual esta despesa será cobrada.
    """
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
    """Converte valores expressos em centavos inteiros para Decimal monetário.

    Args:
        cents (int): Valor bruto expresso em centavos.

    Returns:
        Decimal: O valor convertido em reais (ex: 1500 centavos -> Decimal('15.00')).
    """
    return (Decimal(cents) / Decimal(100)).quantize(Decimal("0.01"))


def detectar_vencimento_fatura(linhas_extraidas: list, cartao) -> date | None:
    """Detecta a data de vencimento da fatura com base na moda (vencimento mais comum) das transações.

    Args:
        linhas_extraidas (list): Lista de dicionários das transações extraídas.
        cartao (CartaoCredito): Instância do cartão de crédito correspondente.

    Returns:
        date | None: A data de vencimento detectada ou None.
    """
    from collections import Counter

    due_dates = []
    for line in linhas_extraidas:
        if line.get("tipo", "D") == "D":
            due_date = calcular_vencimento_fatura(
                line["data"],
                cartao.dia_fechamento,
                cartao.dia_vencimento
            )
            due_dates.append(due_date)

    if due_dates:
        return Counter(due_dates).most_common(1)[0][0]
    return None


