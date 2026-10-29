/**
 * Painel com os sinais de rebalanceamento de várias posições.
 *
 * Fica no topo do Balanceamento, que é o destino do indicador da barra do topo, e no
 * Detalhe do Ativo. Quando chega por `#sinais`, o foco vai para o título do painel: o
 * React Router não rola até a âncora sozinho.
 */
import { useEffect, useRef } from 'react';
import { useLocation } from 'react-router-dom';
import { Scale } from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../ui/Card';
import { Button } from '../ui/Button';
import { SinalResumo } from './SinalResumo';

export const ANCORA_SINAIS = 'sinais';

const AVISO =
  'Os sinais aplicam a regra 5/25 às metas que você definiu em cada carteira; não são ' +
  'recomendação de investimento. A isenção de IR considera só as vendas registradas no FreeCash.';

/**
 * @param {Object} props
 * @param {Array<Object>} props.sinais - Itens de `/api/investimentos/sinais/`.
 * @param {string} [props.titulo]
 * @param {number|null} [props.carteiraEmFoco] - Esconde o atalho para a carteira já aberta.
 * @param {(carteiraId: number) => void} [props.onAbrirCarteira] - Sem ele, não há atalho.
 */
export function PainelSinais({
  sinais,
  titulo = 'Sinais de rebalanceamento',
  carteiraEmFoco = null,
  onAbrirCarteira,
}) {
  const { hash } = useLocation();
  const tituloRef = useRef(null);
  const temSinais = sinais.length > 0;

  useEffect(() => {
    if (temSinais && hash === `#${ANCORA_SINAIS}`) {
      tituloRef.current?.focus();
      tituloRef.current?.scrollIntoView({ block: 'start' });
    }
  }, [hash, temSinais]);

  if (!temSinais) return null;

  return (
    <Card id={ANCORA_SINAIS} data-tour="investimentos-sinais" className="border border-amber-500/30 bg-card shadow-sm">
      <CardHeader>
        <CardTitle
          ref={tituloRef}
          tabIndex={-1}
          className="text-base font-bold text-foreground flex items-center gap-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring rounded"
        >
          <Scale className="h-4 w-4 text-amber-600 dark:text-amber-400" aria-hidden="true" />
          {titulo}
        </CardTitle>
        <CardDescription className="text-xs">{AVISO}</CardDescription>
      </CardHeader>
      <CardContent>
        <ul className="divide-y divide-border/30">
          {sinais.map((sinal) => (
            <li key={sinal.posicao_id} className="py-3 first:pt-0 last:pb-0 space-y-1">
              <SinalResumo
                sinal={sinal}
                titulo={
                  <span className="text-sm font-bold text-foreground">
                    {sinal.ticker}
                    <span className="font-normal text-muted-foreground"> em {sinal.carteira_nome}</span>
                  </span>
                }
              />
              {onAbrirCarteira && sinal.carteira_id !== carteiraEmFoco && (
                <Button
                  variant="link"
                  onClick={() => onAbrirCarteira(sinal.carteira_id)}
                  className="h-auto min-h-6 p-0 text-xs font-semibold underline hover:no-underline"
                >
                  Abrir a carteira {sinal.carteira_nome}
                </Button>
              )}
            </li>
          ))}
        </ul>
      </CardContent>
    </Card>
  );
}
