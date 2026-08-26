import { useState } from 'react';
import { CalendarDays, LayoutGrid, Sparkles, Table2, TrendingDown } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/Card';
import { Button } from '../../components/ui/Button';
import CalendarHeatmap from '../../components/CalendarHeatmap';
import { formatCurrency, formatDateLong } from './formatters';

function renderHeatmapTooltip(day) {
  return (
    <div className="space-y-2">
      <p className="text-xs font-semibold text-foreground">{day.dateLabel}</p>

      <p className="text-sm font-bold tabular-nums">
        <span className="block text-[10px] font-medium uppercase tracking-wider text-muted-foreground">
          {day.metricNome}
        </span>
        <span className={day.value >= 0 ? 'text-emerald-500' : 'text-red-500'}>
          {formatCurrency(day.value)}
        </span>
      </p>

      {day.itens.length === 0 ? (
        <p className="text-xs text-muted-foreground">Sem lançamentos neste dia.</p>
      ) : (
        <ul className="space-y-1 border-t border-border pt-2">
          {day.itens.slice(0, 4).map((item) => (
            <li key={item.id} className="flex items-start justify-between gap-2 text-xs">
              <span className="truncate text-muted-foreground">
                {item.simulado && (
                  <Sparkles className="mr-1 inline h-3 w-3 text-amber-500" aria-hidden="true" />
                )}
                {item.descricao}
              </span>
              <span
                className={`shrink-0 font-semibold tabular-nums ${
                  item.tipo === 'R' ? 'text-emerald-500' : 'text-red-500'
                }`}
              >
                {item.tipo === 'R' ? '+' : '-'}{formatCurrency(item.valor)}
              </span>
            </li>
          ))}
          {day.itens.length > 4 && (
            <li className="text-xs text-muted-foreground">
              e mais {day.itens.length - 4}...
            </li>
          )}
        </ul>
      )}
    </div>
  );
}

