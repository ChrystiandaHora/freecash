/**
 * Painel de Controle de Finanças Pessoais (Dashboard).
 * 
 * Agrega as métricas cruciais de saúde financeira do mês, contendo resumos de receitas,
 * despesas liquidadas vs. previstas, cartões de crédito e taxa de poupança atual.
 * Renderiza gráficos interativos de fluxo de caixa projetado para apoio em tomadas de decisões.
 *
 * @component
 * @returns {React.JSX.Element} Painel visual composto por cartões de KPIs e gráficos analíticos.
 */
import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import api from '../services/api';
import Chart from 'react-apexcharts';
import { 
  ArrowUpRight, 
  ArrowDownRight, 
  Wallet, 
  TrendingUp, 
  Calendar, 
  CheckCircle2, 
  AlertTriangle, 
  Clock,
  ArrowRight,
  TrendingDown,
  RefreshCw,
  Percent,
  ChevronLeft,
  ChevronRight
} from 'lucide-react';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '../components/ui/Card';
import { Button } from '../components/ui/Button';

// Helpers for Month Names in Portuguese
const getMonthNameShort = (monthNumber) => {
  const months = [
    'Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun',
    'Jul', 'Ago', 'Set', 'Out', 'Nov', 'Dez'
  ];
  return months[monthNumber - 1] || '';
};

// Utility to format Brazilian Real values
const formatCurrency = (value) => {
  if (value === undefined || value === null) return 'R$ 0,00';
  return new Intl.NumberFormat('pt-BR', {
    style: 'currency',
    currency: 'BRL',
  }).format(value);
};

// Formata porcentagens com sinal
const formatPercentage = (value) => {
  if (value === undefined || value === null) return '0%';
  const num = parseFloat(value);
  const formatted = num.toFixed(1).replace('.', ',');
  return num >= 0 ? `+${formatted}%` : `${formatted}%`;
};

/**
 * Painel de Controle de Finanças Pessoais (Dashboard).
 * 
 * Agrega as métricas cruciais de saúde financeira do mês, contendo resumos de receitas,
 * despesas liquidadas vs. previstas, cartões de crédito e taxa de poupança atual.
 * Renderiza gráficos interativos de fluxo de caixa projetado para apoio em tomadas de decisões.
 *
 * @component
 * @returns {React.JSX.Element} Painel visual composto por cartões de KPIs e gráficos analíticos.
 */
