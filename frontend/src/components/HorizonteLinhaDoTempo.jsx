/**
 * Linha do tempo do saldo — do primeiro lançamento até 12 meses à frente.
 *
 * Gráfico de uma série só (o saldo), com o trecho realizado em linha contínua e o
 * projetado tracejado: o traço é o segundo canal, então "o que já aconteceu" e "o que
 * se espera" não dependem de cor. Entre os dois fica o degrau de hoje (vencidas e,
 * por padrão, o valor investido), que não é fluxo — por isso não é ligado por linha,
 * e a tabela o explica numa linha própria.
 *
 * A tabela é a versão em texto do gráfico e rola dentro do próprio quadro, para que
 * quatro anos de histórico não estiquem a página. Ao abrir, ela já mostra a linha de
 * hoje: é o ponto em que o passado encontra a projeção.
 */
import { useEffect, useMemo, useRef } from 'react';
import Chart from 'react-apexcharts';

import { useTheme } from '../context/ThemeProvider';
import { montarLinhaDoTempo } from '../lib/linhaDoTempoSaldo';
import { formatarMoeda, formatarMoedaCompacta } from '../lib/moeda';
import { ValorComSinal, Variacao } from './HorizonteValores';

// Slot 1 da paleta categórica validada, um passo por tema
const COR_SERIE = { light: '#2a78d6', dark: '#3987e5' };

const SITUACAO = {
  realizado: 'Realizado',
  abertura: 'Abertura de hoje',
  projetado: 'Projetado',
};

/**
 * @param {Object} props.data - Resposta do horizonte de saldos.
 * @param {boolean} props.considerarMetas - Cenário com aportes às metas.
 * @param {number} props.mesSelecionado - Índice do mês projetado em detalhe.
 * @param {Function} props.onSelecionarMes - Recebe o índice do mês projetado.
 */
