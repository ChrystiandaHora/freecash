"""Projeção de saldo diário e agenda de pagamentos e recebimentos.

Responde a duas perguntas de planejamento que nenhuma tela existente respondia:
*em que dia dos próximos doze meses meu saldo fica negativo?* e *o que vence
nesta semana?*

## Como a projeção é construída

O saldo projetado de um dia é a soma de três partes:

1. **A âncora** — o dinheiro que já está em caixa hoje, vindo de
   `dashboard_helper.saldo_liquidez_ate`. Sem ela a curva partiria de zero e
   mediria apenas o fluxo líquido futuro, não o saldo da conta.
2. **A pendência acumulada** — lançamentos com `data_prevista` no passado que
   nunca foram liquidados. São compromissos reais que ainda vão sair do caixa, e
   por isso entram no primeiro dia da projeção em vez de serem descartados.
3. **O fluxo futuro** — os lançamentos previstos, dia a dia, acumulados.

## Duas invariantes que não podem ser quebradas

**O filtro de cartão.** Toda consulta de valor usa
`Q(cartao__isnull=True) | Q(eh_fatura_cartao=True)`. A compra individual de cartão
e a fatura consolidada representam o mesmo dinheiro: contar as duas faria o saldo
aparecer muito menor do que é. O mesmo filtro está em `saldo_liquidez_ate`, e as
duas metades precisam concordar — se divergirem, a âncora e o fluxo passam a medir
universos diferentes e o resultado não significa nada.

**A recorrência precisa estar materializada.** As ocorrências futuras de uma regra
recorrente só existem como `Conta` depois que alguém as gera. Por isso
`horizonte_saldos` chama `garantir_horizonte` antes de ler: sem isso, os últimos
meses da janela apareceriam sem receita nem despesa fixa — justamente onde a
previsibilidade é mais valiosa.

## O cenário de metas

Metas financeiras têm valor-alvo, acumulado e prazo, mas nenhum cronograma de
aporte. O aporte mensal necessário é derivado — (alvo − acumulado) ÷ meses até o
prazo — e devolvido como uma **série separada**, não somada à principal. A
distinção importa: uma despesa lançada é compromisso assumido; um aporte para meta
é intenção de poupar. Misturar as duas numa única curva faria o usuário ler como
dívida algo que ele decidiu, e pode desfazer.
"""

from calendar import monthrange
from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal

from dateutil.relativedelta import relativedelta
from django.db.models import Q, Sum

from core.models import Conta, MetaFinanceira
from core.services.dashboard_helper import saldo_liquidez_ate
from core.services.recorrencia_service import garantir_horizonte

# Reproduz a regra de `saldo_liquidez_ate`: a compra individual de cartão é
# ignorada, porque o dinheiro sai na fatura consolidada.
FILTRO_CARTAO = Q(cartao__isnull=True) | Q(eh_fatura_cartao=True)

MESES_PADRAO = 12
MESES_MAXIMO = 24


def _centavos(valor) -> Decimal:
    """Normaliza um valor monetário para duas casas decimais.

    A soma é feita em `Decimal` do início ao fim: acumular saldo diário por 365
    dias em ponto flutuante acumula erro visível na tela.

    Args:
        valor: Valor numérico ou nulo.

    Returns:
        Decimal: Valor com duas casas decimais.
    """
    return Decimal(valor or 0).quantize(Decimal("0.01"))


def _movimentos_por_dia(usuario, inicio: date, fim: date) -> dict[date, dict]:
    """Agrupa por dia os lançamentos previstos e ainda não liquidados da janela.

    Args:
        usuario (User): Proprietário dos lançamentos.
        inicio (date): Primeiro dia da janela, inclusive.
        fim (date): Último dia da janela, inclusive.

    Returns:
        dict[date, dict]: Mapa de data para `{"receitas": Decimal, "despesas": Decimal}`.
    """
    linhas = (
        Conta.objects.filter(
            usuario=usuario,
            transacao_realizada=False,
            data_prevista__gte=inicio,
            data_prevista__lte=fim,
        )
        .filter(FILTRO_CARTAO)
        .values("data_prevista", "tipo")
        .annotate(total=Sum("valor"))
    )

    movimentos = defaultdict(lambda: {"receitas": Decimal("0.00"), "despesas": Decimal("0.00")})
    for linha in linhas:
        chave = "receitas" if linha["tipo"] == Conta.TIPO_RECEITA else "despesas"
        movimentos[linha["data_prevista"]][chave] += _centavos(linha["total"])
    return movimentos


