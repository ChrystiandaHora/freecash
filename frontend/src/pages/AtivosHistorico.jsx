/**
 * Página do Livro-Razão e Histórico de Ordens da Carteira.
 * 
 * Exibe o extrato consolidado e cronológico de todas as operações executadas
 * (compras, vendas e recebimentos de dividendos) com suporte a filtros rápidos
 * por tipo de operação e buscas por ticker/nome de ativos.
 *
 * @component
 * @returns {React.JSX.Element}
 */
import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import api from '../services/api';
import {
  History,
  RefreshCw,
  AlertCircle,
  Plus,
  X,
  TrendingUp,
  TrendingDown,
  Gift,
  ArrowUpDown,
  ChevronDown,
  CheckCircle2,
  Filter
} from 'lucide-react';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '../components/ui/Card';
import { Button } from '../components/ui/Button';
import { Input } from '../components/ui/Input';
import { DataTable } from '../components/ui/DataTable';

/* ─────────────────────────── Helpers ─────────────────────────── */
const formatCurrency = (value) => {
  if (value === undefined || value === null) return 'R$ 0,00';
  return new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(value);
};

const formatDate = (dateStr) => {
  if (!dateStr) return '—';
  return new Intl.DateTimeFormat('pt-BR').format(new Date(dateStr + 'T00:00:00'));
};

const TIPO_CONFIG = {
  C: { label: 'Compra',   icon: TrendingUp,   color: 'text-emerald-500',  bg: 'bg-emerald-500/10' },
  V: { label: 'Venda',    icon: TrendingDown,  color: 'text-rose-500',     bg: 'bg-rose-500/10' },
  D: { label: 'Provento', icon: Gift,          color: 'text-amber-500',    bg: 'bg-amber-500/10' },
};

/* ─────────────────────────── Modal ─────────────────────────── */
/**
 * Componente modal para registro e lançamento de novas ordens na carteira.
 * 
 * Abstrai abas separadas para registrar operações padrão de Compra/Venda (C/V)
 * ou recebimento direto de proventos (JCP, Dividendos, Rendimentos de FII).
 * Integra-se dinamicamente com o TanStack React Query para invalidar dados
 * e forçar o re-fetch automático de cotações pós-mutação.
 *
 * @component
 * @param {Object} props - Propriedades do componente.
 * @param {Object[]} props.ativos - Coleção de ativos disponíveis para seleção.
 * @param {Function} props.onClose - Callback disparado ao fechar a modal.
 * @param {Function} props.onSuccess - Callback acionado pós-sucesso da mutação.
 * @returns {React.JSX.Element}
 */
