import Chart from 'react-apexcharts';
import { Activity } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/Card';
import { formatCurrency } from './formatters';

export default function FluxoProjetadoChart({ isLoading, chartData, isDark }) {
  const chartOptions = {
    chart: {
      type: 'bar',
      height: 320,
      toolbar: { show: false },
      fontFamily: 'inherit',
      background: 'transparent',
      animations: { enabled: true, speed: 600 },
    },
    plotOptions: {
      bar: {
        horizontal: false,
        columnWidth: '55%',
        borderRadius: 4,
      },
    },
    colors: ['#3b82f6', '#10b981', '#f43f5e'], // Azul para Fluxo do Mês, Verde para Receitas, Vermelho para Despesas
    dataLabels: { enabled: false },
    xaxis: {
      categories: chartData.map(d => d.label.split('/')[0]),
      labels: {
        style: { colors: isDark ? '#94a3b8' : '#64748b', fontSize: '12px' }
      }
    },
    yaxis: {
      labels: {
        formatter: (val) => formatCurrency(val),
        style: { colors: isDark ? '#94a3b8' : '#64748b', fontSize: '12px' }
      }
    },
    grid: {
      borderColor: isDark ? 'rgba(148, 163, 184, 0.08)' : 'rgba(100, 116, 139, 0.08)',
      strokeDashArray: 4,
    },
    theme: {
      mode: isDark ? 'dark' : 'light',
    },
    tooltip: {
      theme: isDark ? 'dark' : 'light',
      y: {
        formatter: (val) => formatCurrency(val),
      }
    },
    legend: {
      position: 'top',
      horizontalAlign: 'right',
      labels: {
        colors: isDark ? '#f8fafc' : '#0f172a',
      }
    }
  };

  const chartSeries = [
    { name: 'Fluxo do Mês', data: chartData.map(d => d.simNet) },
    { name: 'Receitas', data: chartData.map(d => d.realRevenues + d.simRevenues) },
    { name: 'Despesas', data: chartData.map(d => d.realExpenses + d.simExpenses) },
  ];

  return (
    <Card className="border-border bg-card/65 backdrop-blur-md">
      <CardHeader>
        <CardTitle className="text-lg font-semibold flex items-center gap-2">
          <Activity className="h-5 w-5 text-blue-500" /> Fluxo Projetado (6 meses)
        </CardTitle>
      </CardHeader>
      <CardContent>
        {isLoading ? (
          <div className="flex h-[320px] items-center justify-center">
            <div className="flex flex-col items-center gap-2">
              <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary border-t-transparent" />
              <span className="text-xs text-muted-foreground">Carregando dados da carteira...</span>
            </div>
          </div>
        ) : (
          <Chart
            options={chartOptions}
            series={chartSeries}
            type="bar"
            height={320}
          />
        )}
      </CardContent>
    </Card>
  );
}
