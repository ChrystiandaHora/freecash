/**
 * Formatação monetária compartilhada pelas telas de planejamento.
 *
 * O Horizonte de Saldos precisa de duas formas do mesmo valor: a compacta, que
 * cabe numa célula de grade com doze colunas, e a completa, exibida no detalhe do
 * dia. Concentrar as duas aqui evita que a grade e o detalhe arredondem de formas
 * diferentes e pareçam discordar entre si.
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

/**
 * Formata um valor em reais por extenso.
 *
 * @param {number|string} valor - Valor a formatar.
 * @returns {string} Valor formatado, por exemplo "R$ 1.234,56".
 */
export function formatarMoeda(valor) {
  return COMPLETO.format(Number(valor) || 0);
}

/**
 * Formata um valor em reais de forma abreviada, para caber em célula de grade.
 *
 * @param {number|string} valor - Valor a formatar.
 * @returns {string} Valor abreviado, por exemplo "R$ 1,2 mil".
 */
export function formatarMoedaCompacta(valor) {
  return COMPACTO.format(Number(valor) || 0);
}
