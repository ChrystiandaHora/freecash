/**
 * Sinais de rebalanceamento no telão, em versão compacta.
 *
 * Usa os mesmos textos do painel de sinais (lib/sinais.js), mas em `em`, para escalar
 * com a fonte-base do telão; o `SinalResumo` usa tamanhos fixos pensados para a tela
 * normal. Mostra só os sinais que cabem inteiros e conta o resto.
 */
import { Scale } from 'lucide-react';
import { useMoeda } from '../../hooks/useMoeda';
import { useQuantosCabem } from '../../hooks/useQuantosCabem';
import { textoAcao } from '../../lib/sinais';
import { SinalBadge } from '../investimentos/SinalBadge';

/**
 * @param {Object} props
 * @param {Array<Object>} props.sinais - Itens de `/api/investimentos/sinais/`.
 * @param {string} [props.className]
 */
export function SinaisTelao({ sinais, className = '' }) {
  const { formatarMoeda } = useMoeda();
  const [listaRef, quantos] = useQuantosCabem(sinais.length);
  const restantes = sinais.length - quantos;

  return (
    <section
      aria-labelledby="telao-sinais-titulo"
      className={`flex min-h-0 flex-col rounded-2xl border border-amber-500/30 bg-card px-[1.1em] py-[0.9em] ${className}`}
    >
      <h2
        id="telao-sinais-titulo"
        className="mb-[0.6em] flex shrink-0 items-center gap-[0.5em] text-[0.7em] font-bold uppercase tracking-[0.15em] text-muted-foreground"
      >
        <Scale className="h-[1.2em] w-[1.2em] text-amber-600 dark:text-amber-400" aria-hidden="true" />
        Sinais de rebalanceamento
      </h2>

      <ul ref={listaRef} className="relative space-y-[0.75em] lg:min-h-0 lg:flex-1 lg:overflow-hidden">
        {sinais.map((sinal, idx) => {
          const escondido = idx >= quantos;
          return (
            <li
              key={sinal.posicao_id}
              data-cabe=""
              className={`space-y-[0.25em] ${escondido ? 'invisible' : ''}`}
              aria-hidden={escondido || undefined}
            >
              <div className="flex flex-wrap items-center gap-[0.5em]">
                <span className="font-bold text-foreground">
                  {sinal.ticker}
                  <span className="font-normal text-muted-foreground"> em {sinal.carteira_nome}</span>
                </span>
                <SinalBadge sinal={sinal} />
              </div>
              <p className="text-[0.8em] leading-snug text-foreground">{textoAcao(sinal, formatarMoeda)}</p>
            </li>
          );
        })}
      </ul>

      <p className="min-h-[1.4em] shrink-0 text-[0.75em] text-muted-foreground">
        {restantes > 0 && `e mais ${restantes} ${restantes === 1 ? 'sinal' : 'sinais'} no Balanceamento`}
      </p>
    </section>
  );
}
