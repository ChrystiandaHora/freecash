/**
 * Regra pura de qual carteira a tela de Balanceamento abre (sem DOM nem React).
 *
 * As metas por ativo somam 100% *dentro* de uma carteira, então o consolidado não tem
 * plano por ativo para mostrar — quem cai nele vê um estado vazio. A tela portanto
 * abre sempre numa carteira concreta, e só fica no consolidado quando o usuário o pede
 * no seletor, que é onde vivem as metas *entre* carteiras (ver docs/carteiras.md).
 *
 * O caso que motivou isolar isto: com uma carteira ativa só, o seletor não é
 * renderizado (não há escolha a oferecer) e a tela pedia uma seleção impossível.
 */

/**
 * Resolve a carteira em foco no balanceamento.
 *
 * @param {{carteiraId: number|null, consolidadoExplicito: boolean,
 *   carteirasAtivas: Array<{id: number}>}} params
 * @returns {number|null} Id da carteira a balancear, ou null para o consolidado.
 */
export function resolverCarteiraEmFoco({
  carteiraId,
  consolidadoExplicito,
  carteirasAtivas = [],
}) {
  if (carteiraId) return carteiraId;

  // Com uma carteira só o seletor não aparece, e o consolidado viraria beco sem saída
  const consolidadoAlcancavel = consolidadoExplicito && carteirasAtivas.length > 1;
  if (consolidadoAlcancavel) return null;

  return carteirasAtivas[0]?.id ?? null;
}
