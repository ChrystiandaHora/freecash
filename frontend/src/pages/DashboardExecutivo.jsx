/**
 * Painel BI Executivo Patrimonial (Dashboard Executivo).
 * 
 * Centraliza e consolida as métricas financeiras operacionais (fluxo de caixa pessoal)
 * e o patrimônio acumulado (carteira de investimentos) de forma histórica.
 * Oferece visualizações em nível profissional de evolução de Net Worth (Patrimônio Líquido Real),
 * variação mensal e tabelas de fluxo e saving rate no estilo clássico do Power BI.
 *
 * @component
 * @returns {React.JSX.Element} Painel executivo analítico.
 */
import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import api from '../services/api';
import Chart from 'react-apexcharts';
import { 
  TrendingUp, 
  TrendingDown, 
  Wallet, 
  Gem, 
  Percent, 
  RefreshCw,
  AlertCircle,
  ArrowUpRight,
  ArrowDownRight,
  Coins
} from 'lucide-react';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '../components/ui/Card';
import { Button } from '../components/ui/Button';

// Utility to format currency values (BRL)
const formatCurrency = (value) => {
  if (value === undefined || value === null) return 'R$ 0,00';
  return new Intl.NumberFormat('pt-BR', {
    style: 'currency',
    currency: 'BRL',
  }).format(value);
};

// Utility to format saving rates or percentages
const formatPercentage = (value) => {
  if (value === undefined || value === null) return '0%';
  const num = parseFloat(value);
  const formatted = num.toFixed(1).replace('.', ',');
  return num >= 0 ? `+${formatted}%` : `${formatted}%`;
};

