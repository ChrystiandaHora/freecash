/**
 * Gráfico comparativo da cotação dos ativos ao longo do tempo (Meus Ativos).
 *
 * Plota uma linha por ativo **selecionado**, em duas leituras alternáveis:
 *
 * - **Retorno (%)** — padrão. A cotação medida contra o **preço médio** do ativo, que
 *   é exatamente a conta da coluna «Retorno» da tabela: o último ponto de cada linha
 *   bate com o número que a tabela mostra. O zero é o preço médio, então cruzar a
 *   linha do zero é sair do prejuízo. É o padrão porque a pergunta que a tela responde
 *   é "como está a minha posição", e porque as cotações convivem em ordens de grandeza
 *   diferentes: um FII a R$ 9 e uma ação a R$ 300 na mesma escala em reais deixam a
 *   linha do FII colada no eixo, sem informação nenhuma.
 * - **Preço (R$)** — a cotação nominal, para quem quer o número e não a comparação.
 *
 * **A seleção é do gráfico, não da tabela.** Ele abre com os dois maiores e os dois
 * menores retornos, e a partir daí o usuário acrescenta e remove ativos por aqui. Não
 * segue a busca nem o filtro de classe da tabela: vinte linhas não se leem, e a paleta
 * categórica validada tem oito tons — acima disso não existe par (cor, traço) distinto
 * a oferecer. O universo é a aba (Ativos/Arquivados) e a carteira em foco, e a troca de
 * qualquer uma das duas remonta o componente e refaz a seleção (ver `key` em MeusAtivos).
 *
 * A semente é **valor derivado**, e a edição do usuário um override guardado em
 * `edicao`. É o que impede os dois defeitos clássicos de semear por efeito colateral:
 * sobrescrever a escolha do usuário, e congelar uma semente calculada com os dados da
 * carteira anterior enquanto as queries ainda estão em voo.
 *
 * **Limite conhecido do Retorno:** o preço médio aplicado é o de hoje, inclusive nos
 * pregões passados. Uma compra feita no meio do período mudou o preço médio de
 * verdade, e a linha não reflete isso — reconstruí-lo dia a dia exigiria reprocessar
 * o razão de transações. O último ponto, que é o que a tabela mostra, está sempre
 * correto; os anteriores respondem "quanto este preço valeria contra o que pago hoje".
 * A legenda cita o retorno atual de cada ativo, para amarrar o gráfico à tabela.
 *
 * As séries são alinhadas numa grade de datas única antes de plotar — o tooltip
 * compartilhado do ApexCharts casa as séries por índice do ponto, e sem isso o
 * ponteiro mostrava a data de uma série com o valor de outra. No mesmo passo, pregão
 * sem cotação repete o último fechamento conhecido (ver `alinharEmEixoComum`); a
 * regra é dita ao usuário no rodapé do gráfico, e a tabela mostra os mesmos valores
 * para continuar equivalente ao desenho.
 *
 * Acessibilidade: o container do ApexCharts é `aria-hidden`, e os dados completos vão
 * numa tabela adjacente — mesma decisão já registrada em `A11Y-DECISIONS.md` para os
 * gráficos do dashboard de investimentos (os nós SVG do Apex poluem o leitor de tela
 * com fragmentos de texto sem contexto).
 *
 * @param {object} props
 * @param {Array<{id: number, ticker: string, nome: string, pontos: Array<{data: string, valor: number}>}>} props.series
 *   Todas as séries do universo (aba + carteira), não só as plotadas.
 * @param {Map<number, {preco_medio: string, rentabilidade_percentual: string}>} props.ativosPorId
 *   Preço médio e retorno como a tabela os exibe — já com a sobrescrita por carteira
 *   quando há filtro, e por isso vindos da listagem em vez de recalculados aqui.
 * @param {'retorno'|'preco'} props.escala
 * @param {(escala: 'retorno'|'preco') => void} props.onEscalaChange
 * @param {number} props.dias Janela em dias atualmente selecionada.
 * @param {(dias: number) => void} props.onDiasChange
 * @param {boolean} [props.isLoading]
 * @param {boolean} [props.isError]
 * @returns {React.JSX.Element}
 */
