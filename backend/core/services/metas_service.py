"""
Serviço de Metas Financeiras.

Concentra a regra de bolso que deriva quatro alvos financeiros a partir de dois
números-base — renda mensal e custo de vida mensal:

    * Patrimônio para viver de renda ....... renda mensal x 200
    * Meta mensal (aporte) ................. renda mensal x 0,1  (por mês)
    * Reserva de emergência ................ custo de vida mensal x 6
    * Limite de gastos essenciais .......... renda mensal x 0,6 (teto mensal)

Também calcula as médias mensais sugeridas a partir dos lançamentos já
cadastrados, reaproveitando as agregações do dashboard para herdar o
tratamento de faturas de cartão.
"""

from decimal import Decimal

from dateutil.relativedelta import relativedelta
from django.db import transaction
from django.db.models import OuterRef, Subquery, Sum
from django.utils import timezone

from core.models import MetaFinanceira
from core.services.dashboard_helper import (
    month_start,
    next_month_start,
    totals_for_range_competencia,
)


# Definição declarativa das metas padrão. É a única fonte dos multiplicadores:
# alterar um número aqui reflete no cálculo, na API e na tela.
METAS_PADRAO = (
    {
        "tipo": MetaFinanceira.TIPO_PATRIMONIO_RENDA,
        "nome": "Patrimônio para viver de renda",
        "natureza": MetaFinanceira.NATUREZA_ACUMULO,
        "base_calculo": MetaFinanceira.BASE_RENDA,
        "multiplicador": Decimal("200"),
        "ordem": 1,
        "origem_acumulado": MetaFinanceira.ORIGEM_CARTEIRA,
        "observacao": (
            "Referência de quanto acumular para viver da renda dos seus "
            "investimentos no futuro."
        ),
    },
    {
        "tipo": MetaFinanceira.TIPO_APORTE_MENSAL,
        "nome": "Meta mensal investimento",
        "natureza": MetaFinanceira.NATUREZA_ACUMULO,
        "base_calculo": MetaFinanceira.BASE_RENDA,
        "multiplicador": Decimal("0.1"),
        "ordem": 2,
        "origem_acumulado": MetaFinanceira.ORIGEM_APORTES_MES,
        "observacao": (
            "10% da renda mensal para aportar todo mês e construir patrimônio."
        ),
    },
    {
        "tipo": MetaFinanceira.TIPO_RESERVA_EMERGENCIA,
        "nome": "Reserva de emergência",
        "natureza": MetaFinanceira.NATUREZA_ACUMULO,
        "base_calculo": MetaFinanceira.BASE_CUSTO_VIDA,
        "multiplicador": Decimal("6"),
        "ordem": 3,
        "observacao": (
            "Dinheiro aplicado com segurança e liquidez diária, para imprevistos."
        ),
    },
    {
        "tipo": MetaFinanceira.TIPO_GASTO_ESSENCIAL,
        "nome": "Limite de gastos essenciais",
        "natureza": MetaFinanceira.NATUREZA_TETO,
        "base_calculo": MetaFinanceira.BASE_RENDA,
        "multiplicador": Decimal("0.6"),
        "ordem": 4,
        "observacao": (
            "Teto mensal para moradia, alimentação, transporte e demais custos fixos."
        ),
    },
)


def medias_mensais(usuario, meses: int = 3) -> tuple[float, float]:
    """
    Calcula a média mensal de receitas e despesas dos últimos meses fechados.

    A janela termina no mês corrente (inclusive) e recua `meses` competências.
    Cada mês é somado por `totals_for_range_competencia`, que já descarta as
    compras individuais de cartão quando existe fatura consolidada — sem isso o
    gasto no cartão seria contado duas vezes.

    Args:
        usuario (User): Instância do usuário autenticado no Django.
        meses (int): Quantidade de competências consideradas na média (mínimo 1).

    Returns:
        tuple[float, float]: Média de (receitas, despesas) por mês.
    """
    meses = max(int(meses or 1), 1)

    # Recua até o primeiro mês da janela para depois percorrer no sentido cronológico.
    inicio_janela = month_start(timezone.localdate()) - relativedelta(months=meses - 1)

    total_receitas = 0.0
    total_despesas = 0.0
    cursor = inicio_janela
    for _ in range(meses):
        proximo = next_month_start(cursor)
        receitas, despesas = totals_for_range_competencia(usuario, cursor, proximo)
        total_receitas += receitas
        total_despesas += despesas
        cursor = proximo

    return round(total_receitas / meses, 2), round(total_despesas / meses, 2)


