/**
 * Tela de Gestão de Contas a Pagar (Despesas/Compromissos).
 * 
 * Permite listar, filtrar, editar e registrar novas contas a pagar do investidor/usuário.
 * Oferece ações rápidas para liquidar/pagar compromissos diretamente a partir da listagem
 * e exibe o status de vencimento (Paga, Pendente, Atrasada ou Próxima) com cores representativas.
 *
 * @returns {React.JSX.Element} Tela de controle de contas a pagar contendo KPIs de pendências e tabela CRUD.
 */
import { useState, useMemo } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import {
  Plus, CheckCircle2, AlertCircle, Clock, Loader2,
  CalendarDays, Tag, RefreshCw, Pencil, CreditCard, ExternalLink,
  Trash2, RotateCcw, KanbanSquare, Table2
} from 'lucide-react';

import { fetchContasPagar, pagarConta, deleteContaPagar, desfazerPagamentoConta } from '../services/financeiro';
import { DataTable } from '../components/ui/DataTable';
import { Badge } from '../components/ui/Badge';
import { Alert } from '../components/ui/Alert';
import { Button } from '../components/ui/Button';
import { Modal } from '../components/ui/Modal';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/Card';
import { getCurrentMonthDateRange } from '../lib/utils';
import { useToast } from '../context/ToastContext';
import QuadroContasPagar from '../components/contas/QuadroContasPagar';

// ─── Visões ───────────────────────────────────────────────────────────────────

const TABS = [
  { id: 'kanban', label: 'Kanban', Icon: KanbanSquare },
  { id: 'tabela', label: 'Tabela', Icon: Table2 },
]

const CHAVE_VISTA = 'freecash-contas-pagar-vista'