import { useMemo, useRef, useState } from 'react';
import Chart from 'react-apexcharts';
import { AlertCircle, LineChart, RefreshCw, RotateCcw, X } from 'lucide-react';

import { useTheme } from '../context/ThemeProvider';
import { alinharEmEixoComum, converterSeries } from '../lib/cotacoesSerie';
import {
  MAX_SERIES,
  adicionarAtivo,
  escolherExtremos,
  ordenarPorSlot,
  removerAtivo,
  resolverBusca,
  sanearSelecao,
} from '../lib/selecaoGrafico';
import { Button } from './ui/Button';
import { Input } from './ui/Input';

/**
 * Paleta categórica fixa, validada para daltonismo e contraste nas duas superfícies
 * (ver `A11Y-DECISIONS.md`: cor escolhida pelo usuário não entra em gráfico).
 * A ordem dos tons é o mecanismo de segurança — não reordenar.
 */
const PALETA = {
  light: ['#2a78d6', '#eb6834', '#1baf7a', '#eda100', '#e87ba4', '#008300', '#4a3aa7', '#e34948'],
  dark: ['#3987e5', '#d95926', '#199e70', '#c98500', '#d55181', '#008300', '#9085e9', '#e66767'],
};

/**
 * Segundo canal visual além da cor, exigido pela SC 1.4.1. O `dashArray` do ApexCharts
 * é um número só (o tamanho do traço), então só há ~4 padrões realmente distinguíveis.
 * Eles giram fora de fase com os 8 tons, e o teto de `MAX_SERIES` na seleção é o que
 * garante o resto: 8 e 4 não são coprimos, então uma nona linha repetiria cor **e**
 * traço da primeira — acima da paleta não há par distinto a oferecer.
 */
const TRACEJADOS = [0, 3, 7, 12];

const JANELAS = [
  { dias: 30, rotulo: '1 mês' },
  { dias: 60, rotulo: '2 meses' },
];

const ESCALAS = [
  { id: 'retorno', rotulo: 'Retorno (%)' },
  { id: 'preco', rotulo: 'Preço (R$)' },
];

const LEGENDAS = {
  retorno:
    'Cada linha é a cotação medida contra o preço médio — o zero é o seu custo, e o fim da linha é o Retorno da tabela.',
  preco: 'Cotação de fechamento em reais.',
};

const RECUSAS = {
  vazio: 'Digite o ticker ou o nome do ativo.',
  'nao-encontrado': (texto) =>
    `Não encontramos «${texto}» entre os ativos com cotação no período. Se houver mais de um parecido, digite o ticker inteiro.`,
  'ja-selecionado': 'Este ativo já está no gráfico.',
  cheio: `O gráfico comporta ${MAX_SERIES} ativos. Remova um para adicionar outro.`,
};

const formatCurrency = (value) => {
  if (value === undefined || value === null) return 'R$ 0,00';
  return new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(value);
};

const formatPercentage = (value) => {
  const num = parseFloat(value ?? 0);
  return `${num >= 0 ? '+' : ''}${num.toFixed(2).replace('.', ',')}%`;
};

const formatDate = (isoDate) =>
  new Intl.DateTimeFormat('pt-BR').format(new Date(`${isoDate}T00:00:00`));

/** Converte 'YYYY-MM-DD' em timestamp local, para o eixo `datetime` do ApexCharts. */
const paraTimestamp = (isoDate) => new Date(`${isoDate}T00:00:00`).getTime();

const listarTickers = (series) => series.map((s) => s.ticker).join(', ');