export default function HorizonteLinhaDoTempo({
  data,
  considerarMetas,
  mesSelecionado,
  onSelecionarMes,
}) {
  const { resolvedTheme } = useTheme();
  const escuro = resolvedTheme === 'dark';
  const quadroRef = useRef(null);
  const hojeRef = useRef(null);

  const pontos = useMemo(
    () => montarLinhaDoTempo(data, considerarMetas),
    [data, considerarMetas]
  );
  const mostrarAporte = pontos.some((p) => p.aporte > 0);
  const investidoFora = Number(data.valor_investido) > 0 && !data.investimentos_considerados;

  // Rola só o quadro, nunca a página, para deixar a linha de hoje à vista
  useEffect(() => {
    const quadro = quadroRef.current;
    const hoje = hojeRef.current;
    if (!quadro || !hoje) return;
    quadro.scrollTop = Math.max(0, hoje.offsetTop - quadro.clientHeight / 3);
  }, []);

  const cor = escuro ? COR_SERIE.dark : COR_SERIE.light;
  const tinta = escuro ? '#a3a3a0' : '#5f5e5a';
  const grade = escuro ? '#2c2c2a' : '#e8e7e3';

  const series = [
    {
      name: 'Realizado',
      data: pontos.map((p) => (p.tipo === 'realizado' ? p.saldo : null)),
    },
    {
      name: 'Projetado',
      data: pontos.map((p) => (p.tipo === 'realizado' ? null : p.saldo)),
    },
  ];

  const options = {
    chart: {
      type: 'line',
      toolbar: { show: false },
      zoom: { enabled: false },
      fontFamily: 'inherit',
      background: 'transparent',
      animations: { enabled: false },
    },
    colors: [cor, cor],
    stroke: { width: 2, curve: 'straight', dashArray: [0, 6], lineCap: 'round' },
    markers: { size: 0, hover: { size: 5 }, strokeWidth: 2, strokeColors: escuro ? '#1a1a19' : '#fcfcfb' },
    dataLabels: { enabled: false },
    // A legenda nativa mostraria duas bolinhas iguais; a própria, abaixo, mostra o traço
    legend: { show: false },
    grid: { borderColor: grade, strokeDashArray: 0 },
    xaxis: {
      categories: pontos.map((p) => p.rotulo),
      tickAmount: Math.min(12, pontos.length),
      labels: { rotate: -45, hideOverlappingLabels: true, style: { colors: tinta, fontSize: '11px' } },
      axisBorder: { color: grade },
      axisTicks: { show: false },
      tooltip: { enabled: false },
    },
    yaxis: {
      labels: { formatter: (v) => formatarMoedaCompacta(v), style: { colors: tinta, fontSize: '11px' } },
    },
    annotations: {
      xaxis: [
        {
          x: 'hoje',
          borderColor: tinta,
          strokeDashArray: 0,
          label: {
            text: 'hoje',
            orientation: 'horizontal',
            borderWidth: 0,
            style: { color: tinta, background: 'transparent', fontSize: '11px' },
          },
        },
      ],
    },
    tooltip: {
      theme: escuro ? 'dark' : 'light',
      shared: true,
      intersect: false,
      // Tooltip próprio: o padrão listaria a série vazia de cada trecho com valor nulo
      custom: ({ dataPointIndex }) => {
        const ponto = pontos[dataPointIndex];
        if (!ponto) return '';
        return `<div style="padding:6px 10px;font-size:12px">
          <div style="font-weight:600">${ponto.rotulo}</div>
          <div>${SITUACAO[ponto.tipo]}: ${formatarMoeda(ponto.saldo)}</div>
        </div>`;
      },
    },
  };

  const colunas = mostrarAporte ? 7 : 6;

  return (
    <div className="space-y-4">
      {/* O gráfico repete a tabela abaixo; leitor de tela vai direto a ela */}
      <div aria-hidden="true">
        <div className="flex gap-5 text-xs text-muted-foreground">
          {[['Realizado', undefined], ['Projetado', '6 4']].map(([rotulo, traco]) => (
            <span key={rotulo} className="flex items-center gap-1.5">
              <svg width="24" height="6">
                <line x1="1" y1="3" x2="23" y2="3" stroke={cor} strokeWidth="2" strokeDasharray={traco} strokeLinecap="round" />
              </svg>
              {rotulo}
            </span>
          ))}
        </div>
      </div>
      <div aria-hidden="true" className="-mx-2">
        <Chart key={resolvedTheme} options={options} series={series} type="line" height={280} />
      </div>

      <div
        ref={quadroRef}
        role="region"
        aria-label="Linha do tempo do saldo, mês a mês"
        // `relative` prende os textos sr-only (absolutos) ao corte do quadro
        // Quadro com rolagem própria precisa de foco para rolar pelo teclado (SC 2.1.1)
        // eslint-disable-next-line jsx-a11y/no-noninteractive-tabindex
        tabIndex={0}
        className="relative max-h-[26rem] overflow-auto rounded-xl border border-border/40"
      >
        <table className="w-full min-w-[42rem] text-sm">
          <caption className="sr-only">
            Saldo no fim de cada mês, do primeiro lançamento até 12 meses à frente
            {considerarMetas ? ', descontando os aportes das metas nos meses projetados' : ''}
          </caption>
          <thead className="sticky top-0 z-10 bg-card">
            <tr className="text-xs uppercase tracking-wide text-muted-foreground">
              <th scope="col" className="px-3 py-2 text-left font-semibold">Mês</th>
              <th scope="col" className="px-3 py-2 text-left font-semibold">Situação</th>
              <th scope="col" className="px-3 py-2 text-right font-semibold">Entradas</th>
              <th scope="col" className="px-3 py-2 text-right font-semibold">Saídas</th>
              {mostrarAporte && (
                <th scope="col" className="px-3 py-2 text-right font-semibold">Aporte metas</th>
              )}
              <th scope="col" className="px-3 py-2 text-right font-semibold">Variação</th>
              <th scope="col" className="px-3 py-2 text-right font-semibold">Saldo no fim</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border/40">
            {pontos.map((p) => {
              if (p.tipo === 'abertura') {
                return (
                  <tr key={p.chave} ref={hojeRef} className="bg-primary/5">
                    <th scope="row" className="px-3 py-2 text-left font-bold text-primary">Hoje</th>
                    <td colSpan={colunas - 2} className="px-3 py-2 text-xs text-muted-foreground">
                      Caixa até ontem {formatarMoeda(data.caixa_realizado)}
                      {Number(data.atrasados.receitas) > 0 &&
                        ` + ${formatarMoeda(data.atrasados.receitas)} a receber vencidos`}
                      {Number(data.atrasados.despesas) > 0 &&
                        ` − ${formatarMoeda(data.atrasados.despesas)} em contas vencidas`}
                      {investidoFora && ` − ${formatarMoeda(data.valor_investido)} aplicados na carteira`}
                    </td>
                    <td className="px-3 py-2 text-right font-bold tabular-nums text-foreground">
                      {formatarMoeda(p.saldo)}
                    </td>
                  </tr>
                );
              }

              const selecionado = p.tipo === 'projetado' && p.indiceMes === mesSelecionado;
              const variacao =
                p.tipo === 'projetado' ? p.saldo - p.abertura : p.receitas - p.despesas;
              return (
                <tr key={p.chave} className={selecionado ? 'bg-primary/5' : undefined}>
                  <th scope="row" className="whitespace-nowrap px-3 py-1.5 text-left font-medium">
                    {p.tipo === 'projetado' ? (
                      <button
                        type="button"
                        onClick={() => onSelecionarMes(p.indiceMes)}
                        aria-pressed={selecionado}
                        aria-controls="composicao-detalhe-mes"
                        className={`rounded-md px-1 py-0.5 text-left underline-offset-2 hover:underline ${
                          selecionado ? 'font-bold text-primary underline' : 'text-foreground'
                        }`}
                      >
                        {p.rotulo}
                      </button>
                    ) : (
                      <span className="px-1 text-foreground">{p.rotulo}</span>
                    )}
                  </th>
                  <td className="px-3 py-1.5 text-muted-foreground">{SITUACAO[p.tipo]}</td>
                  <td className="px-3 py-1.5 text-right">
                    <ValorComSinal valor={p.receitas} sinal="+" />
                  </td>
                  <td className="px-3 py-1.5 text-right">
                    <ValorComSinal valor={p.despesas} sinal="−" />
                  </td>
                  {mostrarAporte && (
                    <td className="px-3 py-1.5 text-right">
                      {p.aporte > 0 ? <ValorComSinal valor={p.aporte} sinal="−" /> : '—'}
                    </td>
                  )}
                  <td className="px-3 py-1.5 text-right">
                    <Variacao valor={variacao} />
                  </td>
                  <td className="px-3 py-1.5 text-right font-semibold tabular-nums text-foreground">
                    {formatarMoeda(p.saldo)}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
