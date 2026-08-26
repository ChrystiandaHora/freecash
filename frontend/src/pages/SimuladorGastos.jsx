/**
 * Componente de Simulador de Gastos e Receitas.
 *
 * Permite ao usuário simular cenários financeiros em memória (client-side),
 * cruzando lançamentos temporários com despesas/receitas reais do banco de dados
 * para os próximos 12 meses.
 */
import { useState, useEffect, useMemo, useCallback } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Sparkles, RefreshCw } from 'lucide-react';
import { useToast } from '../context/ToastContext';
import { fetchContas, fetchSaldoAtual } from '../services/financeiro';

// UI components
import { Button } from '../components/ui/Button';
import { Badge } from '../components/ui/Badge';

import PontoDeViradaCard from './simulador/PontoDeViradaCard';
import SaldoKpiCards from './simulador/SaldoKpiCards';
import LancamentoForm from './simulador/LancamentoForm';
import SimulacoesAtivasList from './simulador/SimulacoesAtivasList';
import FluxoProjetadoChart from './simulador/FluxoProjetadoChart';
import AnaliseDetalhada from './simulador/AnaliseDetalhada';

// Meio centavo: abaixo disso o dia conta como zerado, não como negativo.
const EPS = 0.005;

export default function SimuladorGastos() {
  const { addToast } = useToast();

  // Tema atual para o ApexCharts
  const [isDark, setIsDark] = useState(() => document.documentElement.classList.contains('dark'));

  useEffect(() => {
    const observer = new MutationObserver(() => {
      setIsDark(document.documentElement.classList.contains('dark'));
    });
    observer.observe(document.documentElement, { attributes: true, attributeFilter: ['class'] });
    return () => observer.disconnect();
  }, []);

  // Hoje à meia-noite: fronteira entre o que já aconteceu e o que ainda dá para
  // influenciar. A janela de projeção começa no dia 1º do mês corrente (o mês é a
  // unidade da tabela mensal), então os primeiros dias da série diária estão no
  // passado — e nenhum conselho pode apontar para eles.
  const hoje = useMemo(() => {
    const d = new Date();
    return new Date(d.getFullYear(), d.getMonth(), d.getDate());
  }, []);

  // 12 meses de projeção a partir de hoje
  const projectionMonths = useMemo(() => {
    const months = [];
    const today = new Date();
    const currentYear = today.getFullYear();
    const currentMonthIndex = today.getMonth();

    for (let i = 0; i < 12; i++) {
      const d = new Date(currentYear, currentMonthIndex + i, 1);
      const y = d.getFullYear();
      const m = String(d.getMonth() + 1).padStart(2, '0');
      const label = d.toLocaleDateString('pt-BR', { month: 'long', year: 'numeric' });
      months.push({
        key: `${y}-${m}`, // "2026-06"
        label: label.charAt(0).toUpperCase() + label.slice(1),
        year: y,
        monthIndex: d.getMonth(),
      });
    }
    return months;
  }, []);

  // Range de data para buscar no backend
  const dateRange = useMemo(() => {
    if (projectionMonths.length === 0) return { inicio: '', fim: '' };
    const inicio = `${projectionMonths[0].key}-01`;
    const lastMonth = projectionMonths[projectionMonths.length - 1];
    const lastDay = new Date(lastMonth.year, lastMonth.monthIndex + 1, 0).getDate();
    const fim = `${lastMonth.key}-${String(lastDay).padStart(2, '0')}`;
    return { inicio, fim };
  }, [projectionMonths]);

  // Carregar dados reais do backend
  const { data: realContas = [], isLoading, isFetching, refetch } = useQuery({
    queryKey: ['contas-simulacao', dateRange.inicio, dateRange.fim],
    queryFn: () => fetchContas({ data_inicio: dateRange.inicio, data_fim: dateRange.fim }),
    enabled: !!dateRange.inicio && !!dateRange.fim,
  });

  // Véspera da janela. A âncora precisa ser o caixa do dia ANTERIOR ao primeiro dia
  // projetado: ancorar em hoje contaria duas vezes tudo que já foi realizado entre
  // o dia 1º e hoje — uma vez no saldo, outra na curva.
  const dataAncora = useMemo(() => {
    if (!dateRange.inicio) return '';
    const [y, m, d] = dateRange.inicio.split('-').map(Number);
    const vespera = new Date(y, m - 1, d - 1);
    return `${vespera.getFullYear()}-${String(vespera.getMonth() + 1).padStart(2, '0')}-${String(vespera.getDate()).padStart(2, '0')}`;
  }, [dateRange.inicio]);

  // Saldo em caixa na véspera: a projeção parte dele, não de zero. Sem essa âncora
  // o "saldo" da curva seria só o fluxo líquido acumulado, e o dia em que ela cruza
  // o zero sairia sistematicamente adiantado.
  const {
    data: saldoAtual,
    isLoading: isLoadingSaldo,
    isError: isErrorSaldo,
  } = useQuery({
    queryKey: ['saldo-atual', dataAncora],
    queryFn: () => fetchSaldoAtual({ ate: dataAncora }),
    enabled: !!dataAncora,
  });

  const saldoAncorado = !isLoadingSaldo && !isErrorSaldo && saldoAtual != null;
  const saldoInicial = saldoAncorado ? parseFloat(saldoAtual.saldo) || 0 : 0;

  // Lançamento com competência dentro da janela mas cujo caixa já se moveu antes
  // dela abrir — a conta paga adiantado. Não é fluxo por vir, sob nenhuma métrica.
  const jaMovimentouAntesDaJanela = useCallback(
    (c) =>
      Boolean(
        c.transacao_realizada &&
          c.data_realizacao &&
          dataAncora &&
          String(c.data_realizacao).slice(0, 10) <= dataAncora,
      ),
    [dataAncora],
  );

  // O mesmo lançamento, visto pela tabela mensal: lá a curva parte do saldo em
  // caixa, que já o embute — somá-lo de novo o contaria duas vezes. Só vale
  // quando existe âncora; sem ela não há saldo embutindo nada.
  const jaNoSaldoInicial = useCallback(
    (c) => saldoAncorado && jaMovimentouAntesDaJanela(c),
    [saldoAncorado, jaMovimentouAntesDaJanela],
  );

  // Carregar contas simuladas salvas no localStorage
  const [simuladas, setSimuladas] = useState(() => {
    try {
      const saved = localStorage.getItem('freecash-simulacoes');
      return saved ? JSON.parse(saved) : [];
    } catch {
      return [];
    }
  });

  // Salvar no localStorage sempre que as simulações mudarem
  useEffect(() => {
    localStorage.setItem('freecash-simulacoes', JSON.stringify(simuladas));
  }, [simuladas]);

  // Form State
  const [descricao, setDescricao] = useState('');
  const [tipo, setTipo] = useState('D'); // D = Despesa, R = Receita
  const [valor, setValor] = useState('');
  const [categoria, setCategoria] = useState('');
  const [mesInicio, setMesInicio] = useState(projectionMonths[0]?.key || '');
  const [dia, setDia] = useState('1'); // dia do mês em que o lançamento cai
  const [frequencia, setFrequencia] = useState('unica'); // unica, recorrente, parcelada
  const [parcelas, setParcelas] = useState('3');

  // Mapear categorias existentes a partir dos dados do backend para sugerir no input
  const categoriasSugeridas = useMemo(() => {
    const cats = new Set();
    realContas.forEach(c => {
      if (c.categoria_detalhe?.nome) {
        cats.add(c.categoria_detalhe.nome);
      } else if (c.categoria) {
        cats.add(c.categoria);
      }
    });
    return Array.from(cats);
  }, [realContas]);

  // Adicionar nova simulação
  const handleAddSimulacao = (e) => {
    e.preventDefault();
    if (!descricao.trim()) {
      addToast('Por favor, informe uma descrição.', 'warning');
      return;
    }
    const numValor = parseFloat(valor);
    if (isNaN(numValor) || numValor <= 0) {
      addToast('Informe um valor válido maior que zero.', 'warning');
      return;
    }

    const newItem = {
      id: Date.now(),
      descricao: descricao.trim(),
      tipo,
      valor: numValor,
      categoria: categoria.trim() || 'Simulado',
      mesInicio,
      dia: parseInt(dia, 10) || 1,
      frequencia,
      parcelas: frequencia === 'parcelada' ? parseInt(parcelas) || 1 : null,
    };

    setSimuladas(prev => [...prev, newItem]);
    addToast('Lançamento simulado adicionado com sucesso!', 'success');

    // Reset Form
    setDescricao('');
    setValor('');
    setCategoria('');
  };

  // Excluir simulação
  const handleRemoveSimulacao = (id) => {
    setSimuladas(prev => prev.filter(item => item.id !== id));
    addToast('Simulação removida.', 'info');
  };

  // Limpar todas as simulações
  const handleLimparTudo = () => {
    if (window.confirm('Deseja realmente limpar todas as simulações atuais?')) {
      setSimuladas([]);
      addToast('Todas as simulações foram removidas.', 'info');
    }
  };

  // Auxiliar para parsing de mês/ano
  const parseMonthYear = (dateStr) => {
    if (!dateStr) return null;
    const [year, month] = dateStr.split('-');
    return `${year}-${month}`;
  };

  // Calcular valor simulado para um determinado mês
  const getSimulatedAmountForMonth = (item, monthKey) => {
    if (item.frequencia === 'unica') {
      return item.mesInicio === monthKey ? item.valor : 0;
    }

    if (item.frequencia === 'recorrente') {
      return monthKey >= item.mesInicio ? item.valor : 0;
    }

    if (item.frequencia === 'parcelada') {
      if (monthKey < item.mesInicio) return 0;

      const [startYear, startMonth] = item.mesInicio.split('-').map(Number);
      const [currYear, currMonth] = monthKey.split('-').map(Number);

      const diffMonths = (currYear - startYear) * 12 + (currMonth - startMonth);
      return diffMonths < item.parcelas ? (item.valor / item.parcelas) : 0;
    }

    return 0;
  };

  // Processar dados consolidados mês a mês
  const monthlyData = useMemo(() => {
    // A coluna "Saldo acumulado" desta tabela é saldo de verdade: parte do caixa
    // em mãos. É o único lugar da tela que ainda usa a âncora — a série diária e o
    // ponto de virada medem fluxo puro, deliberadamente (ver `dailyData` abaixo).
    // Semear só um dos lados quebraria o casamento entre eles.
    let accumulatedReal = saldoInicial;
    let accumulatedSim = saldoInicial;

    return projectionMonths.map((m) => {
      // Filtrar contas reais do mês correspondente
      const realItemsForMonth = realContas.filter(
        c => parseMonthYear(c.data_prevista) === m.key && !jaNoSaldoInicial(c),
      );

      const realRevenues = realItemsForMonth
        .filter(c => c.tipo === 'R')
        .reduce((sum, c) => sum + parseFloat(c.valor), 0);

      const realExpenses = realItemsForMonth
        .filter(c => c.tipo === 'D')
        .reduce((sum, c) => sum + parseFloat(c.valor), 0);

      // Calcular simulados
      let simRevenues = 0;
      let simExpenses = 0;

      const activeSimulatedItems = [];

      simuladas.forEach((item) => {
        const amt = getSimulatedAmountForMonth(item, m.key);
        if (amt > 0) {
          if (item.tipo === 'R') {
            simRevenues += amt;
          } else {
            simExpenses += amt;
          }
          activeSimulatedItems.push({ ...item, currentMonthVal: amt });
        }
      });

      const realNet = realRevenues - realExpenses;
      const simNet = (realRevenues + simRevenues) - (realExpenses + simExpenses);

      accumulatedReal += realNet;
      accumulatedSim += simNet;

      return {
        ...m,
        realRevenues,
        realExpenses,
        realNet,
        simRevenues,
        simExpenses,
        simNet,
        accumulatedReal,
        accumulatedSim,
        activeSimulatedItems,
      };
    });
  }, [projectionMonths, realContas, simuladas, saldoInicial, jaNoSaldoInicial]);

  // ── Projeção diária ─────────────────────────────────────────────────────────
  // Mesmos insumos do monthlyData (reais + simulados, ignorando tipo 'I'), só
  // que posicionados no dia exato: as contas reais pela `data_prevista` e as
  // simuladas pelo dia do mês escolhido no formulário.
  //
  // A métrica aqui é FLUXO ACUMULADO, não saldo: parte de zero, não do caixa em
  // mãos. É o que a tela precisa para responder "as entradas cobrem as saídas?"
  // sem que um colchão gordo esconda um mês estruturalmente no vermelho — com a
  // âncora, qualquer horizonte fechava em verde enquanto sobrasse caixa.
  // Por construção, o acumulado do último dia de cada mês bate com o
  // `accumulatedSim` daquele mês menos o saldo inicial.
  const dailyData = useMemo(() => {
    const days = [];
    const byKey = new Map();

    projectionMonths.forEach((m) => {
      const totalDays = new Date(m.year, m.monthIndex + 1, 0).getDate();
      for (let d = 1; d <= totalDays; d += 1) {
        const entry = {
          key: `${m.key}-${String(d).padStart(2, '0')}`,
          date: new Date(m.year, m.monthIndex, d),
          receitas: 0,
          despesas: 0,
          itens: [],
        };
        days.push(entry);
        byKey.set(entry.key, entry);
      }
    });

    realContas.forEach((c) => {
      const entry = byKey.get(String(c.data_prevista || '').slice(0, 10));
      if (!entry || (c.tipo !== 'R' && c.tipo !== 'D')) return;
      if (jaMovimentouAntesDaJanela(c)) return;

      const valorItem = parseFloat(c.valor) || 0;
      if (c.tipo === 'R') entry.receitas += valorItem;
      else entry.despesas += valorItem;

      entry.itens.push({
        id: `real-${c.id}`,
        descricao: c.descricao || 'Lançamento sem descrição',
        tipo: c.tipo,
        valor: valorItem,
        simulado: false,
      });
    });

    simuladas.forEach((item) => {
      projectionMonths.forEach((m) => {
        const valorMes = getSimulatedAmountForMonth(item, m.key);
        if (valorMes <= 0) return;

        // Meses curtos puxam o lançamento para o último dia disponível.
        const totalDays = new Date(m.year, m.monthIndex + 1, 0).getDate();
        const diaItem = Math.min(Math.max(parseInt(item.dia, 10) || 1, 1), totalDays);
        const entry = byKey.get(`${m.key}-${String(diaItem).padStart(2, '0')}`);
        if (!entry) return;

        if (item.tipo === 'R') entry.receitas += valorMes;
        else entry.despesas += valorMes;

        entry.itens.push({
          id: `sim-${item.id}-${m.key}`,
          descricao: item.descricao,
          tipo: item.tipo,
          valor: valorMes,
          simulado: true,
        });
      });
    });

    let corrente = 0;
    days.forEach((entry) => {
      entry.fluxo = entry.receitas - entry.despesas;
      corrente += entry.fluxo;
      entry.acumulado = corrente;
    });

    return days;
  }, [projectionMonths, realContas, simuladas, jaMovimentouAntesDaJanela]);

  // Trecho ainda por vir da série diária: o recorte que o mapa de calor pinta e o
  // ponto de virada analisa. Só daqui para frente existe decisão a tomar.
  //
  // O acumulado é rebaseado em zero em hoje. Sem rebase, a primeira célula já
  // apareceria com o fluxo dos dias vividos do mês corrente embutido — um número
  // sem origem visível na tela. Com rebase, todo valor lê como "desde hoje".
  const projecaoFutura = useMemo(() => {
    const inicio = dailyData.findIndex((d) => d.date >= hoje);
    if (inicio < 0) return [];

    const base = inicio > 0 ? dailyData[inicio - 1].acumulado : 0;
    return dailyData
      .slice(inicio)
      .map((d) => ({ ...d, acumulado: d.acumulado - base }));
  }, [dailyData, hoje]);

  // ── Ponto de virada ─────────────────────────────────────────────────────────
  // A conclusão da tela, medida em FLUXO acumulado desde hoje — o saldo em caixa
  // não entra na conta. A pergunta que o card responde deixou de ser "vou ficar
  // sem dinheiro?" e passou a ser "as entradas cobrem as saídas, e de quanto de
  // colchão este horizonte precisa?". Um caixa gordo não pode mais pintar de verde
  // um horizonte que só fecha porque está queimando reserva.
  //
  // Sendo F(t) o fluxo acumulado e A uma injeção feita no dia d, temos
  // F'(t) = F(t) + A para t >= d, e nada muda antes de d. Logo o horizonte inteiro
  // fica não-negativo se e somente se d <= primeiro dia vermelho E A >= |pior
  // acumulado|. Como o pior vale sempre cai em ou depois do primeiro dia vermelho,
  // a solução mínima é única: injetar |pior acumulado| na véspera do primeiro
  // vermelho. Antecipar não barateia; adiar não resolve.
  //
  // Roda sobre `projecaoFutura`, não sobre a série inteira: varrer os dias já
  // vividos do mês corrente faria o card diagnosticar o passado — apontar como
  // "menor folga" o fluxo com que o mês abriu, ou dar um prazo já vencido.
  const pontoDeVirada = useMemo(() => {
    if (projecaoFutura.length === 0) return null;

    const primeiroVermelho = projecaoFutura.find((d) => d.acumulado < -EPS) || null;
    const pior = projecaoFutura.reduce(
      (worst, d) => (worst === null || d.acumulado < worst.acumulado ? d : worst),
      null,
    );

    const inicioHorizonte = projecaoFutura[0].date;
    const vespera = primeiroVermelho
      ? new Date(
          primeiroVermelho.date.getFullYear(),
          primeiroVermelho.date.getMonth(),
          primeiroVermelho.date.getDate() - 1,
        )
      : null;

    // Se o vermelho começa hoje, não sobrou véspera acionável — o prazo para agir
    // já passou.
    const prazoEsgotado = Boolean(vespera && vespera < inicioHorizonte);

    // O "porquê": as despesas (reais + simuladas) entre hoje e o pior dia são o
    // que de fato empurra o acumulado para o vermelho — não basta apontar a
    // data, é preciso nomear as contas. Agrupadas por descrição porque um
    // lançamento recorrente ou parcelado aparece uma vez por mês na série
    // diária, e listar cada ocorrência separadamente só adicionaria ruído.
    let principaisDespesas = [];
    if (primeiroVermelho) {
      const ateOPior = projecaoFutura.filter((d) => d.date <= pior.date);
      const porDescricao = new Map();
      ateOPior.forEach((d) => {
        d.itens.forEach((item) => {
          if (item.tipo !== 'D') return;
          const key = `${item.simulado ? 'sim' : 'real'}-${item.descricao}`;
          const atual = porDescricao.get(key) || {
            descricao: item.descricao,
            simulado: item.simulado,
            total: 0,
            ocorrencias: 0,
          };
          atual.total += item.valor;
          atual.ocorrencias += 1;
          porDescricao.set(key, atual);
        });
      });
      principaisDespesas = Array.from(porDescricao.values()).sort((a, b) => b.total - a.total);
    }

    return {
      primeiroVermelho,
      pior,
      diasNoVermelho: projecaoFutura.filter((d) => d.acumulado < -EPS).length,
      // Colchão mínimo que cobre o vale inteiro. Só existe quando há vale.
      margemNecessaria: primeiroVermelho ? Math.abs(pior.acumulado) : 0,
      dataLimite: prazoEsgotado ? null : vespera,
      prazoEsgotado,
      // Espelho do caso positivo: o dia mais apertado de um horizonte que fecha.
      folgaMinima: primeiroVermelho ? null : pior,
      principaisDespesas,
      inicioHorizonte,
      fimHorizonte: projecaoFutura[projecaoFutura.length - 1].date,
    };
  }, [projecaoFutura]);

  // Cálculo dos KPIs focados no mês atual e na projeção de 6 meses
  const kpis = useMemo(() => {
    if (monthlyData.length === 0) {
      return {
        currentReal: 0,
        currentSim: 0,
        projectedReal6m: 0,
        projectedSim6m: 0,
        diff6m: 0,
      };
    }

    // Mês atual (primeiro mês da projeção)
    const current = monthlyData[0];
    const currentReal = current.realNet;
    const currentSim = current.simNet;

    // Projeção de 6 meses (index 5)
    const targetIdx = Math.min(5, monthlyData.length - 1);
    const projected6m = monthlyData[targetIdx];
    const projectedReal6m = projected6m.accumulatedReal;
    const projectedSim6m = projected6m.accumulatedSim;
    const diff6m = projectedSim6m - projectedReal6m;

    return {
      currentReal,
      currentSim,
      projectedReal6m,
      projectedSim6m,
      diff6m,
    };
  }, [monthlyData]);

  // O diagnóstico só é confiável com as duas pontas carregadas: os lançamentos e
  // a âncora de caixa.
  const projecaoCarregando = isLoading || isLoadingSaldo;

  // Filtrar apenas os primeiros 6 meses para o gráfico
  const chartData = useMemo(() => {
    return monthlyData.slice(0, 6);
  }, [monthlyData]);

  // O botão só existe porque o usuário pode editar uma conta em outra tela e
  // voltar aqui sem que o cache do react-query saiba disso. O toast é o único
  // jeito de confirmar que a busca de fato rodou — sem ele o clique não parece
  // fazer nada quando os números não mudam.
  const handleAtualizarDados = async () => {
    try {
      await refetch();
      addToast('Dados atualizados.', 'success');
    } catch {
      addToast('Não foi possível atualizar os dados.', 'error');
    }
  };

  return (
    <div className="space-y-6 p-1 sm:p-4">
      <div className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-bold tracking-tight text-foreground md:text-3xl">
              Simulador de Gastos
            </h1>
            <Badge variant="secondary" className="bg-primary/10 text-primary border border-primary/20 flex gap-1 items-center px-2.5 py-0.5">
              <Sparkles className="h-3 w-3" /> Sandbox
            </Badge>
          </div>
          <p className="text-sm text-muted-foreground mt-1">
            Simule o impacto de novos gastos e receitas recorrentes ou parceladas em seu fluxo de caixa para os próximos 12 meses.
          </p>
        </div>
        <Button
          variant="outline"
          size="sm"
          onClick={handleAtualizarDados}
          disabled={isFetching}
          className="self-start md:self-center flex gap-2 items-center"
        >
          <RefreshCw className={`h-4 w-4 ${isFetching ? 'animate-spin' : ''}`} />
          Atualizar Dados
        </Button>
      </div>

      <PontoDeViradaCard pontoDeVirada={pontoDeVirada} projecaoCarregando={projecaoCarregando} />

      <SaldoKpiCards isLoading={isLoading} kpis={kpis} />

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <div className="lg:col-span-1 space-y-6">
          <LancamentoForm
            onSubmit={handleAddSimulacao}
            descricao={descricao}
            setDescricao={setDescricao}
            tipo={tipo}
            setTipo={setTipo}
            valor={valor}
            setValor={setValor}
            categoria={categoria}
            setCategoria={setCategoria}
            categoriasSugeridas={categoriasSugeridas}
            mesInicio={mesInicio}
            setMesInicio={setMesInicio}
            projectionMonths={projectionMonths}
            dia={dia}
            setDia={setDia}
            frequencia={frequencia}
            setFrequencia={setFrequencia}
            parcelas={parcelas}
            setParcelas={setParcelas}
          />

          <SimulacoesAtivasList
            simuladas={simuladas}
            onRemove={handleRemoveSimulacao}
            onLimparTudo={handleLimparTudo}
          />
        </div>

        <div className="lg:col-span-2 space-y-6">
          <FluxoProjetadoChart isLoading={isLoading} chartData={chartData} isDark={isDark} />
        </div>
      </div>

      <AnaliseDetalhada
        isLoading={isLoading}
        monthlyData={monthlyData}
        projecaoFutura={projecaoFutura}
        pontoDeVirada={pontoDeVirada}
      />
    </div>
  );
}