function NovaOrdemModal({ ativos, onClose, onSuccess }) {
  const [tab, setTab] = useState('cv'); // 'cv' | 'proventos'
  const [form, setForm] = useState({
    ativo: '',
    tipo: 'C',
    data: new Date().toISOString().split('T')[0],
    quantidade: '',
    preco_unitario: '',
    taxas: '',
    valor_total_provento: '',
  });
  const [error, setError] = useState('');

  const queryClient = useQueryClient();

  const mutation = useMutation({
    mutationFn: async (payload) => {
      const res = await api.post('/api/investimentos/transacoes/', payload);
      return res.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries(['ativos']);
      queryClient.invalidateQueries(['investimentosDashboard']);
      queryClient.invalidateQueries(['investimentosBalanceamento']);
      queryClient.invalidateQueries(['transacoesInvestimento']);
      onSuccess();
    },
    onError: (err) => {
      const apiErr = err.response?.data;
      if (typeof apiErr === 'object' && apiErr !== null) {
        setError(Object.entries(apiErr).map(([key, val]) => `${key}: ${val}`).join(' | '));
      } else {
        setError('Erro ao registrar ordem.');
      }
    },
  });

  const set = (key) => (e) => {
    setForm((f) => ({ ...f, [key]: e.target.value }));
    setError('');
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!form.ativo) { setError('Selecione um ativo.'); return; }
    if (!form.data) { setError('Selecione a data da operação.'); return; }

    let payload = {};
    if (tab === 'proventos') {
      if (!form.valor_total_provento) {
        setError('Preencha o valor do provento.'); return;
      }
      payload = {
        ativo: parseInt(form.ativo),
        tipo: 'D',
        data: form.data,
        quantidade: 1,
        preco_unitario: parseFloat(form.valor_total_provento),
        taxas: 0,
      };
    } else {
      if (!form.quantidade || !form.preco_unitario) {
        setError('Preencha quantidade e preço unitário.'); return;
      }
      payload = {
        ativo: parseInt(form.ativo),
        tipo: form.tipo,
        data: form.data,
        quantidade: parseFloat(form.quantidade),
        preco_unitario: parseFloat(form.preco_unitario),
        taxas: parseFloat(form.taxas) || 0,
      };
    }
    mutation.mutate(payload);
  };

  const labelClass = 'block text-[11px] font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wider mb-1.5';
  const fieldClass = 'h-10 text-sm rounded-xl border-slate-200 dark:border-slate-700';

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-background/80 backdrop-blur-sm" onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <div className="bg-card rounded-2xl shadow-xl w-full max-w-lg border border-border/40 flex flex-col max-h-[90vh]">
        
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-border/40 shrink-0">
          <div>
            <h2 className="text-lg font-bold text-foreground">Nova Ordem</h2>
            <p className="text-xs text-muted-foreground mt-0.5">Registre uma compra, venda ou recebimento de proventos</p>
          </div>
          <button onClick={onClose} className="p-2 rounded-xl text-muted-foreground hover:bg-muted transition-colors">
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Tab selector */}
        <div className="px-6 pt-5 shrink-0">
          <div className="flex bg-muted p-1 rounded-xl">
            {[{ id: 'cv', label: 'Compra / Venda' }, { id: 'proventos', label: 'Proventos / JCP' }].map((t) => (
              <button
                key={t.id}
                type="button"
                onClick={() => { setTab(t.id); setError(''); }}
                className={`flex-1 py-2 text-xs font-semibold rounded-lg transition-all
                  ${tab === t.id ? 'bg-card shadow-sm text-primary' : 'text-muted-foreground hover:text-foreground'}`}
              >
                {t.label}
              </button>
            ))}
          </div>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="overflow-y-auto flex-1 px-6 py-5 space-y-4">

          {/* Ativo */}
          <div>
            <label className={labelClass}>Ativo</label>
            <select
              value={form.ativo}
              onChange={set('ativo')}
              className="w-full h-10 text-sm rounded-xl border border-border bg-card text-foreground px-3 focus:outline-none focus:ring-2 focus:ring-primary/50"
            >
              <option value="">Selecione...</option>
              {ativos.map((a) => (
                <option key={a.id} value={a.id}>{a.ticker} — {a.nome}</option>
              ))}
            </select>
          </div>

          {/* Data */}
          <div>
            <label className={labelClass}>Data</label>
            <Input type="date" value={form.data} onChange={set('data')} className={fieldClass} />
          </div>

          {tab === 'cv' ? (
            <>
              {/* Tipo C/V */}
              <div>
                <label className={labelClass}>Tipo de operação</label>
                <div className="flex gap-3">
                  {[{ v: 'C', l: 'Compra', color: 'emerald' }, { v: 'V', l: 'Venda', color: 'rose' }].map(({ v, l, color }) => (
                    <button
                      key={v}
                      type="button"
                      onClick={() => setForm((f) => ({ ...f, tipo: v }))}
                      className={`flex-1 py-2.5 rounded-xl text-sm font-bold border-2 transition-all
                        ${form.tipo === v
                          ? `border-${color}-500 bg-${color}-500/10 text-${color}-600 dark:text-${color}-400`
                          : 'border-slate-200 dark:border-slate-700 text-slate-500 hover:border-slate-300'}`}
                    >
                      {l}
                    </button>
                  ))}
                </div>
              </div>

              {/* Quantidade */}
              <div>
                <label className={labelClass}>Quantidade</label>
                <Input type="number" placeholder="0" min="0" step="0.00000001" value={form.quantidade} onChange={set('quantidade')} className={fieldClass} />
              </div>

              {/* Preço unitário */}
              <div>
                <label className={labelClass}>Preço unitário (R$)</label>
                <Input type="number" placeholder="0,00" min="0" step="0.01" value={form.preco_unitario} onChange={set('preco_unitario')} className={fieldClass} />
              </div>

              {/* Taxas */}
              <div>
                <label className={labelClass}>Taxas / Corretagem (R$)</label>
                <Input type="number" placeholder="0,00" min="0" step="0.01" value={form.taxas} onChange={set('taxas')} className={fieldClass} />
              </div>

              {/* Preview total */}
              {form.quantidade && form.preco_unitario && (
                <div className="p-3 rounded-xl bg-muted flex justify-between items-center">
                  <span className="text-xs font-semibold text-muted-foreground">Valor total estimado:</span>
                  <span className="text-sm font-extrabold text-foreground">
                    {formatCurrency(
                      parseFloat(form.quantidade) * parseFloat(form.preco_unitario) +
                      (form.tipo === 'C' ? 1 : -1) * parseFloat(form.taxas || 0)
                    )}
                  </span>
                </div>
              )}
            </>
          ) : (
            <>
              <div>
                <label className={labelClass}>Valor do provento recebido (R$)</label>
                <Input type="number" placeholder="0,00" min="0" step="0.01" value={form.valor_total_provento} onChange={set('valor_total_provento')} className={fieldClass} />
              </div>
              <p className="text-[11px] text-muted-foreground">
                Dividendos, JCP, Rendimentos de FII, Cupons, etc. O valor será registrado como tipo "Provento" e não altera sua quantidade de cotas.
              </p>
            </>
          )}

          {error && (
            <div className="flex items-center gap-2 p-3 rounded-xl bg-destructive/10 border border-destructive/20 text-destructive text-xs">
              <AlertCircle className="h-4 w-4 shrink-0" />
              <p className="font-semibold">{error}</p>
            </div>
          )}
        </form>

        {/* Footer */}
        <div className="flex gap-3 p-6 border-t border-border/40 shrink-0">
          <Button type="button" variant="outline" onClick={onClose} className="flex-1 rounded-xl h-10">
            Cancelar
          </Button>
          <Button
            type="submit"
            form="nova-ordem-form"
            onClick={handleSubmit}
            disabled={mutation.isPending}
            className="flex-1 rounded-xl h-10 bg-primary hover:bg-primary/90 text-primary-foreground border-0 font-semibold"
          >
            {mutation.isPending ? <RefreshCw className="h-4 w-4 animate-spin" /> : 'Registrar Ordem'}
          </Button>
        </div>
      </div>
    </div>
  );
}

