/**
 * Indicador de sinais de rebalanceamento na barra do topo.
 *
 * Some quando não há sinal: um "0" fixo em toda tela seria ruído. O número vai no nome
 * acessível ("2 sinais de rebalanceamento"); o contador visual é `aria-hidden` para não
 * ser lido duas vezes. Leva ao painel de sinais do Balanceamento.
 */
import { Link } from 'react-router-dom';
import { Scale } from 'lucide-react';
import { useSinais } from '../../hooks/useSinais';
import { ANCORA_SINAIS } from '../investimentos/PainelSinais';

const CONTADOR_MAXIMO = 9;

export function SinaisIndicador() {
  const { data } = useSinais();
  const total = data?.total ?? 0;
  if (total === 0) return null;

  const rotulo = `${total} ${total === 1 ? 'sinal' : 'sinais'} de rebalanceamento`;

  return (
    <Link
      to={{ pathname: '/investimentos/balanceamento', hash: ANCORA_SINAIS }}
      aria-label={rotulo}
      title={rotulo}
      className="relative inline-flex h-11 w-11 items-center justify-center rounded-xl text-muted-foreground hover:bg-muted/50 hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
    >
      <Scale className="h-[1.1rem] w-[1.1rem]" aria-hidden="true" />
      <span
        aria-hidden="true"
        className="absolute right-1 top-1 min-w-4 rounded-full bg-amber-700 px-1 text-center text-xs font-bold leading-4 text-white"
      >
        {total > CONTADOR_MAXIMO ? `${CONTADOR_MAXIMO}+` : total}
      </span>
    </Link>
  );
}
