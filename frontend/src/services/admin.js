/** Chamadas à API do painel administrativo (exigem privilégio is_staff). */
import api from './api';

/**
 * Lista contas da plataforma com filtros e paginação.
 * @param {Object} [params]
 */
export async function listarUsuarios(params = {}) {
  const limpos = Object.fromEntries(
    Object.entries(params).filter(([, v]) => v !== '' && v != null)
  );
  const { data } = await api.get('/api/admin/usuarios/', { params: limpos });
  return data;
}

/** Suspende o acesso de uma conta e revoga suas sessões. */
export async function suspenderUsuario(id, detalhe = '') {
  const { data } = await api.post(`/api/admin/usuarios/${id}/suspender/`, { detalhe });
  return data;
}

/** Reativa o acesso de uma conta suspensa. */
export async function reativarUsuario(id, detalhe = '') {
  const { data } = await api.post(`/api/admin/usuarios/${id}/reativar/`, { detalhe });
  return data;
}

/** Busca métricas e indicadores de uso da plataforma na janela em dias. */
export async function buscarMetricas(dias = 30) {
  const { data } = await api.get('/api/admin/metricas/', { params: { dias } });
  return data;
}

/** Lista o histórico de auditoria de ações administrativas. */
export async function listarLogsAdmin(page = 1) {
  const { data } = await api.get('/api/admin/logs/', { params: { page } });
  return data;
}