/* ─────────────────────────── Main Page ─────────────────────────── */
export default function AtivosHistorico() {
  const [modalOpen, setModalOpen] = useState(false);
  const [filterTipo, setFilterTipo] = useState(''); // '' | 'C' | 'V' | 'D'
  const [filterAtivo, setFilterAtivo] = useState('');
  const [successMsg, setSuccessMsg] = useState(false);

  const columns = [
    {
      key: 'tipo',
      header: 'Tipo',
      render: (val) => {
        const cfg = TIPO_CONFIG[val] ?? TIPO_CONFIG['C'];
        const Icon = cfg.icon;
        return (
          <div className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg ${cfg.bg}`}>
            <Icon className={`h-3 w-3 ${cfg.color}`} />
            <span className={`text-[10px] font-bold ${cfg.color}`}>{cfg.label}</span>
          </div>
        );
      },
    },
    {
      key: 'data',
      header: 'Data',
      cellClassName: 'font-medium text-muted-foreground',
      render: (val) => formatDate(val),
    },
    {
      key: 'ativo',
      header: 'Ativo',
      render: (_, row) => (
        <>
          <p className="font-bold text-foreground">{row.ativo_detalhe?.ticker ?? '—'}</p>
          <p className="text-[10px] text-muted-foreground truncate max-w-[140px]">{row.ativo_detalhe?.nome}</p>
        </>
      ),
    },
    {
      key: 'quantidade',
      header: 'Qtd',
      className: 'text-right',
      cellClassName: 'text-right font-semibold text-foreground',
      render: (val, row) => row.tipo === 'D' ? '—' : parseFloat(val).toLocaleString('pt-BR'),
    },
    {
      key: 'preco_unitario',
      header: 'Preço Unit.',
      className: 'text-right',
      cellClassName: 'text-right text-muted-foreground',
      render: (val, row) => row.tipo === 'D' ? '—' : formatCurrency(val),
    },
    {
      key: 'taxas',
      header: 'Taxas',
      className: 'text-right',
      cellClassName: 'text-right text-muted-foreground',
      render: (val) => parseFloat(val ?? 0) > 0 ? formatCurrency(val) : '—',
    },
    {
      key: 'valor_total',
      header: 'Valor Total',
      className: 'text-right',
      cellClassName: 'text-right font-extrabold',
      render: (val, row) => {
        const cfg = TIPO_CONFIG[row.tipo] ?? TIPO_CONFIG['C'];
        return (
          <span className={cfg.color}>
            {formatCurrency(val)}
          </span>
        );
      },
    },
  ];

  const {
    data: transacoes,
    isLoading: isLoadingT,
    isError: isErrorT,
    refetch: refetchT,
  } = useQuery({
    queryKey: ['transacoesInvestimento'],
    queryFn: async () => {
      const res = await api.get('/api/investimentos/transacoes/');
      return res.data;
    },
  });

  const {
    data: ativos,
    isLoading: isLoadingA,
  } = useQuery({
    queryKey: ['ativos'],
    queryFn: async () => {
      const res = await api.get('/api/investimentos/ativos/');
      return res.data;
    },
  });

  const handleSuccess = () => {
    setModalOpen(false);
    setSuccessMsg(true);
    setTimeout(() => setSuccessMsg(false), 3000);
    refetchT();
  };

  /* Filtered list */
  const filtered = (transacoes ?? []).filter((t) => {
    if (filterTipo && t.tipo !== filterTipo) return false;
    if (filterAtivo && !(`${t.ativo_detalhe?.ticker} ${t.ativo_detalhe?.nome}`).toLowerCase().includes(filterAtivo.toLowerCase())) return false;
    return true;
  });

  const isLoading = isLoadingT || isLoadingA;

  if (isLoading) return (
    <div className="flex flex-col items-center justify-center min-h-[70vh] gap-4">
      <RefreshCw className="h-8 w-8 text-primary animate-spin" />
      <p className="text-sm font-semibold text-muted-foreground">Carregando histórico...</p>
    </div>
  );

  if (isErrorT) return (
    <div className="flex flex-col items-center justify-center min-h-[70vh] gap-4 text-center">
      <AlertCircle className="h-12 w-12 text-red-500" />
      <h3 className="text-xl font-bold text-slate-800 dark:text-slate-200">Erro ao carregar histórico</h3>
      <Button onClick={() => refetchT()}>Tentar novamente</Button>
    </div>
  );

  return (
    <div className="space-y-6 animate-fade-in">

      {/* ── Header ── */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <div>
          <h1 className="text-3xl font-extrabold tracking-tight text-foreground">
            Histórico de Ordens
          </h1>
          <p className="text-muted-foreground mt-1">
            Livro-razão de compras, vendas e proventos da carteira de ativos
          </p>
        </div>
        <div className="flex items-center gap-3 shrink-0">
          <Button
            onClick={() => setModalOpen(true)}
            className="h-9 px-4 rounded-xl text-xs font-semibold bg-primary hover:bg-primary/90 text-primary-foreground border-0 flex items-center gap-1.5"
          >
            <Plus className="h-4 w-4" />
            Nova Ordem
          </Button>
          <Button variant="outline" size="icon" onClick={() => refetchT()} className="rounded-xl h-9 w-9 shrink-0">
            <RefreshCw className="h-4 w-4 text-muted-foreground" />
          </Button>
        </div>
      </div>

      {/* ── Success ── */}
      {successMsg && (
        <div className="flex items-center gap-2.5 p-3.5 rounded-xl bg-emerald-50 dark:bg-emerald-950/20 border border-emerald-200/50 dark:border-emerald-800/30 text-emerald-600 dark:text-emerald-400 text-xs">
          <CheckCircle2 className="h-4 w-4 shrink-0" />
          <p className="font-semibold">Ordem registrada com sucesso!</p>
        </div>
      )}

      {/* ── KPI Summary ── */}
      <div className="grid grid-cols-3 gap-4">
        {(['C', 'V', 'D']).map((tipo) => {
          const cfg = TIPO_CONFIG[tipo];
          const Icon = cfg.icon;
          const count = (transacoes ?? []).filter((t) => t.tipo === tipo).length;
          const total = (transacoes ?? []).filter((t) => t.tipo === tipo).reduce((s, t) => s + parseFloat(t.valor_total || 0), 0);
          return (
            <Card key={tipo} className="border border-border/40 bg-card shadow-sm relative overflow-hidden">
              <CardContent className="pt-4 pb-4">
                <div className="flex items-center gap-3">
                  <div className={`w-10 h-10 rounded-xl ${cfg.bg} flex items-center justify-center shrink-0`}>
                    <Icon className={`h-4 w-4 ${cfg.color}`} />
                  </div>
                  <div>
                    <p className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider">{cfg.label}s</p>
                    <p className="text-lg font-bold text-foreground">{count}</p>
                    <p className="text-[10px] text-muted-foreground">{formatCurrency(total)}</p>
                  </div>
                </div>
              </CardContent>
            </Card>
          );
        })}
      </div>

      {/* ── Filters ── */}
      <Card className="border border-border/40 bg-card shadow-sm">
        <CardContent className="py-4 flex flex-wrap gap-4 items-center">
          <div className="flex items-center gap-2 text-xs font-semibold text-muted-foreground">
            <Filter className="h-3.5 w-3.5" />
            Filtros:
          </div>

          <div className="flex gap-2">
            {(['', 'C', 'V', 'D']).map((t) => (
              <button
                key={t || 'all'}
                onClick={() => setFilterTipo(t)}
                className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all border
                  ${filterTipo === t
                    ? 'bg-primary text-primary-foreground border-primary shadow-sm'
                    : 'border-border bg-card text-muted-foreground hover:bg-muted'}`}
              >
                {t ? TIPO_CONFIG[t].label : 'Todos'}
              </button>
            ))}
          </div>

          <div className="flex-1 min-w-[160px] max-w-xs">
            <Input
              placeholder="Buscar ativo..."
              value={filterAtivo}
              onChange={(e) => setFilterAtivo(e.target.value)}
              className="h-8 text-xs rounded-xl"
            />
          </div>

          <span className="text-xs text-muted-foreground ml-auto">
            {filtered.length} registro{filtered.length !== 1 ? 's' : ''}
          </span>
        </CardContent>
      </Card>

      {/* ── Ledger Table ── */}
      <Card className="border border-border/40 bg-card shadow-sm">
        <CardHeader>
          <CardTitle className="text-base font-bold text-foreground flex items-center gap-2">
            <History className="h-4 w-4 text-primary" />
            Livro-Razão de Ordens
          </CardTitle>
          <CardDescription className="text-xs">Histórico completo de operações registradas</CardDescription>
        </CardHeader>
        <CardContent className="px-0">
          <DataTable
            columns={columns}
            data={filtered}
            pageSize={10}
            emptyMessage="Nenhuma ordem encontrada no histórico."
          />
        </CardContent>
      </Card>

      {/* ── Modal ── */}
      {modalOpen && (
        <NovaOrdemModal
          ativos={ativos ?? []}
          onClose={() => setModalOpen(false)}
          onSuccess={handleSuccess}
        />
      )}
    </div>
  );
}
