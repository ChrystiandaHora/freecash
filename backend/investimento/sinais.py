"""Sinais de realização e rebalanceamento por posição em carteira.

Regra pura, sem I/O: recebe a posição já resolvida (cotação, preço médio, meta) e
devolve o sinal. Quem consulta o banco é a view; aqui fica só a regra, para que ela
seja testável sem fixture. A origem de cada número — banda 5/25, queda de 20%, isenção
de R$ 20 mil — está em docs/proposta-sinais-realizacao.md.
"""

import re
import unicodedata
from dataclasses import dataclass
from decimal import ROUND_DOWN, Decimal

from django.db import models

# Regra 5/25 (Swedroe): a banda é o menor entre 5 p.p. e 25% da própria meta
BANDA_ABSOLUTA_PP = Decimal("5")
BANDA_RELATIVA = Decimal("0.25")

# Convenção de mercado para "mercado em baixa"; não é stop, é pedido de revisão
QUEDA_RELEVANTE_PERCENTUAL = Decimal("-20")

# Isenção sobre o valor vendido de ações no mês, não sobre o lucro (Lei 11.033/2004)
LIMITE_ISENCAO_ACOES = Decimal("20000")

CENTAVO = Decimal("0.01")


class TipoFiscal(models.TextChoices):
    """Natureza do ativo para o IR, que é o que decide isenção e alíquota."""

    ACAO = "ACAO", "Ação"
    FII = "FII", "Fundo imobiliário"
    ETF = "ETF", "ETF"
    BDR = "BDR", "BDR"
    FUNDO = "FUNDO", "Fundo de investimento"
    RENDA_FIXA = "RF", "Renda fixa"
    OUTRO = "OUTRO", "Outro"


# Trechos dos nomes de categoria/subcategoria, em ordem: BDR vem antes de "ações" porque
# a subcategoria padrão "BDRs (Internacional)" mora dentro da categoria "Ações"
TRECHOS_DE_NOME = (
    ("etf", TipoFiscal.ETF),
    ("imobiliario", TipoFiscal.FII),
    ("fii", TipoFiscal.FII),
    ("fiagro", TipoFiscal.FII),
    ("bdr", TipoFiscal.BDR),
    ("acoes", TipoFiscal.ACAO),
)

TICKER_ACAO = re.compile(r"^[A-Z]{4}[3-8]F?$")
TICKER_BDR = re.compile(r"^[A-Z]{4}(3[2-5]|39)F?$")


class TipoSinal(models.TextChoices):
    SEM_SINAL = "SEM_SINAL", "Sem sinal"
    VENDER_COM_LUCRO = "VENDER_COM_LUCRO", "Vender com lucro"
    VENDER_COM_PREJUIZO = "VENDER_COM_PREJUIZO", "Vender com prejuízo"
    REVISAR_QUEDA = "REVISAR_QUEDA", "Revisar queda"


class SituacaoIsencao(models.TextChoices):
    NAO_SE_APLICA = "NAO_SE_APLICA", "Não se aplica"
    ISENTA = "ISENTA", "Isenta"
    EXCEDE = "EXCEDE", "Excede a isenção do mês"
    TRIBUTAVEL = "TRIBUTAVEL", "Tributável"


@dataclass(frozen=True)
class PosicaoAvaliada:
    """Entrada da regra: a posição de um ativo dentro de uma carteira.

    Atributos:
        quantidade: Cotas custodiadas nesta carteira.
        preco_medio: Preço médio **consolidado** (do CPF), contra o qual se mede o
            lucro — é o número que vai para a declaração.
        cotacao: Última cotação; None quando o ativo nunca foi cotado.
        meta_porcentagem: Meta do ativo dentro da carteira, de 0 a 100.
        tipo_fiscal: Um `TipoFiscal`; decide a isenção e se o ativo entra na regra.
    """

    quantidade: Decimal
    preco_medio: Decimal
    cotacao: Decimal | None
    meta_porcentagem: Decimal
    tipo_fiscal: str


@dataclass(frozen=True)
class Sinal:
    """Saída da regra.

    Atributos:
        tipo: Um `TipoSinal`.
        queda_relevante: Cotação 20% ou mais abaixo do preço médio. Vale também junto
            com sinal de venda, e suspende a sugestão de aporte no ativo.
        peso_mercado: Peso da posição na carteira, a mercado, de 0 a 100.
        banda: Tolerância em p.p. acima da meta antes de sinalizar.
        variacao_preco_medio: Variação % da cotação sobre o preço médio; None quando
            não há custo de aquisição (bonificação).
        cotas_a_vender: Cotas inteiras que levam a posição de volta à meta.
        resultado_venda: Lucro (positivo) ou prejuízo (negativo) da venda sugerida,
            sem as taxas, que só existem quando a ordem existir.
        cotas_dentro_isencao: Preenchido só quando a venda estoura a isenção do mês.
    """

    tipo: str = TipoSinal.SEM_SINAL
    queda_relevante: bool = False
    peso_mercado: Decimal = Decimal(0)
    banda: Decimal = Decimal(0)
    variacao_preco_medio: Decimal | None = None
    cotas_a_vender: Decimal = Decimal(0)
    valor_venda: Decimal = Decimal(0)
    resultado_venda: Decimal = Decimal(0)
    isencao: str = SituacaoIsencao.NAO_SE_APLICA
    cotas_dentro_isencao: Decimal | None = None


