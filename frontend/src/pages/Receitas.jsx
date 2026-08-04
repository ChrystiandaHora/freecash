/**
 * Tela de Gestão de Receitas e Entradas Financeiras.
 * 
 * Permite listar, filtrar por coluna (data, status, categoria) e cadastrar novas
 * receitas ou fluxos recorrentes de caixa. Renderiza cartões informativos contendo o
 * previsto do mês atual e o consolidado realizado/restante de todo o histórico.
 *
 * @component
 * @returns {React.JSX.Element} Dashboard analítico e listagem de receitas.
 */
import { useState, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Plus, CheckCircle2, Clock,
  Loader2, RefreshCw, Repeat, Pencil,
  Trash2
} from 'lucide-react';

import { fetchReceitas, deleteReceita } from '../services/financeiro';
import { DataTable } from '../components/ui/DataTable';
import { Badge } from '../components/ui/Badge';
import { Alert } from '../components/ui/Alert';
import { Button } from '../components/ui/Button';
import { Modal } from '../components/ui/Modal';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/Card';
import { getCurrentMonthDateRange } from '../lib/utils';

// ─── Helpers ──────────────────────────────────────────────────────────────────

const formatCurrency = (val) =>
  new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(val ?? 0)

const formatDate = (dateStr) => {
  if (!dateStr || typeof dateStr !== 'string') return '—'
  const parts = dateStr.split('-')
  if (parts.length < 3) return dateStr
  const [year, month, day] = parts
  return `${day}/${month}/${year}`
}

// ─── Componente Principal ─────────────────────────────────────────────────────

