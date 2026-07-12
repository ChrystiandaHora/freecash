/**
 * Tela de Relatórios Financeiros (DRE e Fluxo de Caixa).
 *
 * Página de análise financeira consolidada que apresenta:
 *
 * 1. **DRE (Demonstração do Resultado do Exercício):** exibe receita bruta,
 *    deduções, despesas operacionais fixas e variáveis, EBITDA, resultado
 *    financeiro (dividendos + rentabilidade de carteira) e lucro líquido.
 *    Inclui cálculo automático da margem líquida.
 *
 * 2. **Fluxo de Caixa Resumido:** apresenta entradas e saídas operacionais
 *    e financeiras com totais líquidos por categoria.
 *
 * Estratégia de Dados (Fallback Gracioso):
 * - Tenta buscar dados do endpoint `/api/relatorios/dre/?ano={ano}`.
 * - Caso indisponível, constrói um DRE composto a partir de dados das APIs
 *   existentes (`/api/dashboard/` e `/api/investimentos/dashboard/`).
 * - Exibe skeleton animado (`FallbackDRETable`) enquanto carrega ou em erro.
 *
 * Funcionalidades: seletor de ano (atual − 3 anos), impressão/exportação PDF
 * nativa (`window.print()`), atualização manual, acordeão de seções.
 *
 * @module Relatorios
 * @component
 * @returns {JSX.Element} Painel de relatórios financeiros com DRE e fluxo de caixa.
 *
 * @example
 * // Rota configurada em App.jsx:
 * <Route path="relatorios" element={<Relatorios />} />
 */
import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import api from '../services/api';
import Chart from 'react-apexcharts';
import {
  Printer,
  RefreshCw,
  AlertCircle,
  TrendingUp,
  TrendingDown,
  DollarSign,
  BarChart3,
  ChevronDown,
  ChevronUp
} from 'lucide-react';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '../components/ui/Card';
import { Button } from '../components/ui/Button';
import { Alert } from '../components/ui/Alert';

/* ─────────────────────────── Helpers ─────────────────────────── */
const formatCurrency = (value) => {
  if (value === undefined || value === null) return 'R$ 0,00';
  return new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(value);
};

const currentYear = new Date().getFullYear();
const YEARS = [currentYear, currentYear - 1, currentYear - 2, currentYear - 3];

/* ─────────────────────────── DRE Row ─────────────────────────── */
function DreRow({ label, value, isTotal = false, isDeducao = false, isSubtotal = false, indent = 0 }) {
  const numVal = parseFloat(value) || 0;
  const isNeg = numVal < 0;

  return (
    <tr className={`transition-colors
      ${isTotal ? 'bg-primary/5 border-t-2 border-b-2 border-primary/20' : ''}
      ${isSubtotal ? 'bg-muted/20 border-t border-border/30' : ''}
      ${!isTotal && !isSubtotal ? 'hover:bg-muted/20' : ''}
    `}>
      <td className={`py-3 px-6 text-sm ${isTotal ? 'font-extrabold' : isSubtotal ? 'font-bold' : 'font-medium'} text-foreground`} style={{ paddingLeft: `${24 + indent * 20}px` }}>
        {isDeducao && <span className="text-rose-500 mr-1.5 text-xs font-bold">(−)</span>}
        {label}
      </td>
      <td className={`py-3 px-6 text-sm text-right tabular-nums font-${isTotal ? 'extrabold' : isSubtotal ? 'bold' : 'semibold'}
        ${isTotal ? (numVal >= 0 ? 'text-emerald-600 dark:text-emerald-400' : 'text-rose-600 dark:text-rose-400') : isNeg || isDeducao ? 'text-rose-600 dark:text-rose-400' : 'text-foreground'}
      `}>
        {formatCurrency(numVal)}
      </td>
      <td className={`py-3 px-6 text-sm text-right tabular-nums ${isNeg ? 'text-rose-600 dark:text-rose-400' : 'text-muted-foreground'}`}>
        {/* Margin % placeholder – calculated from receita bruta if available */}
      </td>
    </tr>
  );
}