def _pendencias_atrasadas(usuario, antes_de: date) -> dict:
    """Soma os lançamentos vencidos e não liquidados até a véspera da janela.

    Eles não podem ser descartados: são dinheiro que ainda vai entrar ou sair. E
    não podem ser distribuídos ao longo da projeção, porque já venceram — o lugar
    honesto é o primeiro dia, onde ficam visíveis como o buraco que já existe.

    Args:
        usuario (User): Proprietário dos lançamentos.
        antes_de (date): Data de corte, exclusiva.

    Returns:
        dict: Totais de receitas e despesas atrasadas.
    """
    qs = (
        Conta.objects.filter(
            usuario=usuario,
            transacao_realizada=False,
            data_prevista__lt=antes_de,
        )
        .filter(FILTRO_CARTAO)
    )
    receitas = qs.filter(tipo=Conta.TIPO_RECEITA).aggregate(t=Sum("valor"))["t"]
    despesas = qs.filter(tipo=Conta.TIPO_DESPESA).aggregate(t=Sum("valor"))["t"]
    return {
        "receitas": _centavos(receitas),
        "despesas": _centavos(despesas),
    }


def _aportes_mensais_de_metas(usuario, inicio: date, fim: date) -> dict[date, Decimal]:
    """Deriva o aporte mensal necessário para cumprir cada meta no prazo.

    Só entram metas não concluídas, com prazo definido e com valor faltante. Uma
    meta sem prazo não tem cronograma dedutível: distribuir o valor faltante numa
    janela arbitrária inventaria um compromisso que o usuário não assumiu.

    Metas cujo prazo já passou e que seguem em aberto são cobradas integralmente no
    primeiro mês da janela — represar o valor num prazo vencido apenas esconderia
    que a meta está atrasada.

    Args:
        usuario (User): Proprietário das metas.
        inicio (date): Primeiro dia da janela.
        fim (date): Último dia da janela.

    Returns:
        dict[date, Decimal]: Aporte a debitar no primeiro dia de cada mês.
    """
    metas = MetaFinanceira.objects.filter(
        usuario=usuario, concluida=False, prazo__isnull=False
    )

    aportes: dict[date, Decimal] = defaultdict(lambda: Decimal("0.00"))
    primeiro_mes = inicio.replace(day=1)

    for meta in metas:
        faltante = _centavos(meta.valor_alvo) - _centavos(meta.valor_acumulado)
        if faltante <= 0:
            continue

        if meta.prazo <= inicio:
            aportes[primeiro_mes] += faltante
            continue

        # Número de meses entre a janela e o prazo, no mínimo 1.
        delta = relativedelta(meta.prazo, inicio)
        meses_restantes = max(1, delta.years * 12 + delta.months)
        parcela = (faltante / Decimal(meses_restantes)).quantize(Decimal("0.01"))

        mes = primeiro_mes
        while mes <= fim and mes <= meta.prazo:
            aportes[mes] += parcela
            mes = mes + relativedelta(months=1)

    return aportes


