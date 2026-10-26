/**
 * Formatação monetária compartilhada pelas telas de planejamento.
 *
 * O Horizonte de Saldos precisa de duas formas do mesmo valor: a compacta, que
 * cabe numa célula de grade com doze colunas, e a completa, exibida no detalhe do
 * dia. Concentrar as duas aqui evita que a grade e o detalhe arredondem de formas
 * diferentes e pareçam discordar entre si.
 *
 * As duas aceitam `{ ocultar }`, ligado pelo olho da barra do topo (ver
 * docs/privacidade-valores.md). Nas telas, use o hook `useMoeda`, que já passa o
 * estado; chamar daqui direto só serve onde não há componente.
 */

const COMPLETO = new Intl.NumberFormat('pt-BR', {
  style: 'currency',
  currency: 'BRL',
});

const COMPACTO = new Intl.NumberFormat('pt-BR', {
  style: 'currency',
  currency: 'BRL',
  notation: 'compact',
  maximumFractionDigits: 1,
});

/** Texto que substitui qualquer valor oculto. Comprimento fixo: não revela a ordem de grandeza. */
export const MASCARA_MOEDA = 'R$ ••••';

/**
 * Formata um valor em reais por extenso.
 *
 * @param {number|string} valor - Valor a formatar.
 * @param {{ocultar?: boolean}} [opcoes] - `ocultar` troca o valor pela máscara.
 * @returns {string} Valor formatado, por exemplo "R$ 1.234,56".
 */
export function formatarMoeda(valor, { ocultar = false } = {}) {
  if (ocultar) return MASCARA_MOEDA;
  return COMPLETO.format(Number(valor) || 0);
}

/**
 * Formata um valor em reais de forma abreviada, para caber em célula de grade.
 *
 * @param {number|string} valor - Valor a formatar.
 * @param {{ocultar?: boolean}} [opcoes] - `ocultar` troca o valor pela máscara.
 * @returns {string} Valor abreviado, por exemplo "R$ 1,2 mil".
 */
export function formatarMoedaCompacta(valor, { ocultar = false } = {}) {
  if (ocultar) return MASCARA_MOEDA;
  return COMPACTO.format(Number(valor) || 0);
}
