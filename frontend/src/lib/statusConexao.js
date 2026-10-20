/**
 * Estado global de conexão com a API.
 *
 * Antes deste módulo, uma API fora do ar não tinha cara própria: cada tela mostrava o
 * seu erro genérico, e a renovação silenciosa do JWT tratava a falha de rede como
 * sessão expirada — o usuário era mandado para o login sem ter feito nada errado e
 * sem saber que o problema era o servidor.
 *
 * É um armazenamento externo mínimo (assinar/ler), e não um contexto React, porque
 * quem informa a queda é o interceptor do axios, que vive fora da árvore de
 * componentes. A leitura nos componentes é feita com `useSyncExternalStore`.
 */

export const STATUS_CONEXAO = {
  ONLINE: 'online',
  SEM_INTERNET: 'sem-internet',
  API_INDISPONIVEL: 'api-indisponivel',
};

/**
 * Respostas que vêm da infraestrutura (proxy, balanceador, plataforma de hospedagem),
 * não do Django: o único 503 do backend é o próprio healthcheck, que não passa pelo
 * interceptor.
 */
const STATUS_DE_GATEWAY = new Set([502, 503, 504]);

/** Intervalos, em segundos, entre as tentativas automáticas de reconexão. */
const INTERVALOS_DE_TENTATIVA = [5, 10, 20, 30];

/**
 * Diz se a falha do axios significa "não consegui falar com o servidor".
 *
 * Erros com resposta do Django (400, 401, 404, 500…) ficam de fora: o servidor está no
 * ar e respondeu, e quem trata é a tela. Requisição cancelada também fica de fora — o
 * React Query aborta as consultas de quem sai da tela, e isso não é queda.
 *
 * @param {unknown} erro - Erro capturado da chamada à API.
 * @returns {boolean}
 */
export function ehFalhaDeConexao(erro) {
  if (!erro?.isAxiosError || erro.code === 'ERR_CANCELED') {
    return false;
  }
  if (erro.response) {
    return STATUS_DE_GATEWAY.has(erro.response.status);
  }
  return true;
}

/**
 * Separa "a sua internet caiu" de "o nosso servidor caiu".
 *
 * A orientação ao usuário é diferente em cada caso: no primeiro, ele pode resolver; no
 * segundo, só pode esperar.
 *
 * @param {boolean} navegadorOnline - Valor de `navigator.onLine`.
 * @returns {string} Um dos valores de `STATUS_CONEXAO` que indicam falha.
 */
export function classificarFalha(navegadorOnline) {
  return navegadorOnline ? STATUS_CONEXAO.API_INDISPONIVEL : STATUS_CONEXAO.SEM_INTERNET;
}

/**
 * Intervalo até a próxima tentativa automática, crescente para não martelar um
 * servidor que está tentando subir.
 *
 * @param {number} tentativa - Quantas tentativas já falharam (a partir de 0).
 * @returns {number} Segundos de espera.
 */
export function intervaloDeTentativa(tentativa) {
  const indice = Math.min(Math.max(tentativa, 0), INTERVALOS_DE_TENTATIVA.length - 1);
  return INTERVALOS_DE_TENTATIVA[indice];
}

let statusAtual = STATUS_CONEXAO.ONLINE;
const ouvintes = new Set();

/** @returns {string} Status de conexão vigente. */
export const lerStatusConexao = () => statusAtual;

/**
 * Atualiza o status e avisa os assinantes, só quando há mudança de fato.
 *
 * @param {string} novoStatus - Um dos valores de `STATUS_CONEXAO`.
 */
export function definirStatusConexao(novoStatus) {
  if (novoStatus === statusAtual) {
    return;
  }
  statusAtual = novoStatus;
  ouvintes.forEach((ouvinte) => ouvinte());
}

/**
 * @param {() => void} ouvinte - Chamado a cada mudança de status.
 * @returns {() => void} Cancela a assinatura.
 */
export function assinarStatusConexao(ouvinte) {
  ouvintes.add(ouvinte);
  return () => ouvintes.delete(ouvinte);
}

/**
 * Resolve quando a conexão volta — imediatamente, se já estiver no ar.
 *
 * @returns {Promise<void>}
 */
export function aguardarConexao() {
  if (statusAtual === STATUS_CONEXAO.ONLINE) {
    return Promise.resolve();
  }
  return new Promise((resolve) => {
    const cancelar = assinarStatusConexao(() => {
      if (statusAtual === STATUS_CONEXAO.ONLINE) {
        cancelar();
        resolve();
      }
    });
  });
}
