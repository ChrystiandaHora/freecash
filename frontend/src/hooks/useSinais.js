/**
 * Sinais de rebalanceamento das posições do usuário (ver lib/sinais.js).
 *
 * Quem altera ordens, metas, ativos ou cotações invalida `['investimentosSinais']`. O
 * `staleTime` evita uma requisição por troca de tela, já que a barra do topo também lê.
 */
import { useQuery } from '@tanstack/react-query';
import { fetchSinais } from '../services/investimentos';

const UM_MINUTO = 60_000;

/**
 * @param {number|string|null} [carteiraId] - Sem carteira, os sinais de todas.
 */
export function useSinais(carteiraId = null) {
  return useQuery({
    queryKey: ['investimentosSinais', carteiraId ?? 'todas'],
    queryFn: () => fetchSinais(carteiraId),
    staleTime: UM_MINUTO,
  });
}
