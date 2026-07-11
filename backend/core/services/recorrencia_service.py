"""Serviço de Geração de Ocorrências de Receita Recorrente.

Como o projeto não possui Celery/cron, as ocorrências futuras (`Conta`) de uma
`ReceitaRecorrente` são geradas sob demanda: ao criar/editar a regra, e ao
listar Receitas de um período além do horizonte já gerado. A geração é
idempotente — chamar duas vezes para o mesmo período nunca duplica registros.
"""

from datetime import date, timedelta
from dateutil.relativedelta import relativedelta

from django.db.models import Max

from core.models import Conta, ReceitaRecorrente
from core.services.fatura_service import add_months

HORIZONTE_PADRAO_MESES = 12


def _proxima_data(data_atual: date, frequencia: str) -> date:
    """Calcula a próxima data de ocorrência a partir da frequência da regra.

    Mensal/anual reaproveitam `add_months` (já trata dia 31 em mês curto).
    """
    if frequencia == ReceitaRecorrente.FREQ_MENSAL:
        return add_months(data_atual, 1)
    if frequencia == ReceitaRecorrente.FREQ_ANUAL:
        return add_months(data_atual, 12)
    if frequencia == ReceitaRecorrente.FREQ_QUINZENAL:
        return data_atual + timedelta(days=14)
    if frequencia == ReceitaRecorrente.FREQ_SEMANAL:
        return data_atual + timedelta(days=7)
    raise ValueError(f"Frequência desconhecida: {frequencia!r}")


def gerar_ocorrencias(regra: ReceitaRecorrente, ate_data: date) -> int:
    """Gera as ocorrências (`Conta`) de uma regra até `ate_data`, sem duplicar.

    Args:
        regra (ReceitaRecorrente): A regra de recorrência.
        ate_data (date): Data limite (inclusive) até onde gerar ocorrências.

    Returns:
        int: Quantidade de novas ocorrências criadas.
    """
    limite = ate_data
    if regra.data_fim and regra.data_fim < limite:
        limite = regra.data_fim

    ultima = (
        regra.ocorrencias.aggregate(max_data=Max("data_prevista"))["max_data"]
    )
    candidata = _proxima_data(ultima, regra.frequencia) if ultima else regra.data_inicio

    criadas = 0
    while candidata <= limite:
        _, criado = Conta.objects.get_or_create(
            receita_recorrente=regra,
            data_prevista=candidata,
            defaults={
                "usuario": regra.usuario,
                "tipo": Conta.TIPO_RECEITA,
                "descricao": regra.descricao,
                "categoria": regra.categoria,
                "valor": regra.valor,
            },
        )
        if criado:
            criadas += 1
        candidata = _proxima_data(candidata, regra.frequencia)

    return criadas


def criar_regra_e_gerar(usuario, descricao, categoria, valor, frequencia, data_inicio, data_fim=None) -> tuple[ReceitaRecorrente, Conta]:
    """Cria a regra de recorrência e gera imediatamente suas ocorrências iniciais.

    Returns:
        tuple[ReceitaRecorrente, Conta]: A regra criada e sua primeira ocorrência.
    """
    regra = ReceitaRecorrente.objects.create(
        usuario=usuario,
        descricao=descricao,
        categoria=categoria,
        valor=valor,
        frequencia=frequencia,
        data_inicio=data_inicio,
        data_fim=data_fim,
    )
    horizonte = data_inicio + relativedelta(months=HORIZONTE_PADRAO_MESES)
    gerar_ocorrencias(regra, horizonte)
    primeira_ocorrencia = regra.ocorrencias.order_by("data_prevista").first()
    return regra, primeira_ocorrencia


def estender_horizonte_se_necessario(usuario, mes: int, ano: int) -> None:
    """Estende a geração de ocorrências de todas as regras ativas do usuário.

    Chamada antes de listar Receitas de um mês/ano: se o período pedido for
    além do horizonte já coberto por alguma regra ativa, gera mais ocorrências.
    """
    fim_periodo = date(ano, mes, 1) + relativedelta(months=1) - timedelta(days=1)
    horizonte_minimo = fim_periodo + relativedelta(months=1)

    regras_ativas = ReceitaRecorrente.objects.filter(usuario=usuario, ativa=True)
    for regra in regras_ativas:
        ultima = regra.ocorrencias.aggregate(max_data=Max("data_prevista"))["max_data"]
        coberto_ate = ultima or (regra.data_inicio - timedelta(days=1))
        if coberto_ate < horizonte_minimo:
            gerar_ocorrencias(regra, horizonte_minimo)


def pausar_regra(regra: ReceitaRecorrente) -> None:
    """Interrompe a geração futura sem apagar ocorrências já existentes."""
    regra.ativa = False
    regra.save(update_fields=["ativa", "atualizada_em"])


def propagar_edicao(regra: ReceitaRecorrente, **campos) -> int:
    """Atualiza a regra e propaga os campos para ocorrências futuras não realizadas.

    Nunca toca ocorrências com `transacao_realizada=True` (histórico fechado).

    Returns:
        int: Quantidade de ocorrências futuras atualizadas.
    """
    for campo, valor in campos.items():
        setattr(regra, campo, valor)
    regra.save()

    campos_conta = {k: v for k, v in campos.items() if k in ("descricao", "categoria", "valor")}
    if not campos_conta:
        return 0

    hoje = date.today()
    return regra.ocorrencias.filter(
        transacao_realizada=False, data_prevista__gte=hoje
    ).update(**campos_conta)
