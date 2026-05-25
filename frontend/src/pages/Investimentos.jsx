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
import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import api from '../services/api';
import Chart from 'react-apexcharts';
import { 
  TrendingUp, 
  TrendingDown, 
  DollarSign, 
  PieChart, 
  Layers, 
  ChevronRight, 
  HelpCircle, 
  AlertCircle, 
  CheckCircle2, 
  RefreshCw,
  Plus,
  Sliders,
  Save,
  Percent
} from 'lucide-react';
import { Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter } from '../components/ui/Card';
import { Button } from '../components/ui/Button';
import { Accordion, AccordionItem } from '../components/ui/Accordion';
import { Input } from '../components/ui/Input';
import { useToast } from '../context/ToastContext';


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
    alocacao_classes = { labels: [], valores: [] },
    ativos = [],
    top_5_ativos = [],
    top_rentabilidade = [],
    proximos_vencimentos = [],
    ultima_transacao = null
  } = dashboardData;

  // Chart configuration for Asset Allocation (Donut)
  const donutChartOptions = {
    chart: {
      type: 'donut',
      fontFamily: 'inherit',
      background: 'transparent',
      animations: { enabled: false },
    },
    labels: alocacao_classes.labels || [],
    colors: ['#10b981', '#3b82f6', '#f59e0b', '#ec4899', '#8b5cf6', '#64748b'],
    dataLabels: { enabled: false },
    stroke: { width: 1, colors: ['rgba(255, 255, 255, 0.05)'] },
    legend: {
      position: 'bottom',
      fontSize: '11px',
      labels: { colors: '#888888' },
      markers: { radius: 12 }
    },
    plotOptions: {
      pie: {
        donut: {
          size: '72%',
          labels: {
            show: true,
            value: {
              formatter: (val) => formatCurrency(val),
              color: '#888888',
              fontSize: '15px',
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
      mode: document.documentElement.classList.contains('dark') ? 'dark' : 'light',
    },
    tooltip: {
      theme: document.documentElement.classList.contains('dark') ? 'dark' : 'light',
      y: {
        formatter: (val) => formatCurrency(val)
      }
    }
  };

  const donutChartSeries = alocacao_classes.valores || [];

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
      <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
        
        {/* Patrimonio Total */}
        <Card className="bg-card border border-border/40 shadow-sm text-card-foreground relative overflow-hidden group">
          <div className="absolute top-0 right-0 w-24 h-24 bg-primary/5 rounded-full blur-2xl pointer-events-none group-hover:bg-primary/10 transition-all duration-300" />
          <CardHeader className="pb-2">
            <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
              Patrimônio Atual
            </span>
          </CardHeader>
          <CardContent>
            <h3 className="text-2xl font-bold tracking-tight text-foreground">
              {formatCurrency(total_patrimonio)}
            </h3>
            <p className="text-[10px] text-muted-foreground mt-2">
              Patrimônio avaliado a mercado
            </p>
          </CardContent>
        </Card>

        {/* Total Investido */}
        <Card className="bg-card border border-border/40 shadow-sm text-card-foreground relative overflow-hidden group">
          <div className="absolute top-0 right-0 w-24 h-24 bg-primary/5 rounded-full blur-2xl pointer-events-none group-hover:bg-primary/10 transition-all duration-300" />
          <CardHeader className="pb-2">
            <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
              Total Investido
            </span>
          </CardHeader>
          <CardContent>
            <h3 className="text-2xl font-bold tracking-tight text-foreground">
              {formatCurrency(total_investido)}
            </h3>
            <p className="text-[10px] text-muted-foreground mt-2">
              Soma histórica de aportes líquidos
            </p>
          </CardContent>
        </Card>

        {/* Rentabilidade */}
        <Card className="bg-card border border-border/40 shadow-sm text-card-foreground relative overflow-hidden group">
          <div className="absolute top-0 right-0 w-24 h-24 bg-primary/5 rounded-full blur-2xl pointer-events-none group-hover:bg-primary/10 transition-all duration-300" />
          <CardHeader className="pb-2">
            <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
              Rentabilidade
            </span>
          </CardHeader>
          <CardContent>
            <h3 className={`text-2xl font-bold tracking-tight ${total_rentabilidade >= 0 ? 'text-primary' : 'text-rose-500'}`}>
              {formatCurrency(total_rentabilidade)}
            </h3>
            <div className="flex items-center gap-1.5 mt-2">
              <span className={`inline-flex items-center text-[10px] font-semibold rounded px-1.5 py-0.5
                ${total_rentabilidade_percentual >= 0 
                  ? 'bg-primary/10 text-primary' 
                  : 'bg-rose-500/10 text-rose-500'
                }
              `}>
                {formatPercentage(total_rentabilidade_percentual)}
              </span>
              <span className="text-[10px] text-muted-foreground">sobre o custo</span>
            </div>
          </CardContent>
        </Card>

        {/* Dividendos */}
        <Card className="bg-card border border-border/40 shadow-sm text-card-foreground relative overflow-hidden group">
          <div className="absolute top-0 right-0 w-24 h-24 bg-amber-500/5 rounded-full blur-2xl pointer-events-none group-hover:bg-amber-500/10 transition-all duration-300" />
          <CardHeader className="pb-2">
            <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
              Proventos / JCP
            </span>
          </CardHeader>
          <CardContent>
            <h3 className="text-2xl font-bold tracking-tight text-amber-500">
              {formatCurrency(total_dividendos)}
            </h3>
            <p className="text-[10px] text-muted-foreground mt-2">
              Rendimentos recebidos na carteira
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Tab 1: Portfolio View */}
      {activeTab === 'portfolio' && (
        <div className="space-y-8">
          
          {/* Charts & Hierarchy Row */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            
            {/* Allocation Donut */}
            <Card className="bg-card border border-border/40 shadow-sm text-card-foreground">
              <CardHeader>
                <CardTitle className="text-base font-bold text-foreground">
                  Alocação por Classe
                </CardTitle>
                <CardDescription className="text-xs text-muted-foreground">
                  Divisão patrimonial agrupada por macro-classes
                </CardDescription>
              </CardHeader>
              <CardContent className="flex justify-center py-4">
                {donutChartSeries.length > 0 ? (
                  <Chart key={`donut-${donutChartSeries.join("-")}`} options={donutChartOptions} series={donutChartSeries} type="donut" width={320} />
                ) : (
                  <div className="py-12 text-center text-xs text-muted-foreground">
                    Nenhum ativo cadastrado para exibir alocação.
                  </div>
                )}
              </CardContent>
            </Card>

            {/* ANBIMA Expandable Hierarchy Tree */}
            <Card className="lg:col-span-2 bg-card border border-border/40 shadow-sm text-card-foreground">
              <CardHeader>
                <CardTitle className="text-base font-bold text-foreground">
                  Estrutura ANBIMA da Carteira
                </CardTitle>
                <CardDescription className="text-xs text-muted-foreground">
                  Hierarquia dinâmica de classes, categorias e ativos ativos
                </CardDescription>
              </CardHeader>
              <CardContent>
                {balanceData && balanceData.classes && balanceData.classes.length > 0 ? (
                  <Accordion>
                    {balanceData.classes.map((classe, idx) => (
                      <AccordionItem 
                        key={idx} 
                        title={`${classe.nome} — ${formatCurrency(classe.ativos.reduce((sum, item) => sum + item.valor_atual, 0))}`}
                      >
                        <div className="overflow-x-auto mt-2">
                          <table className="w-full text-xs text-left border-collapse">
                            <thead>
                              <tr className="border-b border-border/40 text-muted-foreground font-semibold">
                                <th className="py-2.5 px-3">Ticker</th>
                                <th className="py-2.5 px-3">Nome</th>
                                <th className="py-2.5 px-3 text-right">Peso Atual</th>
                                <th className="py-2.5 px-3 text-right">Cotação</th>
                                <th className="py-2.5 px-3 text-right">Saldo Atual</th>
                                <th className="py-2.5 px-3 text-right">Rentabilidade</th>
                              </tr>
                            </thead>
                            <tbody className="divide-y divide-border/40">
                              {classe.ativos.map((at, atIdx) => (
                                <tr key={atIdx} className="hover:bg-muted/40 transition-colors">
                                  <td className="py-2.5 px-3 font-bold text-foreground">
                                    {at.ticker}
                                  </td>
                                  <td className="py-2.5 px-3 text-muted-foreground max-w-[150px] truncate">
                                    {at.nome}
                                  </td>
                                  <td className="py-2.5 px-3 text-right font-semibold text-foreground/85">
                                    {at.perc_atual.toFixed(1).replace('.', ',')}%
                                  </td>
                                  <td className="py-2.5 px-3 text-right text-muted-foreground">
                                    {formatCurrency(at.preco_atual)}
                                  </td>
                                  <td className="py-2.5 px-3 text-right font-bold text-foreground">
                                    {formatCurrency(at.valor_atual)}
                                  </td>
                                  <td className={`py-2.5 px-3 text-right font-semibold ${at.rentabilidade_perc >= 0 ? 'text-primary' : 'text-rose-500'}`}>
                                    {formatPercentage(at.rentabilidade_perc)}
                                  </td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      </AccordionItem>
                    ))}
                  </Accordion>
                ) : (
                  <div className="py-12 text-center text-xs text-muted-foreground">
                    Nenhum dado estruturado de carteira encontrado.
                  </div>
                )}
              </CardContent>
            </Card>

          </div>

          {/* Active Positions Table */}
          <Card className="bg-card border border-border/40 shadow-sm text-card-foreground">
            <CardHeader>
              <CardTitle className="text-base font-bold text-foreground">
                Detalhamento Geral de Posições
              </CardTitle>
              <CardDescription className="text-xs text-muted-foreground">
                Resumo completo dos ativos mantidos em carteira
              </CardDescription>
            </CardHeader>
            <CardContent className="px-0">
              <div className="overflow-x-auto">
                <table className="w-full text-xs text-left border-collapse">
                  <thead>
                    <tr className="border-b border-border/40 text-muted-foreground font-semibold">
                      <th className="px-6 py-3">Ticker</th>
                      <th className="px-6 py-3">Ativo</th>
                      <th className="px-6 py-3 text-right">Preço Médio</th>
                      <th className="px-6 py-3 text-right">Cotação Atual</th>
                      <th className="px-6 py-3 text-right">Quantidade</th>
                      <th className="px-6 py-3 text-right">Investido</th>
                      <th className="px-6 py-3 text-right">Valor Atual</th>
                      <th className="px-6 py-3 text-right">Rentabilidade</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border/40">
                    {ativos && ativos.length > 0 ? (
                      ativos.map((ativo, idx) => (
                        <tr key={idx} className="hover:bg-muted/40 transition-colors">
                          <td className="px-6 py-3.5 font-bold text-foreground">
                            {ativo.ticker}
                          </td>
                          <td className="px-6 py-3.5 text-muted-foreground">
                            {ativo.nome}
                          </td>
                          <td className="px-6 py-3.5 text-right text-muted-foreground">
                            {formatCurrency(ativo.preco_medio)}
                          </td>
                          <td className="px-6 py-3.5 text-right text-muted-foreground">
                            {formatCurrency(ativo.cotacao_atual)}
                          </td>
                          <td className="px-6 py-3.5 text-right font-semibold text-foreground/80">
                            {parseFloat(ativo.quantidade).toString().replace('.', ',')}
                          </td>
                          <td className="px-6 py-3.5 text-right text-muted-foreground">
                            {formatCurrency(ativo.valor_investido_total)}
                          </td>
                          <td className="px-6 py-3.5 text-right font-bold text-foreground">
                            {formatCurrency(ativo.valor_total_atual)}
                          </td>
                          <td className={`px-6 py-3.5 text-right font-bold ${ativo.rentabilidade_percentual >= 0 ? 'text-primary' : 'text-rose-500'}`}>
                            {formatPercentage(ativo.rentabilidade_percentual)}
                          </td>
                        </tr>
                      ))
                    ) : (
                      <tr>
                        <td colSpan="8" className="px-6 py-8 text-center text-muted-foreground">
                          Nenhum ativo em carteira no momento. Crie um ativo para começar.
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </CardContent>
          </Card>

        </div>
      )}

      {/* Tab 2: Rebalancing Tool */}
      {activeTab === 'rebalance' && balanceData && (
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
              <div className="flex items-center gap-2.5 p-3.5 rounded-xl bg-rose-500/10 border border-rose-500/20 text-rose-500 text-xs">
                <AlertCircle className="h-4.5 w-4.5 shrink-0" />
                <p className="font-semibold leading-relaxed">{metaError}</p>
              </div>
            )}

            {saveMetasMutation.isSuccess && (
              <div className="flex items-center gap-2.5 p-3.5 rounded-xl bg-primary/10 border border-primary/20 text-primary/80 text-xs">
                <CheckCircle2 className="h-4.5 w-4.5 shrink-0" />
                <p className="font-semibold leading-relaxed">Metas de alocação salvas e sincronizadas com sucesso!</p>
              </div>
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
      )}

    </div>
  );
}
