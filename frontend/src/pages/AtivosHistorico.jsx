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
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
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
  CheckCircle2,
  Filter,
  Pencil,
  Trash2
} from 'lucide-react';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '../components/ui/Card';
import { Button } from '../components/ui/Button';
import { Input } from '../components/ui/Input';
import { DataTable } from '../components/ui/DataTable';
import { Alert } from '../components/ui/Alert';

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
    </div>
  );
}

/* ─────────────────────────── Delete Confirm ─────────────────────────── */
function DeleteConfirmModal({ label, onConfirm, onClose, isPending }) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-background/80 backdrop-blur-sm">
      <div className="bg-card rounded-2xl shadow-xl w-full max-w-sm border border-border/40 p-6">
        <div className="flex flex-col items-center text-center gap-4">
          <div className="w-14 h-14 rounded-full bg-destructive/10 flex items-center justify-center">
            <Trash2 className="h-6 w-6 text-destructive" />
          </div>
          <div>
            <h3 className="text-base font-bold text-foreground">Confirmar exclusão</h3>
            <p className="text-sm text-muted-foreground mt-1">
              Tem certeza que deseja excluir a ordem de <span className="font-semibold text-foreground">{label}</span>? Esta ação não pode ser desfeita.
            </p>
          </div>
          <div className="flex gap-3 w-full">
            <Button variant="outline" onClick={onClose} className="flex-1 rounded-xl h-10 text-xs">Cancelar</Button>
            <Button onClick={onConfirm} disabled={isPending} className="flex-1 rounded-xl h-10 text-xs bg-destructive hover:bg-destructive/90 text-destructive-foreground border-0 font-semibold">
              {isPending ? <RefreshCw className="h-4 w-4 animate-spin" /> : 'Excluir'}
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}

/* ─────────────────────────── Main Page ─────────────────────────── */
export default function AtivosHistorico() {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const [deletingTransacao, setDeletingTransacao] = useState(null);
  const [filterTipo, setFilterTipo] = useState(''); // '' | 'C' | 'V' | 'D'
  const [filterAtivo, setFilterAtivo] = useState('');
  const [successMsg, setSuccessMsg] = useState('');

  const handleEdit = (transacao) => {
    navigate(`/investimentos/historico/editar/${transacao.id}`);
  };

  const deleteMutation = useMutation({
    mutationFn: async (id) => {
      await api.delete(`/api/investimentos/transacoes/${id}/`);
    },
    onSuccess: () => {
      queryClient.invalidateQueries(['ativos']);
      queryClient.invalidateQueries(['investimentosDashboard']);
      queryClient.invalidateQueries(['transacoesInvestimento']);
      setDeletingTransacao(null);
      setSuccessMsg('Ordem excluída com sucesso!');
      setTimeout(() => setSuccessMsg(''), 3000);
      refetchT();
    },
    onError: () => {
      alert('Erro ao excluir ordem.');
    }
  });

  const getDeleteLabel = (t) => {
    if (!t) return '';
    const tipoLabel = TIPO_CONFIG[t.tipo]?.label || '';
    const ticker = t.ativo_detalhe?.ticker || '';
    const dataFormatted = formatDate(t.data);
    return `${tipoLabel} de ${ticker} em ${dataFormatted}`;
  };

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
      className: 'text-left',
      cellClassName: 'text-left font-semibold text-foreground',
      render: (val, row) => row.tipo === 'D' ? '—' : parseFloat(val).toLocaleString('pt-BR'),
    },
    {
      key: 'preco_unitario',
      header: 'Preço Unit.',
      className: 'text-left',
      cellClassName: 'text-left text-muted-foreground',
      render: (val, row) => row.tipo === 'D' ? '—' : formatCurrency(val),
    },
    {
      key: 'taxas',
      header: 'Taxas',
      className: 'text-left',
      cellClassName: 'text-left text-muted-foreground',
      render: (val) => parseFloat(val ?? 0) > 0 ? formatCurrency(val) : '—',
    },
    {
      key: 'valor_total',
      header: 'Valor Total',
      className: 'text-left',
      cellClassName: 'text-left font-extrabold',
      render: (val, row) => {
        const cfg = TIPO_CONFIG[row.tipo] ?? TIPO_CONFIG['C'];
        return (
          <span className={cfg.color}>
            {formatCurrency(val)}
          </span>
        );
      },
    },
    {
      key: 'acoes',
      header: 'Ações',
      className: 'w-[100px] text-center',
      cellClassName: 'text-center',
      sortable: false,
      render: (_, row) => (
        <div className="flex items-center justify-center gap-1.5">
          <Button
            variant="outline"
            size="icon"
            onClick={() => handleEdit(row)}
            className="h-8 w-8 rounded-lg"
            title="Editar"
          >
            <Pencil className="h-3.5 w-3.5 text-muted-foreground hover:text-foreground" />
          </Button>
          <Button
            variant="outline"
            size="icon"
            onClick={() => setDeletingTransacao(row)}
            className="h-8 w-8 rounded-lg hover:bg-destructive/10 hover:border-destructive/30 group"
            title="Excluir"
          >
            <Trash2 className="h-3.5 w-3.5 text-muted-foreground group-hover:text-destructive transition-colors" />
          </Button>
        </div>
      ),
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

  const handleSuccess = (isEdit) => {
    setModalOpen(false);
    setEditingTransacao(null);
    setSuccessMsg(isEdit ? 'Ordem atualizada com sucesso!' : 'Ordem registrada com sucesso!');
    setTimeout(() => setSuccessMsg(''), 3000);
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
            onClick={() => navigate('/investimentos/historico/novo')}
            className="h-9 px-4 rounded-xl text-xs font-semibold bg-primary hover:bg-primary/95 text-primary-foreground border-0 flex items-center gap-1.5"
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
        <Alert variant="success" icon={CheckCircle2} className="text-xs">
          <span className="font-semibold">{successMsg}</span>
        </Alert>
      )}

      {/* ── KPI Summary ── */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
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



      {/* ── Delete Confirmation ── */}
      {deletingTransacao && (
        <DeleteConfirmModal
          label={getDeleteLabel(deletingTransacao)}
          onConfirm={() => deleteMutation.mutate(deletingTransacao.id)}
          onClose={() => setDeletingTransacao(null)}
          isPending={deleteMutation.isPending}
        />
      )}
    </div>
  );
}
