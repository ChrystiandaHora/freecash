/**
 * Componente de Simulador de Gastos e Receitas.
 * 
 * Permite ao usuário simular cenários financeiros em memória (client-side),
 * cruzando lançamentos temporários com despesas/receitas reais do banco de dados
 * para os próximos 12 meses.
 */
import { useState, useEffect, useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  Plus,
  Trash2,
  AlertCircle,
  Calendar,
  Layers,
  Activity,
  Sparkles,
  RefreshCw,
  FolderOpen
} from 'lucide-react';
import Chart from 'react-apexcharts';
import { useToast } from '../context/ToastContext';
import { fetchContas } from '../services/financeiro';

// UI components
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/Card';
import { Button } from '../components/ui/Button';
import { Input } from '../components/ui/Input';
import { Select } from '../components/ui/Select';
import { Badge } from '../components/ui/Badge';

// Helpers
const formatCurrency = (val) =>
  new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(val ?? 0);

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
  const { data: realContas = [], isLoading, refetch } = useQuery({
    queryKey: ['contas-simulacao', dateRange.inicio, dateRange.fim],
    queryFn: () => fetchContas({ data_inicio: dateRange.inicio, data_fim: dateRange.fim }),
    enabled: !!dateRange.inicio && !!dateRange.fim,
  });

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
      return diffMonths < item.parcelas ? item.valor : 0;
    }
    
    return 0;
  };

  // Processar dados consolidados mês a mês
  const monthlyData = useMemo(() => {
    let accumulatedReal = 0;
    let accumulatedSim = 0;

    return projectionMonths.map((m) => {
      // Filtrar contas reais do mês correspondente
      const realItemsForMonth = realContas.filter(c => parseMonthYear(c.data_prevista) === m.key);

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
  }, [projectionMonths, realContas, simuladas]);

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

  // Filtrar apenas os primeiros 6 meses para o gráfico
  const chartData = useMemo(() => {
    return monthlyData.slice(0, 6);
  }, [monthlyData]);

  // Gráfico do ApexCharts (Fluxo Projetado de 6 Meses)
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
    colors: ['#3b82f6', '#10b981', '#f43f5e'], // Azul para Saldo Projetado, Verde para Receitas, Vermelho para Despesas
    dataLabels: { enabled: false },
    xaxis: {
      categories: chartData.map(d => d.label.split('/')[0]),
      labels: {
        style: { colors: isDark ? '#94a3b8' : '#64748b', fontSize: '11px' }
      }
    },
    yaxis: {
      labels: {
        formatter: (val) => formatCurrency(val),
        style: { colors: isDark ? '#94a3b8' : '#64748b', fontSize: '11px' }
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
    { name: 'Saldo Projetado', data: chartData.map(d => d.simNet) },
    { name: 'Receitas', data: chartData.map(d => d.realRevenues + d.simRevenues) },
    { name: 'Despesas', data: chartData.map(d => d.realExpenses + d.simExpenses) },
  ];

  // Estado para ver detalhes de simulação em um mês específico
  const [selectedMonthDetails, setSelectedMonthDetails] = useState(null);

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
          onClick={() => refetch()} 
          disabled={isLoading}
          className="self-start md:self-center flex gap-2 items-center"
        >
          <RefreshCw className={`h-4 w-4 ${isLoading ? 'animate-spin' : ''}`} />
          Atualizar Dados Reais
        </Button>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <Card className="relative overflow-hidden border-border bg-card/65 backdrop-blur-md transition-all hover:scale-[1.01]">
          <div className="absolute right-3 top-3 rounded-full bg-blue-500/10 p-2 text-blue-500">
            <Activity className="h-5 w-5" />
          </div>
          <CardHeader className="pb-2">
            <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">Saldo Mês Atual (Real)</span>
            <CardTitle className="text-2xl font-bold text-foreground">
              {isLoading ? '...' : formatCurrency(kpis.currentReal)}
            </CardTitle>
          </CardHeader>
          <CardContent className="pt-0">
            <span className="text-xs text-muted-foreground">Lançamento líquido real deste mês</span>
          </CardContent>
        </Card>

        <Card className="relative overflow-hidden border-primary/30 bg-primary/5 backdrop-blur-md transition-all hover:scale-[1.01]">
          <div className="absolute right-3 top-3 rounded-full bg-primary/10 p-2 text-primary">
            <Sparkles className="h-5 w-5" />
          </div>
          <CardHeader className="pb-2">
            <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">Saldo Mês Atual (Simulado)</span>
            <CardTitle className="text-2xl font-bold text-foreground">
              {isLoading ? '...' : formatCurrency(kpis.currentSim)}
            </CardTitle>
          </CardHeader>
          <CardContent className="pt-0">
            <span className="text-xs text-muted-foreground">Fluxo estimado deste mês</span>
          </CardContent>
        </Card>
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <div className="lg:col-span-1 space-y-6">
          <Card className="border-border bg-card/65 backdrop-blur-md">
            <CardHeader>
              <CardTitle className="text-lg font-semibold flex items-center gap-2">
                <Plus className="h-5 w-5 text-primary" /> Novo Lançamento Simulado
              </CardTitle>
            </CardHeader>
            <CardContent>
              <form onSubmit={handleAddSimulacao} className="space-y-4">
                <div>
                  <label className="mb-1.5 block text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                    Descrição
                  </label>
                  <Input 
                    value={descricao} 
                    onChange={e => setDescricao(e.target.value)} 
                    placeholder="Ex: Assinatura Streaming, Notebook Novo" 
                    required
                    id="sim-descricao"
                  />
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="mb-1.5 block text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                      Tipo
                    </label>
                    <Select 
                      value={tipo} 
                      onChange={e => setTipo(e.target.value)}
                      id="sim-tipo"
                    >
                      <option value="D">Despesa (Gasto)</option>
                      <option value="R">Receita (Entrada)</option>
                    </Select>
                  </div>
                  <div>
                    <label className="mb-1.5 block text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                      Valor (R$)
                    </label>
                    <Input 
                      value={valor} 
                      onChange={e => setValor(e.target.value)} 
                      type="number" 
                      step="0.01" 
                      placeholder="0,00" 
                      required
                      id="sim-valor"
                    />
                  </div>
                </div>

                <div>
                  <label className="mb-1.5 block text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                    Categoria
                  </label>
                  <Input 
                    value={categoria} 
                    onChange={e => setCategoria(e.target.value)} 
                    placeholder="Ex: Casa, Lazer, Salário"
                    list="sim-categorias-sugeridas"
                    id="sim-categoria"
                  />
                  <datalist id="sim-categorias-sugeridas">
                    {categoriasSugeridas.map(c => <option key={c} value={c} />)}
                  </datalist>
                </div>

                <div>
                  <label className="mb-1.5 block text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                    Mês de Início
                  </label>
                  <Select 
                    value={mesInicio} 
                    onChange={e => setMesInicio(e.target.value)}
                    id="sim-mes-inicio"
                  >
                    {projectionMonths.map(m => (
                      <option key={m.key} value={m.key}>{m.label}</option>
                    ))}
                  </Select>
                </div>

                <div>
                  <label className="mb-1.5 block text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                    Frequência
                  </label>
                  <Select 
                    value={frequencia} 
                    onChange={e => setFrequencia(e.target.value)}
                    id="sim-frequencia"
                  >
                    <option value="unica">Lançamento Único (Avulso)</option>
                    <option value="recorrente">Mensal Recorrente (Fixo)</option>
                    <option value="parcelada">Parcelado</option>
                  </Select>
                </div>

                {frequencia === 'parcelada' && (
                  <div className="animate-in slide-in-from-top-1 duration-200">
                    <label className="mb-1.5 block text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                      Quantidade de Parcelas (Meses)
                    </label>
                    <Input 
                      value={parcelas} 
                      onChange={e => setParcelas(e.target.value)} 
                      type="number" 
                      min="1" 
                      max="12"
                      required
                      id="sim-parcelas"
                    />
                  </div>
                )}

                <Button type="submit" className="w-full flex items-center justify-center gap-2">
                  <Plus className="h-4 w-4" /> Adicionar à Simulação
                </Button>
              </form>
            </CardContent>
          </Card>

          <Card className="border-border bg-card/65 backdrop-blur-md">
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <CardTitle className="text-lg font-semibold flex items-center gap-2">
                <Layers className="h-5 w-5 text-amber-500" /> Simulações Ativas
              </CardTitle>
              {simuladas.length > 0 && (
                <Button 
                  variant="link" 
                  size="sm" 
                  onClick={handleLimparTudo}
                  className="text-muted-foreground hover:text-destructive text-xs"
                >
                  Limpar Tudo
                </Button>
              )}
            </CardHeader>
            <CardContent className="max-h-[350px] overflow-y-auto pr-1 space-y-3">
              {simuladas.length === 0 ? (
                <div className="flex flex-col items-center justify-center py-6 text-center text-muted-foreground">
                  <AlertCircle className="h-8 w-8 mb-2 text-muted-foreground/50" />
                  <p className="text-xs">Nenhum lançamento simulado ativo.</p>
                  <p className="text-[10px] mt-1">Use o formulário acima para planejar cenários.</p>
                </div>
              ) : (
                simuladas.map((item) => (
                  <div 
                    key={item.id} 
                    className="flex items-center justify-between p-3 rounded-lg border border-border bg-muted/30 hover:bg-muted/60 transition-all duration-200"
                  >
                    <div className="space-y-1">
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-semibold text-foreground">{item.descricao}</span>
                        <Badge 
                          variant="secondary" 
                          className={item.tipo === 'R' ? 'bg-emerald-500/10 text-emerald-500' : 'bg-red-500/10 text-red-500'}
                        >
                          {item.tipo === 'R' ? 'Entrada' : 'Saída'}
                        </Badge>
                      </div>
                      <div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-muted-foreground">
                        <span className="font-semibold text-foreground/80">{formatCurrency(item.valor)}</span>
                        <span>•</span>
                        <span>{item.categoria}</span>
                        <span>•</span>
                        <span className="flex items-center gap-1 font-medium text-amber-500/95">
                          <Calendar className="h-3 w-3" />
                          {item.frequencia === 'unica' && `Único (${item.mesInicio})`}
                          {item.frequencia === 'recorrente' && `Recorrente (desde ${item.mesInicio})`}
                          {item.frequencia === 'parcelada' && `Parcelado (${item.parcelas}x desde ${item.mesInicio})`}
                        </span>
                      </div>
                    </div>
                    <Button 
                      variant="ghost" 
                      size="icon" 
                      onClick={() => handleRemoveSimulacao(item.id)} 
                      className="text-muted-foreground hover:text-destructive active:scale-95"
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </div>
                ))
              )}
            </CardContent>
          </Card>
        </div>

        <div className="lg:col-span-2 space-y-6">
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

          <Card className="border-border bg-card/65 backdrop-blur-md">
            <CardHeader>
              <CardTitle className="text-lg font-semibold flex items-center gap-2">
                <Calendar className="h-5 w-5 text-primary" /> Fluxo de Projeção Mensal
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="overflow-x-auto">
                <table className="w-full border-collapse text-left text-sm">
                  <thead>
                    <tr className="border-b border-border/80 text-muted-foreground text-xs font-semibold uppercase tracking-wider">
                      <th className="py-3 px-4">Mês</th>
                      <th className="py-3 px-3 text-right">Receitas (R+S)</th>
                      <th className="py-3 px-3 text-right">Despesas (R+S)</th>
                      <th className="py-3 px-3 text-right">Saldo do Mês</th>
                      <th className="py-3 px-3 text-right">Saldo Acumulado</th>
                      <th className="py-3 px-4 text-center">Simulações</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border/40">
                    {isLoading ? (
                      <tr>
                        <td colSpan="6" className="py-10 text-center text-muted-foreground text-xs">
                          Buscando contas a pagar e receitas...
                        </td>
                      </tr>
                    ) : (
                      monthlyData.map((data) => {
                        const hasSimulations = data.activeSimulatedItems.length > 0;
                        return (
                          <tr 
                            key={data.key} 
                            className="hover:bg-muted/20 transition-colors duration-150"
                          >
                            <td className="py-3.5 px-4 font-semibold text-foreground">
                              {data.label}
                            </td>
                            <td className="py-3.5 px-3 text-right text-xs">
                              <span className="text-muted-foreground font-medium block">
                                R: {formatCurrency(data.realRevenues)}
                              </span>
                              {data.simRevenues > 0 && (
                                <span className="text-emerald-500 font-bold block text-[10px]">
                                  S: +{formatCurrency(data.simRevenues)}
                                </span>
                              )}
                            </td>
                            <td className="py-3.5 px-3 text-right text-xs">
                              <span className="text-muted-foreground font-medium block">
                                R: {formatCurrency(data.realExpenses)}
                              </span>
                              {data.simExpenses > 0 && (
                                <span className="text-red-500 font-bold block text-[10px]">
                                  S: +{formatCurrency(data.simExpenses)}
                                </span>
                              )}
                            </td>
                            <td className="py-3.5 px-3 text-right">
                              <div className="text-xs">
                                <span className={`font-semibold block ${data.realNet >= 0 ? 'text-emerald-500/80' : 'text-red-500/80'}`}>
                                  R: {formatCurrency(data.realNet)}
                                </span>
                                <span className={`font-bold block ${data.simNet >= 0 ? 'text-emerald-500' : 'text-red-500'}`}>
                                  Proj: {formatCurrency(data.simNet)}
                                </span>
                              </div>
                            </td>
                            <td className="py-3.5 px-3 text-right">
                              <div className="text-xs">
                                <span className="text-muted-foreground block">
                                  R: {formatCurrency(data.accumulatedReal)}
                                </span>
                                <span className={`font-bold block text-sm ${data.accumulatedSim >= 0 ? 'text-emerald-500' : 'text-red-500'}`}>
                                  Proj: {formatCurrency(data.accumulatedSim)}
                                </span>
                              </div>
                            </td>
                            <td className="py-3.5 px-4 text-center">
                              {hasSimulations ? (
                                <Button 
                                  variant="outline" 
                                  size="sm" 
                                  onClick={() => setSelectedMonthDetails(data)}
                                  className="h-7 rounded px-2.5 text-xs bg-amber-500/5 hover:bg-amber-500/10 text-amber-600 dark:text-amber-400 border-amber-500/20"
                                >
                                  Ver ({data.activeSimulatedItems.length})
                                </Button>
                              ) : (
                                <span className="text-xs text-muted-foreground/40">—</span>
                              )}
                            </td>
                          </tr>
                        );
                      })
                    )}
                  </tbody>
                </table>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>

      {selectedMonthDetails && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4 animate-in fade-in duration-200">
          <div className="w-full max-w-md rounded-xl border border-border bg-card p-6 shadow-2xl space-y-4">
            <div className="flex items-center justify-between border-b border-border/80 pb-3">
              <h3 className="text-lg font-bold text-foreground flex items-center gap-2">
                <FolderOpen className="h-5 w-5 text-amber-500" /> Detalhes: {selectedMonthDetails.label}
              </h3>
              <Button 
                variant="ghost" 
                size="sm" 
                onClick={() => setSelectedMonthDetails(null)}
                className="h-8 w-8 p-0 text-muted-foreground hover:text-foreground"
              >
                ✕
              </Button>
            </div>
            
            <p className="text-xs text-muted-foreground">
              Abaixo estão os lançamentos simulados ativos que afetam a projeção deste mês específico:
            </p>

            <div className="space-y-3 max-h-[300px] overflow-y-auto pr-1">
              {selectedMonthDetails.activeSimulatedItems.map((item) => (
                <div 
                  key={item.id} 
                  className="p-3 rounded-lg border border-border bg-muted/40 flex justify-between items-center"
                >
                  <div className="space-y-0.5">
                    <div className="flex items-center gap-1.5">
                      <span className="text-sm font-semibold text-foreground">{item.descricao}</span>
                      <Badge className={item.tipo === 'R' ? 'bg-emerald-500/10 text-emerald-500 border border-emerald-500/20' : 'bg-red-500/10 text-red-500 border border-red-500/20'}>
                        {item.tipo === 'R' ? 'Entrada' : 'Saída'}
                      </Badge>
                    </div>
                    <div className="text-xs text-muted-foreground">
                      Categoria: <span className="text-foreground/80 font-medium">{item.categoria}</span>
                    </div>
                    <div className="text-[10px] text-amber-500/90 font-semibold uppercase">
                      {item.frequencia === 'unica' && 'Único'}
                      {item.frequencia === 'recorrente' && 'Recorrente'}
                      {item.frequencia === 'parcelada' && `Parcelado (${item.parcelas}x)`}
                    </div>
                  </div>
                  <div className="text-right">
                    <span className={`text-sm font-bold block ${item.tipo === 'R' ? 'text-emerald-500' : 'text-red-500'}`}>
                      {item.tipo === 'R' ? '+' : '-'}{formatCurrency(item.currentMonthVal)}
                    </span>
                  </div>
                </div>
              ))}
            </div>

            <div className="flex justify-end pt-2">
              <Button 
                variant="secondary" 
                onClick={() => setSelectedMonthDetails(null)}
                className="px-5"
              >
                Fechar
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