def horizonte_saldos(usuario, hoje: date, meses: int = MESES_PADRAO,
                     limite_atencao: Decimal | None = None) -> dict:
    """Projeta o saldo acumulado dia a dia para os próximos meses.

    Args:
        usuario (User): Proprietário dos dados.
        hoje (date): Primeiro dia da projeção.
        meses (int): Tamanho da janela, em meses.
        limite_atencao (Decimal | None): Saldo abaixo do qual o dia é sinalizado
            como atenção. `None` desliga a sinalização intermediária.

    Returns:
        dict: Janela projetada, agrupada por mês, com o saldo de cada dia, os
            totais mensais, o cenário de metas e o primeiro dia negativo.
    """
    meses = max(1, min(meses, MESES_MAXIMO))
    fim = (hoje.replace(day=1) + relativedelta(months=meses)) - timedelta(days=1)

    # Materializa a recorrência antes de ler: as ocorrências futuras só existem
    # como `Conta` depois de geradas.
    garantir_horizonte(usuario, fim)

    # A âncora é o realizado até ontem: o que for previsto para hoje ainda entra
    # como movimento do dia, e contar as duas coisas duplicaria o valor.
    saldo_inicial = _centavos(saldo_liquidez_ate(usuario, hoje - timedelta(days=1)))
    atrasados = _pendencias_atrasadas(usuario, hoje)
    saldo_inicial += atrasados["receitas"] - atrasados["despesas"]

    movimentos = _movimentos_por_dia(usuario, hoje, fim)
    aportes_meta = _aportes_mensais_de_metas(usuario, hoje, fim)

    saldo = saldo_inicial
    saldo_com_metas = saldo_inicial
    primeiro_negativo = None
    primeiro_negativo_com_metas = None

    meses_saida = []
    cursor = hoje.replace(day=1)

    for _ in range(meses):
        ultimo_dia = monthrange(cursor.year, cursor.month)[1]
        dias_saida = []
        total_receitas = Decimal("0.00")
        total_despesas = Decimal("0.00")

        aporte_do_mes = aportes_meta.get(cursor, Decimal("0.00"))

        for numero_dia in range(1, ultimo_dia + 1):
            dia = date(cursor.year, cursor.month, numero_dia)

            # Dias anteriores a hoje no primeiro mês não fazem parte da projeção:
            # já estão refletidos na âncora.
            if dia < hoje:
                continue

            movimento = movimentos.get(dia)
            receitas = movimento["receitas"] if movimento else Decimal("0.00")
            despesas = movimento["despesas"] if movimento else Decimal("0.00")

            saldo += receitas - despesas
            saldo_com_metas += receitas - despesas

            # O aporte das metas é debitado no primeiro dia projetado do mês.
            if not dias_saida:
                saldo_com_metas -= aporte_do_mes

            total_receitas += receitas
            total_despesas += despesas

            if primeiro_negativo is None and saldo < 0:
                primeiro_negativo = dia.isoformat()
            if primeiro_negativo_com_metas is None and saldo_com_metas < 0:
                primeiro_negativo_com_metas = dia.isoformat()

            dias_saida.append({
                "dia": numero_dia,
                "data": dia.isoformat(),
                "saldo": str(saldo),
                "saldo_com_metas": str(saldo_com_metas),
                "receitas": str(receitas),
                "despesas": str(despesas),
                "tem_lancamentos": bool(movimento),
                # As duas situações vêm do servidor para que a regra de limite não
                # fique duplicada no cliente e possa divergir dela.
                "situacao": _situacao(saldo, limite_atencao),
                "situacao_com_metas": _situacao(saldo_com_metas, limite_atencao),
            })

        meses_saida.append({
            "ano": cursor.year,
            "mes": cursor.month,
            "rotulo": f"{cursor.strftime('%b')}/{cursor.strftime('%y')}",
            "dias": dias_saida,
            "total_receitas": str(total_receitas),
            "total_despesas": str(total_despesas),
            "aporte_metas": str(aporte_do_mes),
            "saldo_final": dias_saida[-1]["saldo"] if dias_saida else str(saldo),
        })

        cursor = cursor + relativedelta(months=1)

    return {
        "inicio": hoje.isoformat(),
        "fim": fim.isoformat(),
        "saldo_inicial": str(saldo_inicial),
        "atrasados": {
            "receitas": str(atrasados["receitas"]),
            "despesas": str(atrasados["despesas"]),
        },
        "limite_atencao": str(limite_atencao) if limite_atencao is not None else None,
        "primeiro_dia_negativo": primeiro_negativo,
        "primeiro_dia_negativo_com_metas": primeiro_negativo_com_metas,
        "meses": meses_saida,
    }