/* ─────────────────────────── DRE from real data ─────────────────────────── */
function DRETable({ ano, data }) {
  // Build DRE from actual dashboard data:
  // data contains: receitas, despesas, investimentos (dividendos), etc.
  const receitas = data?.receitas ?? {};
  const despesas = data?.despesas ?? {};
  const investimentos = data?.investimentos ?? {};

  const receitaBruta = parseFloat(receitas.total_receitas ?? receitas.receita_bruta ?? 0);
  const deducoes = parseFloat(receitas.deducoes ?? 0);
  const receitaLiquida = receitaBruta - deducoes;

  const despesasFixas = parseFloat(despesas.despesas_fixas ?? despesas.fixas ?? 0);
  const despesasVariaveis = parseFloat(despesas.despesas_variaveis ?? despesas.variaveis ?? despesas.total_despesas ?? 0);
  const totalDespesas = despesasFixas + despesasVariaveis;

  const ebitda = receitaLiquida - totalDespesas;

  const proventos = parseFloat(investimentos.dividendos ?? 0);
  const rentabilidade = parseFloat(investimentos.rentabilidade ?? 0);
  const resultadoFinanceiro = proventos + rentabilidade;

  const lucroLiquido = ebitda + resultadoFinanceiro;

  // Compute margin pct against receita bruta
  const margin = receitaBruta > 0 ? (lucroLiquido / receitaBruta * 100).toFixed(1) : 0;

  return (
    <div className="overflow-x-auto rounded-xl border border-border/40">
      <table className="w-full text-left border-collapse">
        {/* Caption */}
        <thead>
          <tr className="bg-muted/60 border-b border-border/40">
            <th className="py-3.5 px-6 text-xs font-bold text-muted-foreground uppercase tracking-widest">
              Demonstração do Resultado (DRE) — {ano}
            </th>
            <th className="py-3.5 px-6 text-xs font-bold text-muted-foreground uppercase tracking-wider text-right w-44">
              Valor
            </th>
            <th className="py-3.5 px-6 text-xs font-bold text-muted-foreground uppercase tracking-wider text-right w-28">
              Margem
            </th>
          </tr>
        </thead>
        <tbody className="divide-y divide-border/40">
          {/* 1. Receita */}
          <DreRow label="1. Receita Bruta" value={receitaBruta} isSubtotal />
          {deducoes > 0 && <DreRow label="Deduções / Impostos" value={-deducoes} isDeducao indent={1} />}
          <DreRow label="= Receita Líquida" value={receitaLiquida} isSubtotal />

          {/* 2. Despesas */}
          <DreRow label="2. Despesas Operacionais" value={-totalDespesas} isSubtotal isDeducao />
          {despesasFixas > 0 && <DreRow label="Despesas Fixas" value={-despesasFixas} indent={1} />}
          {despesasVariaveis > 0 && <DreRow label="Despesas Variáveis" value={-despesasVariaveis} indent={1} />}

          {/* 3. EBITDA */}
          <DreRow label="= Resultado Operacional (EBITDA)" value={ebitda} isSubtotal />

          {/* 4. Resultado Financeiro */}
          <DreRow label="3. Resultado de Investimentos" value={resultadoFinanceiro} isSubtotal />
          {proventos > 0 && <DreRow label="Proventos / Dividendos" value={proventos} indent={1} />}
          {rentabilidade !== 0 && <DreRow label="Rentabilidade de Carteira" value={rentabilidade} indent={1} />}

          {/* 5. Lucro Líquido */}
          <DreRow label="= RESULTADO LÍQUIDO DO PERÍODO" value={lucroLiquido} isTotal />
        </tbody>
        <tfoot>
          <tr className="bg-muted/30">
            <td className="py-3 px-6 text-[11px] font-semibold text-muted-foreground">
              Margem líquida sobre receita bruta
            </td>
            <td className="py-3 px-6 text-right">
              <span className={`inline-flex items-center gap-1 text-sm font-extrabold ${parseFloat(margin) >= 0 ? 'text-emerald-600 dark:text-emerald-400' : 'text-rose-600 dark:text-rose-400'}`}>
                {parseFloat(margin) >= 0 ? <TrendingUp className="h-3.5 w-3.5" /> : <TrendingDown className="h-3.5 w-3.5" />}
                {margin}%
              </span>
            </td>
            <td />
          </tr>
        </tfoot>
      </table>
    </div>
  );
}

