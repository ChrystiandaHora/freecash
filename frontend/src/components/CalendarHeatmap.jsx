/**
 * CalendarHeatmap – o ano inteiro numa faixa só, no formato do gráfico de
 * contribuições do GitHub: 7 linhas (dias da semana) por ~53 colunas (semanas),
 * com os meses rotulados em cima.
 *
 * Cada dia é pintado com um degrau da escala divergente azul (positivo) ↔
 * vermelho (negativo) definida em `index.css`. A leitura pretendida é de
 * relance: onde a faixa fica vermelha, o saldo está no negativo.
 *
 * Acessibilidade (A11Y.md / WCAG 2.2 AA):
 *  - é uma `<table>` real: os meses são cabeçalhos de coluna (`colspan`) e os
 *    dias da semana são cabeçalhos de linha;
 *  - cada célula carrega a data e o valor por extenso para leitores de tela —
 *    as cores nunca são o único canal;
 *  - navegação por setas com um único ponto de tabulação (roving tabindex), e o
 *    balão que aparece no hover é o mesmo que aparece no foco;
 *  - o balão só reforça: os mesmos números estão na visão em tabela.
 */
import { useCallback, useMemo, useRef, useState } from 'react';

const WEEKDAYS = [
  { short: '', full: 'Domingo' },
  { short: 'Seg', full: 'Segunda-feira' },
  { short: '', full: 'Terça-feira' },
  { short: 'Qua', full: 'Quarta-feira' },
  { short: '', full: 'Quinta-feira' },
  { short: 'Sex', full: 'Sexta-feira' },
  { short: '', full: 'Sábado' },
];

const signOf = (level) => (level > 0 ? 'pos' : level < 0 ? 'neg' : 'zero');

/** Largura do balão em px (equivale ao `w-60`), usada para prendê-lo ao card. */
const TOOLTIP_WIDTH = 240;
/** Abaixo desta distância do topo, o balão vira para baixo da célula. */
const TOOLTIP_FLIP_THRESHOLD = 130;

const dayKey = (date) =>
  `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(
    date.getDate(),
  ).padStart(2, '0')}`;

/**
 * Fatia o intervalo em colunas de 7 dias alinhadas ao domingo, preenchendo com
 * `null` as casas antes do primeiro dia e depois do último.
 */
function buildWeeks(firstDate, lastDate) {
  const cursor = new Date(firstDate);
  cursor.setDate(cursor.getDate() - cursor.getDay()); // recua até o domingo

  const weeks = [];
  while (cursor <= lastDate) {
    const week = [];
    for (let i = 0; i < 7; i += 1) {
      const inRange = cursor >= firstDate && cursor <= lastDate;
      week.push(inRange ? new Date(cursor) : null);
      cursor.setDate(cursor.getDate() + 1);
    }
    weeks.push(week);
  }
  return weeks;
}

/**
 * Agrupa colunas consecutivas do mesmo mês para virarem cabeçalhos com
 * `colspan`. Grupos de uma coluna só ficam sem rótulo — não cabe texto.
 */
function buildMonthHeaders(weeks) {
  const headers = [];

  weeks.forEach((week) => {
    const firstDay = week.find(Boolean);
    if (!firstDay) {
      headers.push({ label: '', srLabel: '', span: 1, standalone: true });
      return;
    }

    const id = `${firstDay.getFullYear()}-${firstDay.getMonth()}`;
    const last = headers[headers.length - 1];
    if (last && last.id === id) {
      last.span += 1;
      return;
    }

    headers.push({
      id,
      span: 1,
      label: firstDay.toLocaleDateString('pt-BR', { month: 'short' }).replace('.', ''),
      srLabel: firstDay.toLocaleDateString('pt-BR', { month: 'long', year: 'numeric' }),
    });
  });

  return headers;
}

/**
 * @param {Object} props
 * @param {Map<string, Object>} props.daysByKey
 *   Mapa `YYYY-MM-DD` → dado do dia, com `level` (-3..3) e `srLabel`.
 * @param {Date} props.firstDate Primeiro dia da janela.
 * @param {Date} props.lastDate Último dia da janela.
 * @param {(day: Object) => import('react').ReactNode} props.renderTooltip
 */
