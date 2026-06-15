/**
 * Tela de Gestão de Contas a Pagar (Despesas/Compromissos).
 * 
 * Permite listar, filtrar, editar e registrar novas contas a pagar do investidor/usuário.
 * Oferece ações rápidas para liquidar/pagar compromissos diretamente a partir da listagem
 * e exibe o status de vencimento (Paga, Pendente, Atrasada ou Próxima) com cores representativas.
 *
 * @component
 * @returns {React.JSX.Element} Tela de controle de contas a pagar contendo KPIs de pendências e tabela CRUD.
 */
import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import {
  Plus, CheckCircle2, AlertCircle, Clock, Loader2,
  CalendarDays, Tag, DollarSign, RefreshCw, Filter, Pencil, CreditCard, ExternalLink,
  Trash2
} from 'lucide-react';


import { fetchContasPagar, createContaPagar, updateContaPagar, pagarConta, deleteContaPagar } from '../services/financeiro';
import { DataTable } from '../components/ui/DataTable';
import { Badge } from '../components/ui/Badge';
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

const getStatusInfo = (conta) => {
  if (conta.pago) return { label: 'Paga', variant: 'success', Icon: CheckCircle2 }

  const today = new Date()
  today.setHours(0, 0, 0, 0)

  const [year, month, day] = conta.data_vencimento.split('-')
  const due = new Date(Number(year), Number(month) - 1, Number(day))
  due.setHours(0, 0, 0, 0)

  if (due < today) return { label: 'Atrasado', variant: 'destructive', Icon: AlertCircle }

  const diffDays = Math.round((due - today) / (1000 * 60 * 60 * 24))

  if (diffDays === 0) return { label: 'Próximo Venc.', variant: 'warning', Icon: Clock }
  if (diffDays === 1) return { label: 'Venc. 1 dia', variant: 'warning', Icon: Clock }
  if (diffDays === 2) return { label: 'Venc. 2 dias', variant: 'warning', Icon: Clock }
  if (diffDays === 3) return { label: 'Venc. 3 dias', variant: 'warning', Icon: Clock }
  if (diffDays >= 4 && diffDays <= 7) return { label: 'Próximo Venc.', variant: 'warning', Icon: Clock }

  return { label: 'Pendente', variant: 'secondary', Icon: Clock }
}

// ─── Schema de validação ──────────────────────────────────────────────────────

