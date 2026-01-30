"""
Serviço para gerenciamento de assinaturas e geração de contas recorrentes.
"""

from datetime import date
from dateutil.relativedelta import relativedelta

from core.models import Assinatura, Conta


def gerar_conta_da_assinatura(
    assinatura: Assinatura, mes_referencia: date = None
) -> Conta:
    """
    Gera uma Conta a partir de uma Assinatura.

    Args:
        assinatura: Assinatura a ser processada
        mes_referencia: Mês de referência para a conta (default: próxima geração)

    Returns:
        Conta criada
    """
    if mes_referencia is None:
        mes_referencia = assinatura.proxima_geracao

    # Calcula a data de vencimento
    dia = min(assinatura.dia_vencimento, 28)  # Evita problemas com meses curtos
    try:
        data_vencimento = mes_referencia.replace(day=assinatura.dia_vencimento)
    except ValueError:
        # Mês não tem esse dia (ex: 31 em fevereiro)
        data_vencimento = mes_referencia.replace(day=dia)

    # Cria a conta
    conta = Conta.objects.create(
        usuario=assinatura.usuario,
        tipo=assinatura.tipo,
        descricao=f"{assinatura.descricao}",
        valor=assinatura.valor,
        data_prevista=data_vencimento,
        categoria=assinatura.categoria,
        forma_pagamento=assinatura.forma_pagamento,
        assinatura=assinatura,
        transacao_realizada=False,
    )

    # Avança a próxima geração em 1 mês
    assinatura.proxima_geracao = assinatura.proxima_geracao + relativedelta(months=1)
    assinatura.save(update_fields=["proxima_geracao", "atualizada_em"])

    return conta


def gerar_contas_pendentes():
    """
    Gera contas para todas as assinaturas ativas cuja data de geração já passou.
    Útil para execução em cronjob ou tarefa agendada.

    Returns:
        Lista de contas geradas
    """
    hoje = date.today()
    assinaturas = Assinatura.objects.filter(ativa=True, proxima_geracao__lte=hoje)

    contas_geradas = []
    for assinatura in assinaturas:
        conta = gerar_conta_da_assinatura(assinatura)
        contas_geradas.append(conta)

    return contas_geradas
