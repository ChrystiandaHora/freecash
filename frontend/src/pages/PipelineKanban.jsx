/**
 * Tela de Pipeline Kanban de Contas a Pagar.
 *
 * Visualização ágil do ciclo de vida das contas a pagar através de um
 * quadro Kanban interativo com arrastar-e-soltar (`@hello-pangea/dnd`).
 *
 * Colunas do Quadro:
 * - **Atrasadas** → contas com `data_vencimento` anterior a hoje.
 * - **Para Hoje**  → contas com vencimento no dia atual.
 * - **Próximos 7 Dias** → contas vencendo dentro de 1–7 dias.
 * - **Final do Mês** → contas vencendo após 7 dias.
 * - **Pagas** → contas já quitadas (`pago === true`).
 *
 * Comportamento de Drag & Drop:
 * - Arrastar um card para a coluna **"Pagas"** dispara a mutation
 *   `pagarConta` que registra o pagamento via API (`POST /api/contas-pagar/{id}/pagar/`).
 * - Movimentação entre outras colunas é visual apenas (sem persistência de data).
 *
 * KPIs exibidos: Total Pendente, Total Atrasado, Contas Pagas, Total de Contas.
 *
 * @module PipelineKanban
 * @component
 * @returns {JSX.Element} Quadro Kanban interativo de gerenciamento de contas a pagar.
 *
 * @example
 * // Rota configurada em App.jsx:
 * <Route path="contas-kanban" element={<PipelineKanban />} />
 */
import React, { useMemo } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { DragDropContext, Droppable, Draggable } from '@hello-pangea/dnd';
import {
  AlertCircle, Clock, CalendarDays, CheckCircle2,
  RefreshCw, GripVertical, DollarSign
} from 'lucide-react';

import { fetchContasPagar, pagarConta } from '../services/financeiro';
import { Badge } from '../components/ui/Badge';
import { Button } from '../components/ui/Button';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/Card';

// ─── Helpers ──────────────────────────────────────────────────────────────────

const formatCurrency = (val) =>
  new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(val ?? 0)

const formatDate = (dateStr) => {
  if (!dateStr) return '—'
  const [year, month, day] = dateStr.split('-')
  return `${day}/${month}`
}

// ─── Colunas do Kanban ────────────────────────────────────────────────────────

const COLUMNS = [
  {
    id: 'atrasadas',
    label: 'Atrasadas',
    icon: AlertCircle,
    color: 'text-red-500 dark:text-red-400',
    borderColor: 'border-border/40',
    bgColor: 'bg-muted/40',
    badgeVariant: 'destructive',
  },
  {
    id: 'hoje',
    label: 'Para Hoje',
    icon: AlertCircle,
    color: 'text-amber-500 dark:text-amber-400',
    borderColor: 'border-border/40',
    bgColor: 'bg-muted/40',
    badgeVariant: 'warning',
  },
  {
    id: 'semana',
    label: 'Próximos 7 Dias',
    icon: Clock,
    color: 'text-primary',
    borderColor: 'border-border/40',
    bgColor: 'bg-muted/40',
    badgeVariant: 'default',
  },
  {
    id: 'mes',
    label: 'Final do Mês',
    icon: CalendarDays,
    color: 'text-muted-foreground',
    borderColor: 'border-border/40',
    bgColor: 'bg-muted/40',
    badgeVariant: 'secondary',
  },
  {
    id: 'pagas',
    label: 'Pagas',
    icon: CheckCircle2,
    color: 'text-emerald-500 dark:text-emerald-400',
    borderColor: 'border-border/40',
    bgColor: 'bg-muted/40',
    badgeVariant: 'success',
  },
]


// Classifica uma conta em uma coluna
const getColumnId = (conta) => {
  if (conta.pago) return 'pagas'

  const today = new Date()
  today.setHours(0, 0, 0, 0)
  const due = new Date(conta.data_vencimento + 'T00:00:00')
  const diff = Math.ceil((due - today) / (1000 * 60 * 60 * 24))

  if (diff < 0) return 'atrasadas'
  if (diff === 0) return 'hoje'
  if (diff <= 7) return 'semana'
  return 'mes'
}

// ─── Card de Conta (Kanban item) ──────────────────────────────────────────────