const schema = z.object({
  descricao: z.string().min(3, 'Descrição obrigatória (mín. 3 caracteres)'),
  categoria: z.string().min(1, 'Informe a categoria'),
  valor: z.coerce.number().positive('Valor deve ser positivo'),
  data_vencimento: z.string().min(1, 'Data de vencimento obrigatória'),
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

const EMPTY_FORM = {
  descricao: '',
  categoria: '',
  valor: '',
  data_vencimento: ''
}

// ─── Componente Principal ─────────────────────────────────────────────────────

/**
 * Tela de Gerenciamento de Contas a Pagar e Obrigações Financeiras.
 * 
 * Permite a listagem, filtragem mensal/anual e manipulação de obrigações financeiras (CRUD).
 * Oferece ações rápidas para quitar/marcar contas como pagas com animação de fading visual de linha
 * e modais dedicados de cadastros com esquemas de validação robustos via Zod e React Hook Form.
 *
 * @component
 * @returns {React.JSX.Element}
 */
export default function ContasPagar() {
  const queryClient = useQueryClient()
  const navigate = useNavigate()
  const [modalOpen, setModalOpen] = useState(false)
  const [editingConta, setEditingConta] = useState(null)
  const [confirmId, setConfirmId] = useState(null) // ID da conta a quitar
  const [deleteId, setDeleteId] = useState(null) // ID da conta a excluir
  const [fadingIds, setFadingIds] = useState(new Set())

  // Filtros de Mês e Ano
  const today = new Date()
  const [mes, setMes] = useState(today.getMonth() + 1)
  const [ano, setAno] = useState(today.getFullYear())

  // Query
  const { data: contas = [], isLoading, isError, refetch } = useQuery({
    queryKey: ['contasPagar', mes, ano],
    queryFn: () => fetchContasPagar({ mes, ano }),
  })

  // Mutation: pagar conta
  const pagarMutation = useMutation({
    mutationFn: pagarConta,
    onMutate: (id) => {
      setFadingIds((prev) => new Set(prev).add(id))
    },
    onSuccess: () => {
      setTimeout(() => {
        queryClient.invalidateQueries({ queryKey: ['contasPagar'] })
        setFadingIds(new Set())
        setConfirmId(null)
      }, 500)
    },
  })

  // Mutation: excluir conta
  const deleteMutation = useMutation({
    mutationFn: deleteContaPagar,
    onMutate: (id) => {
      setFadingIds((prev) => new Set(prev).add(id))
    },
    onSuccess: () => {
      setTimeout(() => {
        queryClient.invalidateQueries({ queryKey: ['contasPagar'] })
        setFadingIds(new Set())
        setDeleteId(null)
      }, 500)
    },
  })

  // Mutation: criar conta
  const { register, handleSubmit, reset, formState: { errors, isSubmitting } } = useForm({
    resolver: zodResolver(schema),
  })

  const createMutation = useMutation({
    mutationFn: createContaPagar,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['contasPagar'] })
      setModalOpen(false)
      reset()
    },
  })

  const updateMutation = useMutation({
    mutationFn: updateContaPagar,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['contasPagar'] })
      setModalOpen(false)
      setEditingConta(null)
      reset()
    },
  })

  const onSubmit = (values) => {
    if (editingConta) {
      updateMutation.mutate({ id: editingConta.id, ...values })
    } else {
      createMutation.mutate(values)
    }
  }

  const handleEdit = (conta) => {
    setEditingConta(conta)
    reset({
      descricao: conta.descricao,
      categoria: conta.categoria || '',
      valor: conta.valor,
      data_vencimento: conta.data_vencimento
    })
    setModalOpen(true)
  }

  // ─── KPIs ──────────────────────────────────────────────────────────────────
  const pendentes = contas.filter((c) => !c.pago)
  const atrasadas = contas.filter((c) => {
    if (c.pago) return false
    const [year, month, day] = c.data_vencimento.split('-')
    const due = new Date(Number(year), Number(month) - 1, Number(day))
    due.setHours(0, 0, 0, 0)
    const today = new Date(); today.setHours(0, 0, 0, 0)
    return due < today
  })
  const totalPendente = pendentes.reduce((acc, c) => acc + Number(c.valor ?? 0), 0)
  const totalGeral = contas.reduce((acc, c) => acc + Number(c.valor ?? 0), 0)

  // ─── Colunas da tabela ─────────────────────────────────────────────────────
  const columns = [
    {
      key: 'data_vencimento',
      header: 'Vencimento',
      render: (val) => (
        <span className="flex items-center gap-1.5 font-mono text-xs text-muted-foreground">
          <CalendarDays className="h-3.5 w-3.5" />
          {formatDate(val)}
        </span>
      ),
    },
    {
      key: 'descricao',
      header: 'Descrição',
      render: (val, row) => (
        <span className="flex items-center gap-2">
          {row.eh_fatura_cartao && (
            <span
              title="Fatura de cartão de crédito — valor calculado automaticamente"
              className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-bold uppercase tracking-wide bg-blue-100 dark:bg-blue-900/40 text-blue-700 dark:text-blue-300 border border-blue-200 dark:border-blue-800 shrink-0"
            >
              <CreditCard className="h-2.5 w-2.5" />
              Cartão
            </span>
          )}
          <span className="font-medium text-foreground">{val}</span>
        </span>
      ),
    },

    {
      key: 'categoria',
      header: 'Categoria',
      render: (val) => (
        <span className="flex items-center gap-1.5 text-muted-foreground">
          <Tag className="h-3.5 w-3.5" />
          {val || '—'}
        </span>
      ),
    },
    {
      key: 'valor',
      header: 'Valor',
      render: (val) => (
        <span className="font-semibold text-foreground">
          {formatCurrency(val)}
        </span>
      ),
    },
    {
      key: 'status',
      header: 'Status',
      sortable: false,
      render: (_, row) => {
        const { label, variant, Icon } = getStatusInfo(row)
        return (
          <Badge variant={variant}>
            <Icon className="h-3 w-3" />
            {label}
          </Badge>
        )
      },
    },
    {
      key: 'acoes',
      header: 'Ação',
      sortable: false,
      render: (_, row) => {
        return (
          <div className="flex items-center gap-2">
            {!row.pago && (
              <Button
                size="sm"
                variant="ghost"
                className="h-8 w-8 p-0 rounded-lg text-emerald-600 dark:text-emerald-400 hover:bg-emerald-50 dark:hover:bg-emerald-950/20"
                onClick={() => setConfirmId(row.id)}
                title="Marcar como Pago"
              >
                <CheckCircle2 className="h-4 w-4" />
              </Button>
            )}
            {row.eh_fatura_cartao ? (
              // Faturas de cartão: navegar para Compras Cartão para ver/editar compras individuais + editar metadados
              <div className="flex items-center gap-1">
                <Button
                  size="sm"
                  variant="ghost"
                  className="h-8 w-8 p-0 rounded-lg text-blue-600 dark:text-blue-400 hover:bg-blue-50 dark:hover:bg-blue-900/20"
                  onClick={() => navigate('/compras-cartao')}
                  title="Ver compras individuais desta fatura"
                >
                  <ExternalLink className="h-4 w-4" />
                </Button>
                <Button
                  size="sm"
                  variant="ghost"
                  className="h-8 w-8 p-0 rounded-lg text-muted-foreground hover:text-foreground hover:bg-muted"
                  onClick={() => handleEdit(row)}
                  title="Editar"
                >
                  <Pencil className="h-4 w-4" />
                </Button>
              </div>
            ) : (
              // Contas normais: editar e excluir
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
            )}
          </div>
        )
      },
    },
  ]

  // ─── Render ────────────────────────────────────────────────────────────────
  return (
    <div className="space-y-6 animate-fade-in">
      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-3xl font-extrabold tracking-tight text-foreground">
            Contas a Pagar
          </h1>
          <p className="text-slate-500 dark:text-slate-400 mt-1">
            Gerencie suas obrigações financeiras
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={() => refetch()}>
            <RefreshCw className="mr-1.5 h-4 w-4" />
            Atualizar
          </Button>
          <Button variant="outline" size="sm" onClick={() => navigate('/contas-pagar/lote')}>
            Cadastro em Lote
          </Button>
          <Button onClick={() => { setEditingConta(null); reset(EMPTY_FORM); setModalOpen(true); }}>
            <Plus className="mr-1.5 h-4 w-4" />
            Nova Conta
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

      {/* KPIs */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <Card className="bg-card border border-border/40 shadow-sm text-card-foreground">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground uppercase tracking-wider">
              Total Pendente
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-bold text-foreground">{formatCurrency(totalPendente)}</p>
            <p className="text-xs text-muted-foreground mt-1">{pendentes.length} conta(s) em aberto</p>
          </CardContent>
        </Card>
 
        <Card className="bg-card border border-amber-500/30 shadow-sm text-card-foreground">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground uppercase tracking-wider">
              Atrasadas
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-bold text-rose-600 dark:text-rose-400">{atrasadas.length}</p>
            <p className="text-xs text-muted-foreground mt-1">
              {formatCurrency(atrasadas.reduce((a, c) => a + Number(c.valor ?? 0), 0))}
            </p>
          </CardContent>
        </Card>
 
        <Card className="bg-card border border-border/40 shadow-sm text-card-foreground">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground uppercase tracking-wider">
              Total Geral
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-bold text-foreground">{formatCurrency(totalGeral)}</p>
            <p className="text-xs text-muted-foreground mt-1">{contas.length} conta(s) no total</p>
          </CardContent>
        </Card>
      </div>

      {/* Error state */}
      {isError && (
        <div className="rounded-xl border border-red-500/20 bg-red-500/5 p-4 text-sm text-red-600 dark:text-red-400">
          Não foi possível carregar as contas. Verifique a conexão com a API.
        </div>
      )}

      {/* Tabela */}
      <div>
        <DataTable
          columns={columns}
          data={contas.map((c) => ({
            ...c,
            _fading: fadingIds.has(c.id),
          }))}
          isLoading={isLoading}
          pageSize={10}
          defaultSortKey="data_vencimento"
          defaultSortDir="asc"
          emptyMessage="Nenhuma conta cadastrada para o período selecionado."
          rowClassName={(row) =>
            row._fading ? 'opacity-0 scale-95 transition-all duration-500' : ''
          }
        />
      </div>

      {/* ─── Modal: Confirmar Pagamento ────────────────────────────────────────── */}
      <Modal
        isOpen={!!confirmId}
        onClose={() => setConfirmId(null)}
        title="Confirmar Pagamento"
        description="Esta ação marcará a conta como paga. Deseja continuar?"
      >
        <div className="flex gap-3 justify-end">
          <Button variant="outline" onClick={() => setConfirmId(null)}>
            Cancelar
          </Button>
          <Button
            onClick={() => pagarMutation.mutate(confirmId)}
            disabled={pagarMutation.isPending}
            className="bg-primary hover:bg-primary/90 text-primary-foreground border-0"
          >
            {pagarMutation.isPending ? (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            ) : (
              <CheckCircle2 className="mr-2 h-4 w-4" />
            )}
            Confirmar Pagamento
          </Button>
        </div>
      </Modal>

      {/* ─── Modal: Confirmar Exclusão ─────────────────────────────────────────── */}
      <Modal
        isOpen={!!deleteId}
        onClose={() => setDeleteId(null)}
        title="Confirmar Exclusão"
        description="Esta ação excluirá permanentemente a despesa. Deseja continuar?"
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

      {/* ─── Modal: Nova Conta ────────────────────────────────────────────────── */}
      <Modal
        isOpen={modalOpen}
        onClose={() => { setModalOpen(false); setEditingConta(null); reset() }}
        title={editingConta ? 'Editar Conta a Pagar' : 'Nova Conta a Pagar'}
        description={editingConta ? 'Altere os dados da obrigação financeira' : 'Preencha os dados da obrigação financeira'}
      >
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div className="sm:col-span-2">
              <label className="mb-1.5 block text-sm font-medium text-foreground">
                Descrição <span className="text-red-500">*</span>
              </label>
              <Input {...register('descricao')} placeholder="Ex: Aluguel Março" />
              {errors.descricao && (
                <p className="mt-1 text-xs text-red-500">{errors.descricao.message}</p>
              )}
            </div>

            <div>
              <label className="mb-1.5 block text-sm font-medium text-foreground">
                Categoria <span className="text-red-500">*</span>
              </label>
              <Input {...register('categoria')} placeholder="Ex: Moradia" />
              {errors.categoria && (
                <p className="mt-1 text-xs text-red-500">{errors.categoria.message}</p>
              )}
            </div>

            <div>
              <label className="mb-1.5 block text-sm font-medium text-foreground">
                Valor (R$) <span className="text-red-500">*</span>
              </label>
              <Input
                {...register('valor')}
                type="number"
                step="0.01"
                placeholder="0,00"
                readOnly={!!editingConta?.eh_fatura_cartao}
                className={editingConta?.eh_fatura_cartao ? "bg-muted cursor-not-allowed" : ""}
              />
              {errors.valor && (
                <p className="mt-1 text-xs text-red-500">{errors.valor.message}</p>
              )}
            </div>

            <div className="sm:col-span-2">
              <label className="mb-1.5 block text-sm font-medium text-foreground">
                Data de Vencimento <span className="text-red-500">*</span>
              </label>
              <Input
                {...register('data_vencimento')}
                type="date"
                readOnly={!!editingConta?.eh_fatura_cartao}
                className={editingConta?.eh_fatura_cartao ? "bg-muted cursor-not-allowed" : ""}
              />
              {errors.data_vencimento && (
                <p className="mt-1 text-xs text-red-500">{errors.data_vencimento.message}</p>
              )}
            </div>
          </div>

          {(createMutation.isError || updateMutation.isError) && (
            <p className="text-sm text-red-500">
              Erro ao salvar conta. Tente novamente.
            </p>
          )}

          <div className="flex justify-end gap-3 pt-2">
            <Button variant="outline" type="button" onClick={() => { setModalOpen(false); setEditingConta(null); reset() }}>
              Cancelar
            </Button>
            <Button type="submit" disabled={isSubmitting || createMutation.isPending || updateMutation.isPending}>
              {(isSubmitting || createMutation.isPending || updateMutation.isPending) && (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              )}
              <DollarSign className="mr-1.5 h-4 w-4" />
              Salvar Conta
            </Button>
          </div>
        </form>
      </Modal>
    </div>
  )
}
