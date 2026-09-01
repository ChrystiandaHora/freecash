"""Serviço de geração e manutenção sob demanda de lançamentos recorrentes (receitas e despesas)."""

from datetime import date, timedelta
from dateutil.relativedelta import relativedelta

from django.db.models import Max

from core.models import Conta, LancamentoRecorrente
from core.services.fatura_service import add_months

HORIZONTE_PADRAO_MESES = 12


def _proxima_data(data_atual: date, frequencia: str) -> date:
    """Calcula a próxima data de ocorrência a partir da frequência da regra."""
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
    """Gera de forma idempotente as ocorrências (Conta) da regra até ate_data."""
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
    """Cria a regra de recorrência e materializa ocorrências iniciais pelo horizonte padrão."""
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
    """Gera novas ocorrências se a listagem do mês solicitado exceder o horizonte atual."""
    fim_periodo = date(ano, mes, 1) + relativedelta(months=1) - timedelta(days=1)
    horizonte_minimo = fim_periodo + relativedelta(months=1)

    regras_ativas = LancamentoRecorrente.objects.filter(usuario=usuario, ativa=True)
    for regra in regras_ativas:
        ultima = regra.ocorrencias.aggregate(max_data=Max("data_prevista"))["max_data"]
        coberto_ate = ultima or (regra.data_inicio - timedelta(days=1))
        if coberto_ate < horizonte_minimo:
            gerar_ocorrencias(regra, horizonte_minimo)


def garantir_horizonte(usuario, ate_data: date) -> int:
    """Garante a materialização de ocorrências de todas as regras ativas até ate_data."""
    criadas = 0
    regras_ativas = LancamentoRecorrente.objects.filter(usuario=usuario, ativa=True)
    for regra in regras_ativas:
        criadas += gerar_ocorrencias(regra, ate_data)
    return criadas


def pausar_regra(regra: LancamentoRecorrente) -> None:
    """Interrompe a geração futura sem apagar ocorrências já criadas."""
    regra.ativa = False
    regra.save(update_fields=["ativa", "atualizada_em"])


def propagar_edicao(regra: LancamentoRecorrente, **campos) -> int:
    """Atualiza a regra e propaga alterações para ocorrências futuras não realizadas."""
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

