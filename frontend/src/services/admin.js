/**
 * Chamadas à API do painel administrativo.
 *
 * Todos estes endpoints exigem `is_staff` no servidor. O gate no frontend é
 * conveniência de navegação — quem tentar chamar diretamente recebe 403.
 */
import api from './api';

/**
 * Lista as contas da plataforma.
 *
 * @param {Object} [params] - Filtros da listagem.
 * @param {string} [params.busca] - Termo buscado em nome de usuário e e-mail.
 * @param {string} [params.ativo] - "true" ou "false" para filtrar por estado.
 * @param {string} [params.verificado] - "true" ou "false" para e-mail confirmado.
 * @param {number} [params.page] - Página desejada.
 * @returns {Promise<{count: number, next: string|null, previous: string|null, results: Array}>}
 */
export async function listarUsuarios(params = {}) {
  const limpos = Object.fromEntries(
    Object.entries(params).filter(([, v]) => v !== '' && v != null)
  );
  const { data } = await api.get('/api/admin/usuarios/', { params: limpos });
  return data;
}

/**
 * Suspende o acesso de uma conta e encerra as sessões abertas dela.
 *
 * @param {number} id - Identificador da conta.
 * @param {string} [detalhe] - Motivo registrado no histórico administrativo.
 * @returns {Promise<{detail: string, is_active: boolean}>}
 */
export async function suspenderUsuario(id, detalhe = '') {
  const { data } = await api.post(`/api/admin/usuarios/${id}/suspender/`, { detalhe });
  return data;
}

/**
 * Devolve o acesso a uma conta suspensa.
 *
 * @param {number} id - Identificador da conta.
 * @param {string} [detalhe] - Motivo registrado no histórico administrativo.
 * @returns {Promise<{detail: string, is_active: boolean}>}
 */
export async function reativarUsuario(id, detalhe = '') {
  const { data } = await api.post(`/api/admin/usuarios/${id}/reativar/`, { detalhe });
  return data;
}

/**
 * Busca os indicadores de uso da plataforma.
 *
 * @param {number} [dias=30] - Janela da série de cadastros, em dias.
 * @returns {Promise<Object>}
 */
export async function buscarMetricas(dias = 30) {
  const { data } = await api.get('/api/admin/metricas/', { params: { dias } });
  return data;
}

/**
 * Lista o histórico de ações administrativas.
 *
 * @param {number} [page=1] - Página desejada.
 * @returns {Promise<{count: number, results: Array}>}
 */
export async function listarLogsAdmin(page = 1) {
  const { data } = await api.get('/api/admin/logs/', { params: { page } });
  return data;
}
