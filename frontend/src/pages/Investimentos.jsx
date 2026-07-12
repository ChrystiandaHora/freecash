/**
 * Página Principal de Gestão e Balanceamento de Investimentos.
 * 
 * Componente funcional que serve como o hub de controle patrimonial do investidor.
 * Integra-se às APIs do Django REST Framework para exibir a composição detalhada de ativos,
 * alocação consolidada por macro-classes e a árvore ANBIMA.
 * 
 * Permite também a simulação em tempo real e reajuste de metas de balanceamento,
 * recomendando aportes e ordens ideais de compra.
 *
 * @component
 * @returns {React.JSX.Element} Painel de controle de investimentos contendo abas
 *   de visualização de portfólio e rebalanceamento dinâmico.
 */
import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import api from '../services/api';
import Chart from 'react-apexcharts';
import {
  PieChart,
  AlertCircle,
  CheckCircle2,
  RefreshCw,
  Sliders,
  Save,
  HelpCircle,
} from 'lucide-react';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '../components/ui/Card';
import { Button } from '../components/ui/Button';
import { Accordion, AccordionItem } from '../components/ui/Accordion';
import { Input } from '../components/ui/Input';
import { useToast } from '../context/ToastContext';
import { Alert } from '../components/ui/Alert';


const formatCurrency = (value) => {
  if (value === undefined || value === null) return 'R$ 0,00';
  return new Intl.NumberFormat('pt-BR', {
    style: 'currency',
    currency: 'BRL',
  }).format(value);
};

const formatPercentage = (value) => {
  if (value === undefined || value === null) return '0%';
  const num = parseFloat(value);
  const formatted = num.toFixed(2).replace('.', ',');
  return num >= 0 ? `+${formatted}%` : `${formatted}%`;
};

