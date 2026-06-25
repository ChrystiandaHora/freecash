/**
 * investimentos.js – Funções de acesso à API para o Módulo de Investimentos.
 * Todas as funções utilizam a instância `api` com interceptors JWT já configurados.
 */
import api from './api';

// ─── Ativos ──────────────────────────────────────────────────────────────────

export const fetchAtivos = async () => {
  const { data } = await api.get('/api/investimentos/ativos/');
  return data;
};

export const fetchAtivo = async (id) => {
  const { data } = await api.get(`/api/investimentos/ativos/${id}/`);
  return data;
};

export const createAtivo = async (payload) => {
  const { data } = await api.post('/api/investimentos/ativos/', payload);
  return data;
};

export const updateAtivo = async ({ id, ...payload }) => {
  const { data } = await api.patch(`/api/investimentos/ativos/${id}/`, payload);
  return data;
};

export const deleteAtivo = async (id) => {
  const { data } = await api.delete(`/api/investimentos/ativos/${id}/`);
  return data;
};

// ─── Subcategorias de Investimento ───────────────────────────────────────────

export const fetchSubcategoriasAtivos = async () => {
  const { data } = await api.get('/api/investimentos/subcategorias/');
  return data;
};

export const atualizarCotacoes = async () => {
  const { data } = await api.post('/api/investimentos/ativos/atualizar-cotacoes/');
  return data;
};

export const atualizarAtivo = async (id) => {
  const { data } = await api.post(`/api/investimentos/ativos/${id}/atualizar/`);
  return data;
};

