"""Serviço de Gestão e Processamento de Faturas de Cartão de Crédito.

Este módulo concentra as regras de negócio de consolidação de faturas, cálculo
de datas de fechamento e vencimento de gastos, além da coordenação atômica de
pagamentos e estornos das compras parceladas e individuais do cartão de crédito.
"""

from datetime import date
from decimal import Decimal
import calendar
import logging

from django.db import transaction
from django.db.models import Sum

from core.models import Categoria, Conta

logger = logging.getLogger(__name__)


# Nome da categoria usada para caracterizar automaticamente gastos de cartão
# que o usuário ainda não classificou manualmente.
CATEGORIA_CARTAO_NOME = "Cartão de Crédito"


def obter_categoria_cartao(usuario) -> Categoria:
    """Obtém (ou cria) a categoria de despesa que caracteriza gastos de cartão.

    Serve como classificação automática de fallback: toda fatura consolidada e
    toda compra individual importada sem classificação manual recebe esta
    categoria, evitando que o gasto apareça como "Sem categoria" nos painéis.

    Returns:
        Categoria: A categoria "Cartão de Crédito" do usuário.
    """
    categoria, _ = Categoria.objects.get_or_create(
        usuario=usuario,
        nome=CATEGORIA_CARTAO_NOME,
        defaults={"tipo": Categoria.TIPO_DESPESA},
    )
    return categoria


def garantir_categoria_cartao(conta: Conta) -> bool:
    """Garante que um lançamento de cartão tenha alguma categoria atribuída.

    Não sobrescreve uma classificação existente — apenas preenche o vazio com a
    categoria "Cartão de Crédito".

    Returns:
        bool: True se a categoria foi preenchida agora, False se já existia.
    """
    if conta.categoria_id:
        return False

    conta.categoria = obter_categoria_cartao(conta.usuario)
    conta.save(update_fields=["categoria", "atualizada_em"])
    return True


def obter_ou_criar_fatura(usuario, cartao, data_vencimento: date) -> Conta:
    """Obtém ou cria uma fatura consolidada para o cartão na data de vencimento especificada.

    A fatura é representada como uma entidade 'Conta' especial marcada com a
    flag 'eh_fatura_cartao=True' e isolada por usuário.

    Returns:
        Conta: A instância de fatura existente ou recém-criada.
    """
    mes = data_vencimento.month
    ano = data_vencimento.year

    # Casa por data exata, a mesma chave que `compras_da_fatura`, `atualizar_valor_fatura`
    # e `pagar_fatura` usam. Buscar por mês aqui e por data exata lá deixava a compra de
    # outro dia do mesmo mês consolidada na busca e invisível na soma (ver docs/fatura-cartao.md).
    existentes = list(
        Conta.objects.filter(
            usuario=usuario,
            cartao=cartao,
            eh_fatura_cartao=True,
            data_prevista=data_vencimento,
        ).order_by("id")
    )

    # O aviso continua por mês: mais de uma fatura no período é sinal para o operador,
    # ainda que não defina mais qual delas recebe a compra.
    no_mes = Conta.objects.filter(
        usuario=usuario,
        cartao=cartao,
        eh_fatura_cartao=True,
        data_prevista__year=ano,
        data_prevista__month=mes,
    ).count()
    if no_mes > 1:
        logger.warning(
            "Encontradas %d faturas para o cartão %s em %02d/%d. "
            "Execute `manage.py corrigir_faturas_duplicadas`.",
            no_mes, cartao, mes, ano,
        )

    if existentes:
        # Prioriza uma fatura já liquidada, que carrega o histórico de pagamento
        for fatura in existentes:
            if fatura.transacao_realizada:
                return fatura
        return existentes[0]

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
        categoria=obter_categoria_cartao(usuario),
    )

    return fatura


