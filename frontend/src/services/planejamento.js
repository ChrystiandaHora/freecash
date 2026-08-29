/**
 * Chamadas à API das telas de planejamento.
 *
 * Horizonte de Saldos e Calendário de Pagamentos leem o mesmo acervo de
 * lançamentos por ângulos diferentes: o horizonte responde "para onde meu saldo
 * vai", o calendário responde "o que acontece nesta semana".
 *
 * @module services/planejamento
 */
import api from './api';

/**
 * Busca a projeção de saldo diária.
 *
 * @param {Object} [params] - Parâmetros da projeção.
 * @param {number} [params.meses=12] - Tamanho da janela, em meses.
 * @param {string|number|null} [params.limiteAtencao] - Saldo abaixo do qual o dia
 *   é sinalizado como atenção. Nulo desliga a faixa intermediária.
 * @returns {Promise<Object>} Projeção agrupada por mês.
 */
export async function buscarHorizonteSaldos({ meses = 12, limiteAtencao = null } = {}) {
  const params = { meses };
  if (limiteAtencao !== null && limiteAtencao !== '') {
    params.limite_atencao = limiteAtencao;
  }
  const { data } = await api.get('/api/planejamento/horizonte-saldos/', { params });
  return data;
}

/**
 * Busca a grade de um mês do calendário de pagamentos e recebimentos.
 *
 * @param {number} ano - Ano de referência.
 * @param {number} mes - Mês de referência, de 1 a 12.
 * @returns {Promise<Object>} Dias do mês com seus lançamentos e totais.
 */
export async function buscarCalendario(ano, mes) {
  const { data } = await api.get('/api/planejamento/calendario/', {
    params: { ano, mes },
  });
  return data;
}

/**
 * Marca um lançamento como pago ou recebido.
 *
 * Serve tanto a despesa quanto a receita — diferente da ação do Kanban, que cobre
 * apenas despesas porque aquela tela só lista despesas.
 *
 * @param {number} id - Identificador do lançamento.
 * @param {string} [data] - Data da liquidação no formato AAAA-MM-DD. Omitida, usa hoje.
 * @returns {Promise<{id: number, realizado: boolean, data_realizacao: string|null}>}
 */
export async function liquidarLancamento(id, data) {
  const corpo = data ? { data } : {};
  const { data: resposta } = await api.post(
    `/api/planejamento/lancamentos/${id}/liquidar/`,
    corpo
  );
  return resposta;
}

/**
 * Devolve um lançamento liquidado ao estado pendente.
 *
 * @param {number} id - Identificador do lançamento.
 * @returns {Promise<{id: number, realizado: boolean, data_realizacao: string|null}>}
 */
export async function desfazerLiquidacao(id) {
  const { data } = await api.post(`/api/planejamento/lancamentos/${id}/desfazer/`);
  return data;
}
