/**
 * Preparo puro das séries de cotação para o gráfico de Meus Ativos.
 *
 * Isolado do componente por dois motivos verificáveis em teste.
 *
 * O primeiro é a escala «Retorno», que carrega uma promessa: o último ponto de cada
 * linha tem de ser exatamente o número da coluna «Retorno» da tabela ao lado. Duas
 * contas equivalentes escritas em lugares diferentes divergem em silêncio na primeira
 * vez que uma delas muda; aqui a igualdade é testada.
 *
 * O segundo é o alinhamento no eixo comum. O tooltip compartilhado do ApexCharts casa
 * as séries **por índice do ponto**, não pelo valor de x: com séries de comprimentos
 * diferentes — um ativo cadastrado no meio do período, ou um pregão que o coletor não
 * pegou —, o ponteiro passava a mostrar a data de uma série com o valor de outra.
 * `alinharEmEixoComum` põe todas na mesma grade de datas antes de plotar.
 *
 * Duas escalas, duas perguntas:
 *
 * - `retorno` — a cotação contra o **preço médio**. Zero é o custo, e o fim da linha é
 *   o retorno acumulado. Responde "como está a minha posição".
 * - `preco` — a cotação nominal em reais, sem rebase.
 */

/**
 * Rebaseia um valor contra a referência da escala pedida.
 *
 * @param {number} valor Cotação de fechamento do pregão.
 * @param {'retorno'|'preco'} escala
 * @param {number} precoMedio Preço médio do ativo, como a tabela o exibe.
 * @returns {number|null} Valor plotado, ou `null` quando não há preço médio — sem ele
 *   não há retorno a medir, e devolver 0 diria "empatado", que é falso.
 */
export function converterPonto(valor, escala, precoMedio) {
  if (escala === 'preco') return valor;
  if (!precoMedio) return null;

  return Number((((valor - precoMedio) / precoMedio) * 100).toFixed(2));
}

/**
 * Converte as séries da API para a escala pedida, descartando as que não se aplicam.
 *
 * @param {Array<{id: number, ticker: string, pontos: Array<{data: string, valor: number}>}>} series
 * @param {'retorno'|'preco'} escala
 * @param {Map<number, {preco_medio: string|number, rentabilidade_percentual: string|number}>} ativosPorId
 *   Preço médio e retorno como a **tabela** os exibe — sob filtro de carteira o
 *   serializador já os sobrescreve com os daquela custódia, então o gráfico lê de lá
 *   em vez de recalcular e arriscar divergir.
 * @returns {Array<{id: number, ticker: string, retornoAtual: number,
 *   pontos: Array<{data: string, valor: number, plotado: number|null}>}>}
 */
export function converterSeries(series, escala, ativosPorId = new Map()) {
  return series
    .map((serie) => {
      const ativo = ativosPorId.get(serie.id);
      const precoMedio = parseFloat(ativo?.preco_medio ?? 0);

      return {
        id: serie.id,
        ticker: serie.ticker,
        retornoAtual: parseFloat(ativo?.rentabilidade_percentual ?? 0),
        pontos: serie.pontos.map((ponto) => ({
          data: ponto.data,
          valor: ponto.valor,
          plotado: converterPonto(ponto.valor, escala, precoMedio),
        })),
      };
    })
    .filter((serie) => serie.pontos.some((ponto) => ponto.plotado !== null));
}

/**
 * Põe todas as séries na mesma grade de datas, repetindo o último fechamento nos
 * pregões que faltam.
 *
 * O alinhamento é o que faz o tooltip compartilhado apontar para a data certa: o
 * ApexCharts casa as séries por índice, então arrays de comprimentos diferentes
 * desalinham o ponteiro — era o defeito de mirar num ativo e ler a data de outro.
 *
 * O buraco é preenchido, e não deixado como `null`, porque na base real eles são
 * internos e numerosos: fundos que só recebem cotação quando o coletor roda chegam a
 * ficar sem 20 dos 49 pregões da grade, e uma linha quebrada em vinte pedaços não se
 * lê. Repetir o último fechamento conhecido também é a convenção do próprio domínio —
 * é o que `Ativo.cotacao_atual` faz ao usar a cotação mais recente seja de quando for.
 *
 * Antes da primeira cotação de um ativo o valor fica `null`: ali não há o que repetir,
 * e desenhar a linha desde a origem afirmaria um preço que ninguém observou.
 *
 * @param {Array<{pontos: Array<{data: string, plotado: number|null}>}>} series
 * @returns {{datas: string[], series: Array<{valores: Array<number|null>}>}}
 *   As mesmas séries acrescidas de `valores`, com um item por data de `datas`.
 */
export function alinharEmEixoComum(series) {
  const datas = [...new Set(series.flatMap((s) => s.pontos.map((p) => p.data)))].sort();

  return {
    datas,
    series: series.map((serie) => {
      const porData = new Map(serie.pontos.map((p) => [p.data, p.plotado]));

      let ultimo = null;
      const valores = datas.map((data) => {
        const observado = porData.get(data);
        if (observado !== undefined && observado !== null) ultimo = observado;
        return ultimo;
      });

      return { ...serie, valores };
    }),
  };
}