/* ─────────────────────────── Fallback DRE when API not available ─────────────────────────── */
function FallbackDRETable({ ano }) {
  return (
    <div className="overflow-x-auto rounded-xl border border-border/40">
      <table className="w-full text-left border-collapse">
        <thead>
          <tr className="bg-muted/60 border-b border-border/40">
            <th className="py-3.5 px-6 text-xs font-bold text-muted-foreground uppercase tracking-widest">
              Demonstração do Resultado (DRE) — {ano}
            </th>
            <th className="py-3.5 px-6 text-xs font-bold text-muted-foreground uppercase tracking-wider text-right w-44">Valor</th>
            <th className="py-3.5 px-6 text-xs font-bold text-muted-foreground uppercase tracking-wider text-right w-28">Margem</th>
          </tr>
        </thead>
        <tbody>
          {[
            { label: '1. Receita Bruta', sub: true },
            { label: 'Receitas Recorrentes', indent: 1 },
            { label: 'Receitas Eventuais', indent: 1 },
            { label: '= Receita Líquida', sub: true },
            { label: '2. Despesas Operacionais', sub: true, deducao: true },
            { label: 'Contas a Pagar (Fixas)', indent: 1 },
            { label: 'Cartões de Crédito', indent: 1 },
            { label: '= Resultado Operacional (EBITDA)', sub: true },
            { label: '3. Resultado Financeiro', sub: true },
            { label: '= RESULTADO LÍQUIDO', total: true },
          ].map((row, i) => (
            <tr key={i} className={`${row.total ? 'bg-primary/5 border-t-2 border-b-2 border-primary/20' : row.sub ? 'bg-muted/20' : 'hover:bg-muted/10'}`}>
              <td className={`py-3 px-6 text-sm ${row.total ? 'font-extrabold text-foreground' : row.sub ? 'font-bold text-foreground' : 'font-medium text-muted-foreground'}`} style={{ paddingLeft: `${24 + (row.indent ?? 0) * 20}px` }}>
                {row.deducao && <span className="text-rose-500 mr-1.5 text-xs">(−)</span>}
                {row.label}
              </td>
              <td className="py-3 px-6 text-right">
                <div className="h-3.5 w-24 bg-muted rounded animate-pulse ml-auto" />
              </td>
              <td className="py-3 px-6 text-right">
                <div className="h-3 w-12 bg-muted rounded animate-pulse ml-auto" />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <div className="p-5 border-t border-border/40 flex items-center justify-center gap-2">
        <AlertCircle className="h-4 w-4 shrink-0 text-amber-500" />
        <p className="text-xs text-muted-foreground italic">
          API de Relatórios em construção — os valores acima serão preenchidos automaticamente quando o endpoint <code className="bg-muted px-1.5 py-0.5 rounded text-[10px] text-muted-foreground">/api/relatorios/dre/?ano={ano}</code> estiver disponível.
        </p>
      </div>
    </div>
  );
}

/* ─────────────────────────── Main Page ─────────────────────────── */
export default function Relatorios() {
  const [ano, setAno] = useState(currentYear);
  const [expandedSection, setExpandedSection] = useState('dre');

  const { data: dreData, isLoading, isError, refetch } = useQuery({
    queryKey: ['relatoriosDRE', ano],
    queryFn: async () => {
      const res = await api.get(`/api/relatorios/dre/?ano=${ano}`);
      return res.data;
    },
    retry: 0, // Don't retry if endpoint doesn't exist yet
  });

  // Also fetch dashboard for cross-panel data
  const { data: dashData } = useQuery({
    queryKey: ['dashboardResumo'],
    queryFn: async () => {
      const res = await api.get('/api/dashboard/');
      return res.data;
    },
    retry: 0,
  });

  const { data: invData } = useQuery({
    queryKey: ['investimentosDashboard'],
    queryFn: async () => {
      const res = await api.get('/api/investimentos/dashboard/');
      return res.data;
    },
    retry: 0,
  });

  const handlePrint = () => window.print();

  const apiDataReady = dreData && !isError;

  // Build composite data from available sources
  const compositeData = dreData ?? {
    receitas: {
      total_receitas: dashData?.total_receitas ?? 0,
      deducoes: 0,
    },
    despesas: {
      total_despesas: (dashData?.total_contas_pagas ?? 0) + (dashData?.total_cartoes ?? 0),
      despesas_fixas: dashData?.total_contas_pagas ?? 0,
      despesas_variaveis: dashData?.total_cartoes ?? 0,
    },
    investimentos: {
      dividendos: invData?.total_dividendos ?? 0,
      rentabilidade: invData?.total_rentabilidade ?? 0,
    },
  };

  const sections = [
    { id: 'dre', label: 'DRE — Demonstração do Resultado', icon: BarChart3 },
    { id: 'cashflow', label: 'Fluxo de Caixa Resumido', icon: DollarSign },
    { id: 'heatmap', label: 'Sazonalidade de Despesas (Mapa de Calor)', icon: TrendingUp },
  ];

  const heatmapOptions = {
    chart: {
      type: 'heatmap',
      toolbar: { show: false },
      fontFamily: 'Outfit, Inter, sans-serif',
      foreColor: 'var(--muted-foreground)',
      background: 'transparent',
    },
    dataLabels: { enabled: false },
    stroke: { width: 1, colors: ['var(--background)'] },
    plotOptions: {
      heatmap: {
        radius: 4,
        enableShades: true,
        shadeIntensity: 0.5,
        colorScale: {
          ranges: [
            { from: 0, to: 0, color: '#1e293b', name: 'Sem gastos' },
            { from: 0.01, to: 100, color: '#0ea5e9', name: 'Baixo (< R$100)' },
            { from: 100.01, to: 500, color: '#3b82f6', name: 'Médio (< R$500)' },
            { from: 500.01, to: 1000000, color: '#8b5cf6', name: 'Alto (> R$500)' },
          ]
        }
      }
    },
    xaxis: {
      type: 'category',
      title: {
        text: 'Semanas (últimos 6 meses)',
        style: { fontSize: '11px', fontWeight: 600, color: 'var(--muted-foreground)' }
      },
      axisBorder: { show: false },
      axisTicks: { show: false },
      labels: {
        style: { fontSize: '10px' }
      }
    },
    yaxis: {
      labels: {
        style: { fontSize: '10px' }
      }
    },
    grid: {
      borderColor: 'rgba(255, 255, 255, 0.05)',
      padding: { right: 20 }
    },
    theme: { mode: 'dark' },
    tooltip: {
      theme: 'dark',
      y: {
        formatter: (val) => formatCurrency(val)
      }
    }
  };

  return (
    <>
      {/* ── Print Styles ── */}
      <style>{`
        @media print {
          body * { visibility: hidden !important; }
          #relatorios-print-area, #relatorios-print-area * { visibility: visible !important; }
          #relatorios-print-area { position: fixed; top: 0; left: 0; width: 100%; }
          .no-print { display: none !important; }
          table { page-break-inside: avoid; }
          tr { page-break-inside: avoid; }
        }
      `}</style>

      <div className="space-y-6 animate-fade-in">

        {/* ── Header ── */}
        <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 no-print">
          <div>
            <h1 className="text-3xl font-extrabold tracking-tight text-foreground">
              Relatórios Financeiros
            </h1>
            <p className="text-muted-foreground mt-1">
              DRE e fluxo de caixa consolidados para análise e exportação
            </p>
          </div>
          <div className="flex items-center gap-3 shrink-0">
            {/* Ano selector */}
            <div className="flex items-center gap-2 bg-muted rounded-xl p-1 border border-border/40">
              {YEARS.map((y) => (
                <button
                  key={y}
                  onClick={() => setAno(y)}
                  className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-all cursor-pointer
                    ${ano === y ? 'bg-card text-primary shadow-sm' : 'text-muted-foreground hover:text-foreground'}`}
                >
                  {y}
                </button>
              ))}
            </div>

            <Button
              onClick={handlePrint}
              className="h-9 px-4 rounded-xl text-xs font-semibold bg-primary hover:bg-primary/90 text-primary-foreground border-0 flex items-center gap-1.5"
            >
              <Printer className="h-3.5 w-3.5" />
              Imprimir / PDF
            </Button>

            <Button variant="outline" size="icon" onClick={() => refetch()} className="rounded-xl h-9 w-9 shrink-0">
              <RefreshCw className={`h-4 w-4 text-muted-foreground ${isLoading ? 'animate-spin' : ''}`} />
            </Button>
          </div>
        </div>

        {/* ── KPI Summary Strip ── */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 no-print">
          {[
            {
              label: 'Receita Bruta',
              value: compositeData?.receitas?.total_receitas ?? 0,
              color: 'emerald',
              icon: TrendingUp,
            },
            {
              label: 'Total Despesas',
              value: -(compositeData?.despesas?.total_despesas ?? 0),
              color: 'rose',
              icon: TrendingDown,
            },
            {
              label: 'Proventos',
              value: compositeData?.investimentos?.dividendos ?? 0,
              color: 'amber',
              icon: DollarSign,
            },
            {
              label: 'Rentab. Carteira',
              value: compositeData?.investimentos?.rentabilidade ?? 0,
              color: 'blue',
              icon: BarChart3,
            },
          ].map((kpi) => {
            const Icon = kpi.icon;
            const val = parseFloat(kpi.value) || 0;
            return (
              <Card key={kpi.label} className="border-border/40 shadow-sm relative overflow-hidden">
                <CardContent className="pt-4 pb-4">
                  <div className={`w-10 h-10 rounded-xl bg-primary/10 flex items-center justify-center mb-3`}>
                    <Icon className="h-4 w-4 text-primary" />
                  </div>
                  <p className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider">{kpi.label}</p>
                  <p className={`text-lg font-extrabold mt-0.5 ${
                    kpi.color === 'emerald' ? 'text-emerald-600 dark:text-emerald-400' :
                    kpi.color === 'rose' || val < 0 ? 'text-rose-600 dark:text-rose-400' :
                    kpi.color === 'amber' ? 'text-amber-600 dark:text-amber-400' :
                    'text-primary'
                  }`}>
                    {formatCurrency(val)}
                  </p>
                </CardContent>
              </Card>
            );
          })}
        </div>

        {/* ── Print Area ── */}
        <div id="relatorios-print-area">
          {/* Print header (only visible on print) */}
          <div className="hidden print:block mb-8">
            <h1 className="text-2xl font-bold">FreeCash — Relatório Financeiro {ano}</h1>
            <p className="text-sm text-gray-500 mt-1">Gerado em {new Date().toLocaleDateString('pt-BR', { day: '2-digit', month: 'long', year: 'numeric' })}</p>
            <hr className="mt-4 border-gray-300" />
          </div>

          {/* ── Sections ── */}
          {sections.map((section) => {
            const Icon = section.icon;
            const isOpen = expandedSection === section.id;
            return (
              <Card key={section.id} className="border-border/40 shadow-sm mb-4">
                <CardHeader
                  className="cursor-pointer flex flex-row items-center justify-between no-print"
                  onClick={() => setExpandedSection(isOpen ? null : section.id)}
                >
                  <div className="flex items-center gap-3">
                    <div className="w-9 h-9 rounded-xl bg-primary/10 flex items-center justify-center">
                      <Icon className="h-4 w-4 text-primary" />
                    </div>
                    <div>
                      <CardTitle className="text-sm font-bold text-foreground">{section.label}</CardTitle>
                      <CardDescription className="text-[10px]">Exercício {ano}</CardDescription>
                    </div>
                  </div>
                  {isOpen ? <ChevronUp className="h-4 w-4 text-muted-foreground" /> : <ChevronDown className="h-4 w-4 text-muted-foreground" />}
                </CardHeader>

                {/* Always shown on print */}
                <CardContent className={`${isOpen ? 'block' : 'hidden'} print:!block`}>
                  {section.id === 'dre' && (
                    apiDataReady
                      ? <DRETable ano={ano} data={compositeData} />
                      : <FallbackDRETable ano={ano} />
                  )}

                  {section.id === 'cashflow' && (
                    <div className="overflow-x-auto rounded-xl border border-border/40">
                      <table className="w-full text-left border-collapse">
                        <thead>
                          <tr className="bg-muted/60 border-b border-border/40">
                            <th className="py-3.5 px-6 text-xs font-bold text-muted-foreground uppercase tracking-widest">Fluxo de Caixa — {ano}</th>
                            <th className="py-3.5 px-6 text-xs font-bold text-muted-foreground uppercase tracking-wider text-right w-44">Valor</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-border/40">
                          {[
                            { label: 'Entradas Operacionais (Receitas)', value: compositeData?.receitas?.total_receitas ?? 0 },
                            { label: 'Saídas Operacionais (Despesas)', value: -(compositeData?.despesas?.total_despesas ?? 0) },
                            { label: 'Fluxo Operacional Líquido', value: (compositeData?.receitas?.total_receitas ?? 0) - (compositeData?.despesas?.total_despesas ?? 0), sub: true },
                            { label: 'Entradas Financeiras (Dividendos)', value: compositeData?.investimentos?.dividendos ?? 0 },
                            { label: 'Valorização da Carteira', value: compositeData?.investimentos?.rentabilidade ?? 0 },
                            { label: 'Fluxo Financeiro Líquido', value: (compositeData?.investimentos?.dividendos ?? 0) + (compositeData?.investimentos?.rentabilidade ?? 0), sub: true },
                          ].map((row, i) => (
                            <tr key={i} className={`${row.sub ? 'bg-muted/20 border-t border-border/30' : 'hover:bg-muted/10'}`}>
                              <td className={`py-3 px-6 text-sm ${row.sub ? 'font-bold text-foreground' : 'font-medium text-muted-foreground'}`}>
                                {row.label}
                              </td>
                              <td className={`py-3 px-6 text-sm text-right font-${row.sub ? 'bold' : 'semibold'} tabular-nums ${parseFloat(row.value) < 0 ? 'text-rose-500' : 'text-foreground'}`}>
                                {formatCurrency(row.value)}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}

                  {section.id === 'heatmap' && (
                    <div className="p-4 rounded-xl border border-border/40 bg-card/30 backdrop-blur-md">
                      {compositeData?.sazonalidade?.series ? (
                        <div className="h-[320px] w-full">
                          <Chart
                            options={heatmapOptions}
                            series={compositeData.sazonalidade.series}
                            type="heatmap"
                            height="100%"
                            width="100%"
                          />
                        </div>
                      ) : (
                        <div className="h-[320px] w-full flex items-center justify-center bg-muted/20 animate-pulse rounded-xl">
                          <div className="text-center">
                            <AlertCircle className="h-8 w-8 text-muted-foreground mx-auto mb-2" />
                            <p className="text-xs text-muted-foreground">Buscando histórico de sazonalidade...</p>
                          </div>
                        </div>
                      )}
                    </div>
                  )}
                </CardContent>
              </Card>
            );
          })}

          {/* Print footer */}
          <div className="hidden print:block mt-8 pt-4 border-t border-gray-300 text-xs text-gray-500 text-center">
            <p>FreeCash — Sistema de Gestão Financeira Pessoal</p>
            <p>Documento gerado em {new Date().toLocaleString('pt-BR')} — Uso interno</p>
          </div>
        </div>

        {/* ── Note ── */}
        {isError && (
          <Alert variant="warning" icon={AlertCircle} title="Endpoint de relatórios não disponível" className="text-xs no-print">
            Os relatórios estão sendo exibidos com dados parciais obtidos das APIs existentes (dashboard e investimentos). Configure o endpoint <code className="bg-amber-500/10 px-1 rounded">/api/relatorios/dre/</code> para dados consolidados completos.
          </Alert>
        )}

      </div>
    </>
  );
}