export default function Investimentos() {
  const queryClient = useQueryClient();
  const { addToast } = useToast();

  const [activeTab, setActiveTab] = useState('portfolio'); // 'portfolio' | 'rebalance'
  const [editingMetas, setEditingMetas] = useState({}); // Stores local target % state by asset ID: { [id]: val }
  const [isEditing, setIsEditing] = useState(false);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [metaError, setMetaError] = useState('');
  const [patrimonioMonthsFilter, setPatrimonioMonthsFilter] = useState(12);


  // Fetch investments metrics & charts
  const { 
    data: dashboardData, 
    isLoading: isDashLoading, 
    isError: isDashError, 
    refetch: refetchDash 
  } = useQuery({
    queryKey: ['investimentosDashboard'],
    queryFn: async () => {
      const response = await api.get('/api/investimentos/dashboard/');
      return response.data;
    }
  });

  // Fetch rebalancing metrics
  const { 
    data: balanceData, 
    isLoading: isBalanceLoading, 
    isError: isBalanceError, 
    refetch: refetchBalance 
  } = useQuery({
    queryKey: ['investimentosBalanceamento'],
    queryFn: async () => {
      const response = await api.get('/api/investimentos/balanceamento/');
      return response.data;
    }
  });

  // Save metas mutation
  const saveMetasMutation = useMutation({
    mutationFn: async (metasArray) => {
      const response = await api.post('/api/investimentos/balanceamento/', { metas: metasArray });
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries(['investimentosBalanceamento']);
      setIsEditing(false);
      setEditingMetas({});
      setMetaError('');
    },
    onError: (err) => {
      setMetaError('Erro ao atualizar metas. Tente novamente.');
      console.error(err);
    }
  });

  const handleStartEditing = () => {
    if (!balanceData) return;
    const initialMetas = {};
    balanceData.classes.forEach(cls => {
      cls.ativos.forEach(at => {
        initialMetas[at.id] = at.meta_porcentagem;
      });
    });
    setEditingMetas(initialMetas);
    setIsEditing(true);
    setMetaError('');
  };

  const handleMetaChange = (id, val) => {
    setEditingMetas(prev => ({
      ...prev,
      [id]: val === '' ? 0 : parseFloat(val) || 0
    }));
  };

  const handleSaveMetas = () => {
    // Validate sum of metas adds up to 100%
    const totalSum = Object.values(editingMetas).reduce((acc, curr) => acc + curr, 0);
    if (Math.abs(totalSum - 100) > 0.01 && totalSum > 0) {
      // Allow saving 0 total metas, but if metas are configured, warn if they don't sum 100%
      setMetaError(`A soma das metas deve ser exatamente 100%. Soma atual: ${totalSum.toFixed(1).replace('.', ',')}%`);
      return;
    }

    const payload = Object.entries(editingMetas).map(([id, meta]) => ({
      id: parseInt(id),
      meta: meta
    }));

    saveMetasMutation.mutate(payload);
  };

  const handleRefreshAll = async () => {
    setIsRefreshing(true);
    addToast('Atualizando cotações em tempo real...', 'info', 3000);
    try {
      const response = await api.post('/api/investimentos/ativos/atualizar-cotacoes/');
      const count = response.data?.count || 0;
      addToast(`${count} cotações de ativos atualizadas com sucesso!`, 'success');
    } catch (err) {
      console.error("Erro ao atualizar cotações:", err);
      addToast('Falha ao comunicar com o servidor de cotações.', 'error');
    } finally {
      refetchDash();
      refetchBalance();
      setIsRefreshing(false);
    }
  };

  if (isDashLoading || isBalanceLoading) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[70vh] gap-4">
        <RefreshCw className="h-8 w-8 text-primary animate-spin" />
        <p className="text-sm font-semibold text-slate-500 dark:text-slate-400">
          Analisando carteira e rentabilidades...
        </p>
      </div>
    );
  }

  if (isDashError || isBalanceError) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[70vh] gap-4 text-center max-w-md mx-auto">
        <AlertCircle className="h-12 w-12 text-red-500" />
        <h3 className="text-xl font-bold text-slate-800 dark:text-slate-200">Erro ao carregar carteira</h3>
        <p className="text-sm text-slate-500 dark:text-slate-400">
          Não foi possível carregar os dados de investimentos. Verifique sua conexão com o servidor.
        </p>
        <Button onClick={handleRefreshAll} className="mt-2">
          Recarregar Painel
        </Button>
      </div>
    );
  }

  const {
    total_patrimonio = 0,
    total_investido = 0,
    total_rentabilidade = 0,
    total_rentabilidade_percentual = 0,
    total_dividendos = 0,
    alocacao_categorias = { labels: [], valores: [] },
  } = dashboardData;

  const isDarkTheme = document.documentElement.classList.contains('dark');
  const donutColors = ['#0284c7', '#38bdf8', '#2dd4bf', '#fb923c', '#fb7185', '#c084fc', '#facc15', '#a855f7'];

  // Sort categories by value descending for consistent chart and legend mapping
  const categoryPairs = (alocacao_categorias.labels || []).map((label, idx) => {
    const valor = (alocacao_categorias.valores || [])[idx] || 0;
    return { label, valor };
  });
  categoryPairs.sort((a, b) => b.valor - a.valor);

  const sortedLabels = categoryPairs.map(item => item.label);
  const sortedValues = categoryPairs.map(item => item.valor);

  // Chart configuration for Asset Allocation (Donut)
  const donutChartOptions = {
    chart: {
      type: 'donut',
      fontFamily: 'Outfit, Inter, sans-serif',
      background: 'transparent',
      animations: { enabled: false },
    },
    labels: sortedLabels,
    colors: donutColors,
    dataLabels: { enabled: false },
    stroke: { width: 1, colors: [isDarkTheme ? 'rgba(255, 255, 255, 0.05)' : 'rgba(0, 0, 0, 0.05)'] },
    legend: {
      show: false, // Hidden to use custom HTML legend next to the chart
    },
    plotOptions: {
      pie: {
        expandOnClick: false,
        donut: {
          size: '75%',
          labels: {
            show: true,
            value: {
              formatter: (val) => formatCurrency(val),
              color: isDarkTheme ? '#e2e8f0' : '#1e293b',
              fontSize: '18px',
              fontWeight: 700
            },
            total: {
              show: true,
              label: 'Patrimônio',
              color: '#888888',
              fontSize: '11px',
              fontWeight: 600,
              formatter: () => formatCurrency(total_patrimonio)
            }
          }
        }
      }
    },
    theme: {
      mode: isDarkTheme ? 'dark' : 'light',
    },
    tooltip: {
      theme: isDarkTheme ? 'dark' : 'light',
      y: {
        formatter: (val) => formatCurrency(val)
      }
    }
  };

  const scatterSeries = (balanceData?.classes || []).map(classe => ({
    name: classe.nome,
    data: (classe.ativos || []).map(at => ({
      x: parseFloat(at.rentabilidade_perc) || 0,
      y: parseFloat(at.perc_atual - at.meta_porcentagem) || 0,
      ticker: at.ticker,
      nome: at.nome,
      valor_atual: at.valor_atual
    }))
  }));


  const scatterOptions = {
    chart: {
      type: 'scatter',
      zoom: { enabled: true, type: 'xy' },
      toolbar: { show: false },
      fontFamily: 'Outfit, Inter, sans-serif',
      foreColor: isDarkTheme ? '#888888' : '#666666',
      background: 'transparent',
    },
    xaxis: {
      tickAmount: 6,
      labels: {
        formatter: (val) => parseFloat(val).toFixed(1) + '%'
      },
      title: {
        text: 'Rentabilidade Acumulada (%)',
        style: { fontSize: '11px', fontWeight: 600, color: isDarkTheme ? '#888888' : '#666666' }
      }
    },
    yaxis: {
      tickAmount: 6,
      labels: {
        formatter: (val) => (val > 0 ? '+' : '') + parseFloat(val).toFixed(1) + '%'
      },
      title: {
        text: 'Desvio da Meta Alvo (%)',
        style: { fontSize: '11px', fontWeight: 600, color: isDarkTheme ? '#888888' : '#666666' }
      }
    },
    grid: {
      borderColor: isDarkTheme ? 'rgba(255, 255, 255, 0.05)' : 'rgba(0, 0, 0, 0.05)',
      xaxis: { lines: { show: true } },
      yaxis: { lines: { show: true } }
    },
    theme: {
      mode: isDarkTheme ? 'dark' : 'light',
    },
    markers: {
      size: 10,
      strokeWidth: 2,
      strokeColors: '#fff',
      hover: { size: 12 }
    },
    tooltip: {
      theme: isDarkTheme ? 'dark' : 'light',
      custom: ({ seriesIndex, dataPointIndex, w }) => {
        const point = w.config.series[seriesIndex].data[dataPointIndex];
        if (!point) return '';
        return `
          <div class="p-3 bg-slate-900 border border-slate-700 rounded-lg text-xs" style="min-width: 180px;">
            <div class="font-extrabold text-sm text-white mb-1">${point.ticker}</div>
            <div class="text-slate-400 mb-2 truncate max-w-[200px]">${point.nome}</div>
            <div class="grid grid-cols-2 gap-x-2 gap-y-1 text-white">
              <span class="text-slate-400">Valor:</span>
              <span class="text-right font-semibold">${new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(point.valor_atual)}</span>
              <span class="text-slate-400">Rentabilidade:</span>
              <span class="text-right font-semibold text-emerald-400">${point.x.toFixed(2)}%</span>
              <span class="text-slate-400">Desvio Meta:</span>
              <span class="text-right font-semibold ${point.y < 0 ? 'text-rose-400' : 'text-primary'}">${point.y.toFixed(2)}%</span>
            </div>
          </div>
        `;
      }
    }
  };

  const snowballMonthlyData = dashboardData?.performance_monthly || [];
  const snowballCategories = snowballMonthlyData.map(item => {
    if (!item.data) return '';
    const parts = item.data.split('-');
    if (parts.length < 2) return item.data;
    const year = parts[0].substring(2);
    const monthIndex = parseInt(parts[1], 10);
    const monthsPt = ["", "Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"];
    return `${monthsPt[monthIndex]}/${year}`;
  });

  const snowballSeriesData = snowballMonthlyData.map(item => parseFloat(item.total_dividendos) || 0);

  const snowballChartOptions = {
    chart: {
      type: 'area',
      height: 320,
      toolbar: { show: false },
      fontFamily: 'Outfit, Inter, sans-serif',
      foreColor: isDarkTheme ? '#888888' : '#666666',
      background: 'transparent',
    },
    colors: ['#a855f7'],
    dataLabels: { enabled: false },
    stroke: { curve: 'smooth', width: 3 },
    fill: {
      type: 'gradient',
      gradient: {
        shadeIntensity: 1,
        opacityFrom: 0.45,
        opacityTo: 0.05,
        stops: [0, 90, 100],
      },
    },
    xaxis: {
      categories: snowballCategories,
      labels: {
        style: { fontSize: '10px' },
      },
      axisBorder: { show: false },
      axisTicks: { show: false },
    },
    yaxis: {
      labels: {
        formatter: (val) => formatCurrency(val),
        style: { fontSize: '10px' },
      },
    },
    grid: {
      borderColor: isDarkTheme ? 'rgba(255, 255, 255, 0.05)' : 'rgba(0, 0, 0, 0.05)',
      strokeDashArray: 4,
    },
    theme: {
      mode: isDarkTheme ? 'dark' : 'light',
    },
    tooltip: {
      theme: isDarkTheme ? 'dark' : 'light',
      y: {
        formatter: (val) => formatCurrency(val),
      },
    },
  };

  const snowballChartSeries = [
    { name: 'Renda Passiva Acumulada', data: snowballSeriesData }
  ];

  // Evolução do Patrimônio: patrimônio a mercado vs. custo investido com base no filtro
  const patrimonioMonthlyData = patrimonioMonthsFilter === 0
    ? (dashboardData?.performance_monthly || [])
    : (dashboardData?.performance_monthly || []).slice(-patrimonioMonthsFilter);
  const patrimonioCategories = patrimonioMonthlyData.map(item => {
    if (!item.data) return '';
    const parts = item.data.split('-');
    if (parts.length < 2) return item.data;
    const year = parts[0].substring(2);
    const monthIndex = parseInt(parts[1], 10);
    const monthsPt = ["", "Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"];
    return `${monthsPt[monthIndex]}/${year}`;
  });

  const patrimonioSeriesData = patrimonioMonthlyData.map(item => parseFloat(item.patrimonio) || 0);
  const investidoSeriesData = patrimonioMonthlyData.map(item => parseFloat(item.investido) || 0);

  const patrimonioChartOptions = {
    chart: {
      type: 'area',
      height: 320,
      toolbar: { show: false },
      fontFamily: 'Outfit, Inter, sans-serif',
      foreColor: isDarkTheme ? '#888888' : '#666666',
      background: 'transparent',
    },
    colors: ['#10b981', '#64748b'],
    dataLabels: { enabled: false },
    stroke: { curve: 'smooth', width: [3, 2] },
    fill: {
      type: 'gradient',
      gradient: {
        shadeIntensity: 1,
        opacityFrom: [0.45, 0.05],
        opacityTo: [0.05, 0.02],
        stops: [0, 90, 100],
      },
    },
    xaxis: {
      categories: patrimonioCategories,
      labels: { style: { fontSize: '10px' } },
      axisBorder: { show: false },
      axisTicks: { show: false },
    },
    yaxis: {
      labels: {
        formatter: (val) => new Intl.NumberFormat('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(val),
        style: { fontSize: '10px' },
      },
    },
    grid: {
      borderColor: isDarkTheme ? 'rgba(255, 255, 255, 0.05)' : 'rgba(0, 0, 0, 0.05)',
      strokeDashArray: 4,
    },
    legend: {
      show: false,
    },
    theme: {
      mode: isDarkTheme ? 'dark' : 'light',
    },
    tooltip: {
      theme: isDarkTheme ? 'dark' : 'light',
      y: {
        formatter: (val) => formatCurrency(val),
      },
    },
  };

  const patrimonioChartSeries = [
    { name: 'Patrimônio (Mercado)', data: patrimonioSeriesData },
    { name: 'Investido (Custo)', data: investidoSeriesData },
  ];

  const donutChartSeries = sortedValues;
  const totalValores = donutChartSeries.reduce((acc, curr) => acc + curr, 0);
  const alocacaoItens = categoryPairs.map((item, idx) => {
    const pct = totalValores > 0 ? (item.valor / totalValores) * 100 : 0;
    return {
      label: item.label,
      valor: item.valor,
      pct,
      color: donutColors[idx % donutColors.length]
    };
  });

  return (
    <div className="space-y-8 animate-fade-in">
      
      {/* Top Title & Header Navigation */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <div>
          <h1 className="text-3xl font-extrabold tracking-tight text-foreground">
            Painel de Investimentos
          </h1>
          <p className="text-muted-foreground mt-1">
            Gestão de carteiras, árvore ANBIMA e balanceamento ideal
          </p>
        </div>

        {/* Tab Selection */}
        <div className="flex items-center gap-3 w-full sm:w-auto">
          <div className="flex bg-muted p-1.5 rounded-xl border border-border/40 w-full sm:w-auto">
            <button
              onClick={() => setActiveTab('portfolio')}
              className={`flex-1 sm:flex-initial px-4 py-1.5 text-xs font-semibold rounded-lg transition-all flex items-center justify-center gap-2 cursor-pointer
                ${activeTab === 'portfolio' 
                  ? 'bg-card shadow-sm text-primary' 
                  : 'text-muted-foreground hover:text-foreground'
                }
              `}
            >
              <PieChart className="h-3.5 w-3.5" />
              <span>Visão da Carteira</span>
            </button>
            <button
              onClick={() => setActiveTab('rebalance')}
              className={`flex-1 sm:flex-initial px-4 py-1.5 text-xs font-semibold rounded-lg transition-all flex items-center justify-center gap-2 cursor-pointer
                ${activeTab === 'rebalance' 
                  ? 'bg-card shadow-sm text-primary' 
                  : 'text-muted-foreground hover:text-foreground'
                }
              `}
            >
              <Sliders className="h-3.5 w-3.5" />
              <span>Balanceador Ideal</span>
            </button>
          </div>

          <Button
            variant="outline"
            size="icon"
            onClick={handleRefreshAll}
            disabled={isRefreshing}
            className="rounded-xl h-9 w-9 shrink-0"
          >
            <RefreshCw className={`h-4 w-4 text-muted-foreground ${isRefreshing ? 'animate-spin' : ''}`} />
          </Button>
        </div>
      </div>

      {/* KPI Cards (Always Shown) */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
        
        {/* Card 1: Patrimônio Total */}
        <Card className="bg-card border border-border/40 shadow-sm text-card-foreground p-5 rounded-2xl flex flex-col justify-between">
          <div>
            <div className="flex justify-between items-center text-xs font-bold text-muted-foreground uppercase tracking-wider mb-2">
              <span>Patrimônio total</span>
              <span className={`inline-flex items-center gap-0.5 text-[11px] font-bold rounded-full px-2 py-0.5
                ${total_rentabilidade_percentual >= 0 
                  ? 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400' 
                  : 'bg-rose-500/10 text-rose-600 dark:text-rose-400'
                }
              `}>
                {total_rentabilidade_percentual >= 0 ? '▲' : '▼'} {Math.abs(total_rentabilidade_percentual).toFixed(2).replace('.', ',')}%
              </span>
            </div>
            <h3 className="text-2xl font-bold tracking-tight text-foreground">
              {formatCurrency(total_patrimonio)}
            </h3>
          </div>
          <div className="mt-4 pt-4 border-t border-border/40 flex justify-between items-center text-xs">
            <span className="text-muted-foreground">Valor investido</span>
            <span className="font-semibold text-foreground">{formatCurrency(total_investido)}</span>
          </div>
        </Card>

        {/* Card 2: Lucro Total */}
        <Card className="bg-card border border-border/40 shadow-sm text-card-foreground p-5 rounded-2xl flex flex-col justify-between">
          <div>
            <div className="text-xs font-bold text-muted-foreground uppercase tracking-wider mb-2">
              Lucro total
            </div>
            <h3 className={`text-2xl font-bold tracking-tight ${total_rentabilidade >= 0 ? 'text-emerald-600 dark:text-emerald-400' : 'text-rose-500'}`}>
              {formatCurrency(total_rentabilidade)}
            </h3>
          </div>
          <div className="mt-4 pt-4 border-t border-border/40 grid grid-cols-2 gap-2 text-xs">
            <div>
              <div className="text-[10px] text-muted-foreground uppercase font-semibold">Ganho de Capital</div>
              <div className="font-bold text-foreground mt-0.5">{formatCurrency(total_patrimonio - total_investido)}</div>
            </div>
            <div className="border-l border-border/40 pl-3">
              <div className="text-[10px] text-muted-foreground uppercase font-semibold">Dividendos</div>
              <div className="font-bold text-foreground mt-0.5">{formatCurrency(total_dividendos)}</div>
            </div>
          </div>
        </Card>

        {/* Card 3: Proventos Recebidos */}
        <Card className="bg-card border border-border/40 shadow-sm text-card-foreground p-5 rounded-2xl flex flex-col justify-between">
          <div>
            <div className="text-xs font-bold text-muted-foreground uppercase tracking-wider mb-2">
              Proventos Recebidos (12M)
            </div>
            <h3 className="text-2xl font-bold tracking-tight text-foreground">
              {formatCurrency(total_dividendos)}
            </h3>
          </div>
          <div className="mt-4 pt-4 border-t border-border/40 flex justify-between items-center text-xs">
            <span className="text-muted-foreground">Total</span>
            <span className="font-semibold text-foreground">{formatCurrency(total_dividendos)}</span>
          </div>
        </Card>

        {/* Card 4: Variação / Rentabilidade */}
        <Card className="bg-card border border-border/40 shadow-sm text-card-foreground p-5 rounded-2xl grid grid-cols-2 gap-4 divide-x divide-border/40">
          <div className="flex flex-col justify-between">
            <div>
              <div className="flex items-center gap-1 text-[11px] font-bold text-muted-foreground uppercase tracking-wider mb-1">
                <span>Variação</span>
                <HelpCircle className="cursor-help text-muted-foreground/60 hover:text-muted-foreground h-3 w-3 shrink-0" title="Variação patrimonial a mercado sobre o custo aplicado" />
              </div>
              <div className={`text-base font-extrabold flex items-center gap-0.5
                ${(total_patrimonio - total_investido) >= 0 ? 'text-emerald-600 dark:text-emerald-400' : 'text-rose-500'}
              `}>
                {((total_patrimonio - total_investido) / (total_investido || 1) * 100).toFixed(2).replace('.', ',')}%
                <span className="text-xs">{(total_patrimonio - total_investido) >= 0 ? '▲' : '▼'}</span>
              </div>
            </div>
            <div className="text-[11px] text-muted-foreground font-semibold mt-1">
              + {formatCurrency(total_patrimonio - total_investido)}
            </div>
          </div>
          
          <div className="pl-4 flex flex-col justify-between">
            <div>
              <div className="text-[11px] font-bold text-muted-foreground uppercase tracking-wider mb-1">
                Rentabilidade
              </div>
              <div className={`text-base font-extrabold flex items-center gap-0.5
                ${total_rentabilidade_percentual >= 0 ? 'text-emerald-600 dark:text-emerald-400' : 'text-rose-500'}
              `}>
                {total_rentabilidade_percentual.toFixed(2).replace('.', ',')}%
                <span className="text-xs">↗</span>
              </div>
            </div>
            <div className="text-[10px] text-muted-foreground font-semibold mt-1">
              Histórica
            </div>
          </div>
        </Card>
      </div>

      {/* Tab 1: Portfolio View */}
      {activeTab === 'portfolio' && (
        <div className="space-y-8">
          
          {/* Charts Row */}
          <div className="grid grid-cols-1 lg:grid-cols-5 gap-6">
            
            {/* Evolução do Patrimônio */}
            <Card className="lg:col-span-3 bg-card border border-border/40 shadow-sm text-card-foreground p-5 rounded-2xl flex flex-col justify-between">
              <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 mb-6">
                <div>
                  <CardTitle className="text-base font-bold text-foreground">
                    Evolução do Patrimônio
                  </CardTitle>
                </div>
                
                {/* Header Actions / Filters / Legends */}
                <div className="flex flex-wrap items-center gap-4 w-full sm:w-auto">
                  {/* Legend */}
                  <div className="flex items-center gap-3 text-xs font-semibold">
                    <div className="flex items-center gap-1.5">
                      <span className="w-2.5 h-2.5 rounded-full bg-[#10b981]" />
                      <span className="text-muted-foreground">Patrimônio</span>
                    </div>
                    <div className="flex items-center gap-1.5">
                      <span className="w-2.5 h-2.5 rounded-full bg-[#64748b]" />
                      <span className="text-muted-foreground">Valor investido</span>
                    </div>
                  </div>
                  
                  {/* Filters Dropdowns */}
                  <div className="flex items-center gap-2">
                    <select 
                      value={patrimonioMonthsFilter}
                      onChange={(e) => setPatrimonioMonthsFilter(parseInt(e.target.value))}
                      className="bg-muted text-foreground border border-border/40 rounded-lg pl-2 pr-6 py-1 text-xs font-semibold focus:outline-none cursor-pointer"
                    >
                      <option value={12}>12 Meses</option>
                      <option value={6}>6 Meses</option>
                      <option value={0}>Todo o período</option>
                    </select>
                  </div>
                </div>
              </div>
              
              <CardContent className="p-0">
                <div className="h-[320px] w-full">
                  {patrimonioSeriesData.length > 0 ? (
                    <Chart
                      key={`patrimonio-area-${isDarkTheme}`}
                      options={patrimonioChartOptions}
                      series={patrimonioChartSeries}
                      type="area"
                      height="100%"
                      width="100%"
                    />
                  ) : (
                    <div className="py-24 text-center text-xs text-muted-foreground">
                      Dados insuficientes para gerar a evolução patrimonial.
                    </div>
                  )}
                </div>
              </CardContent>
            </Card>

            {/* Ativos na Carteira (Allocation Donut) */}
            <Card className="lg:col-span-2 bg-card border border-border/40 shadow-sm text-card-foreground p-5 rounded-2xl flex flex-col justify-between">
              <div className="flex justify-between items-center mb-6">
                <CardTitle className="text-base font-bold text-foreground">
                  Ativos na Carteira
                </CardTitle>
              </div>
              
              <CardContent className="p-0 flex flex-col sm:flex-row items-center justify-between gap-6 h-full min-h-[220px]">
                {donutChartSeries.length > 0 ? (
                  <>
                    {/* Donut Chart */}
                    <div className="w-[220px] h-[220px] shrink-0 flex items-center justify-center">
                      <Chart
                        key={`donut-${donutChartSeries.join("-")}`}
                        options={donutChartOptions}
                        series={donutChartSeries}
                        type="donut"
                        width="100%"
                        height="100%"
                      />
                    </div>
                    
                    {/* Custom Legend */}
                    <div className="flex-1 w-full max-h-[220px] overflow-y-auto pr-1 space-y-2">
                      {alocacaoItens.map((item, idx) => (
                        <div key={idx} className="flex justify-between items-center text-xs font-semibold">
                          <div className="flex items-center gap-2 text-muted-foreground truncate flex-1 min-w-0 mr-2">
                            <span className="w-2.5 h-2.5 rounded shrink-0" style={{ backgroundColor: item.color }} />
                            <span className="truncate flex-1">{item.label}</span>
                          </div>
                          <span className="text-foreground font-bold shrink-0">{item.pct.toFixed(2).replace('.', ',')}%</span>
                        </div>
                      ))}
                    </div>
                  </>
                ) : (
                  <div className="py-24 text-center text-xs text-muted-foreground w-full">
                    Nenhum ativo cadastrado para exibir alocação.
                  </div>
                )}
              </CardContent>
            </Card>
          </div>

          {/* Efeito Bola de Neve (Renda Passiva Cumulativa) */}
          {snowballSeriesData.length > 0 && (
            <Card className="bg-card border border-border/40 shadow-sm text-card-foreground">
              <CardHeader>
                <CardTitle className="text-base font-bold text-foreground">
                  Efeito Bola de Neve (Renda Passiva Acumulada)
                </CardTitle>
                <CardDescription className="text-xs text-muted-foreground">
                  Crescimento real e exponencial dos proventos e dividendos acumulados da sua carteira de investimentos
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="h-[280px] w-full">
                  <Chart
                    key={`snowball-${isDarkTheme}`}
                    options={snowballChartOptions}
                    series={snowballChartSeries}
                    type="area"
                    height="100%"
                    width="100%"
                  />
                </div>
              </CardContent>
            </Card>
          )}

        </div>
      )}

      {/* Tab 2: Rebalancing Tool */}
      {activeTab === 'rebalance' && balanceData && (
        <div className="space-y-6">
          <Card className="bg-card border border-border/40 shadow-sm text-card-foreground">
            <CardHeader>
              <CardTitle className="text-base font-bold text-foreground">
                Matriz de Alocação Estratégica (Rentabilidade vs Desvio da Meta)
              </CardTitle>
              <CardDescription className="text-xs text-muted-foreground">
                Compare a rentabilidade acumulada de cada ativo com o seu desvio percentual em relação à meta alocada
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="h-[320px] w-full">
                <Chart
                  key={`scatter-${isDarkTheme}`}
                  options={scatterOptions}
                  series={scatterSeries}
                  type="scatter"
                  height="100%"
                  width="100%"
                />
              </div>
            </CardContent>
          </Card>

          <Card className="bg-card border border-border/40 shadow-sm text-card-foreground">
          <CardHeader className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
            <div>
              <CardTitle className="text-base font-bold text-foreground">
                Simulador de Balanceamento Inteligente
              </CardTitle>
              <CardDescription className="text-xs text-muted-foreground">
                Ajuste os percentuais alvos para cada ativo e o algoritmo recomendará os aportes necessários
              </CardDescription>
            </div>
            <div className="flex items-center gap-3 shrink-0">
              {isEditing ? (
                <>
                  <Button
                    variant="outline"
                    onClick={() => {
                      setIsEditing(false);
                      setMetaError('');
                    }}
                    disabled={saveMetasMutation.isPending}
                    className="h-9 px-4 rounded-xl text-xs font-semibold"
                  >
                    Cancelar
                  </Button>
                  <Button
                    onClick={handleSaveMetas}
                    disabled={saveMetasMutation.isPending}
                    className="h-9 px-4 rounded-xl text-xs font-semibold bg-primary hover:bg-primary/90 flex items-center gap-1.5 border-0 text-white"
                  >
                    {saveMetasMutation.isPending ? (
                      <RefreshCw className="h-3.5 w-3.5 animate-spin text-white" />
                    ) : (
                      <Save className="h-3.5 w-3.5 text-white" />
                    )}
                    <span>Salvar Metas</span>
                  </Button>
                </>
              ) : (
                <Button
                  onClick={handleStartEditing}
                  className="h-9 px-4 rounded-xl text-xs font-semibold bg-primary hover:bg-primary/90 text-white border-0 flex items-center gap-1.5"
                >
                  <Sliders className="h-3.5 w-3.5 text-white" />
                  <span>Ajustar Metas Alvo</span>
                </Button>
              )}
            </div>
          </CardHeader>
          
          <CardContent className="space-y-6">
            
            {/* Meta validation error */}
            {metaError && (
              <Alert variant="error" icon={AlertCircle} className="p-3.5 text-xs">
                <span className="font-semibold leading-relaxed">{metaError}</span>
              </Alert>
            )}

            {saveMetasMutation.isSuccess && (
              <Alert variant="success" icon={CheckCircle2} className="p-3.5 text-xs">
                <span className="font-semibold leading-relaxed">Metas de alocação salvas e sincronizadas com sucesso!</span>
              </Alert>
            )}

            {/* Sum Indicator */}
            {isEditing && (
              <div className="flex items-center justify-between p-3.5 rounded-xl bg-muted border border-border/40 text-xs">
                <span className="text-muted-foreground font-semibold">Soma atual das metas configuradas:</span>
                <span className={`font-extrabold text-sm ${Math.abs(Object.values(editingMetas).reduce((a, b) => a + b, 0) - 100) < 0.01 ? 'text-primary' : 'text-amber-500'}`}>
                  {Object.values(editingMetas).reduce((a, b) => a + b, 0).toFixed(1).replace('.', ',')}% / 100%
                </span>
              </div>
            )}

            {/* Class tables for rebalancing */}
            {balanceData.classes.map((classe, idx) => (
              <div key={idx} className="space-y-3.5">
                <h3 className="text-sm font-bold text-foreground border-l-3 border-primary pl-2">
                  {classe.nome}
                </h3>
                
                <div className="overflow-x-auto">
                  <table className="w-full text-xs text-left border-collapse">
                    <thead>
                      <tr className="border-b border-border/40 text-muted-foreground font-semibold">
                        <th className="py-2.5 px-4">Ticker</th>
                        <th className="py-2.5 px-4">Nome</th>
                        <th className="py-2.5 px-4 text-right">Peso Atual</th>
                        <th className="py-2.5 px-4 text-right">Meta Alvo (%)</th>
                        <th className="py-2.5 px-4 text-right">Saldo Atual</th>
                        <th className="py-2.5 px-4 text-right">Saldo Ideal</th>
                        <th className="py-2.5 px-4 text-right">Aporte Recomendado</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-border/40">
                      {classe.ativos.map((at, atIdx) => {
                        const localMeta = isEditing ? editingMetas[at.id] : at.meta_porcentagem;
                        const idealVal = isEditing 
                          ? (localMeta / 100.0) * balanceData.total_patrimonio 
                          : at.valor_ideal;
                        const diff = isEditing 
                          ? idealVal - at.valor_atual 
                          : at.diferenca;

                        return (
                          <tr key={atIdx} className="hover:bg-muted/40 transition-colors">
                            <td className="py-3 px-4 font-bold text-foreground">
                              {at.ticker}
                            </td>
                            <td className="py-3 px-4 text-muted-foreground max-w-[180px] truncate">
                              {at.nome}
                            </td>
                            <td className="py-3 px-4 text-right font-semibold text-foreground/80">
                              {at.perc_atual.toFixed(2).replace('.', ',')}%
                            </td>
                            <td className="py-3 px-4 text-right w-36">
                              {isEditing ? (
                                <div className="flex items-center justify-end gap-1.5">
                                  <Input
                                    type="number"
                                    value={editingMetas[at.id] !== undefined ? editingMetas[at.id] : at.meta_porcentagem}
                                    onChange={(e) => handleMetaChange(at.id, e.target.value)}
                                    className="h-8 w-20 text-right font-bold text-xs bg-muted rounded-lg px-2 border border-border/40 text-foreground"
                                    min="0"
                                    max="100"
                                    step="0.5"
                                  />
                                  <span className="text-muted-foreground font-semibold">%</span>
                                </div>
                              ) : (
                                <span className="font-bold text-foreground">
                                  {at.meta_porcentagem.toFixed(1).replace('.', ',')}%
                                </span>
                              )}
                            </td>
                            <td className="py-3 px-4 text-right font-medium text-muted-foreground">
                              {formatCurrency(at.valor_atual)}
                            </td>
                            <td className="py-3 px-4 text-right font-medium text-muted-foreground">
                              {formatCurrency(idealVal)}
                            </td>
                            <td className={`py-3 px-4 text-right font-extrabold ${diff > 0.01 ? 'text-primary' : 'text-muted-foreground'}`}>
                              {diff > 0.01 ? `COMPRAR ${formatCurrency(diff)}` : 'Aguardar / Manter'}
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </div>
            ))}

          </CardContent>
        </Card>
        </div>
      )}

    </div>
  );
}