def _situacao(saldo: Decimal, limite_atencao: Decimal | None) -> str:
    """Classifica o saldo de um dia para sinalização na interface.

    A interface precisa comunicar as três situações sem depender só de cor — o
    rótulo textual é o que permite ícone, texto e leitor de tela concordarem.

    Args:
        saldo (Decimal): Saldo acumulado do dia.
        limite_atencao (Decimal | None): Piso de conforto configurado.

    Returns:
        str: "negativo", "atencao" ou "confortavel".
    """
    if saldo < 0:
        return "negativo"
    if limite_atencao is not None and saldo < limite_atencao:
        return "atencao"
    return "confortavel"


def calendario_mes(usuario, ano: int, mes: int) -> dict:
    """Lista, dia a dia, os pagamentos e recebimentos previstos de um mês.

    Diferente da projeção, aqui **não** se aplica o filtro de cartão: quem abre um
    calendário de pagamentos quer ver a compra individual que fez, e não apenas a
    fatura consolidada. Somar valores entre os dois níveis é que seria errado, e
    por isso os totais do dia separam o que é fatura do que é compra avulsa.

    Args:
        usuario (User): Proprietário dos lançamentos.
        ano (int): Ano de referência.
        mes (int): Mês de referência, de 1 a 12.

    Returns:
        dict: Dias do mês com seus lançamentos e totais.
    """
    inicio = date(ano, mes, 1)
    ultimo_dia = monthrange(ano, mes)[1]
    fim = date(ano, mes, ultimo_dia)

    garantir_horizonte(usuario, fim)

    lancamentos = (
        Conta.objects.filter(
            usuario=usuario,
            data_prevista__gte=inicio,
            data_prevista__lte=fim,
        )
        .select_related("categoria", "cartao")
        .order_by("data_prevista", "-valor")
    )

    por_dia: dict[int, list] = defaultdict(list)
    for conta in lancamentos:
        por_dia[conta.data_prevista.day].append({
            "id": conta.id,
            "tipo": conta.tipo,
            "descricao": conta.descricao,
            "valor": str(_centavos(conta.valor)),
            "realizado": conta.transacao_realizada,
            "eh_fatura_cartao": conta.eh_fatura_cartao,
            "categoria": conta.categoria.nome if conta.categoria else None,
            "cartao": conta.cartao.nome if conta.cartao else None,
            "recorrente": conta.recorrencia_id is not None,
        })

    hoje = date.today()
    dias_saida = []
    for numero_dia in range(1, ultimo_dia + 1):
        itens = por_dia.get(numero_dia, [])
        dia = date(ano, mes, numero_dia)

        # Os totais desconsideram a compra individual de cartão, cujo desembolso
        # acontece na fatura — somar as duas contaria o mesmo dinheiro duas vezes.
        para_totais = [
            i for i in itens if i["cartao"] is None or i["eh_fatura_cartao"]
        ]
        receitas = sum(
            (Decimal(i["valor"]) for i in para_totais if i["tipo"] == Conta.TIPO_RECEITA),
            Decimal("0.00"),
        )
        despesas = sum(
            (Decimal(i["valor"]) for i in para_totais if i["tipo"] == Conta.TIPO_DESPESA),
            Decimal("0.00"),
        )

        dias_saida.append({
            "dia": numero_dia,
            "data": dia.isoformat(),
            "dia_semana": dia.weekday(),
            "eh_hoje": dia == hoje,
            "lancamentos": itens,
            "total_receitas": str(receitas),
            "total_despesas": str(despesas),
            "pendentes": sum(1 for i in itens if not i["realizado"]),
        })

    return {
        "ano": ano,
        "mes": mes,
        # Segunda-feira = 0, para que o cliente monte a grade sem recalcular.
        "dia_semana_do_primeiro": inicio.weekday(),
        "dias_no_mes": ultimo_dia,
        "dias": dias_saida,
    }
