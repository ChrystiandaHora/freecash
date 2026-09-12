/** Chamadas à API das telas de planejamento (Horizonte de Saldos e Calendário). */
import api from './api';

/**
 * Busca a projeção diária de saldo no horizonte especificado.
 * @param {Object} [params]
 * @param {number} [params.meses=12]
 * @param {string|number|null} [params.limiteAtencao]
 * @param {boolean} [params.considerarInvestimentos=false]
 */
export async function buscarHorizonteSaldos({
  meses = 12,
  limiteAtencao = null,
  considerarInvestimentos = false,
} = {}) {
  const params = { meses };
  if (limiteAtencao !== null && limiteAtencao !== '') {
    params.limite_atencao = limiteAtencao;
  }
  if (considerarInvestimentos) {
    params.considerar_investimentos = true;
  }
  const { data } = await api.get('/api/planejamento/horizonte-saldos/', { params });
  return data;
}

/**
 * Busca a grade de lançamentos do mês no calendário financeiro.
 * @param {number} ano
 * @param {number} mes - Mês de 1 a 12.
 */
export async function buscarCalendario(ano, mes) {
  const { data } = await api.get('/api/planejamento/calendario/', {
    params: { ano, mes },
  });
  return data;
}

/**
 * Marca um lançamento (despesa ou receita) como liquidado.
 * @param {number} id
 * @param {string} [data] - Data YYYY-MM-DD (padrão: hoje no servidor).
 */
export async function liquidarLancamento(id, data) {
  const corpo = data ? { data } : {};
  const { data: resposta } = await api.post(
    `/api/planejamento/lancamentos/${id}/liquidar/`,
    corpo
  );
  return resposta;
}

/** Devolve um lançamento liquidado ao estado pendente. */
export async function desfazerLiquidacao(id) {
  const { data } = await api.post(`/api/planejamento/lancamentos/${id}/desfazer/`);
  return data;
}

