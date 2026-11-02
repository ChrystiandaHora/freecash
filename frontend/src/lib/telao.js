/**
 * Regras puras do telão de investimentos (ver pages/Telao.jsx).
 *
 * O telão pede sincronização ao servidor, e é o servidor quem decide se vai à fonte de
 * cotações (ver docs/cotacoes-e-preco-medio.md). Aqui fica só o que a tela calcula:
 * quando pedir de novo, como mostrar a contagem, o status e a variação do dia.
 */

export const INTERVALO_SINCRONIZACAO_MS = 15 * 60 * 1000;

/** Piso entre pedidos: protege contra um `proxima_em` no passado virar laço. */
export const ATRASO_MINIMO_MS = 60 * 1000;

/** Folga para não chegar um instante antes do fim do cooldown e perder o ciclo. */
export const FOLGA_MS = 5 * 1000;

/** Sem resposta do servidor (rede, 429 do próprio app), tenta de novo antes do ciclo. */
export const RETENTATIVA_APOS_FALHA_MS = 2 * 60 * 1000;

export const STATUS_SINCRONIZACAO = Object.freeze({
  ATUALIZADO: 'atualizado',
  EM_CACHE: 'em_cache',
  FORA_DO_PREGAO: 'fora_do_pregao',
  LIMITADO: 'limitado',
  FALHOU: 'falhou',
});

const ROTULOS_STATUS = {
  [STATUS_SINCRONIZACAO.ATUALIZADO]: 'Pregão aberto',
  [STATUS_SINCRONIZACAO.EM_CACHE]: 'Pregão aberto',
  [STATUS_SINCRONIZACAO.FORA_DO_PREGAO]: 'Pregão fechado',
  [STATUS_SINCRONIZACAO.LIMITADO]: 'Fonte de cotações pediu uma pausa',
  [STATUS_SINCRONIZACAO.FALHOU]: 'Fonte de cotações indisponível',
};

const HORA = new Intl.DateTimeFormat('pt-BR', { hour: '2-digit', minute: '2-digit' });
const DIA = new Intl.DateTimeFormat('pt-BR', { day: '2-digit', month: '2-digit' });

const VARIACAO = new Intl.NumberFormat('pt-BR', {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
  signDisplay: 'exceptZero',
});

/**
 * Quanto esperar até o próximo pedido de sincronização.
 *
 * Segue o `proxima_em` do servidor, com teto de um intervalo: fora do pregão o próximo
 * pedido não consulta a fonte, mas ainda relê o banco e mantém a sessão viva.
 *
 * @param {string|null|undefined} proximaEm - ISO 8601 devolvido por `telao/sincronizar/`.
 * @param {number} [agora] - Epoch em ms.
 * @returns {number} Atraso em ms, entre `ATRASO_MINIMO_MS` e `INTERVALO_SINCRONIZACAO_MS`.
 */
export function calcularAtrasoProximaSincronizacao(proximaEm, agora = Date.now()) {
  const alvo = Date.parse(proximaEm ?? '');
  if (Number.isNaN(alvo)) return INTERVALO_SINCRONIZACAO_MS;
  const atraso = alvo - agora + FOLGA_MS;
  return Math.min(Math.max(atraso, ATRASO_MINIMO_MS), INTERVALO_SINCRONIZACAO_MS);
}

/**
 * Contagem regressiva em "mm:ss".
 *
 * @param {number} ms
 * @returns {string}
 */
export function formatarContagem(ms) {
  const totalSegundos = Math.max(0, Math.ceil(ms / 1000));
  const minutos = String(Math.floor(totalSegundos / 60)).padStart(2, '0');
  const segundos = String(totalSegundos % 60).padStart(2, '0');
  return `${minutos}:${segundos}`;
}

/**
 * Momento da última cotação: "HH:MM" se for de hoje, "dd/mm, HH:MM" se não for.
 *
 * Sem o dia, "14:15" depois de um fim de semana pareceria de hoje.
 *
 * @param {string|null|undefined} iso
 * @param {number} [agora] - Epoch em ms.
 * @returns {string|null} Null sem instante.
 */
export function formatarAtualizacao(iso, agora = Date.now()) {
  const instante = Date.parse(iso ?? '');
  if (Number.isNaN(instante)) return null;
  const hora = HORA.format(instante);
  return DIA.format(instante) === DIA.format(agora) ? hora : `${DIA.format(instante)}, ${hora}`;
}

/**
 * @param {string|undefined} status - Status de `telao/sincronizar/`.
 * @returns {string|null} Texto curto para a faixa do topo.
 */
export function rotuloStatus(status) {
  return ROTULOS_STATUS[status] ?? null;
}

/**
 * Variação do dia pronta para exibir, com o sentido para ícone e cor.
 *
 * O sentido existe para que a alta e a baixa não sejam comunicadas só por cor.
 *
 * @param {number|null|undefined} pct
 * @returns {{texto: string, sentido: 'alta'|'baixa'|'estavel'}|null} Null sem pregão anterior.
 */
export function apresentarVariacao(pct) {
  if (pct === null || pct === undefined || Number.isNaN(Number(pct))) return null;
  const arredondado = Math.round(Number(pct) * 100) / 100;
  let sentido = 'estavel';
  if (arredondado > 0) sentido = 'alta';
  else if (arredondado < 0) sentido = 'baixa';
  return { texto: `${VARIACAO.format(arredondado)}%`, sentido };
}

/** Folga de arredondamento de subpixel ao comparar bordas medidas. */
const TOLERANCIA_PX = 0.5;

/**
 * Quantos itens, a partir do primeiro, cabem inteiros acima de uma borda.
 *
 * O telão não rola nem pagina sozinho (WCAG 2.2.2): o que não cabe na altura da tela é
 * escondido e contado ("e mais X"). Para no primeiro que não cabe, para que a lista
 * visível nunca tenha buraco.
 *
 * @param {number[]} fundos - Borda inferior de cada item, na ordem (px).
 * @param {number} limite - Borda inferior da área disponível (px).
 * @returns {number}
 */
export function contarQueCabem(fundos, limite) {
  const primeiroQueNaoCabe = fundos.findIndex((fundo) => fundo > limite + TOLERANCIA_PX);
  return primeiroQueNaoCabe === -1 ? fundos.length : primeiroQueNaoCabe;
}