def gasto_essencial_do_mes(usuario) -> float:
    """
    Soma as despesas com competência no mês corrente.

    Alimenta o acompanhamento da meta de teto: é o valor comparado contra o
    limite de gastos essenciais.

    Args:
        usuario (User): Instância do usuário autenticado no Django.

    Returns:
        float: Total de despesas previstas para o mês corrente.
    """
    inicio = month_start(timezone.localdate())
    _, despesas = totals_for_range_competencia(usuario, inicio, next_month_start(inicio))
    return despesas


def patrimonio_carteira(usuario) -> Decimal:
    """
    Soma o valor de mercado atual da carteira de investimentos do usuário.

    Cada posição é avaliada pela cotação mais recente, caindo para o preço médio
    quando o ativo ainda não tem cotação — o mesmo critério de
    `Ativo.valor_total_atual` e do dashboard de investimentos. A cotação entra
    por `Subquery` para que uma carteira grande não gere uma consulta por ativo.

    Args:
        usuario (User): Instância do usuário autenticado no Django.

    Returns:
        Decimal: Valor de mercado da carteira, com duas casas decimais.
    """
    # Import local: `investimento.models` já importa `core.models`, então um
    # import no topo deste módulo fecharia um ciclo.
    from investimento.models import Ativo, Cotacao

    ultima_cotacao = Cotacao.objects.filter(ativo_id=OuterRef("pk")).order_by(
        "-data", "-criada_em"
    )
    ativos = (
        Ativo.objects.filter(usuario=usuario, ativo=True)
        .annotate(cotacao_recente=Subquery(ultima_cotacao.values("valor")[:1]))
        .values_list("quantidade", "preco_medio", "cotacao_recente")
    )

    total = Decimal("0")
    for quantidade, preco_medio, cotacao_recente in ativos:
        quantidade = quantidade or Decimal("0")
        referencia = cotacao_recente if cotacao_recente is not None else (preco_medio or Decimal("0"))
        total += quantidade * referencia

    return total.quantize(Decimal("0.01"))


def aportes_do_mes(usuario) -> Decimal:
    """
    Soma quanto foi aportado na carteira de investimentos no mês corrente.

    Considera as ordens de compra (`Transacao` do tipo 'C') com data dentro da
    competência atual. Vendas não abatem: rebalancear a carteira não desfaz o
    dinheiro que entrou. Proventos também ficam de fora, por não serem aporte.

    Args:
        usuario (User): Instância do usuário autenticado no Django.

    Returns:
        Decimal: Total aportado no mês, com duas casas decimais.
    """
    # Import local: `investimento.models` já importa `core.models`.
    from investimento.models import Transacao

    inicio = month_start(timezone.localdate())
    total = Transacao.objects.filter(
        usuario=usuario,
        tipo=Transacao.TIPO_COMPRA,
        data__gte=inicio,
        data__lt=next_month_start(inicio),
    ).aggregate(total=Sum("valor_total"))["total"] or Decimal("0")

    return Decimal(total).quantize(Decimal("0.01"))


def valores_externos(usuario) -> dict:
    """
    Resolve, de uma vez, todas as origens automáticas de progresso.

    Serve para que a serialização de uma lista de metas leia estes números do
    contexto em vez de consultar o banco meta a meta.

    Args:
        usuario (User): Instância do usuário autenticado no Django.

    Returns:
        dict: Mapa de `MetaFinanceira.origem_acumulado` para o valor calculado.
    """
    return {
        MetaFinanceira.ORIGEM_CARTEIRA: patrimonio_carteira(usuario),
        MetaFinanceira.ORIGEM_APORTES_MES: aportes_do_mes(usuario),
    }