export default function DashboardExecutivo() {
  const [mesesFiltro, setMesesFiltro] = useState(12);

  const { data, isLoading, isError, refetch, isFetching } = useQuery({
    queryKey: ['dashboardExecutivo', mesesFiltro],
    queryFn: async () => {
      const response = await api.get(`/api/dashboard/executivo/?meses=${mesesFiltro}`);
      return response.data;
    },
  });

  if (isLoading) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[70vh] gap-4">
        <RefreshCw className="h-8 w-8 text-primary animate-spin" />
        <p className="text-sm font-semibold text-slate-500 dark:text-slate-400">
          Consolidando dados executivos e BI...
        </p>
      </div>
    );
  }

  if (isError) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[70vh] gap-4 text-center max-w-md mx-auto">
        <AlertCircle className="h-12 w-12 text-red-500" />
        <h3 className="text-xl font-bold text-slate-800 dark:text-slate-200">Erro ao processar dados de BI</h3>
        <p className="text-sm text-slate-500 dark:text-slate-400">
          Não conseguimos carregar as métricas do painel executivo. Certifique-se de que o backend esteja operando corretamente.
        </p>
        <Button onClick={() => refetch()} className="mt-2">
          Recarregar Painel
        </Button>
      </div>
    );
  }

  const {
    meses = [],
    liquidez = [],
    custodia = [],
    patrimonio_liquido = [],
    evolucao_mensal = [],
    tabela_dre = [],
    proventos_acumulados = [],
    kpis = { total_liquidez: 0, total_custodia: 0, total_patrimonio_liquido: 0, saving_rate_medio: 0 }
  } = data;

  // Chart 1: Net Worth Evolution Trend (Area Chart)
  const netWorthChartOptions = {
    chart: {
      type: 'area',
      height: 350,
      toolbar: { show: true, tools: { download: true, selection: false, zoom: false, zoomin: false, zoomout: false, pan: false, reset: false } },
      fontFamily: 'inherit',
      background: 'transparent',
      animations: { enabled: false },
    },
    colors: ['#3b82f6', '#10b981', '#f59e0b'], // Net Worth, Custodia, Liquidez
    dataLabels: { enabled: false },
    stroke: {
      curve: 'smooth',
      width: [3, 2, 2],
      dashArray: [0, 0, 4]
    },
    fill: {
      type: 'gradient',
      gradient: {
        shadeIntensity: 1,
        opacityFrom: [0.25, 0.15, 0.05],
        opacityTo: [0.01, 0.01, 0.01],
        stops: [0, 90, 100],
      },
    },
    xaxis: {
      categories: meses,
      labels: {
        style: { colors: '#888888', fontSize: '11px', fontWeight: 500 },
      },
      axisBorder: { show: false },
      axisTicks: { show: false },
    },
    yaxis: {
      labels: {
        formatter: (val) => formatCurrency(val),
        style: { colors: '#888888', fontSize: '11px', fontWeight: 500 },
      },
    },
    grid: {
      borderColor: 'rgba(148, 163, 184, 0.08)',
      strokeDashArray: 4,
      xaxis: { lines: { show: false } },
    },
    theme: {
      mode: document.documentElement.classList.contains('dark') ? 'dark' : 'light',
    },
    legend: {
      position: 'top',
      horizontalAlign: 'right',
      fontSize: '12px',
      labels: { colors: '#888888' },
      markers: { radius: 12 }
    },
    tooltip: {
      theme: document.documentElement.classList.contains('dark') ? 'dark' : 'light',
      y: {
        formatter: (val) => formatCurrency(val),
      },
    },
  };

  const netWorthChartSeries = [
    { name: 'Patrimônio Líquido Real', data: patrimonio_liquido },
    { name: 'Custódia (Investimentos)', data: custodia },
    { name: 'Liquidez Física (Caixa)', data: liquidez }
  ];

  // Chart 2: Net Worth Delta Monthly Change (Bar Chart)
  const deltaChartOptions = {
    chart: {
      type: 'bar',
      height: 350,
      toolbar: { show: false },
      fontFamily: 'inherit',
      background: 'transparent',
      animations: { enabled: false },
    },
    colors: ['#10b981'],
    plotOptions: {
      bar: {
        colors: {
          ranges: [{
            from: -999999999,
            to: 0,
            color: '#f43f5e'
          }]
        },
        columnWidth: '60%',
        borderRadius: 4,
      }
    },
    dataLabels: { enabled: false },
    xaxis: {
      categories: meses,
      labels: {
        style: { colors: '#888888', fontSize: '11px', fontWeight: 500 },
      },
    },
    yaxis: {
      labels: {
        formatter: (val) => formatCurrency(val),
        style: { colors: '#888888', fontSize: '11px', fontWeight: 500 },
      },
    },
    grid: {
      borderColor: 'rgba(148, 163, 184, 0.08)',
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

  const deltaChartSeries = [
    { name: 'Variação Líquida', data: evolucao_mensal }
  ];

  // Cálculos para o gráfico de Cascata (Waterfall) de Fluxo Patrimonial Consolidado (12m)
  const totalReceitasDRE = (tabela_dre || []).reduce((sum, row) => sum + row.receitas, 0);
  const totalDespesasDRE = (tabela_dre || []).reduce((sum, row) => sum + row.despesas, 0);
  const totalAportesDRE = (tabela_dre || []).reduce((sum, row) => sum + row.aportes, 0);
  const acumuladoFinalDRE = totalReceitasDRE - totalDespesasDRE - totalAportesDRE;

  const waterfallChartSeries = [{
    name: 'Fluxo Patrimonial',
    data: [
      { x: 'Receitas (+)', y: [0, totalReceitasDRE] },
      { x: 'Despesas (-)', y: [totalReceitasDRE, totalReceitasDRE - totalDespesasDRE] },
      { x: 'Aportes (-)', y: [totalReceitasDRE - totalDespesasDRE, totalReceitasDRE - totalDespesasDRE - totalAportesDRE] },
      { x: 'Saldo Real (=)', y: [0, acumuladoFinalDRE] }
    ]
  }];

  const waterfallChartOptions = {
    chart: {
      type: 'bar',
      height: 320,
      toolbar: { show: false },
      fontFamily: 'inherit',
      background: 'transparent',
      animations: { enabled: false }
    },
    colors: ['#3b82f6'],
    plotOptions: {
      bar: {
        columnWidth: '50%',
        colors: {
          ranges: [{
            from: -999999999,
            to: 999999999,
            color: '#3b82f6'
          }]
        }
      }
    },
    dataLabels: {
      enabled: true,
      formatter: (val) => {
        if (Array.isArray(val)) {
          const diff = val[1] - val[0];
          return formatCurrency(diff);
        }
        return '';
      },
      style: {
        fontSize: '10px',
        fontWeight: 'bold',
        colors: ['#ffffff']
      }
    },
    xaxis: {
      type: 'category',
      labels: {
        style: { colors: '#888888', fontSize: '11px', fontWeight: 500 }
      }
    },
    yaxis: {
      labels: {
        formatter: (val) => formatCurrency(val),
        style: { colors: '#888888', fontSize: '11px', fontWeight: 500 }
      }
    },
    grid: {
      borderColor: 'rgba(148, 163, 184, 0.08)',
      strokeDashArray: 4,
    },
    theme: {
      mode: document.documentElement.classList.contains('dark') ? 'dark' : 'light',
    },
    tooltip: {
      theme: document.documentElement.classList.contains('dark') ? 'dark' : 'light',
      custom: function({ series, seriesIndex, dataPointIndex, w }) {
        const val = w.config.series[seriesIndex].data[dataPointIndex].y;
        const label = w.config.series[seriesIndex].data[dataPointIndex].x;
        const diff = val[1] - val[0];
        
        let colorClass = 'text-primary';
        if (label.includes('Despesa')) colorClass = 'text-rose-500';
        else if (label.includes('Aporte')) colorClass = 'text-amber-500';
        else if (label.includes('Receita')) colorClass = 'text-emerald-500';

        return `<div class="p-3 text-xs bg-card border border-border/50 shadow-xl rounded-xl">` +
          `<span class="font-bold text-foreground block mb-1.5">${label}</span>` +
          `<span class="text-muted-foreground font-semibold">Valor Total: </span>` +
          `<span class="font-black ${colorClass}">${formatCurrency(diff)}</span>` +
          `</div>`;
      }
    }
  };

  // Chart 4: Cumulative Passive Income (Snowball Chart)
  const snowballChartOptions = {
    chart: {
      type: 'area',
      height: 320,
      toolbar: { show: false },
      fontFamily: 'inherit',
      background: 'transparent',
      animations: { enabled: true },
    },
    colors: ['#a855f7'], // Indigo/Purple color for the passive income snowball
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
      categories: meses,
      labels: {
        style: { colors: '#888888', fontSize: '11px', fontWeight: 500 },
      },
      axisBorder: { show: false },
      axisTicks: { show: false },
    },
    yaxis: {
      labels: {
        formatter: (val) => formatCurrency(val),
        style: { colors: '#888888', fontSize: '11px', fontWeight: 500 },
      },
    },
    grid: {
      borderColor: 'rgba(148, 163, 184, 0.08)',
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

  const snowballChartSeries = [
    { name: 'Renda Passiva Acumulada', data: proventos_acumulados }
  ];

  return (
    <div className="space-y-8 animate-fade-in font-sans">
      
      {/* ── HEADER ── */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <div>
          <h1 className="text-3xl font-extrabold tracking-tight text-foreground flex items-center gap-2">
            <Coins className="h-8 w-8 text-primary" />
            Dashboard Executivo BI
          </h1>
          <p className="text-muted-foreground mt-1">
            Consolidação analítica de fluxo operacional e evolução patrimonial estilo Power BI
          </p>
        </div>

        <div className="flex items-center gap-3">
          {/* Period selector */}
          <div className="flex items-center gap-1 bg-muted rounded-xl p-1 border border-border/40 shrink-0">
            {[
              { val: 3, label: '3m' },
              { val: 6, label: '6m' },
              { val: 12, label: '12m' },
              { val: 24, label: '24m' },
              { val: 'all', label: 'Tudo' }
            ].map((p) => (
              <button
                key={p.val}
                onClick={() => setMesesFiltro(p.val)}
                className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-all cursor-pointer
                  ${mesesFiltro === p.val ? 'bg-card text-primary shadow-sm' : 'text-muted-foreground hover:text-foreground'}`}
              >
                {p.label}
              </button>
            ))}
          </div>

          <Button
            variant="outline"
            size="icon"
            onClick={() => refetch()}
            disabled={isFetching}
            className="rounded-xl h-9 w-9 shrink-0"
          >
            <RefreshCw className={`h-4 w-4 text-muted-foreground ${isFetching ? 'animate-spin' : ''}`} />
          </Button>
        </div>
      </div>

      {/* ── KPI INDICATORS GRID ── */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
        
        {/* Total Net Worth */}
        <Card className="bg-card border border-border/40 shadow-sm relative overflow-hidden group">
          <div className="absolute top-0 right-0 w-24 h-24 bg-primary/5 rounded-full blur-2xl pointer-events-none group-hover:bg-primary/10 transition-all duration-300" />
          <CardHeader className="pb-2">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                Patrimônio Líquido Real
              </span>
              <div className="w-8 h-8 rounded-lg bg-primary/10 flex items-center justify-center">
                <TrendingUp className="h-4.5 w-4.5 text-primary" />
              </div>
            </div>
          </CardHeader>
          <CardContent>
            <h3 className="text-2xl font-black tracking-tight text-foreground">
              {formatCurrency(kpis.total_patrimonio_liquido)}
            </h3>
            <p className="text-[10px] text-muted-foreground mt-2 font-medium">
              Soma total: Caixa físico + Investimentos
            </p>
          </CardContent>
        </Card>

        {/* Custody Value */}
        <Card className="bg-card border border-border/40 shadow-sm relative overflow-hidden group">
          <div className="absolute top-0 right-0 w-24 h-24 bg-emerald-500/5 rounded-full blur-2xl pointer-events-none group-hover:bg-emerald-500/10 transition-all duration-300" />
          <CardHeader className="pb-2">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                Custódia (Bolsa)
              </span>
              <div className="w-8 h-8 rounded-lg bg-emerald-500/10 flex items-center justify-center">
                <Gem className="h-4.5 w-4.5 text-emerald-500" />
              </div>
            </div>
          </CardHeader>
          <CardContent>
            <h3 className="text-2xl font-black tracking-tight text-emerald-500">
              {formatCurrency(kpis.total_custodia)}
            </h3>
            <p className="text-[10px] text-muted-foreground mt-2 font-medium">
              Avaliação de mercado de ativos custodiados
            </p>
          </CardContent>
        </Card>

        {/* Bank Liquidity */}
        <Card className="bg-card border border-border/40 shadow-sm relative overflow-hidden group">
          <div className="absolute top-0 right-0 w-24 h-24 bg-amber-500/5 rounded-full blur-2xl pointer-events-none group-hover:bg-amber-500/10 transition-all duration-300" />
          <CardHeader className="pb-2">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                Liquidez Física
              </span>
              <div className="w-8 h-8 rounded-lg bg-amber-500/10 flex items-center justify-center">
                <Wallet className="h-4.5 w-4.5 text-amber-500" />
              </div>
            </div>
          </CardHeader>
          <CardContent>
            <h3 className="text-2xl font-black tracking-tight text-foreground">
              {formatCurrency(kpis.total_liquidez)}
            </h3>
            <p className="text-[10px] text-muted-foreground mt-2 font-medium">
              Saldos disponíveis em contas bancárias
            </p>
          </CardContent>
        </Card>

        {/* Saving Rate */}
        <Card className="bg-card border border-border/40 shadow-sm relative overflow-hidden group">
          <div className="absolute top-0 right-0 w-24 h-24 bg-teal-500/5 rounded-full blur-2xl pointer-events-none group-hover:bg-teal-500/10 transition-all duration-300" />
          <CardHeader className="pb-2">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                Saving Rate Médio
              </span>
              <div className="w-8 h-8 rounded-lg bg-teal-500/10 flex items-center justify-center">
                <Percent className="h-4.5 w-4.5 text-teal-500" />
              </div>
            </div>
          </CardHeader>
          <CardContent>
            <h3 className="text-2xl font-black tracking-tight text-teal-500">
              {formatPercentage(kpis.saving_rate_medio)}
            </h3>
            <p className="text-[10px] text-muted-foreground mt-2 font-medium">
              Taxa média de poupança dos últimos 12m
            </p>
          </CardContent>
        </Card>
      </div>

      {/* ── CHARTS ROW ── */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        
        {/* Net Worth Area Trend */}
        <Card className="lg:col-span-2 bg-card border border-border/40 shadow-sm">
          <CardHeader>
            <CardTitle className="text-base font-bold text-foreground">
              Evolução Patrimonial Cumulativa
            </CardTitle>
            <CardDescription className="text-xs">
              Curva histórica mostrando o crescimento real do patrimônio líquido vs. caixa e custódia
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Chart
              key={`net-worth-trend-${meses.join('-')}`}
              options={netWorthChartOptions}
              series={netWorthChartSeries}
              type="area"
              height={320}
            />
          </CardContent>
        </Card>

        {/* Delta Net Worth Bar */}
        <Card className="bg-card border border-border/40 shadow-sm">
          <CardHeader>
            <CardTitle className="text-base font-bold text-foreground">
              Variação Líquida Mensal
            </CardTitle>
            <CardDescription className="text-xs">
              Aumento ou redução do valor líquido real a cada período
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Chart
              key={`delta-nw-${meses.join('-')}`}
              options={deltaChartOptions}
              series={deltaChartSeries}
              type="bar"
              height={320}
            />
          </CardContent>
        </Card>
      </div>

      {/* Waterfall & Snowball Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card className="bg-card border border-border/40 shadow-sm text-card-foreground">
          <CardHeader>
            <CardTitle className="text-base font-bold text-foreground">
              Cascata de Transição do Fluxo Patrimonial (12m)
            </CardTitle>
            <CardDescription className="text-xs">
              Representação visual das receitas totais sendo reduzidas por despesas e aportes até as sobras líquidas reais
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Chart
              key={`waterfall-${meses.join('-')}`}
              options={waterfallChartOptions}
              series={waterfallChartSeries}
              type="bar"
              height={320}
            />
          </CardContent>
        </Card>

        <Card className="bg-card border border-border/40 shadow-sm text-card-foreground">
          <CardHeader>
            <CardTitle className="text-base font-bold text-foreground">
              Efeito Bola de Neve (Renda Passiva Acumulada)
            </CardTitle>
            <CardDescription className="text-xs">
              Crescimento exponencial dos dividendos e proventos recebidos e acumulados ao longo do tempo
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Chart
              key={`snowball-${meses.join('-')}`}
              options={snowballChartOptions}
              series={snowballChartSeries}
              type="area"
              height={320}
            />
          </CardContent>
        </Card>
      </div>

      {/* ── BI DATA MATRIX TABLE ── */}
      <Card className="bg-card border border-border/40 shadow-sm">
        <CardHeader>
          <CardTitle className="text-base font-bold text-foreground">
            Matriz de Performance e Saving Rate
          </CardTitle>
          <CardDescription className="text-xs">
            Visão financeira resumida e taxa de acumulação mensal (DRE operacional + investimentos)
          </CardDescription>
        </CardHeader>
        <CardContent className="px-0 pb-0">
          <div className="overflow-x-auto">
            <table className="w-full text-xs text-left border-collapse">
              <thead>
                <tr className="border-b border-border bg-muted/30 font-bold text-muted-foreground uppercase tracking-wider text-[10px]">
                  <th className="px-6 py-3.5">Mês</th>
                  <th className="px-6 py-3.5 text-right">Faturamento (R$)</th>
                  <th className="px-6 py-3.5 text-right">Despesas (R$)</th>
                  <th className="px-6 py-3.5 text-right">Balanço Caixa (R$)</th>
                  <th className="px-6 py-3.5 text-right">Aportes (Investimentos)</th>
                  <th className="px-6 py-3.5 text-right">Taxa Poupança</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border/30">
                {tabela_dre.map((row, idx) => {
                  const isPosBalanço = row.saldo >= 0;
                  const isPosAportes = row.aportes >= 0;
                  const savingRate = row.receitas > 0 ? (row.saldo / row.receitas) * 100 : 0;
                  return (
                    <tr key={idx} className="hover:bg-muted/20 transition-colors font-medium">
                      <td className="px-6 py-3.5 font-bold text-foreground">
                        {row.mes}
                      </td>
                      <td className="px-6 py-3.5 text-right text-foreground/80">
                        {formatCurrency(row.receitas)}
                      </td>
                      <td className="px-6 py-3.5 text-right text-rose-500/90 dark:text-rose-400/80">
                        {formatCurrency(row.despesas)}
                      </td>
                      <td className={`px-6 py-3.5 text-right font-semibold ${isPosBalanço ? 'text-primary' : 'text-rose-500'}`}>
                        {isPosBalanço ? '+' : ''}{formatCurrency(row.saldo)}
                      </td>
                      <td className={`px-6 py-3.5 text-right font-semibold ${row.aportes > 0 ? 'text-emerald-500' : 'text-foreground/70'}`}>
                        {formatCurrency(row.aportes)}
                      </td>
                      <td className="px-6 py-3.5 text-right">
                        <span className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-lg text-[10px] font-extrabold
                          ${savingRate >= 20 
                            ? 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400' 
                            : savingRate > 0 
                              ? 'bg-primary/10 text-primary' 
                              : 'bg-rose-500/10 text-rose-500'
                          }
                        `}>
                          {savingRate >= 0 ? <ArrowUpRight className="h-3 w-3" /> : <ArrowDownRight className="h-3 w-3" />}
                          {savingRate.toFixed(1).replace('.', ',')}%
                        </span>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>
      
    </div>
  );
}