// Preferência de exibição de um dispositivo, no mesmo padrão do tema e da carteira:
// atravessa o F5 e não tem por que ir para o servidor.
const lerVistaSalva = () => {
  try {
    const salva = localStorage.getItem(CHAVE_VISTA)
    return TABS.some((t) => t.id === salva) ? salva : 'kanban'
  } catch {
    return 'kanban'
  }
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

const formatCurrency = (val) =>
  new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(val ?? 0)

const formatDate = (dateStr) => {
  if (!dateStr) return '—'
  const [year, month, day] = dateStr.split('-')
  return `${day}/${month}/${year}`
}

const getStatusInfo = (conta) => {
  if (!conta) return { label: 'Pendente', variant: 'secondary', Icon: Clock }
  if (conta.pago) return { label: 'Pago', variant: 'success', Icon: CheckCircle2 }

  if (!conta.data_vencimento || typeof conta.data_vencimento !== 'string') {
    return { label: 'Pendente', variant: 'secondary', Icon: Clock }
  }

  const today = new Date()
  today.setHours(0, 0, 0, 0)

  const parts = conta.data_vencimento.split('-')
  if (parts.length < 3) return { label: 'Pendente', variant: 'secondary', Icon: Clock }

  const [year, month, day] = parts
  const due = new Date(Number(year), Number(month) - 1, Number(day))
  due.setHours(0, 0, 0, 0)

  if (due < today) return { label: 'Atrasado', variant: 'destructive', Icon: AlertCircle }

  const diffDays = Math.round((due - today) / (1000 * 60 * 60 * 24))

  if (diffDays === 0) return { label: 'Vence Hoje', variant: 'urgent', Icon: Clock }
  if (diffDays === 1) return { label: 'Vence amanhã', variant: 'urgent', Icon: Clock }
  if (diffDays === 2) return { label: 'Vence 2 dias', variant: 'warning', Icon: Clock }
  if (diffDays === 3) return { label: 'Vence 3 dias', variant: 'warning', Icon: Clock }

  return { label: 'Pendente', variant: 'secondary', Icon: Clock }
}

// ─── Componente Principal ─────────────────────────────────────────────────────

/**
 * Tela de Gerenciamento de Contas a Pagar e Obrigações Financeiras.
 * 
 * Permite a listagem, filtragem por coluna (data, status, categoria) e manipulação de obrigações financeiras (CRUD).
 * Oferece ações rápidas para quitar/marcar contas como pagas com animação de fading visual de linha
 * e modais dedicados de cadastros com esquemas de validação robustos via Zod e React Hook Form.
 */
export default function ContasPagar() {
  const queryClient = useQueryClient()
  const navigate = useNavigate()
  const { addToast } = useToast()
  const [confirmId, setConfirmId] = useState(null) // ID da conta a quitar
  const [deleteId, setDeleteId] = useState(null) // ID da conta a excluir
  const [deletingConta, setDeletingConta] = useState(null) // Conta em exclusão (para o aviso de cascata)
  const [desfazerPagamentoId, setDesfazerPagamentoId] = useState(null) // ID da conta a reverter pagamento
  const [editingConta, setEditingConta] = useState(null)
  const [fadingIds, setFadingIds] = useState(new Set())
  const [filteredContas, setFilteredContas] = useState(null)
  const [actionError, setActionError] = useState('')
  const [vista, setVista] = useState(lerVistaSalva)

  const trocarVista = (proxima) => {
    setVista(proxima)
    try {
      localStorage.setItem(CHAVE_VISTA, proxima)
    } catch {
      // Janela privada ou storage bloqueado: a escolha ainda vale nesta sessão.
    }
  }

  const handleTabKeyDown = (event, index) => {
    const keyToIndex = {
      ArrowRight: (index + 1) % TABS.length,
      ArrowLeft: (index - 1 + TABS.length) % TABS.length,
      Home: 0,
      End: TABS.length - 1,
    }
    const nextIndex = keyToIndex[event.key]
    if (nextIndex === undefined) return

    event.preventDefault()
    const nextTab = TABS[nextIndex]
    trocarVista(nextTab.id)
    document.getElementById(`tab-${nextTab.id}`)?.focus()
  }

  /**
   * Reverte o fade otimista da linha e informa o erro.
   * Sem isso, uma falha de API deixaria a linha "desaparecida" para sempre, sem feedback algum.
   */
  const handleMutationError = (mensagem) => {
    setFadingIds(new Set())
    setConfirmId(null)
    setDeleteId(null)
    setDeletingConta(null)
    setDesfazerPagamentoId(null)
    setActionError(mensagem)
  }

  /**
   * Limpa o erro anterior ao iniciar uma nova tentativa. Sem isso o banner
   * `role="alert"` ficaria na tela permanentemente, inclusive após um retry
   * bem-sucedido, e reanunciaria a cada remontagem.
   */
  const beginMutation = (id) => {
    setActionError('')
    if (id !== undefined) setFadingIds((prev) => new Set(prev).add(id))
  }

  // Query
  const { data: contas = [], isLoading, isError, isFetching, refetch } = useQuery({
    queryKey: ['contasPagar'],
    queryFn: () => fetchContasPagar(),
  })

  const handleAtualizar = async () => {
    try {
      await refetch()
      addToast('Dados atualizados.', 'success')
    } catch {
      addToast('Não foi possível atualizar os dados.', 'error')
    }
  }

  // Mutation: pagar conta
  const pagarMutation = useMutation({
    mutationFn: pagarConta,
    onMutate: beginMutation,
    onSuccess: () => {
      setTimeout(() => {
        queryClient.invalidateQueries({ queryKey: ['contasPagar'] })
        setFadingIds(new Set())
        setConfirmId(null)
      }, 500)
    },
    onError: () => handleMutationError('Não foi possível registrar o pagamento. Tente novamente.'),
  })

  // Mutation: excluir conta
  const deleteMutation = useMutation({
    mutationFn: deleteContaPagar,
    onMutate: beginMutation,
    onSuccess: () => {
      setTimeout(() => {
        queryClient.invalidateQueries({ queryKey: ['contasPagar'] })
        // Excluir uma fatura remove também as compras do cartão: revalida essas telas
        queryClient.invalidateQueries({ queryKey: ['compras-cartao'] })
        queryClient.invalidateQueries({ queryKey: ['cartoes'] })
        setFadingIds(new Set())
        setDeleteId(null)
        setDeletingConta(null)
      }, 500)
    },
    onError: () => handleMutationError('Não foi possível excluir a conta. Tente novamente.'),
  })

  // Mutation: desfazer pagamento
  const desfazerPagamentoMutation = useMutation({
    mutationFn: desfazerPagamentoConta,
    onMutate: () => beginMutation(),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['contasPagar'] })
      setDesfazerPagamentoId(null)
      setEditingConta(null)
    },
    onError: () => handleMutationError('Não foi possível desfazer o pagamento. Tente novamente.'),
  })



  const handleEdit = (conta) => {
    navigate(`/contas-pagar/editar/${conta.id}`)
  }

  // ─── Ordenação inteligente: atrasadas → pendentes → pagas ─────────────────
  const contasOrdenadas = useMemo(() => {
    const todayMs = new Date().setHours(0, 0, 0, 0)

    const prioridade = (c) => {
      if (!c) return 3
      if (c.pago) return 3
      if (!c.data_vencimento || typeof c.data_vencimento !== 'string') return 2
      const parts = c.data_vencimento.split('-')
      if (parts.length < 3) return 2
      const [y, m, d] = parts
      const due = new Date(Number(y), Number(m) - 1, Number(d)).setHours(0, 0, 0, 0)
      if (due < todayMs) return 0  // atrasada
      if (due === todayMs) return 1 // vence hoje
      return 2                      // pendente futura
    }

    return [...(contas || [])].sort((a, b) => {
      const diff = prioridade(a) - prioridade(b)
      if (diff !== 0) return diff
      return (a?.data_vencimento || '').localeCompare(b?.data_vencimento || '')
    })
  }, [contas])

  // O quadro mostra o mês corrente, o mesmo recorte que /contas-kanban pede ao
  // servidor. Sem data de vencimento a conta fica fora, como no filtro de lá.
  const contasDoMes = useMemo(() => {
    const { from, to } = getCurrentMonthDateRange()
    return (contasOrdenadas || []).filter(
      (c) => typeof c.data_vencimento === 'string' && c.data_vencimento >= from && c.data_vencimento <= to
    )
  }, [contasOrdenadas])

  // ─── KPIs ──────────────────────────────────────────────────────────────────
  // Os três indicadores descrevem o conjunto que está à vista: sob a tabela, o que o
  // filtro dela deixou; sob o quadro, o mês que o quadro mostra. Deixá-los presos ao
  // filtro da tabela faria o kanban exibir números de um recorte invisível.
  const contasParaKpis = vista === 'kanban' ? contasDoMes : (filteredContas ?? contasOrdenadas)
  const pendentes = (contasParaKpis || []).filter((c) => !c.pago)
  const atrasadas = (contasParaKpis || []).filter((c) => {
    if (c.pago || !c.data_vencimento || typeof c.data_vencimento !== 'string') return false
    const parts = c.data_vencimento.split('-')
    if (parts.length < 3) return false
    const [year, month, day] = parts
    const due = new Date(Number(year), Number(month) - 1, Number(day))
    due.setHours(0, 0, 0, 0)
    const today = new Date(); today.setHours(0, 0, 0, 0)
    return due < today
  })
  const totalPendente = pendentes.reduce((acc, c) => acc + Number(c.valor ?? 0), 0)

  // Terceiro indicador: o que já foi PAGO dentro do período filtrado.
  //
  // Antes ele somava "o mês atual" — mas calculado sobre o conjunto já filtrado, o
  // que o tornava a interseção entre o período escolhido e o mês corrente. Filtrando
  // qualquer outro mês, essa interseção é vazia e o card exibia R$ 0,00 com a tabela
  // cheia. No filtro de julho, os três indicadores mostravam zero para 15 linhas
  // liquidadas — a tela informava nada.
  //
  // Agora os três descrevem o MESMO conjunto: o que está na tabela. "Pago" completa
  // "pendente" e "atrasadas" e nunca é trivialmente zero quando há linhas.
  const pagas = (contasParaKpis || []).filter((c) => c.pago)
  const totalPago = pagas.reduce((acc, c) => acc + Number(c.valor ?? 0), 0)

  // ─── Dados da Tabela Memoizados ───────────────────────────────────────────
  const tableData = useMemo(() => {
    return (contasOrdenadas || []).map((c) => ({
      ...c,
      _fading: fadingIds.has(c.id),
    }))
  }, [contasOrdenadas, fadingIds])
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
              className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-xs font-bold uppercase tracking-wide bg-blue-100 dark:bg-blue-900/40 text-blue-700 dark:text-blue-300 border border-blue-200 dark:border-blue-800 shrink-0"
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
      filterType: 'select',
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
      // Coluna derivada: não é ordenável, mas o filtro é útil e usa o status calculado
      filterable: true,
      filterType: 'select',
      filterOptions: ['Pago', 'Atrasado', 'Vence em breve', 'Pendente'],
      filterAccessor: (row) => {
        const { label } = getStatusInfo(row)
        return label.startsWith('Vence') ? 'Vence em breve' : label
      },
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
            {!row.pago ? (
              <Button
                size="sm"
                variant="ghost"
                className="h-8 w-8 p-0 rounded-lg text-emerald-600 dark:text-emerald-400 hover:bg-emerald-50 dark:hover:bg-emerald-950/20"
                onClick={() => setConfirmId(row.id)}
                title="Marcar como Pago"
                aria-label={`Marcar ${row.descricao} como pago`}
              >
                <CheckCircle2 className="h-4 w-4" aria-hidden="true" />
              </Button>
            ) : (
              <Button
                size="sm"
                variant="ghost"
                className="h-8 w-8 p-0 rounded-lg text-amber-600 dark:text-amber-400 hover:bg-amber-50 dark:hover:bg-amber-950/20"
                onClick={() => {
                  setDesfazerPagamentoId(row.id)
                  setEditingConta(row)
                }}
                title="Desfazer Pagamento"
                aria-label={`Desfazer pagamento de ${row.descricao}`}
              >
                <RotateCcw className="h-4 w-4" aria-hidden="true" />
              </Button>
            )}
            {row.eh_fatura_cartao ? (
              // Faturas de cartão: ver/editar compras individuais, editar metadados e excluir o período inteiro
              <div className="flex items-center gap-1">
                <Button
                  size="sm"
                  variant="ghost"
                  className="h-8 w-8 p-0 rounded-lg text-blue-600 dark:text-blue-400 hover:bg-blue-50 dark:hover:bg-blue-900/20"
                  onClick={() => navigate('/compras-cartao')}
                  title="Ver compras individuais desta fatura"
                  aria-label={`Ver compras individuais da fatura ${row.descricao}`}
                >
                  <ExternalLink className="h-4 w-4" aria-hidden="true" />
                </Button>
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
                  onClick={() => { setDeleteId(row.id); setDeletingConta(row); }}
                  title="Excluir fatura e suas compras"
                  aria-label={`Excluir fatura ${row.descricao} e suas compras`}
                >
                  <Trash2 className="h-4 w-4" aria-hidden="true" />
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
                  aria-label={`Editar ${row.descricao}`}
                >
                  <Pencil className="h-4 w-4" aria-hidden="true" />
                </Button>
                <Button
                  size="sm"
                  variant="ghost"
                  className="h-8 w-8 p-0 rounded-lg text-rose-500 hover:text-rose-600 hover:bg-rose-50 dark:hover:bg-rose-950/20"
                  onClick={() => { setDeleteId(row.id); setDeletingConta(row); }}
                  title="Excluir"
                  aria-label={`Excluir ${row.descricao}`}
                >
                  <Trash2 className="h-4 w-4" aria-hidden="true" />
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
          <Button variant="outline" size="sm" onClick={handleAtualizar} disabled={isFetching}>
            <RefreshCw className={`mr-1.5 h-4 w-4 ${isFetching ? 'animate-spin' : ''}`} />
            Atualizar
          </Button>
          <Button variant="outline" size="sm" onClick={() => navigate('/contas-pagar/lote')}>
            Cadastro em Lote
          </Button>
          <Button size="sm" onClick={() => navigate('/contas-pagar/novo')}>
            <Plus className="mr-1.5 h-4 w-4" />
            Nova Conta
          </Button>
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
              Pago no Período
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-bold text-foreground">{formatCurrency(totalPago)}</p>
            <p className="text-xs text-muted-foreground mt-1">
              {pagas.length} conta(s) liquidada(s)
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Error state */}
      {isError && (
        <Alert variant="error">
          Não foi possível carregar as contas. Verifique a conexão com a API.
        </Alert>
      )}

      {/* Erro de ação (pagar / excluir / desfazer) */}
      {actionError && (
        <Alert variant="error">
          {actionError}
        </Alert>
      )}

      {/* Abas — padrão WAI-ARIA de tabs: troca a região visível, navegável por setas */}
      <div role="tablist" aria-label="Visão das contas a pagar" className="flex border-b border-border/40 self-start">
        {TABS.map((tab, index) => {
          const { Icon } = tab
          const ativa = vista === tab.id
          return (
            <button
              key={tab.id}
              id={`tab-${tab.id}`}
              role="tab"
              type="button"
              aria-selected={ativa}
              aria-controls={`painel-${tab.id}`}
              // Só a aba ativa fica na ordem de tabulação; as demais vêm pelas setas.
              tabIndex={ativa ? 0 : -1}
              onClick={() => trocarVista(tab.id)}
              onKeyDown={(e) => handleTabKeyDown(e, index)}
              className={`flex items-center gap-2 px-4 py-2.5 text-xs uppercase tracking-wider border-b-2 transition-all ${ativa ? 'border-primary text-primary font-extrabold' : 'border-transparent text-muted-foreground hover:text-foreground font-bold'}`}
            >
              <Icon className="h-3.5 w-3.5" aria-hidden="true" />
              {tab.label}
            </button>
          )
        })}
      </div>

      {/* Painel: Kanban */}
      {vista === 'kanban' && (
        <div id="painel-kanban" role="tabpanel" aria-labelledby="tab-kanban" tabIndex={0} className="space-y-4">
          <div className="flex items-center gap-2 rounded-xl border border-primary/20 bg-primary/5 px-4 py-2.5 text-sm text-primary">
            <CheckCircle2 className="h-4 w-4 shrink-0" aria-hidden="true" />
            <p>
              Mostrando o mês corrente. Arraste um card para <strong>"Pagas"</strong> para
              registrar o pagamento, ou clique no card para editá-lo. Para filtrar outros
              períodos e excluir contas, use a <strong>Tabela</strong>.
            </p>
          </div>
          {isLoading ? (
            <p role="status" className="text-sm text-muted-foreground">Carregando contas a pagar...</p>
          ) : (
            <QuadroContasPagar contas={contasDoMes} />
          )}
        </div>
      )}

      {/* Painel: Tabela */}
      {vista === 'tabela' && (
        <div id="painel-tabela" role="tabpanel" aria-labelledby="tab-tabela" tabIndex={0}>
          <DataTable
            columns={columns}
            data={tableData}
            isLoading={isLoading}
            pageSize={10}
            defaultFilters={{ data_vencimento: getCurrentMonthDateRange() }}
            emptyMessage="Nenhuma conta cadastrada."
            onFilteredDataChange={setFilteredContas}
            rowClassName={(row) =>
              row._fading ? 'opacity-0 scale-95 transition-all duration-500' : ''
            }
          />
        </div>
      )}

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
        onClose={() => { setDeleteId(null); setDeletingConta(null); }}
        title={deletingConta?.eh_fatura_cartao ? 'Excluir Fatura do Cartão' : 'Confirmar Exclusão'}
        description={
          deletingConta?.eh_fatura_cartao
            ? `Esta é uma fatura de cartão. Excluí-la removerá permanentemente a fatura e também ${deletingConta.qtd_compras_vinculadas ?? 0} compra(s) individual(is) lançada(s) neste vencimento. Esta ação não pode ser desfeita. Deseja continuar?`
            : 'Esta ação excluirá permanentemente a despesa. Deseja continuar?'
        }
      >
        <div className="flex gap-3 justify-end">
          <Button variant="outline" onClick={() => { setDeleteId(null); setDeletingConta(null); }}>
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

      {/* ─── Modal: Desfazer Pagamento ────────────────────────────────────────── */}
      <Modal
        isOpen={!!desfazerPagamentoId}
        onClose={() => { setDesfazerPagamentoId(null); setEditingConta(null); }}
        title="Desfazer Pagamento"
        description={
          editingConta?.eh_fatura_cartao
            ? "Esta é uma fatura de cartão. Desfazer o pagamento irá reverter também todas as compras individuais desta fatura. Deseja continuar?"
            : "Esta ação reverterá o status da conta para pendente. Deseja continuar?"
        }
      >
        <div className="flex gap-3 justify-end">
          <Button variant="outline" onClick={() => { setDesfazerPagamentoId(null); setEditingConta(null); }}>
            Cancelar
          </Button>
          <Button
            onClick={() => desfazerPagamentoMutation.mutate(desfazerPagamentoId)}
            disabled={desfazerPagamentoMutation.isPending}
            className="bg-amber-600 hover:bg-amber-700 text-white border-0"
          >
            {desfazerPagamentoMutation.isPending ? (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            ) : (
              <RotateCcw className="mr-2 h-4 w-4" />
            )}
            Confirmar Reversão
          </Button>
        </div>
      </Modal>


    </div>
  )
}