def calcular_valor_alvo(definicao: dict, renda: Decimal | None, custo_vida: Decimal | None) -> Decimal:
    """
    Aplica o multiplicador de uma meta padrão sobre a base correspondente.

    Args:
        definicao (dict): Entrada de `METAS_PADRAO` (ou equivalente) com as
            chaves `base_calculo` e `multiplicador`.
        renda (Decimal | None): Renda mensal de referência.
        custo_vida (Decimal | None): Custo de vida mensal de referência.

    Returns:
        Decimal: Valor-alvo com duas casas decimais; zero se a base estiver vazia.
    """
    base_map = {
        MetaFinanceira.BASE_RENDA: renda,
        MetaFinanceira.BASE_CUSTO_VIDA: custo_vida,
    }
    base = base_map.get(definicao.get("base_calculo"))
    multiplicador = definicao.get("multiplicador")

    if base is None or multiplicador is None:
        return Decimal("0.00")

    return (Decimal(base) * Decimal(multiplicador)).quantize(Decimal("0.01"))


@transaction.atomic
def gerar_metas_padrao(usuario, plano) -> list[MetaFinanceira]:
    """
    Cria ou recalcula as quatro metas padrão do usuário.

    Cria o que faltar e recalcula os valores-alvo conforme a base atual do plano.

    O que é do usuário não é tocado num recálculo: nome, multiplicador,
    observação, natureza, origem do progresso, valor acumulado, prazo e
    conclusão. O alvo é recomputado a partir do multiplicador **armazenado** —
    quem trocou o ×200 por ×150 continua com ×150 depois de clicar em recalcular.
    Só a criação usa os valores de `METAS_PADRAO`.

    Args:
        usuario (User): Proprietário das metas.
        plano (PlanoMetas): Plano com renda e custo de vida de referência.

    Returns:
        list[MetaFinanceira]: As metas padrão criadas ou atualizadas, em ordem.
    """
    existentes = {
        meta.tipo: meta
        for meta in MetaFinanceira.objects.filter(
            usuario=usuario, tipo__in=[d["tipo"] for d in METAS_PADRAO]
        )
    }

    metas = []
    for definicao in METAS_PADRAO:
        meta = existentes.get(definicao["tipo"])

        if meta is None:
            meta = MetaFinanceira.objects.create(
                usuario=usuario,
                tipo=definicao["tipo"],
                nome=definicao["nome"],
                natureza=definicao["natureza"],
                base_calculo=definicao["base_calculo"],
                multiplicador=definicao["multiplicador"],
                valor_alvo=calcular_valor_alvo(
                    definicao, plano.renda_mensal, plano.custo_vida_mensal
                ),
                ordem=definicao["ordem"],
                observacao=definicao["observacao"],
                origem_acumulado=definicao.get(
                    "origem_acumulado", MetaFinanceira.ORIGEM_MANUAL
                ),
            )
        else:
            meta.valor_alvo = calcular_valor_alvo(
                {
                    "base_calculo": meta.base_calculo,
                    "multiplicador": meta.multiplicador,
                },
                plano.renda_mensal,
                plano.custo_vida_mensal,
            )
            meta.save(update_fields=["valor_alvo", "atualizada_em"])

        metas.append(meta)

    return metas


def multiplicadores_padrao() -> dict:
    """
    Multiplicadores de fábrica de cada meta padrão.

    Alimenta o botão "restaurar padrões" da tela sem que o frontend precise
    repetir os números — `METAS_PADRAO` segue sendo a fonte única.

    Returns:
        dict: Mapa de tipo da meta para o multiplicador padrão, como string.
    """
    return {d["tipo"]: str(d["multiplicador"]) for d in METAS_PADRAO}