const ContaCard = ({ conta, provided, snapshot, colId }) => {
  const isAtrasada = colId === 'atrasadas'
  const isPaga = colId === 'pagas'

  return (
    <div
      ref={provided.innerRef}
      {...provided.draggableProps}
      className={`rounded-xl border bg-card p-4 shadow-sm transition-all duration-200 select-none
        ${snapshot.isDragging ? 'shadow-xl scale-[1.02] ring-2 ring-primary/30' : 'hover:shadow-md hover:-translate-y-0.5'}
        ${isPaga ? 'opacity-60' : ''}
      `}
    >
      {/* Drag handle */}
      <div className="flex items-start justify-between gap-2 mb-3">
        <span
          {...provided.dragHandleProps}
          className="mt-0.5 text-muted-foreground/40 hover:text-muted-foreground cursor-grab active:cursor-grabbing"
          aria-label="Arrastar"
        >
          <GripVertical className="h-4 w-4" />
        </span>
        {isPaga ? (
          <Badge variant="success">
            <CheckCircle2 className="h-3 w-3" />
            Paga
          </Badge>
        ) : isAtrasada ? (
          <Badge variant="destructive">
            <AlertCircle className="h-3 w-3" />
            Atrasada
          </Badge>
        ) : null}
      </div>

      {/* Conteúdo */}
      <p className="font-semibold text-sm text-foreground leading-snug line-clamp-2 mb-1">
        {conta.descricao}
      </p>
      {conta.categoria && (
        <p className="text-xs text-muted-foreground mb-3">{conta.categoria}</p>
      )}

      {/* Rodapé */}
      <div className="flex items-center justify-between mt-2 pt-2 border-t border-border/60">
        <span className="text-xs text-muted-foreground flex items-center gap-1">
          <CalendarDays className="h-3 w-3" />
          {formatDate(conta.data_vencimento)}
        </span>
        <span className={`text-sm font-bold ${isAtrasada ? 'text-red-500' : 'text-foreground'}`}>
          {formatCurrency(conta.valor)}
        </span>
      </div>
    </div>
  )
}

// ─── Coluna Kanban ────────────────────────────────────────────────────────────

const KanbanColumn = ({ col, contas, provided, snapshot }) => {
  const Icon = col.icon
  const total = contas.reduce((a, c) => a + Number(c.valor ?? 0), 0)

  return (
    <div className="flex flex-col rounded-2xl border border-border/40 bg-muted/40 min-h-[300px] min-w-[260px] max-w-[300px] flex-shrink-0">
      {/* Header */}
      <div className="flex items-center justify-between p-4 pb-3">
        <div className="flex items-center gap-2">
          <Icon className={`h-4 w-4 ${col.color}`} />
          <span className="font-semibold text-sm text-foreground">{col.label}</span>
          <span className="inline-flex h-5 w-5 items-center justify-center rounded-full text-xs font-bold bg-background text-muted-foreground border border-border/40">
            {contas.length}
          </span>
        </div>
        {contas.length > 0 && (
          <span className="text-xs font-medium text-muted-foreground">
            {formatCurrency(total)}
          </span>
        )}
      </div>

      {/* Droppable area */}
      <div
        ref={provided.innerRef}
        {...provided.droppableProps}
        className={`flex-1 space-y-3 p-3 pt-1 min-h-[200px] rounded-b-2xl transition-colors duration-200 ${
          snapshot.isDraggingOver ? 'bg-primary/5 ring-1 ring-inset ring-primary/20' : ''
        }`}
      >
        {contas.length === 0 && !snapshot.isDraggingOver && (
          <div className="flex h-32 items-center justify-center rounded-xl border border-dashed border-border/40">
            <p className="text-xs text-muted-foreground/60">Nenhuma conta aqui</p>
          </div>
        )}
        {contas.map((conta, index) => (
          <Draggable key={String(conta.id)} draggableId={String(conta.id)} index={index}>
            {(provided, snapshot) => (
              <ContaCard
                conta={conta}
                provided={provided}
                snapshot={snapshot}
                colId={col.id}
              />
            )}
          </Draggable>
        ))}
        {provided.placeholder}
      </div>
    </div>
  )
}

// ─── Componente Principal ─────────────────────────────────────────────────────

