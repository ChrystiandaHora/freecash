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
import { useQuery, useQueryClient } from '@tanstack/react-query';
import api from '../services/api';
import Chart from 'react-apexcharts';
import {
  PieChart,
  AlertCircle,
  CheckCircle2,
  RefreshCw,
} from 'lucide-react';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '../components/ui/Card';
import { Button } from '../components/ui/Button';
import { Accordion, AccordionItem } from '../components/ui/Accordion';
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

  const [isRefreshing, setIsRefreshing] = useState(false);
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
      setIsRefreshing(false);
    }
  };

  if (isDashLoading) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[70vh] gap-4">
        <RefreshCw className="h-8 w-8 text-primary animate-spin" />
        <p className="text-sm font-semibold text-slate-500 dark:text-slate-400">
          Analisando carteira e rentabilidades...
        </p>
      </div>
    );
  }

  if (isDashError) {
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
      custom: ({ series, seriesIndex, dataPointIndex }) => {
        const patrimonio = series[0]?.[dataPointIndex] ?? 0;
        const investido = series[1]?.[dataPointIndex] ?? 0;
        const delta = patrimonio - investido;
        const deltaColor = delta >= 0 ? '#10b981' : '#f43f5e';
        const deltaSign = delta >= 0 ? '+' : '';
        const fmt = (v) => formatCurrency(v);
        return [
          '<div style="padding:10px 14px;font-family:Outfit,Inter,sans-serif;font-size:12px;line-height:1.6;">',
          `<div style="margin-bottom:4px;"><span style="display:inline-block;width:10px;height:10px;border-radius:50%;background:#10b981;margin-right:6px;"></span><strong>Patrimônio:</strong> ${fmt(patrimonio)}</div>`,
          `<div style="margin-bottom:4px;"><span style="display:inline-block;width:10px;height:10px;border-radius:50%;background:#64748b;margin-right:6px;"></span><strong>Investido:</strong> ${fmt(investido)}</div>`,
          `<div style="border-top:1px solid rgba(128,128,128,0.2);margin-top:6px;padding-top:6px;color:${deltaColor};"><strong>Ganho/Perda:</strong> ${deltaSign}${fmt(delta)}</div>`,
          '</div>',
        ].join('');
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
            Gestão de carteiras e árvore ANBIMA
          </p>
        </div>

        {/* Actions */}
        <div className="flex items-center gap-3 w-full sm:w-auto">
          <Button
            variant="outline"
            onClick={handleRefreshAll}
            disabled={isRefreshing}
            className="rounded-xl h-9 px-4 shrink-0 flex items-center gap-2"
          >
            <RefreshCw className={`h-4 w-4 text-muted-foreground ${isRefreshing ? 'animate-spin' : ''}`} />
            <span className="text-xs font-semibold text-muted-foreground">Atualizar Dados</span>
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
              <div className="text-[11px] font-bold text-muted-foreground uppercase tracking-wider mb-1">
                Variação
              </div>
              <div className={`text-base font-extrabold flex items-center gap-0.5
                ${(total_patrimonio - total_investido) >= 0 ? 'text-emerald-600 dark:text-emerald-400' : 'text-rose-500'}
              `}>
                {((total_patrimonio - total_investido) / (total_investido || 1) * 100).toFixed(2).replace('.', ',')}%
                <span className="text-xs">{(total_patrimonio - total_investido) >= 0 ? '▲' : '▼'}</span>
              </div>
            </div>
            <div className={`text-[11px] font-semibold mt-1 ${
              (total_patrimonio - total_investido) >= 0
                ? 'text-emerald-600 dark:text-emerald-400'
                : 'text-rose-500'
            }`}>
              {formatCurrency(total_patrimonio - total_investido)}
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
                <span className="text-xs">{total_rentabilidade_percentual >= 0 ? '▲' : '▼'}</span>
              </div>
            </div>
            <div className="text-[10px] text-muted-foreground font-semibold mt-1">
              Cap. + dividendos
            </div>
          </div>
        </Card>
      </div>

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
                  <div className="h-full flex items-center justify-center text-xs text-muted-foreground font-semibold">
                    Sem dados históricos suficientes.
                  </div>
                )}
              </div>
            </CardContent>
          </Card>

          {/* Ativos na Carteira (Donut) */}
          <Card className="lg:col-span-2 bg-card border border-border/40 shadow-sm text-card-foreground p-5 rounded-2xl flex flex-col justify-between">
            <CardHeader className="p-0 mb-6">
              <CardTitle className="text-base font-bold text-foreground">Ativos na Carteira</CardTitle>
            </CardHeader>
            <CardContent className="p-0 flex flex-col sm:flex-row items-center gap-6 justify-between flex-1">
              <div className="relative w-[180px] h-[180px] sm:w-[200px] sm:h-[200px] shrink-0">
                {donutChartSeries.length > 0 ? (
                  <Chart
                    options={donutChartOptions}
                    series={donutChartSeries}
                    type="donut"
                    width="100%"
                    height="100%"
                  />
                ) : (
                  <div className="h-full flex items-center justify-center text-xs text-muted-foreground font-semibold">
                    Sem ativos cadastrados.
                  </div>
                )}
              </div>

              {/* Custom Legend */}
              <div className="flex-1 w-full space-y-2.5 max-h-[220px] overflow-y-auto custom-scrollbar pr-1">
                {alocacaoItens.map((item) => (
                  <div key={item.label} className="flex items-center justify-between text-xs font-semibold">
                    <div className="flex items-center gap-2 min-w-0">
                      <span className="w-2.5 h-2.5 rounded-full shrink-0" style={{ backgroundColor: item.color }} />
                      <span className="text-muted-foreground truncate">{item.label}</span>
                    </div>
                    <span className="text-foreground shrink-0 pl-2">{item.pct.toFixed(2).replace('.', ',')}%</span>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>

        </div>

        {/* Efeito Bola de Neve */}
        {snowballSeriesData.length > 0 && (
          <Card className="bg-card border border-border/40 shadow-sm text-card-foreground p-5 rounded-2xl">
            <CardHeader className="p-0 mb-6">
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

    </div>
  );
}