export default function CalendarHeatmap({ daysByKey, firstDate, lastDate, renderTooltip }) {
  const containerRef = useRef(null);
  const [tooltip, setTooltip] = useState(null);
  const [rovingKey, setRovingKey] = useState(null);

  const weeks = useMemo(() => buildWeeks(firstDate, lastDate), [firstDate, lastDate]);
  const monthHeaders = useMemo(() => buildMonthHeaders(weeks), [weeks]);

  // Um único ponto de tabulação na faixa inteira: o dia percorrido, ou o primeiro.
  const firstKey = dayKey(firstDate);
  const focusableKey = rovingKey && daysByKey.has(rovingKey) ? rovingKey : firstKey;

  const showTooltip = useCallback((cellEl, day) => {
    const container = containerRef.current;
    if (!container || !day) return;

    const cell = cellEl.getBoundingClientRect();
    const box = container.getBoundingClientRect();
    const x = cell.left - box.left + cell.width / 2;
    const y = cell.top - box.top;

    // Mantém o balão dentro do card: preso às bordas na horizontal, virado para
    // baixo quando não há espaço acima da célula.
    const halfWidth = TOOLTIP_WIDTH / 2;
    const below = y < TOOLTIP_FLIP_THRESHOLD;

    setTooltip({
      day,
      below,
      x: Math.min(Math.max(x, halfWidth), Math.max(box.width - halfWidth, halfWidth)),
      y: below ? y + cell.height + 8 : y - 8,
    });
  }, []);

  const hideTooltip = useCallback(() => setTooltip(null), []);

  /**
   * Setas seguem a geometria da faixa: vertical anda um dia (dentro da semana),
   * horizontal anda uma semana. Home/End vão para as pontas do intervalo.
   */
  const handleKeyDown = useCallback(
    (event, date) => {
      const deltas = { ArrowDown: 1, ArrowUp: -1, ArrowRight: 7, ArrowLeft: -7 };

      let target;
      if (event.key in deltas) {
        target = new Date(date);
        target.setDate(target.getDate() + deltas[event.key]);
      } else if (event.key === 'Home') {
        target = firstDate;
      } else if (event.key === 'End') {
        target = lastDate;
      } else {
        return;
      }

      event.preventDefault();
      const key = dayKey(target);
      if (!daysByKey.has(key)) return; // não sai da janela de projeção

      setRovingKey(key);
      containerRef.current?.querySelector(`[data-cell-id="${key}"]`)?.focus();
    },
    [daysByKey, firstDate, lastDate],
  );

  return (
    <div ref={containerRef} className="relative">
      <div className="overflow-x-auto pb-1">
        <table className="border-separate border-spacing-0.75">
          <caption className="sr-only">
            Mapa de calor diário: uma coluna por semana, uma linha por dia da semana.
          </caption>
          <thead>
            <tr>
              <td className="w-8" />
              {monthHeaders.map((month, i) => (
                <th
                  key={month.id || `vazio-${i}`}
                  scope="colgroup"
                  colSpan={month.span}
                  className="pb-1 text-left align-bottom text-[10px] font-medium capitalize text-muted-foreground"
                >
                  {month.span > 1 && (
                    <>
                      <span aria-hidden="true">{month.label}</span>
                      <span className="sr-only">{month.srLabel}</span>
                    </>
                  )}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {WEEKDAYS.map((weekday, row) => (
              <tr key={row}>
                <th
                  scope="row"
                  className="pr-1 text-right align-middle text-[10px] font-medium text-muted-foreground"
                >
                  <span aria-hidden="true">{weekday.short}</span>
                  <span className="sr-only">{weekday.full}</span>
                </th>

                {weeks.map((week, col) => {
                  const date = week[row];
                  if (!date) {
                    return <td key={col} className="h-3.5 w-3.5" />;
                  }

                  const key = dayKey(date);
                  const day = daysByKey.get(key);
                  const level = day?.level ?? 0;

                  return (
                    <td key={col} className="p-0">
                      <div
                        data-cell-id={key}
                        data-level={day ? level : undefined}
                        data-sign={day ? signOf(level) : undefined}
                        data-empty={day ? undefined : 'true'}
                        tabIndex={key === focusableKey ? 0 : -1}
                        onKeyDown={(e) => handleKeyDown(e, date)}
                        onFocus={(e) => showTooltip(e.currentTarget, day)}
                        onBlur={hideTooltip}
                        onMouseEnter={(e) => showTooltip(e.currentTarget, day)}
                        onMouseLeave={hideTooltip}
                        className="heat-cell h-3.5 w-3.5 cursor-default rounded-[2px] transition-transform duration-100 hover:scale-150 focus-visible:scale-150 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring"
                      >
                        <span className="sr-only">
                          {day?.srLabel ?? 'Dia fora da janela de projeção'}
                        </span>
                      </div>
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {tooltip && (
        <div
          role="presentation"
          className={`pointer-events-none absolute z-30 w-60 -translate-x-1/2 rounded-lg border border-border bg-popover p-3 text-popover-foreground shadow-xl ${
            tooltip.below ? '' : '-translate-y-full'
          }`}
          style={{ left: tooltip.x, top: tooltip.y }}
        >
          {renderTooltip(tooltip.day)}
        </div>
      )}
    </div>
  );
}