export default function Receitas() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [deleteId, setDeleteId] = useState(null)
  const [fadingIds, setFadingIds] = useState(new Set())
  const [filteredReceitas, setFilteredReceitas] = useState(null)
  const [actionError, setActionError] = useState('')

  const { data: receitas = [], isLoading, isError, refetch } = useQuery({
    queryKey: ['receitas'],
    queryFn: () => fetchReceitas(),
  })

  const deleteMutation = useMutation({
    mutationFn: deleteReceita,
    onMutate: (id) => {
      // Limpa o erro anterior: sem isso o banner role="alert" ficaria na tela
      // permanentemente, inclusive após um retry bem-sucedido.
      setActionError('')
      setFadingIds((prev) => new Set(prev).add(id))
    },
    onSuccess: () => {
      setTimeout(() => {
        queryClient.invalidateQueries({ queryKey: ['receitas'] })
        setFadingIds(new Set())
        setDeleteId(null)
      }, 500)
    },
    // Sem isto, uma falha de API deixaria a linha com fade otimista aplicado
    // permanentemente, sem qualquer aviso ao usuário.
    onError: () => {
      setFadingIds(new Set())
      setDeleteId(null)
      setActionError('Não foi possível excluir a receita. Tente novamente.')
    },
  })

  const handleEdit = (conta) => {
    navigate(`/receitas/editar/${conta.id}`)
  }

  // ─── KPIs (calculados dinamicamente com base nos filtros da tabela) ────────
  const receitasParaKpis = filteredReceitas ?? receitas
  const realizadas = (receitasParaKpis || []).filter((r) => r.realizada)
  const previstas = (receitasParaKpis || []).filter((r) => !r.realizada)

  const totalRealizado = realizadas.reduce((a, r) => a + Number(r.valor ?? 0), 0)

  // "Previsto no Mês" fica restrito ao mês atual: somar todo o histórico (anos de
  // receitas) não é uma métrica útil — a listagem completa já está na tabela abaixo.
  const hoje = new Date()
  const receitasMesAtual = (receitasParaKpis || []).filter((r) => {
    if (!r.data_recebimento || typeof r.data_recebimento !== 'string') return false
    const parts = r.data_recebimento.split('-')
    if (parts.length < 2) return false
    const [year, month] = parts
    return Number(month) === hoje.getMonth() + 1 && Number(year) === hoje.getFullYear()
  })
  const totalPrevistoMes = receitasMesAtual.reduce((a, r) => a + Number(r.valor ?? 0), 0)

  // ─── Dados da Tabela Memoizados ───────────────────────────────────────────
  const tableData = useMemo(() => {
    return (receitas || []).map((r) => ({
      ...r,
      _fading: fadingIds.has(r.id),
    }))
  }, [receitas, fadingIds])

  // ─── Colunas ───────────────────────────────────────────────────────────────
  const columns = [
    {
      key: 'data_recebimento',
      header: 'Data',
      render: (val) => (
        <span className="font-mono text-xs text-muted-foreground">{formatDate(val)}</span>
      ),
    },
    {
      key: 'descricao',
      header: 'Descrição',
      render: (val, row) => (
        <div className="flex items-center gap-2">
          {row.tipo === 'recorrente' && (
            <Repeat className="h-3.5 w-3.5 shrink-0 text-primary" title="Recorrente" />
          )}
          <span className="font-medium text-foreground">{val}</span>
        </div>
      ),
    },
    {
      key: 'categoria',
      header: 'Categoria',
      filterType: 'select',
      render: (val) => <span className="text-muted-foreground">{val || '—'}</span>,
    },
    {
      key: 'valor',
      header: 'Valor',
      render: (val) => (
        <span className="font-semibold text-emerald-600 dark:text-emerald-400">
          + {formatCurrency(val)}
        </span>
      ),
    },
    {
      key: 'realizada',
      header: 'Status',
      filterType: 'boolean',
      filterTrueLabel: 'Recebida',
      filterFalseLabel: 'Prevista',
      render: (val) =>
        val ? (
          <Badge variant="success">
            <CheckCircle2 className="h-3 w-3" />
            Recebida
          </Badge>
        ) : (
          <Badge variant="secondary">
            <Clock className="h-3 w-3" />
            Prevista
          </Badge>
        ),
    },
    {
      key: 'acoes',
      header: 'Ação',
      sortable: false,
      render: (_, row) => (
        <div className="flex items-center gap-1">
          <Button
            size="sm"
            variant="ghost"
            className="h-8 w-8 p-0 rounded-lg text-muted-foreground hover:text-foreground hover:bg-muted"
            onClick={() => handleEdit(row)}
            title="Editar"
            aria-label={`Editar ${row.descricao}`}
          >
            <Pencil className="h-4 w-4" aria-hidden="true" />
          </Button>
          <Button
            size="sm"
            variant="ghost"
            className="h-8 w-8 p-0 rounded-lg text-rose-500 hover:text-rose-600 hover:bg-rose-50 dark:hover:bg-rose-950/20"
            onClick={() => setDeleteId(row.id)}
            title="Excluir"
            aria-label={`Excluir ${row.descricao}`}
          >
            <Trash2 className="h-4 w-4" aria-hidden="true" />
          </Button>
        </div>
      ),
    },
  ]

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-3xl font-extrabold tracking-tight text-foreground">
            Receitas
          </h1>
          <p className="text-slate-500 dark:text-slate-400 mt-1">
            Acompanhe suas entradas financeiras
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={() => refetch()}>
            <RefreshCw className="mr-1.5 h-4 w-4" />
            Atualizar
          </Button>
          <Button onClick={() => navigate('/receitas/novo')}>
            <Plus className="mr-1.5 h-4 w-4" />
            Nova Receita
          </Button>
        </div>
      </div>

      {/* KPIs */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <Card className="bg-card border border-border/40 shadow-sm text-card-foreground">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground uppercase tracking-wider">
              Previsto no Mês
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-bold text-foreground">{formatCurrency(totalPrevistoMes)}</p>
            <p className="text-xs text-muted-foreground mt-1">{receitasMesAtual.length} receita(s)</p>
          </CardContent>
        </Card>
 
        <Card className="bg-card border border-emerald-500/30 shadow-sm text-card-foreground">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground uppercase tracking-wider">
              Receitas Realizadas
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-bold text-emerald-600 dark:text-emerald-400">{formatCurrency(totalRealizado)}</p>
            <p className="text-xs text-muted-foreground mt-1">{realizadas.length} recebida(s)</p>
          </CardContent>
        </Card>
 
        <Card className="bg-card border border-border/40 shadow-sm text-card-foreground">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground uppercase tracking-wider">
              Ainda Previstas
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-bold text-amber-600 dark:text-amber-400">
              {formatCurrency(previstas.reduce((a, r) => a + Number(r.valor ?? 0), 0))}
            </p>
            <p className="text-xs text-muted-foreground mt-1">{previstas.length} a receber</p>
          </CardContent>
        </Card>
      </div>

      {/* Error */}
      {isError && (
        <Alert variant="error">
          Não foi possível carregar as receitas. Verifique a conexão com a API.
        </Alert>
      )}

      {/* Erro de exclusão */}
      {actionError && (
        <Alert variant="error">
          {actionError}
        </Alert>
      )}

      {/* Tabela */}
      <DataTable
        columns={columns}
        data={tableData}
        isLoading={isLoading}
        pageSize={10}
        defaultFilters={{ data_recebimento: getCurrentMonthDateRange() }}
        emptyMessage="Nenhuma receita cadastrada."
        onFilteredDataChange={setFilteredReceitas}
        rowClassName={(row) =>
          row._fading ? 'opacity-0 scale-95 transition-all duration-500' : ''
        }
      />

      {/* ─── Modal: Cadastro / Edição ─────────────────────────────────────────── */}


      {/* ─── Modal: Confirmar Exclusão ─────────────────────────────────────────── */}
      <Modal
        isOpen={!!deleteId}
        onClose={() => setDeleteId(null)}
        title="Confirmar Exclusão"
        description="Esta ação excluirá permanentemente a receita. Deseja continuar?"
      >
        <div className="flex gap-3 justify-end">
          <Button variant="outline" onClick={() => setDeleteId(null)}>
            Cancelar
          </Button>
          <Button
            onClick={() => deleteMutation.mutate(deleteId)}
            disabled={deleteMutation.isPending}
            className="bg-rose-600 hover:bg-rose-700 text-white border-0"
          >
            {deleteMutation.isPending ? (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            ) : (
              <Trash2 className="mr-2 h-4 w-4" />
            )}
            Confirmar Exclusão
          </Button>
        </div>
      </Modal>
    </div>
  )
}
