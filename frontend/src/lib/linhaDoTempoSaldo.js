/**
 * Linha do tempo do saldo: do primeiro lançamento liquidado até 12 meses à frente.
 *
 * Junta três trechos da resposta de `/api/planejamento/horizonte-saldos/` numa lista
 * só, na ordem em que o tempo passa:
 *
 * 1. **realizado** — um ponto por mês do `historico`, terminando no caixa de ontem;
 * 2. **abertura** — o caixa de abertura de hoje, já sem contas vencidas e, se for o
 *    caso, sem o valor investido. É um degrau, não um fluxo: por isso vira ponto
 *    próprio, e a tela o explica em vez de ligá-lo ao passado com uma linha;
 * 3. **projetado** — o fechamento de cada mês da projeção.
 *
 * Fica fora do componente para poder ser testada sem montar o gráfico.
 */

/**
 * Rótulo curto do mês em português, sem o ponto da abreviação.
 *
 * @param {number} ano
 * @param {number} mes - De 1 a 12.
 * @returns {string} Por exemplo "out/26".
 */
export function rotuloMes(ano, mes) {
  const nome = new Date(ano, mes - 1, 1)
    .toLocaleDateString('pt-BR', { month: 'short' })
    .replace('.', '');
  return `${nome}/${String(ano).slice(-2)}`;
}

/**
 * Monta os pontos da linha do tempo.
 *
 * @param {Object} data - Resposta do horizonte de saldos.
 * @param {boolean} considerarMetas - Usa os saldos do cenário com aportes às metas.
 * @returns {Array<Object>} Pontos com `chave`, `rotulo`, `tipo`, `saldo` e, nos meses,
 *   `receitas`, `despesas` e `aporte`; os projetados trazem `indiceMes`.
 */
export function montarLinhaDoTempo(data, considerarMetas) {
  const sufixo = considerarMetas ? '_com_metas' : '';
  const ontem = new Date(`${data.inicio}T00:00:00`);
  ontem.setDate(ontem.getDate() - 1);
  const ateOntem = ontem.toLocaleDateString('pt-BR', { day: '2-digit', month: '2-digit' });

  const realizados = (data.historico ?? []).map((m) => ({
    chave: `r-${m.ano}-${m.mes}`,
    rotulo: m.parcial ? `${rotuloMes(m.ano, m.mes)} até ${ateOntem}` : rotuloMes(m.ano, m.mes),
    tipo: 'realizado',
    receitas: Number(m.receitas),
    despesas: Number(m.despesas),
    aporte: 0,
    saldo: Number(m.saldo_final),
  }));

  const abertura = {
    chave: 'abertura',
    rotulo: 'hoje',
    tipo: 'abertura',
    saldo: Number(data.saldo_inicial),
  };

  const projetados = data.meses.map((m, indiceMes) => ({
    chave: `p-${m.ano}-${m.mes}`,
    rotulo: rotuloMes(m.ano, m.mes),
    tipo: 'projetado',
    indiceMes,
    receitas: Number(m.total_receitas),
    despesas: Number(m.total_despesas),
    aporte: considerarMetas ? Number(m.aporte_metas) : 0,
    abertura: Number(m[`saldo_abertura${sufixo}`]),
    saldo: Number(m[`saldo_final${sufixo}`]),
  }));

  return [...realizados, abertura, ...projetados];
}
