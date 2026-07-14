/**
 * Tela de Gestão de Receitas e Entradas Financeiras.
 * 
 * Permite listar, filtrar por período (mês/ano) e cadastrar novas receitas ou fluxos
 * recorrentes de caixa. Renderiza cartões informativos contendo o consolidado previsto,
 * realizado e restante de entradas do mês de competência selecionado.
 *
 * @component
 * @returns {React.JSX.Element} Dashboard analítico e listagem de receitas.
 */
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import {
  Plus, TrendingUp, CheckCircle2, Clock,
  Loader2, RefreshCw, ArrowUpCircle, Repeat, Filter, Pencil,
  Trash2
} from 'lucide-react';

import { fetchReceitas, createReceita, updateReceita, deleteReceita } from '../services/financeiro';
import { DataTable } from '../components/ui/DataTable';
import { Badge } from '../components/ui/Badge';
import { Alert } from '../components/ui/Alert';
import { Button } from '../components/ui/Button';
import { Modal } from '../components/ui/Modal';
import { Input } from '../components/ui/Input';
import { Select } from '../components/ui/Select';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/Card';

// ─── Helpers ──────────────────────────────────────────────────────────────────

const formatCurrency = (val) =>
  new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(val ?? 0)

const formatDate = (dateStr) => {
  if (!dateStr) return '—'
  const [year, month, day] = dateStr.split('-')
  return `${day}/${month}/${year}`
}

// ─── Schema ───────────────────────────────────────────────────────────────────

const schema = z.object({
  descricao: z.string().min(3, 'Descrição obrigatória (mín. 3 caracteres)'),
  categoria: z.string().min(1, 'Informe a categoria'),
  valor: z.coerce.number().positive('Valor deve ser positivo'),
  data_recebimento: z.string().min(1, 'Data obrigatória'),
  tipo: z.enum(['unica', 'recorrente']),
  recorrencia: z.string().optional(),
  data_fim: z.string().optional(),
})

const MONTHS = [
  { value: 1, label: 'Janeiro' },
  { value: 2, label: 'Fevereiro' },
  { value: 3, label: 'Março' },
  { value: 4, label: 'Abril' },
  { value: 5, label: 'Maio' },
  { value: 6, label: 'Junho' },
  { value: 7, label: 'Julho' },
  { value: 8, label: 'Agosto' },
  { value: 9, label: 'Setembro' },
  { value: 10, label: 'Outubro' },
  { value: 11, label: 'Novembro' },
  { value: 12, label: 'Dezembro' }
]

const currentYear = new Date().getFullYear()
const YEARS = Array.from({ length: 7 }, (_, i) => currentYear - 2 + i)

// ─── Componente Principal ─────────────────────────────────────────────────────

export default function Receitas() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [deleteId, setDeleteId] = useState(null)
  const [fadingIds, setFadingIds] = useState(new Set())

  // Filtros de Mês e Ano
  const today = new Date()
  const [mes, setMes] = useState(today.getMonth() + 1)
  const [ano, setAno] = useState(today.getFullYear())

  const { data: receitas = [], isLoading, isError, refetch } = useQuery({
    queryKey: ['receitas', mes, ano],
    queryFn: () => fetchReceitas({ mes, ano }),
  })

  const { register, handleSubmit, reset, watch, setValue, formState: { errors, isSubmitting } } = useForm({
    resolver: zodResolver(schema),
    defaultValues: { tipo: 'unica' },
  })

  const watchTipo = watch('tipo')

  const deleteMutation = useMutation({
    mutationFn: deleteReceita,
    onMutate: (id) => {
      setFadingIds((prev) => new Set(prev).add(id))
    },
    onSuccess: () => {
      setTimeout(() => {
        queryClient.invalidateQueries({ queryKey: ['receitas'] })
        setFadingIds(new Set())
        setDeleteId(null)
      }, 500)
    },
  })

  const createMutation = useMutation({
    queryKey: ['receitas'],
    mutationFn: createReceita,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['receitas'] })
      setModalOpen(false)
      reset()
    },
  })

  const updateMutation = useMutation({
    mutationFn: updateReceita,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['receitas'] })
      setModalOpen(false)
      setEditingConta(null)
      reset()
    },
  })

  const handleEdit = (conta) => {
    navigate(`/receitas/editar/${conta.id}`)
  }

  // ─── KPIs ──────────────────────────────────────────────────────────────────
  const receitasMes = receitas
  const realizadas = receitasMes.filter((r) => r.realizada)
  const previstas = receitasMes.filter((r) => !r.realizada)

  const totalPrevisto = receitasMes.reduce((a, r) => a + Number(r.valor ?? 0), 0)
  const totalRealizado = realizadas.reduce((a, r) => a + Number(r.valor ?? 0), 0)

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
          >
            <Pencil className="h-4 w-4" />
          </Button>
          <Button
            size="sm"
            variant="ghost"
            className="h-8 w-8 p-0 rounded-lg text-rose-500 hover:text-rose-600 hover:bg-rose-50 dark:hover:bg-rose-950/20"
            onClick={() => setDeleteId(row.id)}
            title="Excluir"
          >
            <Trash2 className="h-4 w-4" />
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

      {/* Filtro de Período */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between bg-card border border-border/40 p-4 rounded-xl shadow-sm">
        <div className="flex items-center gap-2 text-muted-foreground text-sm font-medium">
          <Filter className="h-4 w-4 text-primary" />
          <span>Filtrar Período:</span>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          {/* Seletor de Mês */}
          <div className="w-[160px]">
            <Select value={mes} onChange={(e) => setMes(Number(e.target.value))}>
              {MONTHS.map((m) => (
                <option key={m.value} value={m.value}>
                  {m.label}
                </option>
              ))}
            </Select>
          </div>

          {/* Seletor de Ano */}
          <div className="w-[110px]">
            <Select value={ano} onChange={(e) => setAno(Number(e.target.value))}>
              {YEARS.map((y) => (
                <option key={y} value={y}>
                  {y}
                </option>
              ))}
            </Select>
          </div>

          {/* Botão de Reset Mês Atual */}
          {(mes !== today.getMonth() + 1 || ano !== today.getFullYear()) && (
            <Button
              variant="ghost"
              size="sm"
              onClick={() => {
                setMes(today.getMonth() + 1);
                setAno(today.getFullYear());
              }}
              className="text-xs text-muted-foreground hover:text-foreground h-10 px-3"
            >
              Mês Atual
            </Button>
          )}
        </div>
      </div>

      {/* KPIs do Mês */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <Card className="bg-card border border-border/40 shadow-sm text-card-foreground">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground uppercase tracking-wider">
              Previsto no Mês
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-bold text-foreground">{formatCurrency(totalPrevisto)}</p>
            <p className="text-xs text-muted-foreground mt-1">{receitasMes.length} receita(s)</p>
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

      {/* Tabela */}
      <DataTable
        columns={columns}
        data={receitas.map((r) => ({
          ...r,
          _fading: fadingIds.has(r.id),
        }))}
        isLoading={isLoading}
        pageSize={10}
        emptyMessage="Nenhuma receita cadastrada para o período selecionado."
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
