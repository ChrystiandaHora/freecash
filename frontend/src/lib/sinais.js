/**
 * Leitura dos sinais de rebalanceamento que vêm de `/api/investimentos/sinais/` e do
 * payload do balanceamento.
 *
 * A regra que gera o sinal mora no backend (`investimento/sinais.py`); aqui ficam só os
 * rótulos e as frases, puros e testáveis. Dinheiro chega por um formatador injetado,
 * para respeitar o olho de privacidade — percentual e quantidade de cotas ficam à
 * mostra, como no resto do app (ver docs/privacidade-valores.md e
 * docs/proposta-sinais-realizacao.md).
 */

/** Tipos fiscais aceitos por `Ativo.tipo_fiscal`; vazio deixa o backend deduzir. */
export const TIPOS_FISCAIS = [
  { valor: 'ACAO', rotulo: 'Ação' },
  { valor: 'FII', rotulo: 'Fundo imobiliário (FII/Fiagro)' },
  { valor: 'ETF', rotulo: 'ETF' },
  { valor: 'BDR', rotulo: 'BDR' },
  { valor: 'FUNDO', rotulo: 'Fundo de investimento' },
  { valor: 'RF', rotulo: 'Renda fixa' },
  { valor: 'OUTRO', rotulo: 'Outro' },
];

const APRESENTACAO = {
  VENDER_COM_LUCRO: { rotulo: 'Rebalancear com lucro', variante: 'success' },
  VENDER_COM_PREJUIZO: { rotulo: 'Rebalancear com prejuízo', variante: 'warning' },
  REVISAR_QUEDA: { rotulo: 'Revisar queda', variante: 'destructive' },
};

const formatoMeta = new Intl.NumberFormat('pt-BR', { maximumFractionDigits: 2 });
const formatoVariacao = new Intl.NumberFormat('pt-BR', {
  minimumFractionDigits: 1,
  maximumFractionDigits: 1,
});

const cotas = (n) => `${n} ${n === 1 ? 'cota' : 'cotas'}`;

/**
 * @param {{tipo: string}|undefined} sinal
 * @returns {{rotulo: string, variante: string}|null} Texto e variante do `Badge`, ou null sem sinal.
 */
export function apresentarSinal(sinal) {
  return APRESENTACAO[sinal?.tipo] ?? null;
}

/**
 * Frase do que o sinal sugere fazer.
 *
 * @param {Object} sinal - Item de sinal da API.
 * @param {(valor: number) => string} formatarMoeda - Formatador já ligado ao olho.
 * @returns {string|null}
 */
export function textoAcao(sinal, formatarMoeda) {
  const queda = sinal?.queda_relevante
    ? `Caiu ${formatoVariacao.format(Math.abs(sinal.variacao_preco_medio))}% desde o seu preço médio.`
    : '';

  if (sinal?.tipo === 'REVISAR_QUEDA') {
    return `${queda} Revise o motivo de ter este ativo antes de reforçar ou vender.`;
  }
  if (!apresentarSinal(sinal)) return null;

  const venda =
    `Vender ${cotas(sinal.cotas_a_vender)} (${formatarMoeda(sinal.valor_venda)}) ` +
    `para voltar à meta de ${formatoMeta.format(sinal.meta_porcentagem)}%`;
  const resultado =
    sinal.resultado_venda >= 0
      ? ` realiza lucro de ${formatarMoeda(sinal.resultado_venda)}.`
      : ` realiza prejuízo de ${formatarMoeda(-sinal.resultado_venda)}, ` +
        'que pode abater lucros futuros do mesmo tipo de ativo.';
  return queda ? `${venda}${resultado} ${queda}` : `${venda}${resultado}`;
}

/**
 * Frase sobre a isenção de R$ 20 mil em vendas de ações no mês.
 *
 * O limite é escrito por extenso, e não pelo formatador: é regra pública, não dinheiro
 * do usuário, e não some com o olho.
 *
 * @param {Object} sinal - Item de sinal da API.
 * @returns {string|null} Null quando o sinal não sugere venda.
 */
export function textoIsencao(sinal) {
  switch (sinal?.isencao) {
    case 'ISENTA':
      return 'Cabe na isenção de R$ 20 mil em vendas de ações no mês.';
    case 'EXCEDE':
      return sinal.cotas_dentro_isencao > 0
        ? `Passa de R$ 20 mil em vendas de ações no mês. Até ${cotas(sinal.cotas_dentro_isencao)} ` +
            'cabem na isenção agora; o restante pode ficar para o mês que vem.'
        : 'As vendas de ações deste mês já passaram de R$ 20 mil: o lucro do mês é tributável.';
    case 'TRIBUTAVEL':
      return 'Este tipo de ativo não tem a isenção de R$ 20 mil: o lucro é tributável.';
    default:
      return null;
  }
}

/**
 * Queda relevante suspende a sugestão de aporte até o usuário confirmar a tese.
 *
 * @param {Object|undefined} sinal
 * @returns {boolean}
 */
export function suspendeAporte(sinal) {
  return Boolean(sinal?.queda_relevante);
}

/**
 * @param {Array<{ativo_id: number}>} sinais
 * @returns {Map<number, Array<Object>>} Sinais por ativo; um ativo pode ter um por carteira.
 */
export function sinaisPorAtivo(sinais) {
  const porAtivo = new Map();
  for (const sinal of sinais) {
    porAtivo.set(sinal.ativo_id, [...(porAtivo.get(sinal.ativo_id) ?? []), sinal]);
  }
  return porAtivo;
}
