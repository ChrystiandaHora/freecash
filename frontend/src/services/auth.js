/**
 * Chamadas à API dos fluxos de identidade.
 *
 * Reúne confirmação de e-mail, redefinição de senha e leitura do estado da conta.
 * Os endpoints de login, refresh e logout continuam em `context/AuthProvider.jsx`,
 * onde vivem junto do ciclo de vida do token.
 */
import api from './api';

/**
 * Busca a identidade e o estado da conta autenticada.
 *
 * O estado precisa vir daqui e não do conteúdo do JWT: com rotação de refresh
 * token, o SimpleJWT preserva o payload original e troca apenas `jti` e `exp`,
 * então um valor embutido no token ficaria desatualizado por até sete dias — um
 * administrador rebaixado continuaria com o papel antigo por uma semana.
 *
 * @returns {Promise<{username: string, email: string, email_verificado: boolean, is_staff: boolean}>}
 */
export async function buscarPerfil() {
  const { data } = await api.get('/api/auth/me/');
  return data;
}

/**
 * Confirma a posse do endereço de e-mail a partir do link recebido.
 *
 * @param {{uid: string, token: string}} params - Identificador e token do link.
 * @returns {Promise<{detail: string, email_verificado: boolean}>}
 */
export async function confirmarEmail({ uid, token }) {
  const { data } = await api.post('/api/auth/verificar-email/', { uid, token });
  return data;
}

/**
 * Solicita um novo e-mail de confirmação para a conta autenticada.
 *
 * @returns {Promise<{detail: string}>}
 */
export async function reenviarConfirmacaoEmail() {
  const { data } = await api.post('/api/auth/verificar-email/reenviar/');
  return data;
}

/**
 * Pede o envio do link de redefinição de senha.
 *
 * A resposta é sempre a mesma, exista ou não conta com aquele endereço — é o que
 * impede que o endpoint seja usado para descobrir quem tem conta no sistema.
 *
 * @param {string} email - Endereço informado pelo usuário.
 * @returns {Promise<{detail: string}>}
 */
export async function solicitarResetSenha(email) {
  const { data } = await api.post('/api/auth/senha/reset/', { email });
  return data;
}

/**
 * Efetiva a troca de senha a partir do link recebido por e-mail.
 *
 * @param {{uid: string, token: string, nova_senha: string, confirmar: string}} params
 * @returns {Promise<{detail: string}>}
 */
export async function confirmarResetSenha({ uid, token, nova_senha, confirmar }) {
  const { data } = await api.post('/api/auth/senha/reset/confirmar/', {
    uid,
    token,
    nova_senha,
    confirmar,
  });
  return data;
}

/**
 * Busca os dados completos da conta, incluindo preferências.
 *
 * Diferente de `buscarPerfil`, que serve ao cabeçalho e ao roteamento, este
 * devolve também moeda padrão e e-mail pendente de confirmação — dados que só a
 * tela de conta usa.
 *
 * @returns {Promise<Object>} Dados da conta.
 */
export async function buscarConta() {
  const { data } = await api.get('/api/auth/perfil/');
  return data;
}

/**
 * Atualiza nome de usuário e preferências.
 *
 * Não exige a senha atual: são dados que não redirecionam recuperação de conta
 * nem dão acesso a nada.
 *
 * @param {{username?: string, moeda_padrao?: string}} campos - Campos a alterar.
 * @returns {Promise<Object>} Dados atualizados da conta.
 */
export async function atualizarPerfil(campos) {
  const { data } = await api.patch('/api/auth/perfil/', campos);
  return data;
}

/**
 * Solicita a troca do endereço de e-mail.
 *
 * O endereço novo fica pendente e só passa a valer quando o link enviado a ele é
 * aberto — até lá, o e-mail atual continua servindo para entrar e recuperar a conta.
 *
 * @param {{senha_atual: string, novo_email: string}} dados - Senha e novo endereço.
 * @returns {Promise<{detail: string, email_pendente: string}>}
 */
export async function solicitarTrocaEmail(dados) {
  const { data } = await api.post('/api/auth/email/alterar/', dados);
  return data;
}

/**
 * Descarta uma troca de e-mail pendente, invalidando o link já enviado.
 *
 * @returns {Promise<Object>} Dados atualizados da conta.
 */
export async function cancelarTrocaEmail() {
  const { data } = await api.post('/api/auth/email/alterar/cancelar/');
  return data;
}

/**
 * Efetiva a troca de e-mail a partir do link recebido no novo endereço.
 *
 * @param {{uid: string, token: string}} params - Identificador e token do link.
 * @returns {Promise<{detail: string, email: string}>}
 */
export async function confirmarTrocaEmail({ uid, token }) {
  const { data } = await api.post('/api/auth/email/alterar/confirmar/', { uid, token });
  return data;
}

/**
 * Troca a senha com o usuário já autenticado.
 *
 * As demais sessões da conta são encerradas; a atual continua, com um token novo.
 *
 * @param {{senha_atual: string, nova_senha: string, confirmar: string}} dados
 * @returns {Promise<{detail: string, access: string}>}
 */
export async function alterarSenha(dados) {
  const { data } = await api.post('/api/auth/senha/alterar/', dados);
  return data;
}

/**
 * Exclui definitivamente a conta e todos os seus dados.
 *
 * @param {{senha_atual: string, confirmacao: string}} dados - Senha e o nome de
 *   usuário digitado por extenso como segunda confirmação.
 * @returns {Promise<{detail: string}>}
 */
export async function excluirConta(dados) {
  const { data } = await api.post('/api/auth/conta/excluir/', dados);
  return data;
}

/**
 * Busca quantas sessões da conta estão ativas.
 *
 * A contagem superestima por natureza: com rotação de refresh token, uma sessão
 * abandonada sem logout deixa o último token pendente até expirar. Por isso a
 * resposta traz `janela_dias`, e a interface fala em "últimos N dias" em vez de
 * afirmar uma precisão que o dado não tem.
 *
 * @returns {Promise<{ativas: number, janela_dias: number}>}
 */
export async function buscarSessoes() {
  const { data } = await api.get('/api/auth/sessoes/');
  return data;
}

/**
 * Encerra as demais sessões da conta e renova a sessão em uso.
 *
 * O servidor revoga todos os refresh tokens e emite um novo para quem chamou — o
 * cookie de refresh não alcança essa rota, então não há como poupar seletivamente a
 * sessão atual. O `access` devolvido precisa ser gravado pelo chamador, senão a
 * própria sessão cai na requisição seguinte.
 *
 * @returns {Promise<{detail: string, access: string, ativas: number}>}
 */
export async function encerrarOutrasSessoes() {
  const { data } = await api.post('/api/auth/sessoes/encerrar-outras/');
  return data;
}
