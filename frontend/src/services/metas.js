/**
 * metas.js – Funções de acesso à API do Módulo de Metas Financeiras.
 * Todas as funções utilizam a instância `api` com interceptors JWT já configurados.
 */
import api from './api';

// ─── Base de Cálculo (renda mensal e custo de vida) ──────────────────────────

export const fetchPlanoMetas = async () => {
  const { data } = await api.get('/api/financeiro/metas-plano/');
  return data;
};

export const updatePlanoMetas = async (payload) => {
  const { data } = await api.put('/api/financeiro/metas-plano/', payload);
  return data;
};

// ─── Metas ───────────────────────────────────────────────────────────────────

export const fetchMetas = async () => {
  const { data } = await api.get('/api/financeiro/metas/');
  return data;
};

export const createMeta = async (payload) => {
  const { data } = await api.post('/api/financeiro/metas/', payload);
  return data;
};

export const updateMeta = async ({ id, ...payload }) => {
  const { data } = await api.patch(`/api/financeiro/metas/${id}/`, payload);
  return data;
};

export const deleteMeta = async (id) => {
  const { data } = await api.delete(`/api/financeiro/metas/${id}/`);
  return data;
};

/**
 * Ajusta em lote os multiplicadores das metas derivadas de uma base.
 * Recebe um mapa de tipo da meta para o novo fator, ex.: `{ patrimonio_renda: 150 }`.
 */
export const updateMultiplicadores = async (payload) => {
  const { data } = await api.put('/api/financeiro/metas/multiplicadores/', payload);
  return data;
};

/** Cria ou recalcula as quatro metas padrão a partir da base de cálculo salva. */
export const gerarMetasPadrao = async () => {
  const { data } = await api.post('/api/financeiro/metas/gerar-padrao/');
  return data;
};

/** Registra um aporte e soma o valor no acumulado da meta. */
export const createAporteMeta = async ({ metaId, ...payload }) => {
  const { data } = await api.post(`/api/financeiro/metas/${metaId}/aportes/`, payload);
  return data;
};

/** Exclui um aporte e desconta o valor do acumulado da meta. */
export const deleteAporteMeta = async ({ metaId, aporteId }) => {
  const { data } = await api.delete(`/api/financeiro/metas/${metaId}/aportes/${aporteId}/`);
  return data;
};
