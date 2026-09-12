/** Chamadas à API dos fluxos de identidade, autenticação e gerenciamento de conta. */
import api from './api';

/** Busca identidade e perfil básico da conta autenticada. */
export async function buscarPerfil() {
  const { data } = await api.get('/api/auth/me/');
  return data;
}

/** Confirma endereço de e-mail via token de verificação. */
export async function confirmarEmail({ uid, token }) {
  const { data } = await api.post('/api/auth/verificar-email/', { uid, token });
  return data;
}

/** Reenvia e-mail de confirmação para a conta autenticada. */
export async function reenviarConfirmacaoEmail() {
  const { data } = await api.post('/api/auth/verificar-email/reenviar/');
  return data;
}

/** Solicita envio do link de redefinição de senha. */
export async function solicitarResetSenha(email) {
  const { data } = await api.post('/api/auth/senha/reset/', { email });
  return data;
}

/** Efetiva redefinição de senha com token de uso único. */
export async function confirmarResetSenha({ uid, token, nova_senha, confirmar }) {
  const { data } = await api.post('/api/auth/senha/reset/confirmar/', {
    uid,
    token,
    nova_senha,
    confirmar,
  });
  return data;
}

/** Busca dados completos da conta e preferências do usuário. */
export async function buscarConta() {
  const { data } = await api.get('/api/auth/perfil/');
  return data;
}

/** Atualiza nome de usuário e preferências da conta. */
export async function atualizarPerfil(campos) {
  const { data } = await api.patch('/api/auth/perfil/', campos);
  return data;
}

/** Solicita alteração de e-mail (envia link de confirmação ao novo endereço). */
export async function solicitarTrocaEmail(dados) {
  const { data } = await api.post('/api/auth/email/alterar/', dados);
  return data;
}

/** Cancela alteração pendente de e-mail. */
export async function cancelarTrocaEmail() {
  const { data } = await api.post('/api/auth/email/alterar/cancelar/');
  return data;
}

/** Confirma nova posse de e-mail via link de validação. */
export async function confirmarTrocaEmail({ uid, token }) {
  const { data } = await api.post('/api/auth/email/alterar/confirmar/', { uid, token });
  return data;
}

/** Altera a senha da conta autenticada e encerra outras sessões. */
export async function alterarSenha(dados) {
  const { data } = await api.post('/api/auth/senha/alterar/', dados);
  return data;
}

/** Exclui definitivamente a conta e seus dados associados. */
export async function excluirConta(dados) {
  const { data } = await api.post('/api/auth/conta/excluir/', dados);
  return data;
}

/** Retorna contagem de sessões ativas estimadas na janela recente. */
export async function buscarSessoes() {
  const { data } = await api.get('/api/auth/sessoes/');
  return data;
}

/**
 * Encerra outras sessões e emite novo token de acesso para a sessão atual.
 * @returns {Promise<{detail: string, access: string, ativas: number}>}
 */
export async function encerrarOutrasSessoes() {
  const { data } = await api.post('/api/auth/sessoes/encerrar-outras/');
  return data;
}

