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
  TrendingUp,
  TrendingDown,
  Gift,
  CheckCircle2,
  Pencil,
  Trash2
} from 'lucide-react';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '../components/ui/Card';
import { Button } from '../components/ui/Button';
import { DataTable } from '../components/ui/DataTable';
import { Alert } from '../components/ui/Alert';
import { Modal } from '../components/ui/Modal';

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
    <Modal isOpen title="Confirmar exclusão" onClose={onClose} size="sm">
      <div className="flex flex-col items-center text-center gap-4">
        <div className="w-14 h-14 rounded-full bg-destructive/10 flex items-center justify-center">
          <Trash2 className="h-6 w-6 text-destructive" aria-hidden="true" />
        </div>
        <p className="text-sm text-muted-foreground">
          Tem certeza que deseja excluir a ordem de <span className="font-semibold text-foreground">{label}</span>? Esta ação não pode ser desfeita.
        </p>
        <div className="flex gap-3 w-full">
          <Button variant="outline" onClick={onClose} className="flex-1 rounded-xl h-10 text-xs">Cancelar</Button>
          <Button onClick={onConfirm} disabled={isPending} className="flex-1 rounded-xl h-10 text-xs bg-destructive hover:bg-destructive/90 text-destructive-foreground border-0 font-semibold">
            {isPending ? <RefreshCw className="h-4 w-4 animate-spin" aria-hidden="true" /> : 'Excluir'}
          </Button>
        </div>
      </div>
    </Modal>
  );
}

/* ─────────────────────────── Main Page ─────────────────────────── */
export default function AtivosHistorico() {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const [deletingTransacao, setDeletingTransacao] = useState(null);
  const [successMsg, setSuccessMsg] = useState('');
  const [errorMsg, setErrorMsg] = useState('');
  const [filteredTransacoes, setFilteredTransacoes] = useState(null);

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
      setDeletingTransacao(null);
      setErrorMsg('Erro ao excluir ordem. Tente novamente.');
      setTimeout(() => setErrorMsg(''), 5000);
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
      filterType: 'select',
      filterOptions: Object.entries(TIPO_CONFIG).map(([value, cfg]) => ({
        value,
        label: cfg.label,
      })),
      render: (val) => {
        const cfg = TIPO_CONFIG[val] ?? TIPO_CONFIG['C'];
        const Icon = cfg.icon;
        return (
          <div className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg ${cfg.bg}`}>
            <Icon className={`h-3 w-3 ${cfg.color}`} />
            <span className={`text-xs font-bold ${cfg.color}`}>{cfg.label}</span>
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
      filterType: 'text',
      filterPlaceholder: 'Ticker ou nome...',
      // O valor bruto é o ID do ativo; filtra-se pelo texto efetivamente exibido
      filterAccessor: (row) =>
        `${row.ativo_detalhe?.ticker ?? ''} ${row.ativo_detalhe?.nome ?? ''}`,
      render: (_, row) => (
        <>
          <p className="font-bold text-foreground">{row.ativo_detalhe?.ticker ?? '—'}</p>
          <p className="text-xs text-muted-foreground truncate max-w-[140px]">{row.ativo_detalhe?.nome}</p>
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
            aria-label="Editar ordem"
          >
            <Pencil className="h-3.5 w-3.5 text-muted-foreground hover:text-foreground" aria-hidden="true" />
          </Button>
          <Button
            variant="outline"
            size="icon"
            onClick={() => setDeletingTransacao(row)}
            className="h-8 w-8 rounded-lg hover:bg-destructive/10 hover:border-destructive/30 group"
            title="Excluir"
            aria-label="Excluir ordem"
          >
            <Trash2 className="h-3.5 w-3.5 text-muted-foreground group-hover:text-destructive transition-colors" aria-hidden="true" />
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

  const isLoading = isLoadingT;

  if (isLoading) return (
    <div role="status" className="flex flex-col items-center justify-center min-h-[70vh] gap-4">
      <RefreshCw className="h-8 w-8 text-primary animate-spin" aria-hidden="true" />
      <p className="text-sm font-semibold text-muted-foreground">Carregando histórico...</p>
    </div>
  );

  if (isErrorT) return (
    <div role="alert" className="flex flex-col items-center justify-center min-h-[70vh] gap-4 text-center">
      <AlertCircle className="h-12 w-12 text-red-500" aria-hidden="true" />
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
          <Button variant="outline" size="icon" onClick={() => refetchT()} className="rounded-xl h-9 w-9 shrink-0" aria-label="Atualizar histórico">
            <RefreshCw className="h-4 w-4 text-muted-foreground" aria-hidden="true" />
          </Button>
        </div>
      </div>

      {/* ── Feedback ── */}
      {successMsg && (
        <Alert variant="success" icon={CheckCircle2} className="text-xs">
          <span className="font-semibold">{successMsg}</span>
        </Alert>
      )}
      {errorMsg && (
        <Alert variant="error" icon={AlertCircle} className="text-xs">
          <span className="font-semibold">{errorMsg}</span>
        </Alert>
      )}

      {/* ── KPI Summary ── */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        {(['C', 'V', 'D']).map((tipo) => {
          const cfg = TIPO_CONFIG[tipo];
          const Icon = cfg.icon;
          const transacoesParaKpis = filteredTransacoes ?? transacoes;
          const count = (transacoesParaKpis ?? []).filter((t) => t.tipo === tipo).length;
          const total = (transacoesParaKpis ?? []).filter((t) => t.tipo === tipo).reduce((s, t) => s + parseFloat(t.valor_total || 0), 0);
          return (
            <Card key={tipo} className="border border-border/40 bg-card shadow-sm relative overflow-hidden">
              <CardContent className="pt-4 pb-4">
                <div className="flex items-center gap-3">
                  <div className={`w-10 h-10 rounded-xl ${cfg.bg} flex items-center justify-center shrink-0`}>
                    <Icon className={`h-4 w-4 ${cfg.color}`} />
                  </div>
                  <div>
                    <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">{cfg.label}s</p>
                    <p className="text-lg font-bold text-foreground">{count}</p>
                    <p className="text-xs text-muted-foreground">{formatCurrency(total)}</p>
                  </div>
                </div>
              </CardContent>
            </Card>
          );
        })}
      </div>

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
            data={transacoes ?? []}
            pageSize={10}
            emptyMessage="Nenhuma ordem encontrada no histórico."
            onFilteredDataChange={setFilteredTransacoes}
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
