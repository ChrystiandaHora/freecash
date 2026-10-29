/** Localiza na página o elemento marcado com `data-tour`, para o tour destacá-lo. */

/**
 * @param {string} [alvo] Valor do atributo `data-tour`.
 * @returns {Element|null} O elemento, ou null se não existe ou está escondido (`display: none`).
 */
export function elementoDoAlvo(alvo) {
  if (!alvo) return null;
  const elemento = document.querySelector(`[data-tour="${alvo}"]`);
  return elemento && elemento.getClientRects().length > 0 ? elemento : null;
}
