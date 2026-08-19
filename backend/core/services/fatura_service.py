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

    Args:
        usuario (User): Instância do usuário proprietário.

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

    Args:
        conta (Conta): Fatura consolidada ou compra individual de cartão.

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

    Args:
        usuario (User): Instância do usuário proprietário.
        cartao (CartaoCredito): Instância do cartão de crédito correspondente.
        data_vencimento (date): Data de vencimento prevista da fatura.

    Returns:
        Conta: A instância de fatura existente ou recém-criada.
    """
    mes = data_vencimento.month
    ano = data_vencimento.year

    # Buscar fatura existente para este cartão/mês/ano.
    # Ordenamos por id para que a escolha seja determinística caso a base já
    # contenha faturas duplicadas do mesmo período (ver comando
    # `corrigir_faturas_duplicadas`), evitando que o sistema alterne entre elas.
    existentes = list(
        Conta.objects.filter(
            usuario=usuario,
            cartao=cartao,
            eh_fatura_cartao=True,
            data_prevista__year=ano,
            data_prevista__month=mes,
        ).order_by("id")
    )

    if existentes:
        if len(existentes) > 1:
            logger.warning(
                "Encontradas %d faturas duplicadas para o cartão %s em %02d/%d "
                "(ids=%s). Execute `manage.py corrigir_faturas_duplicadas`.",
                len(existentes), cartao, mes, ano, [f.id for f in existentes],
            )
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


def deduplicar_faturas(usuario=None, dry_run: bool = False) -> list[dict]:
    """Garante uma única fatura consolidada por usuário/cartão/mês.

    Faturas consolidadas duplicadas surgem quando um mesmo período ganha mais de
    uma linha `Conta` com `eh_fatura_cartao=True` — tipicamente ao restaurar um
    backup gerado por uma versão que criava faturas "fantasma" durante o import.

    Em cada grupo duplicado preserva a fatura liquidada (que carrega a data de
    pagamento real) ou, na ausência de uma paga, a mais antiga. As compras
    individuais do cartão NÃO são tocadas: elas se vinculam à fatura por
    `data_prevista`, portanto seguem corretamente associadas à fatura preservada.

    Args:
        usuario (User, optional): Restringe a limpeza a um usuário. None varre todos.
        dry_run (bool): Se True, apenas relata as duplicidades sem excluir nada.

    Returns:
        list[dict]: Um registro por período duplicado, com as chaves `cartao_id`,
            `usuario_id`, `ano`, `mes`, `mantida` (Conta) e `removidas` (list[Conta]).
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

        relatorio.append({
            "usuario_id": usuario_id,
            "cartao_id": cartao_id,
            "ano": ano,
            "mes": mes,
            "mantida": mantida,
            "removidas": removidas,
        })
        ids_para_remover.extend(f.id for f in removidas)

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

    Args:
        fatura (Conta): Instância da fatura consolidada.

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

    Args:
        fatura (Conta): Instância da fatura consolidada a excluir.

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


