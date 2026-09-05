/**
 * investimentos.js – Funções de acesso à API para o Módulo de Investimentos.
 * Todas as funções utilizam a instância `api` com interceptors JWT já configurados.
 */
import api from './api';

/**
 * Monta os query params do filtro de carteira. Ausente significa consolidado, por isso
 * o valor vazio é omitido em vez de virar string vazia.
 *
 * @param {number|string|null} carteiraId
 * @returns {{params?: {carteira: number|string}}}
 */
const escopoDaCarteira = (carteiraId) =>
  carteiraId ? { params: { carteira: carteiraId } } : {};

// ─── Carteiras ───────────────────────────────────────────────────────────────

export const fetchCarteiras = async () => {
  const { data } = await api.get('/api/investimentos/carteiras/');
  return data;
};

export const createCarteira = async (payload) => {
  const { data } = await api.post('/api/investimentos/carteiras/', payload);
  return data;
};

export const updateCarteira = async ({ id, ...payload }) => {
  const { data } = await api.patch(`/api/investimentos/carteiras/${id}/`, payload);
  return data;
};

export const deleteCarteira = async (id) => {
  const { data } = await api.delete(`/api/investimentos/carteiras/${id}/`);
  return data;
};

export const transferirEntreCarteiras = async (payload) => {
  const { data } = await api.post('/api/investimentos/transacoes/transferir/', payload);
  return data;
};

// ─── Posições por carteira ───────────────────────────────────────────────────

export const fetchPosicoes = async (carteiraId = null, ativoId = null) => {
  const params = {
    ...(carteiraId ? { carteira: carteiraId } : {}),
    ...(ativoId ? { ativo: ativoId } : {}),
  };
  const { data } = await api.get('/api/investimentos/posicoes/', { params });
  return data;
};

export const updateMetaPosicao = async ({ id, meta_porcentagem }) => {
  const { data } = await api.patch(`/api/investimentos/posicoes/${id}/`, { meta_porcentagem });
  return data;
};

// ─── Ativos ──────────────────────────────────────────────────────────────────

export const fetchAtivos = async (carteiraId = null) => {
  const { data } = await api.get('/api/investimentos/ativos/', escopoDaCarteira(carteiraId));
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