export default function MapaDeCalorDiario({
  isLoading,
  projecaoFutura,
  pontoDeVirada,
  heatmapMetric,
  setHeatmapMetric,
}) {
  const [showHeatmapTable, setShowHeatmapTable] = useState(false);

  const EPS = 0.005;

  // Discretiza a série diária em 7 classes: neutro + 3 degraus por braço.
  // Os cortes são os tercis de cada braço, então a escala se adapta à ordem de
  // grandeza da carteira em vez de usar limites fixos arbitrários.
  const valueOf = (d) => (heatmapMetric === 'acumulado' ? d.acumulado : d.fluxo);
  const values = projecaoFutura.map(valueOf);

  const asc = (a, b) => a - b;
  const positives = values.filter((v) => v > EPS).sort(asc);
  const negatives = values.filter((v) => v < -EPS).map(Math.abs).sort(asc);
  const tercil = (arr, p) =>
    arr.length ? arr[Math.min(arr.length - 1, Math.floor(arr.length * p))] : 0;

  const posCuts = [tercil(positives, 1 / 3), tercil(positives, 2 / 3)];
  const negCuts = [tercil(negatives, 1 / 3), tercil(negatives, 2 / 3)];

  const levelOf = (v) => {
    if (v > EPS) return v <= posCuts[0] ? 1 : v <= posCuts[1] ? 2 : 3;
    if (v < -EPS) {
      const mag = Math.abs(v);
      return mag <= negCuts[0] ? -1 : mag <= negCuts[1] ? -2 : -3;
    }
    return 0;
  };

  const metricNome =
    heatmapMetric === 'acumulado' ? 'Fluxo acumulado desde hoje' : 'Fluxo do dia';
  const daysByKey = new Map();

  projecaoFutura.forEach((d) => {
    const value = valueOf(d);
    const level = levelOf(value);
    const dateLabel = formatDateLong(d.date);
    const sinal = level > 0 ? 'positivo' : level < 0 ? 'negativo' : 'zerado';

    daysByKey.set(d.key, {
      ...d,
      value,
      level,
      dateLabel,
      metricNome,
      srLabel:
        `${dateLabel}: ${metricNome.toLowerCase()} de ${formatCurrency(value)} (${sinal}). ` +
        `Entradas ${formatCurrency(d.receitas)}, saídas ${formatCurrency(d.despesas)}.`,
    });
  });

  // Legenda: uma faixa por classe, com o intervalo em reais no rótulo.
  const legend = [
    { level: -3, label: `Abaixo de -${formatCurrency(negCuts[1])}` },
    { level: -2, label: `-${formatCurrency(negCuts[1])} a -${formatCurrency(negCuts[0])}` },
    { level: -1, label: `-${formatCurrency(negCuts[0])} a zero` },
    { level: 0, label: 'Sem movimento (zero)' },
    { level: 1, label: `Zero a ${formatCurrency(posCuts[0])}` },
    { level: 2, label: `${formatCurrency(posCuts[0])} a ${formatCurrency(posCuts[1])}` },
    { level: 3, label: `Acima de ${formatCurrency(posCuts[1])}` },
  ];

  const firstDate = projecaoFutura[0]?.date || null;
  const lastDate = projecaoFutura[projecaoFutura.length - 1]?.date || null;

  // Dias com algum lançamento — a visão em tabela do mapa de calor. Dias sem
  // movimento repetem o saldo do dia anterior, então nada se perde ao omiti-los.
  const heatmapTableRows = projecaoFutura.filter((d) => d.itens.length > 0);

  return (
    <Card className="border-border bg-card/65 backdrop-blur-md">
      <CardHeader className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <CardTitle className="text-lg font-semibold flex items-center gap-2">
            <CalendarDays className="h-5 w-5 text-primary" aria-hidden="true" />
            Mapa de Calor Diário
          </CardTitle>
          <p className="mt-1 text-sm text-muted-foreground">
            Cada quadradinho é um dia, de hoje até o fim da janela de 12 meses. Azul
            indica que as entradas ainda cobrem as saídas; vermelho (hachurado) indica
            que as saídas passaram. Não considera o saldo em caixa. Passe o mouse — ou
            navegue com as setas — para ver o dia.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <div className="flex rounded-lg border border-border p-0.5" role="group" aria-label="Métrica do mapa de calor">
            {[
              { id: 'acumulado', label: 'Fluxo acumulado' },
              { id: 'fluxo', label: 'Fluxo do dia' },
            ].map((opt) => (
              <button
                key={opt.id}
                type="button"
                aria-pressed={heatmapMetric === opt.id}
                onClick={() => setHeatmapMetric(opt.id)}
                className={`rounded-md px-3 py-1.5 text-xs font-semibold transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring ${
                  heatmapMetric === opt.id
                    ? 'bg-primary text-primary-foreground'
                    : 'text-muted-foreground hover:bg-muted/60'
                }`}
              >
                {opt.label}
              </button>
            ))}
          </div>

          <Button
            variant="outline"
            size="sm"
            aria-pressed={showHeatmapTable}
            aria-controls="heatmap-conteudo"
            onClick={() => setShowHeatmapTable((v) => !v)}
            className="flex items-center gap-2"
          >
            {showHeatmapTable ? (
              <><LayoutGrid className="h-4 w-4" aria-hidden="true" /> Ver calendário</>
            ) : (
              <><Table2 className="h-4 w-4" aria-hidden="true" /> Ver tabela</>
            )}
          </Button>
        </div>
      </CardHeader>

      <CardContent className="space-y-5">
        <div className="flex flex-wrap items-center gap-x-6 gap-y-2 rounded-lg border border-border bg-muted/30 px-4 py-3 text-sm">
          <span className="flex items-center gap-2">
            <TrendingDown
              className={`h-4 w-4 ${pontoDeVirada?.diasNoVermelho > 0 ? 'text-red-600 dark:text-red-400' : 'text-emerald-600 dark:text-emerald-400'}`}
              aria-hidden="true"
            />
            <strong className="font-semibold text-foreground">
              {pontoDeVirada?.diasNoVermelho ?? 0}
            </strong>
            <span className="text-muted-foreground">
              {pontoDeVirada?.diasNoVermelho === 1 ? 'dia no vermelho' : 'dias no vermelho'}
            </span>
          </span>
          {pontoDeVirada?.primeiroVermelho && (
            <span className="text-muted-foreground">
              Primeiro em{' '}
              <strong className="font-semibold text-foreground">
                {formatDateLong(pontoDeVirada.primeiroVermelho.date)}
              </strong>
            </span>
          )}
          {pontoDeVirada?.pior && pontoDeVirada.pior.acumulado < 0 && (
            <span className="text-muted-foreground">
              Pior acumulado{' '}
              <strong className="font-semibold text-red-600 dark:text-red-400">
                {formatCurrency(pontoDeVirada.pior.acumulado)}
              </strong>{' '}
              em{' '}
              <strong className="font-semibold text-foreground">
                {formatDateLong(pontoDeVirada.pior.date)}
              </strong>
            </span>
          )}
        </div>

        <div id="heatmap-conteudo">
          {isLoading ? (
            <div className="flex h-64 items-center justify-center">
              <div className="flex flex-col items-center gap-2">
                <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary border-t-transparent" />
                <span className="text-xs text-muted-foreground">Montando a projeção diária...</span>
              </div>
            </div>
          ) : showHeatmapTable ? (
            <div className="max-h-130 overflow-auto">
              <table className="w-full border-collapse text-left text-sm">
                <caption className="pb-3 text-left text-xs text-muted-foreground">
                  Dias com algum lançamento previsto ou simulado. Dias omitidos não têm
                  movimento e mantêm o acumulado do dia anterior. O acumulado parte de
                  zero hoje e não inclui o saldo em caixa.
                </caption>
                <thead className="sticky top-0 bg-card">
                  <tr className="border-b border-border/80 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                    <th scope="col" className="py-2.5 px-3">Data</th>
                    <th scope="col" className="py-2.5 px-3 text-right">Entradas</th>
                    <th scope="col" className="py-2.5 px-3 text-right">Saídas</th>
                    <th scope="col" className="py-2.5 px-3 text-right">Fluxo do dia</th>
                    <th scope="col" className="py-2.5 px-3 text-right">Fluxo acumulado</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border/40">
                  {heatmapTableRows.length === 0 ? (
                    <tr>
                      <td colSpan="5" className="py-10 text-center text-xs text-muted-foreground">
                        Nenhum lançamento previsto na janela de projeção.
                      </td>
                    </tr>
                  ) : (
                    heatmapTableRows.map((d) => (
                      <tr key={d.key} className="transition-colors hover:bg-muted/20">
                        <th scope="row" className="py-2.5 px-3 text-left font-medium text-foreground tabular-nums">
                          {d.date.toLocaleDateString('pt-BR')}
                        </th>
                        <td className="py-2.5 px-3 text-right tabular-nums text-muted-foreground">
                          {formatCurrency(d.receitas)}
                        </td>
                        <td className="py-2.5 px-3 text-right tabular-nums text-muted-foreground">
                          {formatCurrency(d.despesas)}
                        </td>
                        <td className={`py-2.5 px-3 text-right font-medium tabular-nums ${d.fluxo >= 0 ? 'text-emerald-500' : 'text-red-500'}`}>
                          {formatCurrency(d.fluxo)}
                        </td>
                        <td className={`py-2.5 px-3 text-right font-bold tabular-nums ${d.acumulado >= 0 ? 'text-emerald-500' : 'text-red-500'}`}>
                          {formatCurrency(d.acumulado)}
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          ) : firstDate && lastDate ? (
            <CalendarHeatmap
              daysByKey={daysByKey}
              firstDate={firstDate}
              lastDate={lastDate}
              renderTooltip={renderHeatmapTooltip}
            />
          ) : null}
        </div>

        <div>
          <h3 className="mb-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
            Escala — {heatmapMetric === 'acumulado' ? 'fluxo acumulado desde hoje' : 'fluxo do dia'}
          </h3>
          <ul className="flex flex-wrap gap-x-4 gap-y-2">
            {legend.map((item) => (
              <li key={item.level} className="flex items-center gap-1.5 text-xs text-muted-foreground">
                <span
                  className="heat-cell h-3.5 w-3.5 shrink-0 rounded-[3px] ring-1 ring-inset ring-border"
                  data-level={item.level}
                  data-sign={item.level > 0 ? 'pos' : item.level < 0 ? 'neg' : 'zero'}
                  aria-hidden="true"
                />
                {item.label}
              </li>
            ))}
          </ul>
          <p className="mt-2 text-xs text-muted-foreground">
            Os cortes são os tercis da própria projeção, então a escala acompanha a ordem de
            grandeza do seu fluxo. A hachura diagonal marca os dias negativos sem depender
            da cor, e a visão em tabela traz os mesmos números por extenso.
          </p>
        </div>
      </CardContent>
    </Card>
  );
}