export default function GraficoCotacoesAtivos({
  series = [],
  ativosPorId = new Map(),
  escala,
  onEscalaChange,
  dias,
  onDiasChange,
  isLoading = false,
  isError = false,
}) {
  const { resolvedTheme } = useTheme();
  const [tabelaAberta, setTabelaAberta] = useState(false);
  const [busca, setBusca] = useState('');
  const [recusa, setRecusa] = useState('');
  const listaChipsRef = useRef(null);

  const emReais = escala === 'preco';

  // A semente é derivada, e `edicao` é o override do usuário — `null` significa
  // "ainda não mexeu", e `[]` significa "esvaziou de propósito". Sem essa distinção,
  // remover o último chip re-semearia na hora.
  const semente = useMemo(() => escolherExtremos(series, ativosPorId), [series, ativosPorId]);
  const [edicao, setEdicao] = useState(null);

  // Sanear no render, e não por efeito: excluir ou transferir um ativo encolhe o
  // universo sem trocar carteira nem aba, então a remontagem não acontece e a seleção
  // fica guardando um id que não existe mais.
  const selecionados = useMemo(
    () => sanearSelecao(edicao ?? semente, new Set(series.map((s) => s.id))),
    [edicao, semente, series]
  );

  const slotPorAtivo = useMemo(
    () => new Map(selecionados.map(({ id, slot }) => [id, slot])),
    [selecionados]
  );
  const cores = PALETA[resolvedTheme === 'dark' ? 'dark' : 'light'];
  const corDe = (ativoId) => cores[(slotPorAtivo.get(ativoId) ?? 0) % cores.length];
  const tracejadoDe = (ativoId) =>
    TRACEJADOS[(slotPorAtivo.get(ativoId) ?? 0) % TRACEJADOS.length];

  // Ordenar por slot aqui, e não na hora de desenhar: é o que faz a ordem dos chips,
  // da legenda e das colunas da tabela de dados serem a mesma.
  const seriesSelecionadas = useMemo(
    () => ordenarPorSlot(series, selecionados),
    [series, selecionados]
  );

  const seriesPlotadas = useMemo(
    () => converterSeries(seriesSelecionadas, escala, ativosPorId),
    [seriesSelecionadas, escala, ativosPorId]
  );

  const idsPlotados = new Set(seriesPlotadas.map((s) => s.id));
  const semLinha = seriesSelecionadas.filter((s) => !idsPlotados.has(s.id));

  // Grade de datas única, compartilhada pelo gráfico e pela tabela alternativa. É o
  // que faz o tooltip apontar para a data certa — sem ela o ApexCharts casa as séries
  // por índice do ponto, e comprimentos diferentes desalinham o ponteiro.
  const { datas, series: seriesAlinhadas } = useMemo(
    () => alinharEmEixoComum(seriesPlotadas),
    [seriesPlotadas]
  );

  const seriesApex = useMemo(
    () =>
      seriesAlinhadas.map((s) => ({
        name: s.ticker,
        data: s.valores.map((valor, i) => [paraTimestamp(datas[i]), valor]),
      })),
    [seriesAlinhadas, datas]
  );

  const idsSelecionados = new Set(selecionados.map((s) => s.id));
  const disponiveis = series.filter((s) => !idsSelecionados.has(s.id));

  /** Materializa a semente no primeiro toque, para a edição partir do que está na tela. */
  const editar = (transformar) => setEdicao((atual) => transformar(atual ?? semente));

  const handleAdicionar = (event) => {
    event.preventDefault();
    const alvo = resolverBusca(busca, series, idsSelecionados);

    if (alvo.erro) {
      setRecusa(
        typeof RECUSAS[alvo.erro] === 'function' ? RECUSAS[alvo.erro](busca.trim()) : RECUSAS[alvo.erro]
      );
      return;
    }

    let recusado = '';
    editar((atual) => {
      const { selecionados: proximos, resultado } = adicionarAtivo(atual, alvo.id);
      if (resultado !== 'adicionado') recusado = RECUSAS[resultado] ?? '';
      return proximos;
    });

    setRecusa(recusado);
    if (!recusado) setBusca('');
  };

  /**
   * Remove o chip e devolve o foco a um vizinho.
   *
   * Sem isto o nó focado sai do DOM e o foco cai no `<body>`, jogando quem navega por
   * teclado de volta ao topo da página a cada remoção.
   */
  const handleRemover = (id, indice) => {
    editar((atual) => removerAtivo(atual, id));
    setRecusa('');

    queueMicrotask(() => {
      const botoes = listaChipsRef.current?.querySelectorAll('button');
      if (!botoes?.length) {
        document.getElementById('grafico-busca-ativo')?.focus();
        return;
      }
      (botoes[indice] ?? botoes[botoes.length - 1]).focus();
    });
  };

  const handleRestaurar = () => {
    setEdicao(null);
    setRecusa('');
    setBusca('');
  };

  const reduzirMovimento =
    typeof window !== 'undefined' &&
    window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;

  const opcoes = {
    chart: {
      type: 'line',
      height: 320,
      toolbar: { show: false },
      zoom: { enabled: false },
      fontFamily: 'inherit',
      background: 'transparent',
      animations: { enabled: !reduzirMovimento },
    },
    theme: { mode: resolvedTheme },
    colors: seriesAlinhadas.map((s) => corDe(s.id)),
    stroke: {
      curve: 'straight',
      width: 2,
      dashArray: seriesAlinhadas.map((s) => tracejadoDe(s.id)),
    },
    dataLabels: { enabled: false },
    markers: { size: 0, hover: { size: 6 } },
    legend: {
      show: true,
      position: 'bottom',
      horizontalAlign: 'left',
      fontSize: '12px',
      fontWeight: 600,
      markers: { width: 10, height: 10, radius: 3 },
      itemMargin: { horizontal: 10, vertical: 4 },
      // Rótulo direto com o número da tabela: é o que amarra as duas leituras, e
      // vale nas duas escalas — o retorno do ativo não muda porque o eixo mudou.
      formatter: (nome, opts) => {
        const serie = seriesAlinhadas[opts.seriesIndex];
        return serie ? `${nome} ${formatPercentage(serie.retornoAtual)}` : nome;
      },
    },
    xaxis: {
      type: 'datetime',
      labels: {
        datetimeUTC: false,
        format: 'dd/MM',
        style: { colors: '#888888', fontSize: '12px', fontWeight: 500 },
      },
      axisBorder: { show: false },
      axisTicks: { show: false },
      // A tarja de data sob o eixo duplica o cabeçalho do tooltip; a crosshair é o
      // que faltava para o ponteiro dizer a que pregão o tooltip se refere.
      tooltip: { enabled: false },
      crosshairs: {
        show: true,
        stroke: { color: 'rgba(148, 163, 184, 0.5)', width: 1, dashArray: 3 },
      },
    },
    yaxis: {
      labels: {
        formatter: (val) => (emReais ? formatCurrency(val) : formatPercentage(val)),
        style: { colors: '#888888', fontSize: '12px', fontWeight: 500 },
      },
    },
    grid: {
      borderColor: 'rgba(148, 163, 184, 0.12)',
      strokeDashArray: 4,
      padding: { left: 10, right: 20 },
    },
    tooltip: {
      theme: resolvedTheme,
      // Compartilhado só é correto porque as séries foram alinhadas na mesma grade
      // de datas: o ApexCharts casa os pontos por índice, não pelo valor de x.
      shared: true,
      intersect: false,
      followCursor: false,
      x: { format: 'dd/MM/yyyy' },
      y: {
        formatter: (val) =>
          val === null || val === undefined
            ? '—'
            : emReais
              ? formatCurrency(val)
              : formatPercentage(val),
      },
    },
    // No Retorno o zero é o preço médio: a linha que separa lucro de prejuízo, e a
    // referência de leitura do gráfico inteiro. Por isso vai desenhada e rotulada.
    annotations: emReais
      ? {}
      : {
          yaxis: [
            {
              y: 0,
              borderColor: 'rgba(148, 163, 184, 0.5)',
              strokeDashArray: 0,
              label: {
                text: 'Preço médio',
                position: 'left',
                textAnchor: 'start',
                style: {
                  fontSize: '11px',
                  fontWeight: 600,
                  background: 'transparent',
                  color: '#888888',
                },
              },
            },
          ],
        },
  };

  const janelaRotulo = JANELAS.find((j) => j.dias === dias)?.rotulo ?? `${dias} dias`;
  const escalaRotulo = ESCALAS.find((e) => e.id === escala)?.rotulo ?? '';

  /**
   * Texto da região viva: o RESULTADO da leitura atual, não o evento que a produziu.
   * Com o teto de oito séries dá para nomear os tickers, que é o resultado de verdade
   * (exigência do `guide-charts.md`). Adicionar, remover, restaurar e trocar de escala
   * mudam este texto e são anunciados por aqui, sem nenhum "PETR4 adicionado".
   */
  const resumoAcessivel = () => {
    if (isLoading) return 'Carregando cotações.';
    if (selecionados.length === 0) {
      return 'Nenhum ativo no gráfico. Busque um ativo ou use «Restaurar extremos».';
    }

    const plotadas = `${janelaRotulo}, ${escalaRotulo}: ${seriesAlinhadas.length} ${
      seriesAlinhadas.length === 1 ? 'ativo' : 'ativos'
    } no gráfico — ${listarTickers(seriesAlinhadas)} — em ${datas.length} ${
      datas.length === 1 ? 'pregão' : 'pregões'
    }.`;

    if (semLinha.length === 0) return plotadas;
    return `${plotadas} ${listarTickers(semLinha)} sem preço médio: sem linha nesta escala.`;
  };

  const totalUniverso = series.length;

  return (
    <section
      aria-labelledby="grafico-cotacoes-titulo"
      className="bg-card border border-border/40 shadow-sm text-card-foreground rounded-xl p-6 space-y-5"
    >
      <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4">
        <div>
          <h2
            id="grafico-cotacoes-titulo"
            className="text-sm font-bold text-foreground flex items-center gap-2 uppercase tracking-wider"
          >
            <LineChart className="h-4 w-4 text-primary" aria-hidden="true" />
            Como cada ativo se moveu no período
          </h2>
          <p className="text-xs text-muted-foreground mt-1">
            {LEGENDAS[escala]} Abre com os 2 maiores e os 2 menores retornos entre os{' '}
            {totalUniverso} ativos com cotação, e não segue os filtros da tabela.
          </p>
        </div>

        <div className="flex flex-col sm:flex-row gap-3 shrink-0">
          {/* Filtro do mesmo conjunto, não troca de região: radiogroup, e não tablist
              (critério registrado em A11Y-DECISIONS.md) */}
          <div
            role="radiogroup"
            aria-label="Escala do gráfico"
            className="inline-flex rounded-xl border border-border/40 p-0.5 bg-muted/30 self-start"
          >
            {ESCALAS.map((opcao) => (
              <button
                key={opcao.id}
                type="button"
                role="radio"
                aria-checked={escala === opcao.id}
                onClick={() => onEscalaChange(opcao.id)}
                className={`px-3 py-1.5 text-xs rounded-lg transition-all ${
                  escala === opcao.id
                    ? 'bg-card text-foreground font-extrabold shadow-sm'
                    : 'text-muted-foreground hover:text-foreground font-semibold'
                }`}
              >
                {opcao.rotulo}
              </button>
            ))}
          </div>

          <div
            role="radiogroup"
            aria-label="Período do gráfico"
            className="inline-flex rounded-xl border border-border/40 p-0.5 bg-muted/30 self-start"
          >
            {JANELAS.map((janela) => (
              <button
                key={janela.dias}
                type="button"
                role="radio"
                aria-checked={dias === janela.dias}
                onClick={() => onDiasChange(janela.dias)}
                className={`px-3 py-1.5 text-xs rounded-lg transition-all ${
                  dias === janela.dias
                    ? 'bg-card text-foreground font-extrabold shadow-sm'
                    : 'text-muted-foreground hover:text-foreground font-semibold'
                }`}
              >
                {janela.rotulo}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Seleção: chips do que está no gráfico + busca aditiva */}
      <div className="rounded-xl border border-border/40 bg-muted/10 p-4 space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <ul
            ref={listaChipsRef}
            aria-label="Ativos no gráfico"
            className="flex flex-wrap items-center gap-2"
          >
            {selecionados.length === 0 && (
              <li className="text-xs text-muted-foreground">Nenhum ativo no gráfico.</li>
            )}
            {seriesSelecionadas.map((serie, indice) => (
              <li
                key={serie.id}
                className="inline-flex items-center gap-1.5 rounded-full border border-border/60 bg-card px-2.5 py-1 text-xs text-foreground"
              >
                {/* Amarra o chip à linha pelos DOIS canais, cor e traço — a cor nunca
                    é o único portador, o ticker está escrito ao lado */}
                <svg width="14" height="8" viewBox="0 0 14 8" aria-hidden="true" className="shrink-0">
                  <line
                    x1="0"
                    y1="4"
                    x2="14"
                    y2="4"
                    stroke={corDe(serie.id)}
                    strokeWidth="2"
                    strokeDasharray={tracejadoDe(serie.id) || undefined}
                  />
                </svg>
                <span className="font-semibold">{serie.ticker}</span>
                <button
                  type="button"
                  onClick={() => handleRemover(serie.id, indice)}
                  className="rounded-full p-1 text-muted-foreground hover:bg-muted hover:text-foreground transition-colors"
                >
                  {/* Nome por conteúdo, nunca aria-label (A11Y-DECISIONS.md) */}
                  <span className="sr-only">Remover {serie.ticker} do gráfico</span>
                  <X className="h-3 w-3" aria-hidden="true" />
                </button>
              </li>
            ))}
          </ul>

          <Button
            type="button"
            variant="ghost"
            onClick={handleRestaurar}
            className="h-8 px-3 gap-1.5 text-xs font-semibold rounded-lg shrink-0"
          >
            <RotateCcw className="h-3.5 w-3.5" aria-hidden="true" />
            Restaurar extremos
          </Button>
        </div>

        <form onSubmit={handleAdicionar} className="flex flex-wrap items-end gap-2">
          <div className="flex-1 min-w-56">
            <label
              htmlFor="grafico-busca-ativo"
              className="block text-xs font-semibold text-foreground mb-1"
            >
              Adicionar ativo ao gráfico
            </label>
            <Input
              id="grafico-busca-ativo"
              list="grafico-ativos-disponiveis"
              value={busca}
              onChange={(e) => {
                setBusca(e.target.value);
                setRecusa('');
              }}
              // O histórico do navegador competiria com o datalist na mesma caixa
              autoComplete="off"
              placeholder="Ticker ou nome"
              aria-describedby="grafico-busca-dica"
              className="h-9 text-xs rounded-lg"
            />
            {/* Dica persistente, não só no erro: o datalist não expõe contagem de
                sugestões nem posição, então as instruções têm de ser texto visível */}
            <p id="grafico-busca-dica" className="text-xs text-muted-foreground mt-1">
              Digite o ticker e pressione Enter. Até {MAX_SERIES} ativos no gráfico.
            </p>
          </div>

          <datalist id="grafico-ativos-disponiveis">
            {disponiveis.map((serie) => (
              <option key={serie.id} value={serie.ticker}>
                {serie.nome || serie.ticker}
                {parseFloat(ativosPorId.get(serie.id)?.preco_medio ?? 0) > 0
                  ? ''
                  : ' — sem preço médio'}
              </option>
            ))}
          </datalist>

          {/* Habilitado mesmo no teto: `disabled` sai da ordem de tabulação e tornaria
              a regra invisível para teclado e leitor de tela (A11Y-DECISIONS.md) */}
          <Button type="submit" variant="outline" className="h-9 px-4 text-xs rounded-lg mb-6">
            Adicionar
          </Button>
        </form>

        {/* Recusa é resposta a uma ação deliberada, não interrupção: status, não alert */}
        <p role="status" className="text-xs font-semibold text-amber-600 dark:text-amber-400">
          {recusa}
        </p>
      </div>

      {/* Anuncia o resultado da leitura atual, não o evento (guide-charts.md) */}
      <p className="sr-only" aria-live="polite">
        {resumoAcessivel()}
      </p>

      {isLoading ? (
        <div role="status" className="flex items-center justify-center gap-3 py-20">
          <RefreshCw className="h-5 w-5 text-primary animate-spin" aria-hidden="true" />
          <span className="text-xs font-semibold text-muted-foreground">
            Carregando histórico de cotações...
          </span>
        </div>
      ) : isError ? (
        <div role="alert" className="flex items-center justify-center gap-2 py-20 text-xs text-muted-foreground">
          <AlertCircle className="h-4 w-4 text-destructive" aria-hidden="true" />
          Não foi possível carregar o histórico de cotações.
        </div>
      ) : seriesAlinhadas.length === 0 ? (
        <p className="py-20 text-center text-xs text-muted-foreground">
          {totalUniverso === 0
            ? `Nenhum ativo aqui tem cotação registrada nos últimos ${dias} dias. Use «Atualizar Cotações» para buscar o histórico.`
            : selecionados.length === 0
              ? 'Nenhum ativo no gráfico. Busque um ativo acima ou use «Restaurar extremos».'
              : 'Nenhum dos ativos escolhidos tem preço médio, então não há retorno a medir. Veja em «Preço (R$)».'}
        </p>
      ) : (
        <>
          <div aria-hidden="true">
            <Chart options={opcoes} series={seriesApex} type="line" height={320} />
          </div>

          <p className="text-xs text-muted-foreground">
            Pregão sem cotação repete o último fechamento conhecido.
            {semLinha.length > 0 &&
              ` ${listarTickers(semLinha)} ${semLinha.length === 1 ? 'não tem' : 'não têm'} preço médio: sem linha no Retorno.`}
          </p>

          <details
            className="rounded-xl border border-border/40 bg-muted/10"
            onToggle={(e) => setTabelaAberta(e.currentTarget.open)}
          >
            <summary className="cursor-pointer px-4 py-3 text-xs font-bold text-foreground uppercase tracking-wider">
              Ver os dados do gráfico em tabela
            </summary>
            {/* Só monta as células quando aberta */}
            {tabelaAberta && (
              <div className="overflow-x-auto max-h-96 overflow-y-auto border-t border-border/40">
                <table className="w-full text-xs text-left border-collapse">
                  <caption className="sr-only">
                    {emReais ? 'Cotação de fechamento' : 'Retorno sobre o preço médio'} dos ativos
                    escolhidos, por pregão, {janelaRotulo.toLowerCase()}. Pregão sem cotação repete
                    o último fechamento conhecido.
                  </caption>
                  <thead className="sticky top-0 bg-card">
                    <tr className="border-b border-border/40 text-muted-foreground font-semibold">
                      <th scope="col" className="py-2.5 px-4">Pregão</th>
                      {seriesAlinhadas.map((s) => (
                        <th key={s.id} scope="col" className="py-2.5 px-4 text-right whitespace-nowrap">
                          {s.ticker}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border/20">
                    {/* Mesma grade do gráfico: a alternativa textual tem de ser
                        equivalente ao desenho, e não uma segunda leitura dos dados */}
                    {datas.map((data, i) => (
                      <tr key={data}>
                        <th scope="row" className="py-2 px-4 font-semibold text-muted-foreground whitespace-nowrap">
                          {formatDate(data)}
                        </th>
                        {seriesAlinhadas.map((s) => (
                          <td key={s.id} className="py-2 px-4 text-right text-foreground/80 whitespace-nowrap">
                            {s.valores[i] === null
                              ? '—'
                              : emReais
                                ? formatCurrency(s.valores[i])
                                : formatPercentage(s.valores[i])}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </details>
        </>
      )}
    </section>
  );
}
