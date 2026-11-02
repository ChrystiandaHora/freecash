/**
 * Donut de alocação do telão, com a mesma informação repetida em texto ao lado.
 *
 * O gráfico fica `aria-hidden`: o leitor de tela lê a lista, como no painel de
 * investimentos. A `key` do `<Chart>` inclui tema e privacidade porque o ApexCharts não
 * relê formatadores nem cores sozinho. A legenda mostra só os itens que cabem na altura
 * do painel e conta o resto, como a tabela.
 */
import Chart from 'react-apexcharts';
import { useMoeda } from '../../hooks/useMoeda';
import { useQuantosCabem } from '../../hooks/useQuantosCabem';
import { CORES_ALOCACAO } from '../../lib/coresAlocacao';

const PERCENTUAL = new Intl.NumberFormat('pt-BR', { maximumFractionDigits: 1, minimumFractionDigits: 1 });

/**
 * @param {Object} props
 * @param {string} props.titulo
 * @param {string} props.id - Prefixo de ids, único na página.
 * @param {{labels: string[], valores: number[]}} props.alocacao
 * @param {string} [props.className]
 */
export function DonutAlocacao({ titulo, id, alocacao, className = '' }) {
  const { formatarMoeda, valoresOcultos } = useMoeda();
  const isDarkTheme = document.documentElement.classList.contains('dark');

  const itens = (alocacao?.labels ?? [])
    .map((label, idx) => ({ label, valor: Number(alocacao.valores?.[idx]) || 0 }))
    .filter((item) => item.valor > 0)
    .sort((a, b) => b.valor - a.valor);
  const total = itens.reduce((acc, item) => acc + item.valor, 0);
  const [legendaRef, quantos] = useQuantosCabem(itens.length);
  const restantes = itens.length - quantos;

  const opcoes = {
    chart: { type: 'donut', background: 'transparent', animations: { enabled: false } },
    labels: itens.map((item) => item.label),
    colors: CORES_ALOCACAO,
    dataLabels: { enabled: false },
    legend: { show: false },
    stroke: { width: 1, colors: [isDarkTheme ? 'rgba(255, 255, 255, 0.05)' : 'rgba(0, 0, 0, 0.05)'] },
    plotOptions: { pie: { expandOnClick: false, donut: { size: '70%' } } },
    tooltip: { enabled: false },
    states: { hover: { filter: { type: 'none' } } },
  };

  return (
    <section
      aria-labelledby={`${id}-titulo`}
      className={`flex min-h-0 flex-col rounded-2xl border border-border/60 bg-card px-[1.1em] py-[0.9em] ${className}`}
    >
      <h2 id={`${id}-titulo`} className="mb-[0.6em] shrink-0 text-[0.7em] font-bold uppercase tracking-[0.15em] text-muted-foreground">
        {titulo}
      </h2>

      {itens.length === 0 ? (
        <p className="py-[1em] text-center text-muted-foreground">Sem posições para distribuir.</p>
      ) : (
        <div className="flex min-h-0 flex-1 items-start gap-[1em]">
          <div aria-hidden="true" className="w-[7.5em] shrink-0">
            <Chart
              key={`${id}-${isDarkTheme}-${valoresOcultos}`}
              options={opcoes}
              series={itens.map((item) => item.valor)}
              type="donut"
              width="100%"
            />
          </div>
          <div className="flex h-full min-h-0 min-w-0 flex-1 flex-col">
            <ul ref={legendaRef} className="relative space-y-[0.35em] text-[0.85em] lg:min-h-0 lg:flex-1 lg:overflow-hidden">
              {itens.map((item, idx) => {
                const escondido = idx >= quantos;
                return (
                  <li
                    key={item.label}
                    data-cabe=""
                    className={`flex items-center gap-[0.5em] ${escondido ? 'invisible' : ''}`}
                    aria-hidden={escondido || undefined}
                  >
                    <span
                      aria-hidden="true"
                      className="h-[0.6em] w-[0.6em] shrink-0 rounded-full"
                      style={{ backgroundColor: CORES_ALOCACAO[idx % CORES_ALOCACAO.length] }}
                    />
                    <span className="min-w-0 flex-1 truncate text-foreground">{item.label}</span>
                    <span className="font-bold tabular-nums text-foreground">
                      {PERCENTUAL.format(total > 0 ? (item.valor / total) * 100 : 0)}%
                    </span>
                    <span className="sr-only">, {formatarMoeda(item.valor)}</span>
                  </li>
                );
              })}
            </ul>
            <p className="min-h-[1.4em] shrink-0 text-[0.75em] text-muted-foreground">
              {restantes > 0 && `e mais ${restantes}`}
            </p>
          </div>
        </div>
      )}
    </section>
  );
}
