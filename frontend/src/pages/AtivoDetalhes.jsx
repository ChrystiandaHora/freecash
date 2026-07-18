/**
 * Tela de Visualização Detalhada do Ativo (Livro-Razão & Indicadores).
 * 
 * Centraliza e exibe informações cadastrais, parâmetros de renda fixa,
 * métricas de rentabilidade a mercado e o histórico completo de transações do ativo.
 *
 * @component
 * @returns {React.JSX.Element} Tela widescreen SaaS Flat Premium.
 */
import { useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { 
  ArrowLeft,
  RefreshCw,
  AlertCircle,
  Calendar,
  Gem,
  Coins,
  Percent
} from 'lucide-react';

import api from '../services/api';
import Chart from 'react-apexcharts';
import { fetchAtivo, atualizarAtivo } from '../services/investimentos';
import { useToast } from '../context/ToastContext';
import { Button } from '../components/ui/Button';

// Helpers de formatação
const formatCurrency = (value) => {
  if (value === undefined || value === null) return 'R$ 0,00';
  return new Intl.NumberFormat('pt-BR', {
    style: 'currency',
    currency: 'BRL',
  }).format(value);
};

const formatPercentage = (value) => {
  if (value === undefined || value === null) return '0,00%';
  const num = parseFloat(value);
  const formatted = num.toFixed(2).replace('.', ',');
  return num >= 0 ? `+${formatted}%` : `${formatted}%`;
};

const formatCNPJ = (cnpj) => {
  if (!cnpj || cnpj.length !== 14) return cnpj;
  return `${cnpj.slice(0, 2)}.${cnpj.slice(2, 5)}.${cnpj.slice(5, 8)}/${cnpj.slice(8, 12)}-${cnpj.slice(12)}`;
};

export default function AtivoDetalhes() {
  const { id } = useParams();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { addToast } = useToast();
  const [activeTab, setActiveTab] = useState('geral'); // 'geral' | 'rentabilidade' | 'transacoes'

  /* ── Queries ── */
  const { data: ativo, isLoading: loadingAtivo, isError: errorAtivo } = useQuery({
    queryKey: ['ativoDetalhe', id],
    queryFn: () => fetchAtivo(id),
    enabled: !!id
  });

  const { data: transacoes = [], isLoading: loadingTransacoes } = useQuery({
    queryKey: ['transacoesAtivo', id],
    queryFn: async () => {
      const res = await api.get(`/api/investimentos/transacoes/?ativo=${id}`);
      return res.data;
    },
    enabled: !!id
  });

  /* ── Mutations ── */
  const updateAssetMutation = useMutation({
    mutationFn: () => atualizarAtivo(id),
    onSuccess: (data) => {
      // Invalida e força re-fetch de todos os dados relevantes deste ativo
      queryClient.invalidateQueries(['ativos']);
      queryClient.invalidateQueries(['ativoDetalhe', id]);
      queryClient.invalidateQueries(['transacoesAtivo', id]);
      queryClient.invalidateQueries(['investimentosDashboard']);

      const count = data?.count || 0;
      if (count > 0) {
        addToast(`Ativo atualizado! ${count} cotações salvas com sucesso.`, 'success');
      } else {
        addToast('Histórico do ativo já estava atualizado.', 'info');
      }
    },
    onError: (err) => {
      const errMsg = err?.response?.data?.error || 'Erro ao comunicar com o servidor.';
      addToast(`Falha ao atualizar ativo: ${errMsg}`, 'error');
    }
  });

  const handleRefresh = () => {
    updateAssetMutation.mutate();
  };

  const isLoading = loadingAtivo || loadingTransacoes;

  if (isLoading) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[70vh] gap-4">
        <RefreshCw className="h-8 w-8 text-primary animate-spin" />
        <p className="text-sm font-semibold text-muted-foreground">
          Carregando dados estruturados do ativo...
        </p>
      </div>
    );
  }

  if (errorAtivo || !ativo) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[70vh] gap-4 text-center max-w-md mx-auto">
        <AlertCircle className="h-12 w-12 text-destructive" />
        <h3 className="text-xl font-bold text-foreground">Ativo não encontrado</h3>
        <p className="text-sm text-muted-foreground">
          Não conseguimos carregar as informações deste ativo ou ele foi removido permanentemente da carteira.
        </p>
        <Button onClick={() => navigate('/investimentos/ativos')} className="mt-2 rounded-xl">
          Voltar para Ativos
        </Button>
      </div>
    );
  }

  // Cálculos financeiros locais
  const valorTotalAtual = parseFloat(ativo.valor_total_atual || 0);
  const rentabilidadePerc = parseFloat(ativo.rentabilidade_percentual || 0);
  const totalCustoInvestido = parseFloat(ativo.quantidade || 0) * parseFloat(ativo.preco_medio || 0);

  return (
    <div className="space-y-6 animate-fade-in text-foreground">
      
      {/* Botão Voltar & Cabeçalho Principal */}
      <div className="space-y-2">
        <button 
          onClick={() => navigate('/investimentos/ativos')}
          className="inline-flex items-center gap-1.5 text-xs font-semibold text-muted-foreground hover:text-foreground transition-colors active:scale-98"
        >
          <ArrowLeft className="h-3.5 w-3.5" />
          Voltar para Meus Ativos
        </button>

        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div className="flex items-center gap-3.5">
            <div className="w-12 h-12 rounded-2xl bg-primary/10 border border-primary/20 flex items-center justify-center shrink-0 shadow-sm">
              <Gem className="h-6 w-6 text-primary" />
            </div>
            <div>
              <h1 className="text-2xl font-bold tracking-tight text-foreground flex items-center gap-2">
                {ativo.ticker}
                <span className="inline-flex items-center rounded-lg bg-slate-100 dark:bg-slate-900 px-2.5 py-0.5 text-xs font-medium text-slate-800 dark:text-slate-300">
                  {ativo.subcategoria_detalhe?.nome || 'Subclasse não definida'}
                </span>
              </h1>
              <p className="text-xs text-muted-foreground mt-0.5">
                {ativo.nome || 'Visualização estruturada do ativo'}
              </p>
            </div>
          </div>

          {ativo.ticker && (
            <div className="flex items-center gap-2 shrink-0 self-start sm:self-auto">
              <Button 
                onClick={handleRefresh}
                disabled={updateAssetMutation.isPending}
                className="rounded-xl h-10 px-4 gap-2 font-semibold transition-all shadow-sm active:scale-98"
              >
                <RefreshCw className={`h-4 w-4 ${updateAssetMutation.isPending ? 'animate-spin' : ''}`} />
                {updateAssetMutation.isPending ? 'Atualizando Ativo...' : 'Atualizar Ativo'}
              </Button>
            </div>
          )}
        </div>
      </div>

      {/* Grid Rápido de KPIs a mercado */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        
        <div className="bg-card border border-border/40 shadow-sm text-card-foreground rounded-xl p-6 relative overflow-hidden transition-all hover:shadow-md">
          <div className="absolute -right-4 -bottom-4 h-16 w-16 opacity-5 text-foreground">
            <Coins className="h-full w-full" />
          </div>
          <p className="text-[10px] font-bold text-muted-foreground uppercase tracking-wider">Patrimônio Alocado</p>
          <h3 className="text-2xl font-bold tracking-tight text-foreground mt-2">
            {formatCurrency(valorTotalAtual)}
          </h3>
          <p className="text-xs text-muted-foreground mt-1">
            Posição atualizada a mercado
          </p>
        </div>

        <div className="bg-card border border-border/40 shadow-sm text-card-foreground rounded-xl p-6 relative overflow-hidden transition-all hover:shadow-md">
          <div className="absolute -right-4 -bottom-4 h-16 w-16 opacity-5 text-foreground">
            <Gem className="h-full w-full" />
          </div>
          <p className="text-[10px] font-bold text-muted-foreground uppercase tracking-wider">Custo Original (Principal)</p>
          <h3 className="text-2xl font-bold tracking-tight text-foreground mt-2">
            {formatCurrency(totalCustoInvestido)}
          </h3>
          <p className="text-xs text-muted-foreground mt-1">
            Cotas: <span className="font-semibold text-foreground/80">{parseFloat(ativo.quantidade || 0).toString().replace('.', ',')}</span> | P. Médio: <span className="font-semibold text-foreground/80">{formatCurrency(ativo.preco_medio)}</span>
          </p>
        </div>

        <div className="bg-card border border-border/40 shadow-sm text-card-foreground rounded-xl p-6 relative overflow-hidden transition-all hover:shadow-md">
          <div className="absolute -right-4 -bottom-4 h-16 w-16 opacity-5 text-foreground">
            <Percent className="h-full w-full" />
          </div>
          <p className="text-[10px] font-bold text-muted-foreground uppercase tracking-wider">Resultado Acumulado</p>
          <h3 className={`text-2xl font-bold tracking-tight mt-2 ${parseFloat(ativo.rentabilidade || 0) >= 0 ? 'text-primary' : 'text-rose-500'}`}>
            {formatCurrency(parseFloat(ativo.rentabilidade || 0))}
          </h3>
          <p className={`text-xs font-bold mt-1 ${parseFloat(ativo.rentabilidade || 0) >= 0 ? 'text-primary' : 'text-rose-500'}`}>
            {formatPercentage(rentabilidadePerc)}
          </p>
        </div>

      </div>

      {/* Box Principal de Conteúdo */}
      <div className="bg-card border border-border/40 shadow-sm text-card-foreground rounded-xl p-6 space-y-6">
        
        {/* Abas */}
        <div className="flex border-b border-border/40 self-start shrink-0 w-full">
          {[
            { id: 'geral', label: 'Parâmetros & Dados Gerais' },
            { id: 'rentabilidade', label: 'Desempenho Financeiro' },
            { id: 'transacoes', label: 'Histórico do Razão' }
          ].map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`px-4 py-2.5 text-xs font-bold uppercase tracking-wider border-b-2 transition-all gap-2 flex items-center ${activeTab === tab.id ? 'border-primary text-primary' : 'border-transparent text-muted-foreground hover:text-foreground'}`}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {/* Tab 1: Geral */}
        {activeTab === 'geral' && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6 animate-in fade-in duration-200">
            
            <div className="space-y-4 bg-muted/10 p-5 rounded-xl border border-border/20">
              <h3 className="text-sm font-bold text-foreground flex items-center gap-1.5 uppercase tracking-wider border-b border-border/20 pb-3">
                Dados Cadastrais
              </h3>
              <div className="grid grid-cols-2 gap-y-3 gap-x-4 text-xs">
                <span className="font-semibold text-muted-foreground">Código Ticker:</span>
                <span className="font-extrabold text-foreground">{ativo.ticker}</span>

                <span className="font-semibold text-muted-foreground">Nome do Ativo:</span>
                <span className="font-semibold text-foreground">{ativo.nome || '—'}</span>

                {ativo.cnpj && (
                  <>
                    <span className="font-semibold text-muted-foreground">CNPJ do Fundo:</span>
                    <span className="font-semibold text-foreground">{formatCNPJ(ativo.cnpj)}</span>
                  </>
                )}

                <span className="font-semibold text-muted-foreground">Segmento / Subclasse:</span>
                <span className="font-semibold text-foreground">
                  {ativo.subcategoria_detalhe?.categoria_detalhe?.nome || '—'} — {ativo.subcategoria_detalhe?.nome || '—'}
                </span>

                <span className="font-semibold text-muted-foreground">Alocação Alvo / Meta:</span>
                <span className="font-bold text-foreground">
                  {parseFloat(ativo.meta_porcentagem || 0).toFixed(1).replace('.', ',')}%
                </span>

                <span className="font-semibold text-muted-foreground">Status Operacional:</span>
                <span className="font-bold">
                  {ativo.ativo ? (
                    <span className="text-primary bg-primary/10 border border-primary/20 px-2 py-0.5 rounded-md text-[10px]">CUSTÓDIA ATIVA</span>
                  ) : (
                    <span className="text-muted-foreground bg-muted border border-border/40 px-2 py-0.5 rounded-md text-[10px]">ARQUIVADO</span>
                  )}
                </span>
              </div>
            </div>

            <div className="space-y-4 bg-muted/10 p-5 rounded-xl border border-border/20">
              <h3 className="text-sm font-bold text-foreground flex items-center gap-1.5 uppercase tracking-wider border-b border-border/20 pb-3">
                <Calendar className="h-4 w-4 text-muted-foreground" /> Detalhes Contratados (Renda Fixa/Dívida)
              </h3>
              <div className="grid grid-cols-2 gap-y-3 gap-x-4 text-xs">
                <span className="font-semibold text-muted-foreground">Emissor Financeiro:</span>
                <span className="font-semibold text-foreground">{ativo.emissor || '—'}</span>

                <span className="font-semibold text-muted-foreground">Maturidade / Vencimento:</span>
                <span className="font-semibold text-foreground">
                  {ativo.data_vencimento ? new Intl.DateTimeFormat('pt-BR').format(new Date(ativo.data_vencimento + 'T00:00:00')) : '—'}
                </span>

                <span className="font-semibold text-muted-foreground">Indexador Monetário:</span>
                <span className="font-semibold text-foreground">{ativo.indexador || '—'}</span>

                <span className="font-semibold text-muted-foreground">Taxa Nominal:</span>
                <span className="font-semibold text-foreground">
                  {ativo.taxa ? `${parseFloat(ativo.taxa).toString().replace('.', ',')}%` : '—'}
                </span>
              </div>
            </div>

          </div>
        )}

        {/* Tab 2: Rentabilidade */}
        {activeTab === 'rentabilidade' && (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 animate-in fade-in duration-200">
            
            {/* Coluna da esquerda: tabelas de preços e consolidação */}
            <div className="lg:col-span-1 space-y-6">
              <div className="space-y-4 bg-muted/10 p-5 rounded-xl border border-border/20">
                <h3 className="text-xs font-bold text-foreground uppercase tracking-wider border-b border-border/20 pb-3">
                  Comparativo de Preços
                </h3>
                <div className="grid grid-cols-2 gap-y-3 gap-x-4 text-xs">
                  <span className="text-muted-foreground">Preço Médio:</span>
                  <span className="font-semibold text-foreground">{formatCurrency(ativo.preco_medio)}</span>

                  <span className="text-muted-foreground">Cotação Atual:</span>
                  <span className="font-semibold text-foreground">{formatCurrency(ativo.cotacao_atual)}</span>

                  <span className="text-muted-foreground">Diferença/Preço:</span>
                  <span className={`font-bold ${parseFloat(ativo.cotacao_atual || 0) - parseFloat(ativo.preco_medio || 0) >= 0 ? 'text-primary' : 'text-rose-500'}`}>
                    {formatCurrency(parseFloat(ativo.cotacao_atual || 0) - parseFloat(ativo.preco_medio || 0))}
                  </span>
                </div>
              </div>

              <div className="space-y-4 bg-muted/10 p-5 rounded-xl border border-border/20">
                <h3 className="text-xs font-bold text-foreground uppercase tracking-wider border-b border-border/20 pb-3">
                  Resultado Consolidado
                </h3>
                <div className="grid grid-cols-2 gap-y-3 gap-x-4 text-xs">
                  <span className="text-muted-foreground">Total Pago:</span>
                  <span className="font-semibold text-foreground">{formatCurrency(totalCustoInvestido)}</span>

                  <span className="text-muted-foreground">Valor de Mercado:</span>
                  <span className="font-semibold text-foreground">{formatCurrency(valorTotalAtual)}</span>

                  <span className="font-bold text-foreground border-t border-border/20 pt-2 mt-1">Lucro/Prejuízo:</span>
                  <span className={`font-bold border-t border-border/20 pt-2 mt-1 ${parseFloat(ativo.rentabilidade || 0) >= 0 ? 'text-primary' : 'text-rose-500'}`}>
                    {formatCurrency(parseFloat(ativo.rentabilidade || 0))}
                  </span>
                </div>
              </div>
            </div>

            {/* Coluna da direita: gráfico de tendência de cotação */}
            <div className="lg:col-span-2 space-y-4 bg-muted/10 p-5 rounded-xl border border-border/20 flex flex-col">
              <h3 className="text-xs font-bold text-foreground uppercase tracking-wider border-b border-border/20 pb-3">
                Histórico de Cotações (Últimos 30 Dias)
              </h3>
              {ativo.historico_cotacoes && ativo.historico_cotacoes.length > 0 ? (
                <div className="flex-1 min-h-[220px]">
                  <Chart
                    options={{
                      chart: {
                        type: 'area',
                        height: 220,
                        sparkline: { enabled: false },
                        toolbar: { show: false },
                        fontFamily: 'inherit',
                        background: 'transparent',
                        animations: { enabled: true }
                      },
                      dataLabels: {
                        enabled: false
                      },
                      markers: {
                        size: 0,
                        hover: {
                          size: 5
                        }
                      },
                      colors: [rentabilidadePerc >= 0 ? '#10b981' : '#f43f5e'],
                      stroke: { curve: 'smooth', width: 2 },
                      fill: {
                        type: 'gradient',
                        gradient: {
                          shadeIntensity: 1,
                          opacityFrom: 0.3,
                          opacityTo: 0.01,
                          stops: [0, 90, 100],
                        },
                      },
                      xaxis: {
                        categories: (ativo.historico_cotacoes || []).map(q => {
                          const parts = q.data.split('-');
                          return `${parts[2]}/${parts[1]}`;
                        }),
                        labels: {
                          style: { colors: '#888888', fontSize: '9px', fontWeight: 500 }
                        },
                        axisBorder: { show: false },
                        axisTicks: { show: false },
                        tickAmount: 6
                      },
                      yaxis: {
                        labels: {
                          formatter: (val) => formatCurrency(val),
                          style: { colors: '#888888', fontSize: '9px', fontWeight: 500 }
                        }
                      },
                      grid: {
                        borderColor: 'rgba(148, 163, 184, 0.08)',
                        strokeDashArray: 4,
                        padding: {
                          left: 10,
                          right: 20
                        }
                      },
                      theme: {
                        mode: document.documentElement.classList.contains('dark') ? 'dark' : 'light',
                      },
                      tooltip: {
                        theme: document.documentElement.classList.contains('dark') ? 'dark' : 'light',
                        shared: true,
                        intersect: false,
                        y: {
                          formatter: (val) => formatCurrency(val),
                          title: { formatter: () => 'Preço: ' }
                        }
                      },
                    }}
                    series={[
                      { name: 'Fechamento', data: (ativo.historico_cotacoes || []).map(q => q.valor) }
                    ]}
                    type="area"
                    height={220}
                  />
                </div>
              ) : (
                <div className="flex-grow flex items-center justify-center text-xs text-muted-foreground py-12">
                  Nenhum registro histórico de cotações disponível para este ativo.
                </div>
              )}
            </div>

          </div>
        )}

        {/* Tab 3: Transações */}
        {activeTab === 'transacoes' && (
          <div className="space-y-4 animate-in fade-in duration-200">
            <div className="overflow-x-auto rounded-xl border border-border/40">
              <table className="w-full text-xs text-left border-collapse">
                <thead>
                  <tr className="border-b border-border/40 text-muted-foreground font-semibold bg-muted/20">
                    <th className="py-3 px-5">Operação</th>
                    <th className="py-3 px-5">Data Fiel</th>
                    <th className="py-3 px-5 text-right">Quantidade</th>
                    <th className="py-3 px-5 text-right">Preço Unit.</th>
                    <th className="py-3 px-5 text-right">Taxas / Encargos</th>
                    <th className="py-3 px-5 text-right">Total Líquido</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border/20">
                  {transacoes.length > 0 ? (
                    transacoes.map((t) => {
                      const isCompra = t.tipo === 'C';
                      const isVenda = t.tipo === 'V';
                      const isProvento = t.tipo === 'D';

                      let badgeColor = 'bg-slate-100 text-slate-700 dark:bg-slate-900 dark:text-slate-300';
                      let label = 'Operação';
                      if (isCompra) {
                        badgeColor = 'bg-emerald-500/10 text-emerald-500';
                        label = 'Compra';
                      } else if (isVenda) {
                        badgeColor = 'bg-rose-500/10 text-rose-500';
                        label = 'Venda';
                      } else if (isProvento) {
                        badgeColor = 'bg-amber-500/10 text-amber-500';
                        label = 'Provento';
                      }

                      return (
                        <tr key={t.id} className="hover:bg-muted/30 transition-colors">
                          <td className="py-3.5 px-5">
                            <span className={`inline-flex items-center rounded-lg px-2.5 py-0.5 text-[10px] font-bold uppercase tracking-wider ${badgeColor}`}>
                              {label}
                            </span>
                          </td>
                          <td className="py-3.5 px-5 text-muted-foreground font-semibold">
                            {new Intl.DateTimeFormat('pt-BR').format(new Date(t.data + 'T00:00:00'))}
                          </td>
                          <td className="py-3.5 px-5 text-right font-bold text-foreground/80">
                            {isProvento ? '—' : parseFloat(t.quantidade).toString().replace('.', ',')}
                          </td>
                          <td className="py-3.5 px-5 text-right text-muted-foreground">
                            {isProvento ? '—' : formatCurrency(t.preco_unitario)}
                          </td>
                          <td className="py-3.5 px-5 text-right text-muted-foreground">
                            {parseFloat(t.taxas || 0) > 0 ? formatCurrency(t.taxas) : '—'}
                          </td>
                          <td className={`py-3.5 px-5 text-right font-extrabold ${isCompra ? 'text-emerald-500' : isVenda ? 'text-rose-500' : 'text-amber-500'}`}>
                            {formatCurrency(t.valor_total)}
                          </td>
                        </tr>
                      );
                    })
                  ) : (
                    <tr>
                      <td colSpan={6} className="py-16 text-center text-muted-foreground font-semibold">
                        Nenhuma movimentação de livro-razão identificada para este ativo.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        )}

      </div>

    </div>
  );
}