def inferir_tipo_fiscal(
    ticker: str,
    *,
    cnpj: str | None = "",
    classe: str = "",
    categoria: str = "",
    subcategoria: str = "",
) -> str:
    """Deduz o tipo fiscal de um ativo que o usuário não classificou.

    A classificação do usuário vem antes do ticker porque o ticker não resolve o
    final 11: FII, ETF e unit o dividem. O que não dá para deduzir fica em `OUTRO`,
    que o sinal trata como tributável — o lado seguro de errar.

    Returns:
        str: Um `TipoFiscal`.
    """
    if "renda fixa" in _normalizar(classe):
        return TipoFiscal.RENDA_FIXA
    nomes = _normalizar(f"{categoria} {subcategoria}")
    for trecho, tipo in TRECHOS_DE_NOME:
        if trecho in nomes:
            return tipo
    if cnpj:
        return TipoFiscal.FUNDO

    simbolo = ticker.strip().upper()
    if ":" in simbolo:
        return TipoFiscal.OUTRO
    simbolo = simbolo.removesuffix(".SA")
    if TICKER_BDR.match(simbolo):
        return TipoFiscal.BDR
    if TICKER_ACAO.match(simbolo):
        return TipoFiscal.ACAO
    return TipoFiscal.OUTRO


def _normalizar(texto: str) -> str:
    sem_acento = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return sem_acento.lower()


def calcular_banda(meta_porcentagem: Decimal) -> Decimal:
    """Devolve a tolerância da regra 5/25 para uma meta.

    Returns:
        Decimal: O menor entre 5 p.p. e 25% da meta, em pontos percentuais.
    """
    return min(BANDA_ABSOLUTA_PP, meta_porcentagem * BANDA_RELATIVA)


def avaliar_posicao(
    posicao: PosicaoAvaliada,
    *,
    total_mercado_carteira: Decimal,
    vendas_acoes_no_mes: Decimal = Decimal(0),
) -> Sinal:
    """Avalia se a posição saiu da banda da meta ou caiu além do limite de revisão.

    A venda sugerida leva a posição de volta à meta, não à borda da banda. Meta zero
    é lida como "sem meta", e não como ordem de zerar a posição: do contrário, quem
    ainda não configurou metas veria sinal de venda em todos os ativos.

    Args:
        posicao: A posição a avaliar.
        total_mercado_carteira: Soma a mercado de todas as posições da carteira.
        vendas_acoes_no_mes: Valor já vendido de ações no mês, somado à venda sugerida
            para a isenção — que é sobre o valor vendido, não sobre o lucro.

    Returns:
        Sinal: O sinal da posição; `SEM_SINAL` para renda fixa, posição zerada ou
            ativo sem cotação.
    """
    cotacao = posicao.cotacao
    if (
        posicao.tipo_fiscal == TipoFiscal.RENDA_FIXA
        or not cotacao
        or posicao.quantidade <= 0
        or total_mercado_carteira <= 0
    ):
        return Sinal()

    peso = posicao.quantidade * cotacao / total_mercado_carteira * 100
    banda = calcular_banda(posicao.meta_porcentagem)
    variacao = _variacao_sobre_preco_medio(cotacao, posicao.preco_medio)
    queda = variacao is not None and variacao <= QUEDA_RELEVANTE_PERCENTUAL
    cotas = _cotas_para_voltar_a_meta(posicao, peso, banda, total_mercado_carteira)

    if cotas == 0:
        return Sinal(
            tipo=TipoSinal.REVISAR_QUEDA if queda else TipoSinal.SEM_SINAL,
            queda_relevante=queda,
            peso_mercado=peso,
            banda=banda,
            variacao_preco_medio=variacao,
        )

    valor_venda = (cotas * cotacao).quantize(CENTAVO)
    resultado = (cotas * (cotacao - posicao.preco_medio)).quantize(CENTAVO)
    isencao, cotas_isentas = _avaliar_isencao(
        posicao.tipo_fiscal, valor_venda, cotacao, vendas_acoes_no_mes
    )
    return Sinal(
        tipo=(
            TipoSinal.VENDER_COM_LUCRO if resultado >= 0 else TipoSinal.VENDER_COM_PREJUIZO
        ),
        queda_relevante=queda,
        peso_mercado=peso,
        banda=banda,
        variacao_preco_medio=variacao,
        cotas_a_vender=cotas,
        valor_venda=valor_venda,
        resultado_venda=resultado,
        isencao=isencao,
        cotas_dentro_isencao=cotas_isentas,
    )


def _variacao_sobre_preco_medio(cotacao: Decimal, preco_medio: Decimal) -> Decimal | None:
    if preco_medio <= 0:
        return None
    return (cotacao / preco_medio - 1) * 100


def _cotas_para_voltar_a_meta(
    posicao: PosicaoAvaliada, peso: Decimal, banda: Decimal, total: Decimal
) -> Decimal:
    meta = posicao.meta_porcentagem
    if meta <= 0 or peso <= meta + banda:
        return Decimal(0)
    excesso = (peso - meta) / 100 * total
    return (excesso / posicao.cotacao).to_integral_value(rounding=ROUND_DOWN)


def _avaliar_isencao(
    tipo_fiscal: str, valor_venda: Decimal, cotacao: Decimal, vendas_no_mes: Decimal
) -> tuple[str, Decimal | None]:
    # ETF entra como tributável: as fontes divergem, e errar deste lado só mostra um aviso a mais
    if tipo_fiscal != TipoFiscal.ACAO:
        return SituacaoIsencao.TRIBUTAVEL, None
    if vendas_no_mes + valor_venda <= LIMITE_ISENCAO_ACOES:
        return SituacaoIsencao.ISENTA, None
    disponivel = max(LIMITE_ISENCAO_ACOES - vendas_no_mes, Decimal(0))
    return SituacaoIsencao.EXCEDE, (disponivel / cotacao).to_integral_value(rounding=ROUND_DOWN)