def atualizar_valor_fatura(fatura: Conta) -> None:
    """Recalcula e salva o valor total consolidado da fatura com base nas despesas vinculadas.

    Soma de forma segura os valores de todas as compras individuais associadas à
    fatura, desde que a fatura ainda não esteja liquidada (paga).
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
        data_pagamento: Data de realização do pagamento. Defaults to timezone.localdate().
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


def deduplicar_faturas(usuario=None, dry_run: bool = False) -> list[dict]:
    """Garante uma única fatura consolidada por usuário/cartão/mês.

    Duplicatas surgem quando um período ganha mais de uma `Conta` com
    `eh_fatura_cartao=True` — tipicamente ao restaurar backup de uma versão que criava
    faturas fantasma no import.

    Em cada grupo preserva a fatura liquidada, que carrega a data de pagamento real, ou a
    mais antiga. As compras das faturas removidas são **reatribuídas** à mantida: o vínculo
    é por `data_prevista`, então apagar uma fatura de outro dia do mesmo mês deixaria as
    compras dela sem fatura nenhuma — órfãs no extrato e fora de qualquer soma.

    Args:
        usuario: Restringe a limpeza a um usuário. None varre todos.

    Returns:
        list[dict]: Um registro por período duplicado, com `cartao_id`, `usuario_id`,
            `ano`, `mes`, `mantida` (Conta), `removidas` (list[Conta]) e
            `datas_reatribuidas` (list[date]) — as datas cujas compras mudaram de fatura.
    """
    from collections import defaultdict

    queryset = Conta.objects.filter(eh_fatura_cartao=True)
    if usuario is not None:
        queryset = queryset.filter(usuario=usuario)

    grupos = defaultdict(list)
    for fatura in queryset.order_by("id"):
        chave = (
            fatura.usuario_id,
            fatura.cartao_id,
            fatura.data_prevista.year,
            fatura.data_prevista.month,
        )
        grupos[chave].append(fatura)

    relatorio = []
    ids_para_remover = []

    for (usuario_id, cartao_id, ano, mes), lista in sorted(grupos.items()):
        if len(lista) < 2:
            continue

        mantida = next(
            (f for f in lista if f.transacao_realizada),
            lista[0],
        )
        removidas = [f for f in lista if f.id != mantida.id]

        datas_orfas = [
            f.data_prevista for f in removidas if f.data_prevista != mantida.data_prevista
        ]

        relatorio.append({
            "usuario_id": usuario_id,
            "cartao_id": cartao_id,
            "ano": ano,
            "mes": mes,
            "mantida": mantida,
            "removidas": removidas,
            "datas_reatribuidas": datas_orfas,
        })
        ids_para_remover.extend(f.id for f in removidas)
        if datas_orfas and not dry_run:
            movidas = Conta.objects.filter(
                usuario_id=usuario_id,
                cartao_id=cartao_id,
                eh_fatura_cartao=False,
                data_prevista__in=datas_orfas,
            ).update(data_prevista=mantida.data_prevista)
            if movidas:
                logger.info(
                    "Deduplicação: %d compra(s) reatribuída(s) à fatura %s.",
                    movidas, mantida.id,
                )

    if ids_para_remover and not dry_run:
        with transaction.atomic():
            Conta.objects.filter(id__in=ids_para_remover).delete()
        logger.info(
            "Deduplicação de faturas: %d fatura(s) duplicada(s) removida(s) (ids=%s).",
            len(ids_para_remover), ids_para_remover,
        )

    return relatorio


def compras_da_fatura(fatura: Conta):
    """Retorna o queryset das compras individuais vinculadas a uma fatura consolidada.

    O vínculo entre uma compra e sua fatura é implícito: mesmo usuário, mesmo
    cartão e mesma data de vencimento (`data_prevista`).

    Returns:
        QuerySet: Compras individuais do cartão pertencentes a esta fatura.
    """
    return Conta.objects.filter(
        usuario=fatura.usuario,
        cartao=fatura.cartao,
        eh_fatura_cartao=False,
        data_prevista=fatura.data_prevista,
    )


@transaction.atomic
def excluir_fatura(fatura: Conta) -> int:
    """Exclui a fatura consolidada junto com todas as compras individuais dela.

    A remoção é atômica e os signals de reconsolidação são desconectados durante
    a operação: sem isso, a exclusão de cada compra tentaria recalcular (e
    possivelmente recriar) a fatura que está sendo removida.

    Returns:
        int: Quantidade de compras individuais removidas junto com a fatura.
    """
    from django.db.models.signals import post_save, post_delete
    from core.signals import monitorar_salvamento_conta, monitorar_delecao_conta

    compras = compras_da_fatura(fatura)
    total_compras = compras.count()

    post_save.disconnect(monitorar_salvamento_conta, sender=Conta)
    post_delete.disconnect(monitorar_delecao_conta, sender=Conta)
    try:
        compras.delete()
        fatura.delete()
    finally:
        post_save.connect(monitorar_salvamento_conta, sender=Conta)
        post_delete.connect(monitorar_delecao_conta, sender=Conta)

    return total_compras


def fatura_pode_ser_editada(fatura: Conta) -> bool:
    """Verifica se a fatura consolidada pode sofrer modificações.

    Returns:
        bool: True se a fatura estiver aberta (não liquidada), False caso contrário.
    """
    return not fatura.transacao_realizada


def despesa_pode_ser_editada(despesa: Conta) -> bool:
    """Verifica se uma despesa individual atrelada a cartão pode ser alterada.

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
        months: Quantidade de meses a adicionar (positivo ou negativo).

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
        cents: Valor bruto expresso em centavos.

    Returns:
        Decimal: O valor convertido em reais (ex: 1500 centavos -> Decimal('15.00')).
    """
    return (Decimal(cents) / Decimal(100)).quantize(Decimal("0.01"))


def detectar_vencimento_fatura(linhas_extraidas: list, cartao) -> date | None:
    """Detecta o vencimento da fatura pela moda dos vencimentos das transações.

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