export default function Dashboard() {
  const [periodo, setPeriodo] = useState(0); // 0: Atual, 1: Anterior, 2: Próximo, -1: Customizado
  const [customDate, setCustomDate] = useState(() => {
    const d = new Date();
    return { mes: d.getMonth() + 1, ano: d.getFullYear() };
  });
  const [showDatePicker, setShowDatePicker] = useState(false);
  const [tempDate, setTempDate] = useState(() => {
    const d = new Date();
    return { mes: d.getMonth() + 1, ano: d.getFullYear() };
  });

  // Fetch dashboard data
  const { data, isLoading, isError, refetch, isFetching } = useQuery({
    queryKey: ['dashboard', periodo, periodo === -1 ? customDate : null],
    queryFn: async () => {
      const params = {};
      if (periodo === -1) {
        params.mes = customDate.mes;
        params.ano = customDate.ano;
      } else {
        params.periodo = periodo;
      }
      const response = await api.get('/api/dashboard/', { params });
      return response.data;
    },
  });

  if (isLoading) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[70vh] gap-4">
        <RefreshCw className="h-8 w-8 text-primary animate-spin" />
        <p className="text-sm font-semibold text-slate-500 dark:text-slate-400">
          Carregando dados consolidados...
        </p>
      </div>
    );
  }

  if (isError) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[70vh] gap-4 text-center max-w-md mx-auto">
        <AlertTriangle className="h-12 w-12 text-red-500" />
        <h3 className="text-xl font-bold text-slate-800 dark:text-slate-200">Erro ao carregar dados</h3>
        <p className="text-sm text-slate-500 dark:text-slate-400">
          Não conseguimos nos comunicar com as APIs do backend. Por favor, verifique se os serviços do Docker estão funcionando corretamente.
        </p>
        <Button onClick={() => refetch()} className="mt-2">
          Tentar Novamente
        </Button>
      </div>
    );
  }

  // Extract variables safely
  const {
    total_receitas = 0,
    total_despesas = 0,
    saldo_mes = 0,
    receitas_pct = 0,
    despesas_pct = 0,
    saldo_pct = 0,
    media_gasto_dia = 0,
    taxa_poupanca = null,
    contas_pagas = 0,
    contas_pendentes = 0,
    contas_atrasadas = 0,
    grafico_diario = { labels: [], receitas: [], despesas: [] },
    grafico_projetado = { labels: [], receitas: [], despesas: [], saldos: [] },
    breakdown_despesas = [],
    top_categoria = null,
    proximas_contas = [],
    ultimas_transacoes = [],
  } = data;

  // Configuration for Cash Flow Chart (Daily)
  const dailyChartOptions = {
    chart: {
      type: 'area',
      height: 350,
      toolbar: { show: false },
      fontFamily: 'inherit',
      background: 'transparent',
      animations: { enabled: false },
    },
    colors: ['#007acc', '#f43f5e'],
    dataLabels: { enabled: false },
    stroke: {
      curve: 'smooth',
      width: 2,
    },
    fill: {
      type: 'gradient',
      gradient: {
        shadeIntensity: 1,
        opacityFrom: 0.35,
        opacityTo: 0.02,
        stops: [0, 90, 100],
      },
    },
    xaxis: {
      categories: grafico_diario.labels || [],
      labels: {
        style: { colors: '#888888', fontSize: '10px' },
      },
      axisBorder: { show: false },
      axisTicks: { show: false },
    },
    yaxis: {
      labels: {
        formatter: (val) => formatCurrency(val),
        style: { colors: '#888888', fontSize: '10px' },
      },
    },
    grid: {
      borderColor: 'rgba(148, 163, 184, 0.1)',
      strokeDashArray: 4,
      xaxis: { lines: { show: false } },
    },
    theme: {
      mode: document.documentElement.classList.contains('dark') ? 'dark' : 'light',
    },
    tooltip: {
      theme: document.documentElement.classList.contains('dark') ? 'dark' : 'light',
      y: {
        formatter: (val) => formatCurrency(val),
      },
    },
  };

  const dailyChartSeries = [
    { name: 'Receitas', data: grafico_diario.receitas || [] },
    { name: 'Despesas', data: grafico_diario.despesas || [] },
  ];

  // Configuration for Projected 6 Months Chart
  const projectedChartOptions = {
    chart: {
      type: 'bar',
      height: 350,
      toolbar: { show: false },
      fontFamily: 'inherit',
      background: 'transparent',
      animations: { enabled: false },
    },
    colors: ['#007acc', '#10b981', '#f43f5e'],
    plotOptions: {
      bar: {
        horizontal: false,
        columnWidth: '55%',
        borderRadius: 4,
      },
    },
    dataLabels: { enabled: false },
    xaxis: {
      categories: grafico_projetado.labels || [],
      labels: {
        style: { colors: '#888888', fontSize: '10px' },
      },
    },
    yaxis: {
      labels: {
        formatter: (val) => formatCurrency(val),
        style: { colors: '#888888', fontSize: '10px' },
      },
    },
    grid: {
      borderColor: 'rgba(148, 163, 184, 0.1)',
      strokeDashArray: 4,
    },
    theme: {
      mode: document.documentElement.classList.contains('dark') ? 'dark' : 'light',
    },
    tooltip: {
      theme: document.documentElement.classList.contains('dark') ? 'dark' : 'light',
      y: {
        formatter: (val) => formatCurrency(val),
      },
    },
  };

  const projectedChartSeries = [
    { name: 'Saldo Projetado', data: grafico_projetado.saldos || [] },
    { name: 'Receitas', data: grafico_projetado.receitas || [] },
    { name: 'Despesas', data: grafico_projetado.despesas || [] },
  ];

  return (
    <div className="space-y-8 animate-fade-in">
      
      {/* Top Banner Area */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <div>
          <h1 className="text-3xl font-extrabold tracking-tight text-foreground">
            Seu Painel Financeiro
          </h1>
          <p className="text-muted-foreground mt-1">
            Resumo consolidado para o período selecionado
          </p>
        </div>

        {/* Period Selector & Refresh */}
        <div className="relative flex items-center gap-3 w-full sm:w-auto">
          <div className="flex bg-muted p-1.5 rounded-xl border border-border/40 w-full sm:w-auto">
            <button
              onClick={() => {
                setPeriodo(0);
                setShowDatePicker(false);
              }}
              className={`flex-1 sm:flex-initial px-4 py-1.5 text-xs font-semibold rounded-lg transition-all cursor-pointer
                ${periodo === 0 
                  ? 'bg-card shadow-sm text-primary' 
                  : 'text-muted-foreground hover:text-foreground'
                }
              `}
            >
              Mês Atual
            </button>
            <button
              onClick={() => {
                setPeriodo(1);
                setShowDatePicker(false);
              }}
              className={`flex-1 sm:flex-initial px-4 py-1.5 text-xs font-semibold rounded-lg transition-all cursor-pointer
                ${periodo === 1 
                  ? 'bg-card shadow-sm text-primary' 
                  : 'text-muted-foreground hover:text-foreground'
                }
              `}
            >
              Mês Anterior
            </button>
            <button
              onClick={() => {
                setPeriodo(2);
                setShowDatePicker(false);
              }}
              className={`flex-1 sm:flex-initial px-4 py-1.5 text-xs font-semibold rounded-lg transition-all cursor-pointer
                ${periodo === 2 
                  ? 'bg-card shadow-sm text-primary' 
                  : 'text-muted-foreground hover:text-foreground'
                }
              `}
            >
              Próximo Mês
            </button>
            <button
              onClick={() => {
                setTempDate(periodo === -1 ? customDate : { mes: new Date().getMonth() + 1, ano: new Date().getFullYear() });
                setShowDatePicker(!showDatePicker);
              }}
              className={`flex-1 sm:flex-initial px-4 py-1.5 text-xs font-semibold rounded-lg transition-all cursor-pointer
                ${periodo === -1 
                  ? 'bg-card shadow-sm text-primary' 
                  : 'text-muted-foreground hover:text-foreground'
                }
              `}
            >
              {periodo === -1 ? `${getMonthNameShort(customDate.mes)}/${customDate.ano}` : 'Personalizado...'}
            </button>
          </div>

          {showDatePicker && (
            <>
              <div 
                className="fixed inset-0 z-40 bg-transparent" 
                onClick={() => setShowDatePicker(false)} 
              />
              <div className="absolute right-12 top-full mt-2 z-50 w-72 bg-card border border-border shadow-xl rounded-2xl p-4 animate-in fade-in slide-in-from-top-2 duration-150">
                <div className="flex flex-col gap-4">
                  <div className="flex items-center justify-between pb-2 border-b border-border/40">
                    <span className="text-xs font-bold text-foreground">
                      Selecione o Período
                    </span>
                    <div className="flex items-center gap-3">
                      <button 
                        onClick={() => setTempDate(prev => ({ ...prev, ano: prev.ano - 1 }))}
                        className="p-1 rounded hover:bg-muted text-muted-foreground hover:text-foreground transition-colors cursor-pointer"
                        title="Ano Anterior"
                      >
                        <ChevronLeft className="h-4 w-4" />
                      </button>
                      <span className="text-xs font-bold text-foreground font-mono select-none">
                        {tempDate.ano}
                      </span>
                      <button 
                        onClick={() => setTempDate(prev => ({ ...prev, ano: prev.ano + 1 }))}
                        className="p-1 rounded hover:bg-muted text-muted-foreground hover:text-foreground transition-colors cursor-pointer"
                        title="Próximo Ano"
                      >
                        <ChevronRight className="h-4 w-4" />
                      </button>
                    </div>
                  </div>

                  <div className="grid grid-cols-3 gap-2">
                    {Array.from({ length: 12 }, (_, i) => i + 1).map((m) => {
                      const isSelected = tempDate.mes === m;
                      return (
                        <button
                          key={m}
                          onClick={() => setTempDate(prev => ({ ...prev, mes: m }))}
                          className={`py-1.5 text-xs font-medium rounded-lg transition-all cursor-pointer
                            ${isSelected 
                              ? 'bg-primary text-primary-foreground font-bold shadow-sm' 
                              : 'text-muted-foreground hover:bg-muted hover:text-foreground'
                            }
                          `}
                        >
                          {getMonthNameShort(m)}
                        </button>
                      );
                    })}
                  </div>

                  <div className="flex items-center gap-2 pt-2 border-t border-border/40">
                    <button
                      onClick={() => setShowDatePicker(false)}
                      className="flex-1 py-1.5 text-xs font-semibold rounded-lg border border-border/40 hover:bg-muted text-muted-foreground transition-all cursor-pointer"
                    >
                      Cancelar
                    </button>
                    <button
                      onClick={() => {
                        setCustomDate(tempDate);
                        setPeriodo(-1);
                        setShowDatePicker(false);
                      }}
                      className="flex-1 py-1.5 text-xs font-semibold rounded-lg bg-primary text-primary-foreground hover:bg-primary/90 transition-all shadow-sm cursor-pointer"
                    >
                      Confirmar
                    </button>
                  </div>
                </div>
              </div>
            </>
          )}
          
          <Button
            variant="outline"
            size="icon"
            onClick={() => refetch()}
            className="rounded-xl h-9 w-9 shrink-0"
            disabled={isFetching}
          >
            <RefreshCw className={`h-4 w-4 text-muted-foreground ${isFetching ? 'animate-spin' : ''}`} />
          </Button>
        </div>
      </div>

      {/* KPI Cards Grid */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        
        {/* Receitas Card */}
        <Card className="border-border/40 shadow-sm relative overflow-hidden group">
          <div className="absolute top-0 right-0 w-24 h-24 bg-primary/5 rounded-full blur-2xl pointer-events-none group-hover:bg-primary/10 transition-all duration-300" />
          <CardHeader className="pb-2">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                Faturamento / Receitas
              </span>
              <div className="w-8 h-8 rounded-lg bg-primary/10 flex items-center justify-center">
                <ArrowUpRight className="h-4.5 w-4.5 text-primary" />
              </div>
            </div>
          </CardHeader>
          <CardContent>
            <h3 className="text-2xl font-bold tracking-tight text-foreground">
              {formatCurrency(total_receitas)}
            </h3>
            <div className="flex items-center gap-1.5 mt-2">
              <span className={`inline-flex items-center text-[11px] font-semibold rounded px-1.5 py-0.5
                ${receitas_pct >= 0 
                  ? 'bg-primary/10 text-primary' 
                  : 'bg-rose-500/10 text-rose-600'
                }
              `}>
                {formatPercentage(receitas_pct)}
              </span>
              <span className="text-[10px] text-muted-foreground">vs mês anterior</span>
            </div>
          </CardContent>
        </Card>

        {/* Despesas Card */}
        <Card className="border-border/40 shadow-sm relative overflow-hidden group">
          <div className="absolute top-0 right-0 w-24 h-24 bg-rose-500/5 rounded-full blur-2xl pointer-events-none group-hover:bg-rose-500/10 transition-all duration-300" />
          <CardHeader className="pb-2">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                Custos / Despesas
              </span>
              <div className="w-8 h-8 rounded-lg bg-rose-500/10 flex items-center justify-center">
                <ArrowDownRight className="h-4.5 w-4.5 text-rose-500" />
              </div>
            </div>
          </CardHeader>
          <CardContent>
            <h3 className="text-2xl font-bold tracking-tight text-foreground">
              {formatCurrency(total_despesas)}
            </h3>
            <div className="flex items-center gap-1.5 mt-2">
              <span className={`inline-flex items-center text-[11px] font-semibold rounded px-1.5 py-0.5
                ${despesas_pct <= 0 
                  ? 'bg-primary/10 text-primary' 
                  : 'bg-rose-500/10 text-rose-600'
                }
              `}>
                {formatPercentage(despesas_pct)}
              </span>
              <span className="text-[10px] text-muted-foreground">vs mês anterior</span>
            </div>
          </CardContent>
        </Card>

        {/* Saldo Líquido Card */}
        <Card className="border-border/40 shadow-sm relative overflow-hidden group">
          <div className="absolute top-0 right-0 w-24 h-24 bg-teal-500/5 rounded-full blur-2xl pointer-events-none group-hover:bg-teal-500/10 transition-all duration-300" />
          <CardHeader className="pb-2">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                Saldo / Resultado
              </span>
              <div className="w-8 h-8 rounded-lg bg-teal-500/10 flex items-center justify-center">
                <Wallet className="h-4.5 w-4.5 text-teal-500" />
              </div>
            </div>
          </CardHeader>
          <CardContent>
            <h3 className="text-2xl font-bold tracking-tight text-foreground">
              {formatCurrency(saldo_mes)}
            </h3>
            <div className="flex items-center gap-1.5 mt-2">
              <span className={`inline-flex items-center text-[11px] font-semibold rounded px-1.5 py-0.5
                ${saldo_mes >= 0 
                  ? 'bg-primary/10 text-primary' 
                  : 'bg-rose-500/10 text-rose-600'
                }
              `}>
                {formatPercentage(saldo_pct)}
              </span>
              <span className="text-[10px] text-muted-foreground">taxa de poupança: {typeof taxa_poupanca === 'number' ? `${taxa_poupanca.toFixed(1).replace('.', ',')}%` : 'N/A'}</span>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Main Charts & Breakdown Section */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        
        {/* Area Flow Chart */}
        <Card className="lg:col-span-2 border-border/40 shadow-sm">
          <CardHeader className="flex flex-row items-center justify-between">
            <div>
              <CardTitle className="text-base font-bold text-foreground">
                Fluxo de Caixa Mensal
              </CardTitle>
              <CardDescription className="text-xs">
                Entradas e saídas mapeadas por dia de competência
              </CardDescription>
            </div>
            <div className="flex items-center gap-1.5 text-xs text-muted-foreground font-semibold px-2.5 py-1 rounded bg-muted border border-border/40">
              <Calendar className="h-3.5 w-3.5" />
              <span>{data.periodo_label}</span>
            </div>
          </CardHeader>
          <CardContent>
            {grafico_diario?.labels?.length > 0 ? (
              <Chart
                key={`daily-${periodo}-${customDate.mes}-${customDate.ano}`}
                options={dailyChartOptions}
                series={dailyChartSeries}
                type="area"
                height={320}
              />
            ) : (
              <div className="flex h-[320px] items-center justify-center text-xs text-muted-foreground font-medium">
                Carregando dados do gráfico...
              </div>
            )}
          </CardContent>
        </Card>

        {/* Expenses Category Breakdown */}
        <Card className="border-border/40 shadow-sm">
          <CardHeader>
            <CardTitle className="text-base font-bold text-foreground">
              Maiores Gastos
            </CardTitle>
            <CardDescription className="text-xs">
              Detalhamento de categorias com maior peso no mês
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-5">
            {breakdown_despesas && breakdown_despesas.length > 0 ? (
              breakdown_despesas.map((item, idx) => (
                <div key={idx} className="space-y-1.5">
                  <div className="flex items-center justify-between text-xs font-semibold">
                    <span className="text-foreground font-medium">
                      {item.nome}
                    </span>
                    <span className="text-foreground font-bold">
                      {formatCurrency(item.valor)} ({(parseFloat(item.pct) || 0).toFixed(1).replace('.', ',')}%)
                    </span>
                  </div>
                  {/* Custom animated progress bar */}
                  <div className="w-full h-2 bg-muted rounded-full overflow-hidden border border-border/40">
                    <div 
                      className="h-full bg-primary rounded-full transition-all duration-500" 
                      style={{ width: `${Math.min(item.pct || 0, 100)}%` }}
                    />
                  </div>
                </div>
              ))
            ) : (
              <div className="flex flex-col items-center justify-center py-10 text-center gap-2 text-muted-foreground">
                <CheckCircle2 className="h-8 w-8 text-muted-foreground/60" />
                <p className="text-xs font-medium">Nenhum custo registrado para o período.</p>
              </div>
            )}

            {/* Quick Metrics */}
            <div className="pt-4 border-t border-border/40 space-y-3.5">
              <div className="flex items-center justify-between text-xs">
                <span className="text-muted-foreground font-medium">Gasto médio diário</span>
                <span className="font-bold text-foreground">
                  {formatCurrency(media_gasto_dia)}
                </span>
              </div>
              <div className="flex items-center justify-between text-xs">
                <span className="text-muted-foreground font-medium">Maior foco de custos</span>
                <span className="font-bold text-teal-500">
                  {top_categoria?.nome || 'Nenhum'}
                </span>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Bill Status & Projections Section */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        
        {/* Bill Status Check Widget */}
        <Card className="border-border/40 shadow-sm">
          <CardHeader>
            <CardTitle className="text-base font-bold text-foreground">
              Status de Despesas do Mês
            </CardTitle>
            <CardDescription className="text-xs">
              Acompanhamento de pagamentos planejados
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-3 gap-3">
              <div className="flex flex-col items-center justify-center p-3 rounded-xl bg-primary/10 border border-primary/20">
                <span className="text-primary font-extrabold text-xl">{contas_pagas}</span>
                <span className="text-[10px] font-semibold text-primary/80 uppercase tracking-wider mt-1 text-center">Pagas</span>
              </div>
              <div className="flex flex-col items-center justify-center p-3 rounded-xl bg-amber-500/10 border border-amber-500/20">
                <span className="text-amber-500 font-extrabold text-xl">{contas_pendentes}</span>
                <span className="text-[10px] font-semibold text-amber-600 uppercase tracking-wider mt-1 text-center">Pendentes</span>
              </div>
              <div className="flex flex-col items-center justify-center p-3 rounded-xl bg-rose-500/10 border border-rose-500/20">
                <span className="text-rose-500 font-extrabold text-xl">{contas_atrasadas}</span>
                <span className="text-[10px] font-semibold text-rose-600 uppercase tracking-wider mt-1 text-center font-bold animate-pulse">Atrasadas</span>
              </div>
            </div>
            
            <div className="flex items-center justify-between text-xs bg-muted border border-border/40 rounded-xl p-3.5">
              <div className="flex items-center gap-2 text-muted-foreground font-medium">
                <Clock className="h-4 w-4 text-primary" />
                <span>Atualização silenciosa</span>
              </div>
              <span className="font-semibold text-foreground">100% Sincronizado</span>
            </div>
          </CardContent>
        </Card>

        {/* Projected 6 Months Chart */}
        <Card className="lg:col-span-2 border-border/40 shadow-sm">
          <CardHeader>
            <CardTitle className="text-base font-bold text-foreground">
              Fluxo Projetado (6 Meses)
            </CardTitle>
            <CardDescription className="text-xs">
              Simulação de receitas, despesas e saldos para os próximos períodos
            </CardDescription>
          </CardHeader>
          <CardContent>
            {grafico_projetado?.labels?.length > 0 ? (
              <Chart
                key={`proj-${periodo}-${customDate.mes}-${customDate.ano}`}
                options={projectedChartOptions}
                series={projectedChartSeries}
                type="bar"
                height={260}
              />
            ) : (
              <div className="flex h-[260px] items-center justify-center text-xs text-muted-foreground font-medium">
                Carregando projeções...
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Lists of Transactions / Upcoming Bills */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        
        {/* Upcoming Bills List */}
        <Card className="border-border/40 shadow-sm">
          <CardHeader>
            <CardTitle className="text-base font-bold text-foreground">
              Próximos Vencimentos
            </CardTitle>
            <CardDescription className="text-xs">
              Próximas despesas planejadas no sistema
            </CardDescription>
          </CardHeader>
          <CardContent className="px-0">
            <div className="overflow-x-auto font-sans">
              <table className="w-full text-xs text-left border-collapse">
                <thead>
                  <tr className="border-b border-border/40 text-muted-foreground font-semibold">
                    <th className="px-6 py-3 font-semibold text-muted-foreground">Descrição</th>
                    <th className="px-6 py-3 font-semibold text-muted-foreground">Categoria</th>
                    <th className="px-6 py-3 font-semibold text-muted-foreground">Vencimento</th>
                    <th className="px-6 py-3 font-semibold text-muted-foreground text-right">Valor</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border/40">
                  {proximas_contas && proximas_contas.length > 0 ? (
                    proximas_contas.map((conta, idx) => (
                      <tr key={idx} className="hover:bg-muted/30 transition-colors">
                        <td className="px-6 py-3.5 font-medium text-foreground">
                          {conta.descricao}
                        </td>
                        <td className="px-6 py-3.5 text-muted-foreground">
                          {conta.categoria_nome || 'Sem Categoria'}
                        </td>
                        <td className="px-6 py-3.5 text-muted-foreground font-semibold">
                          {new Date(conta.data_prevista + 'T12:00:00').toLocaleDateString('pt-BR')}
                        </td>
                        <td className="px-6 py-3.5 text-right font-bold text-rose-600 dark:text-rose-400">
                          {formatCurrency(conta.valor)}
                        </td>
                      </tr>
                    ))
                  ) : (
                    <tr>
                      <td colSpan="4" className="px-6 py-8 text-center text-muted-foreground">
                        Nenhuma conta pendente para os próximos dias!
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>

        {/* Recent Transactions List */}
        <Card className="border-border/40 shadow-sm">
          <CardHeader>
            <CardTitle className="text-base font-bold text-foreground">
              Histórico Recente (Caixa)
            </CardTitle>
            <CardDescription className="text-xs">
              Últimos lançamentos liquidados e efetivados
            </CardDescription>
          </CardHeader>
          <CardContent className="px-0">
            <div className="overflow-x-auto font-sans">
              <table className="w-full text-xs text-left border-collapse">
                <thead>
                  <tr className="border-b border-border/40 text-muted-foreground font-semibold">
                    <th className="px-6 py-3 font-semibold text-muted-foreground">Descrição</th>
                    <th className="px-6 py-3 font-semibold text-muted-foreground">Categoria</th>
                    <th className="px-6 py-3 font-semibold text-muted-foreground">Data</th>
                    <th className="px-6 py-3 font-semibold text-muted-foreground text-right">Valor</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border/40">
                  {ultimas_transacoes && ultimas_transacoes.length > 0 ? (
                    ultimas_transacoes.map((trans, idx) => {
                      const isReceita = trans.tipo === 'R';
                      return (
                        <tr key={idx} className="hover:bg-muted/30 transition-colors">
                          <td className="px-6 py-3.5 font-medium text-foreground">
                            {trans.descricao}
                          </td>
                          <td className="px-6 py-3.5 text-muted-foreground">
                            {trans.categoria_nome || 'Sem Categoria'}
                          </td>
                          <td className="px-6 py-3.5 text-muted-foreground font-semibold">
                            {new Date(trans.data_realizacao + 'T12:00:00').toLocaleDateString('pt-BR')}
                          </td>
                          <td className={`px-6 py-3.5 text-right font-bold ${isReceita ? 'text-primary' : 'text-rose-600 dark:text-rose-400'}`}>
                            {isReceita ? '+' : '-'}{formatCurrency(trans.valor)}
                          </td>
                        </tr>
                      );
                    })
                  ) : (
                    <tr>
                      <td colSpan="4" className="px-6 py-8 text-center text-muted-foreground">
                        Nenhum histórico de caixa recente liquidado.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      </div>

    </div>
  );
}
