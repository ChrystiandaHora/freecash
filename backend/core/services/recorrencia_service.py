"""Serviço de Geração de Ocorrências de Lançamento Recorrente.

Como o projeto não possui Celery/cron, as ocorrências futuras (`Conta`) de um
`LancamentoRecorrente` são geradas sob demanda: ao criar/editar a regra, ao
listar um período além do horizonte já gerado, e ao montar a projeção de saldos.
A geração é idempotente — chamar duas vezes para o mesmo período nunca duplica
registros.

A regra cobre receita **e** despesa. Enquanto cobria só entradas, qualquer
projeção de longo prazo ficava otimista: a receita fixa era materializada meses à
frente e as despesas fixas não existiam fora do que fora lançado à mão.
"""

from datetime import date, timedelta
from dateutil.relativedelta import relativedelta

from django.db.models import Max

from core.models import Conta, LancamentoRecorrente
from core.services.fatura_service import add_months

HORIZONTE_PADRAO_MESES = 12


def _proxima_data(data_atual: date, frequencia: str) -> date:
    """Calcula a próxima data de ocorrência a partir da frequência da regra.

    Mensal/anual reaproveitam `add_months` (já trata dia 31 em mês curto).
    """
    if frequencia == LancamentoRecorrente.FREQ_MENSAL:
        return add_months(data_atual, 1)
    if frequencia == LancamentoRecorrente.FREQ_ANUAL:
        return add_months(data_atual, 12)
    if frequencia == LancamentoRecorrente.FREQ_QUINZENAL:
        return data_atual + timedelta(days=14)
    if frequencia == LancamentoRecorrente.FREQ_SEMANAL:
        return data_atual + timedelta(days=7)
    raise ValueError(f"Frequência desconhecida: {frequencia!r}")


def gerar_ocorrencias(regra: LancamentoRecorrente, ate_data: date) -> int:
    """Gera as ocorrências (`Conta`) de uma regra até `ate_data`, sem duplicar.

    Args:
        ate_data: Data limite (inclusive) até onde gerar ocorrências.

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
            recorrencia=regra,
            data_prevista=candidata,
            defaults={
                "usuario": regra.usuario,
                # O tipo vem da regra: era fixo em receita quando o modelo só
                # cobria entradas.
                "tipo": regra.tipo,
                "descricao": regra.descricao,
                "categoria": regra.categoria,
                "valor": regra.valor,
            },
        )
        if criado:
            criadas += 1
        candidata = _proxima_data(candidata, regra.frequencia)

    return criadas


def criar_regra_e_gerar(usuario, descricao, categoria, valor, frequencia, data_inicio,
                        data_fim=None, tipo=LancamentoRecorrente.TIPO_RECEITA) -> tuple[LancamentoRecorrente, Conta]:
    """Cria a regra de recorrência e gera imediatamente suas ocorrências iniciais.

    Args:
        data_fim: Limite opcional de geração.
        tipo: Receita ou despesa. O default de receita preserva o
            comportamento das chamadas anteriores à generalização do modelo.

    Returns:
        tuple[LancamentoRecorrente, Conta]: A regra criada e sua primeira ocorrência.
    """
    regra = LancamentoRecorrente.objects.create(
        usuario=usuario,
        tipo=tipo,
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

    regras_ativas = LancamentoRecorrente.objects.filter(usuario=usuario, ativa=True)
    for regra in regras_ativas:
        ultima = regra.ocorrencias.aggregate(max_data=Max("data_prevista"))["max_data"]
        coberto_ate = ultima or (regra.data_inicio - timedelta(days=1))
        if coberto_ate < horizonte_minimo:
            gerar_ocorrencias(regra, horizonte_minimo)


def garantir_horizonte(usuario, ate_data: date) -> int:
    """Materializa as ocorrências de todas as regras ativas até `ate_data`.

    `estender_horizonte_se_necessario` resolve "estou listando o mês X"; esta resolve "vou
    projetar até a data Y", que é o que o Horizonte de Saldos precisa. Sem ela, a projeção
    leria só o horizonte já gerado — 12 meses a contar da criação de cada regra, não de
    hoje — e os meses finais viriam vazios. Idempotente: `get_or_create` por
    (regra, data_prevista).

    Args:
        ate_data: Data limite, inclusive.

    Returns:
        int: Quantidade de ocorrências criadas nesta chamada.
    """
    criadas = 0
    regras_ativas = LancamentoRecorrente.objects.filter(usuario=usuario, ativa=True)
    for regra in regras_ativas:
        criadas += gerar_ocorrencias(regra, ate_data)
    return criadas


def pausar_regra(regra: LancamentoRecorrente) -> None:
    """Interrompe a geração futura sem apagar ocorrências já existentes."""
    regra.ativa = False
    regra.save(update_fields=["ativa", "atualizada_em"])


def propagar_edicao(regra: LancamentoRecorrente, **campos) -> int:
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
