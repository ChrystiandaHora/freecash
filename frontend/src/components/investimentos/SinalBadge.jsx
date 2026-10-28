/**
 * Badge do sinal de rebalanceamento de uma posição.
 *
 * O tipo do sinal vai no texto, não só na cor (SC 1.4.1), e o ícone é decorativo. A
 * queda relevante junto de um sinal de venda ganha um segundo badge, porque são dois
 * fatos diferentes: sair da meta e cair desde o preço médio.
 */
import { AlertTriangle, TrendingDown, TrendingUp } from 'lucide-react';
import { Badge } from '../ui/Badge';
import { cn } from '../../lib/utils';
import { apresentarSinal } from '../../lib/sinais';

const ICONES = { success: TrendingUp, warning: TrendingDown, destructive: AlertTriangle };

/**
 * @param {Object} props
 * @param {Object} props.sinal - Sinal da API; sem sinal, não renderiza nada.
 * @param {string} [props.className]
 */
export function SinalBadge({ sinal, className }) {
  const apresentacao = apresentarSinal(sinal);
  if (!apresentacao) return null;

  const Icone = ICONES[apresentacao.variante];
  const mostrarQueda = sinal.queda_relevante && sinal.tipo !== 'REVISAR_QUEDA';

  return (
    <span className={cn('inline-flex flex-wrap items-center gap-1', className)}>
      <Badge variant={apresentacao.variante}>
        <Icone className="h-3 w-3" aria-hidden="true" />
        {apresentacao.rotulo}
      </Badge>
      {mostrarQueda && (
        <Badge variant="destructive">
          <AlertTriangle className="h-3 w-3" aria-hidden="true" />
          Queda relevante
        </Badge>
      )}
    </span>
  );
}

/**
 * Um badge por tipo de sinal, para o ativo que tem sinal em mais de uma carteira.
 *
 * @param {Object} props
 * @param {Array<Object>} [props.sinais]
 */
export function SinaisBadges({ sinais = [] }) {
  const porTipo = new Map(sinais.map((sinal) => [sinal.tipo, sinal]));
  return [...porTipo.values()].map((sinal) => <SinalBadge key={sinal.tipo} sinal={sinal} />);
}
