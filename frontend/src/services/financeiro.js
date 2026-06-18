/**
 * financeiro.js – Funções de acesso à API para o Bloco A Financeiro.
 * Todas as funções utilizam a instância `api` com interceptors JWT já configurados.
 */
import api from './api'

// ─── Contas a Pagar ──────────────────────────────────────────────────────────

export const fetchContasPagar = async (params = {}) => {
  const { data } = await api.get('/api/financeiro/contas-pagar/', { params })
  return data
}

export const createContaPagar = async (payload) => {
  const { data } = await api.post('/api/financeiro/contas-pagar/', payload)
  return data
}

export const updateContaPagar = async ({ id, ...payload }) => {
  const { data } = await api.put(`/api/financeiro/contas-pagar/${id}/`, payload)
  return data
}

export const pagarConta = async (id) => {
  const { data } = await api.put(`/api/financeiro/contas-pagar/${id}/pagar/`)
  return data
}

export const desfazerPagamentoConta = async (id) => {
  const { data } = await api.put(`/api/financeiro/contas-pagar/${id}/desfazer-pagamento/`)
  return data
}

export const createContasPagarLote = async (payload) => {
  const { data } = await api.post('/api/financeiro/contas-pagar/lote/', payload)
  return data
}

// ─── Cartões ─────────────────────────────────────────────────────────────────

export const fetchCartoes = async () => {
  const { data } = await api.get('/api/financeiro/cartoes/')
  return data
}

// ─── Receitas ─────────────────────────────────────────────────────────────────

export const fetchReceitas = async (params = {}) => {
  const { data } = await api.get('/api/financeiro/receitas/', { params })
  return data
}

export const createReceita = async (payload) => {
  const { data } = await api.post('/api/financeiro/receitas/', payload)
  return data
}

export const updateReceita = async ({ id, ...payload }) => {
  const { data } = await api.put(`/api/financeiro/receitas/${id}/`, payload)
  return data
}

// ─── Transações ───────────────────────────────────────────────────────────────

export const fetchTransacoes = async (params = {}) => {
  const { data } = await api.get('/api/financeiro/transacoes/', { params })
  return data
}

export const deleteContaPagar = async (id) => {
  const { data } = await api.delete(`/api/financeiro/contas-pagar/${id}/`)
  return data
}

export const deleteReceita = async (id) => {
  const { data } = await api.delete(`/api/financeiro/receitas/${id}/`)
  return data
}