export default function PipelineKanban() {
  const queryClient = useQueryClient()

  const { data: contas = [], isLoading, isError, refetch } = useQuery({
    queryKey: ['contasPagar'],
    queryFn: () => fetchContasPagar(),
  })

  const pagarMutation = useMutation({
    mutationFn: pagarConta,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['contasPagar'] })
    },
  })

  // Organiza contas em colunas
  const columnData = useMemo(() => {
    const map = {}
    COLUMNS.forEach((col) => { map[col.id] = [] })
    contas.forEach((conta) => {
      const colId = getColumnId(conta)
      if (map[colId]) map[colId].push(conta)
    })
    return map
  }, [contas])

  const onDragEnd = (result) => {
    const { source, destination, draggableId } = result
    if (!destination) return
    if (source.droppableId === destination.droppableId) return

    // Mover para "pagas" dispara a mutation de quitação
    if (destination.droppableId === 'pagas') {
      const id = Number(draggableId)
      pagarMutation.mutate(id)
    }
    // Nota: Para reordenação em outras colunas, seria necessário
    // um endpoint de atualização de data_vencimento no backend.
    // Por ora, o kanban reflete o estado do backend.
  }

  // KPIs
  const totalPendente = contas
    .filter((c) => !c.pago)
    .reduce((a, c) => a + Number(c.valor ?? 0), 0)

  const totalAtrasado = (columnData.atrasadas ?? [])
    .reduce((a, c) => a + Number(c.valor ?? 0), 0)

  if (isLoading) {
    return (
      <div className="space-y-6 animate-fade-in">
        <div>
          <h1 className="text-3xl font-extrabold tracking-tight text-foreground">
            Pipeline Kanban
          </h1>
          <p className="text-muted-foreground mt-1">Visão ágil das contas a pagar</p>
        </div>
        <div className="flex gap-4 overflow-x-auto pb-4">
          {COLUMNS.map((col) => (
            <div key={col.id} className={`flex-shrink-0 w-[280px] rounded-2xl border ${col.borderColor} p-4`}>
              <div className="h-4 w-32 animate-pulse rounded bg-muted mb-4" />
              <div className="space-y-3">
                {Array.from({ length: 3 }).map((_, i) => (
                  <div key={i} className="h-24 animate-pulse rounded-xl bg-muted" />
                ))}
              </div>
            </div>
          ))}
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-3xl font-extrabold tracking-tight text-foreground">
            Pipeline Kanban
          </h1>
          <p className="text-muted-foreground mt-1">
            Arraste contas para a coluna "Pagas" para quitá-las
          </p>
        </div>
        <Button variant="outline" size="sm" onClick={() => refetch()}>
          <RefreshCw className="mr-1.5 h-4 w-4" />
          Atualizar
        </Button>
      </div>

      {/* KPIs */}
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
        <Card className="border-border/40 shadow-sm">
          <CardHeader className="pb-1">
            <CardTitle className="text-xs font-medium text-muted-foreground uppercase tracking-wider">Total Pendente</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-xl font-bold text-foreground">{formatCurrency(totalPendente)}</p>
          </CardContent>
        </Card>

        <Card className="border-red-500/20 shadow-sm">
          <CardHeader className="pb-1">
            <CardTitle className="text-xs font-medium text-muted-foreground uppercase tracking-wider">Atrasadas</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-xl font-bold text-red-500">{formatCurrency(totalAtrasado)}</p>
          </CardContent>
        </Card>

        <Card className="border-border/40 shadow-sm">
          <CardHeader className="pb-1">
            <CardTitle className="text-xs font-medium text-muted-foreground uppercase tracking-wider">Contas Pagas</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-xl font-bold text-emerald-500">{(columnData.pagas ?? []).length}</p>
          </CardContent>
        </Card>

        <Card className="border-border/40 shadow-sm">
          <CardHeader className="pb-1">
            <CardTitle className="text-xs font-medium text-muted-foreground uppercase tracking-wider">Total de Contas</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-xl font-bold text-foreground">{contas.length}</p>
          </CardContent>
        </Card>
      </div>

      {/* Error */}
      {isError && (
        <div className="rounded-xl border border-red-500/20 bg-red-500/5 p-4 text-sm text-red-600 dark:text-red-400">
          Não foi possível carregar as contas. Verifique a conexão com a API.
        </div>
      )}

      {/* Instruções */}
      <div className="flex items-center gap-2 rounded-xl border border-primary/20 bg-primary/5 px-4 py-2.5 text-sm text-primary">
        <DollarSign className="h-4 w-4 shrink-0" />
        <p>
<<<<<<< HEAD
          Arraste um card para a coluna <strong>"Pagas"</strong> para registrar o pagamento automaticamente no backend.
=======
          Arraste um card para a coluna <strong>"Pagas ✓"</strong> para registrar o pagamento automaticamente no backend.
>>>>>>> 7e86a8f384903efab0be4239287b3e855a9ae5bb
        </p>
      </div>

      {/* Board */}
      <DragDropContext onDragEnd={onDragEnd}>
        <div className="flex gap-4 overflow-x-auto pb-6 -mx-2 px-2">
          {COLUMNS.map((col) => (
            <Droppable key={col.id} droppableId={col.id}>
              {(provided, snapshot) => (
                <KanbanColumn
                  col={col}
                  contas={columnData[col.id] ?? []}
                  provided={provided}
                  snapshot={snapshot}
                />
              )}
            </Droppable>
          ))}
        </div>
      </DragDropContext>
    </div>
  )
}
