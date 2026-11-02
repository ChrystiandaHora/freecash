import { ANCORA_SINAIS } from './sinais';

const CHAVE_DAS_LIDAS = 'freecash_notificacoes_lidas';

/**
 * Notificações do sino da barra superior.
 *
 * Duas fontes hoje: os sinais de rebalanceamento das carteiras e a situação do e-mail.
 * Ambas são informativas e só apontam para onde o assunto se resolve — o Balanceamento,
 * que rola até o painel de sinais pelo `#sinais`, e Minha Conta, que tem o aviso
 * completo com o reenvio do link. Nenhuma ação da conta depende de confirmar o e-mail:
 * ele serve para recuperar a senha.
 *
 * Cada item leva uma `assinatura` que muda quando o assunto muda (um sinal novo, outro
 * endereço de e-mail). É ela, e não o `id`, que fica marcada como lida: assim a
 * notificação clicada sai do contador, mas volta a contar se houver novidade.
 *
 * @param {{ email?: string, email_verificado?: boolean } | null | undefined} perfil
 * @param {{ posicao_id: number, tipo: string }[]} [sinais=[]] - Sinais em aberto.
 * @returns {{ id: string, assinatura: string, titulo: string, texto: string, destino: string }[]}
 */
export function montarNotificacoes(perfil, sinais = []) {
  return [notificacaoDeSinais(sinais), notificacaoDeEmail(perfil)].filter(Boolean);
}

/** Destino do item de sinais: o `#` faz o PainelSinais rolar e focar o próprio título. */
const DESTINO_SINAIS = `/investimentos/balanceamento#${ANCORA_SINAIS}`;

function notificacaoDeSinais(sinais) {
  const total = sinais.length;
  if (!total) return null;

  const chaves = sinais.map((sinal) => `${sinal.posicao_id}-${sinal.tipo}`).sort();

  return {
    id: 'sinais-rebalanceamento',
    assinatura: `sinais:${chaves.join(',')}`,
    titulo: `${total} ${total === 1 ? 'sinal' : 'sinais'} de rebalanceamento`,
    texto: 'Posições das suas carteiras se afastaram da meta definida.',
    destino: DESTINO_SINAIS,
  };
}

function notificacaoDeEmail(perfil) {
  // Sem perfil carregado não há o que afirmar
  if (!perfil || perfil.email_verificado) return null;

  if (!perfil.email) {
    return {
      id: 'email-ausente',
      assinatura: 'email-ausente',
      titulo: 'Cadastre um e-mail',
      texto: 'Ele permite recuperar a senha se você a esquecer.',
      destino: '/conta',
    };
  }

  return {
    id: 'email-nao-confirmado',
    assinatura: `email-nao-confirmado:${perfil.email}`,
    titulo: 'Confirme seu e-mail',
    texto: 'Ele permite recuperar a senha se você a esquecer.',
    destino: '/conta',
  };
}

/**
 * Lê as assinaturas já lidas neste navegador.
 *
 * @param {Storage} [storage] Armazenamento (injetável para teste).
 * @returns {string[]} As assinaturas. Armazenamento indisponível ou corrompido conta como vazio.
 */
export function lerLidas(storage = globalThis.localStorage) {
  try {
    const lista = JSON.parse(storage.getItem(CHAVE_DAS_LIDAS) || '[]');
    return Array.isArray(lista) ? lista : [];
  } catch {
    return [];
  }
}

/**
 * @param {{ assinatura: string }[]} notificacoes
 * @param {string[]} lidas
 * @returns {{ assinatura: string }[]} As notificações ainda não lidas.
 */
export function naoLidas(notificacoes, lidas) {
  return notificacoes.filter((notificacao) => !lidas.includes(notificacao.assinatura));
}

/**
 * Marca a notificação como lida e grava a lista.
 *
 * Só sobrevivem as assinaturas das notificações que existem agora: o que mudou ou sumiu
 * é descartado, e a lista nunca passa do número de notificações possíveis.
 *
 * @param {{ assinatura: string }} notificacao A notificação clicada.
 * @param {{ assinatura: string }[]} notificacoes Todas as notificações atuais, lidas ou não.
 * @param {string[]} lidas As assinaturas lidas até aqui.
 * @param {Storage} [storage] Armazenamento (injetável para teste).
 * @returns {string[]} A nova lista de lidas.
 */
export function marcarLida(notificacao, notificacoes, lidas, storage = globalThis.localStorage) {
  const atuais = notificacoes.map((item) => item.assinatura);
  const novas = [
    ...new Set([...lidas.filter((assinatura) => atuais.includes(assinatura)), notificacao.assinatura]),
  ];

  try {
    storage.setItem(CHAVE_DAS_LIDAS, JSON.stringify(novas));
  } catch {
    // Navegação privada ou cota cheia: vale só até recarregar a página, nada quebra
  }
  return novas;
}
