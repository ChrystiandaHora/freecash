/**
 * Quadro Kanban das contas a pagar, com arrastar-e-soltar.
 *
 * Sete colunas derivadas do vencimento — Atrasadas, Vence Hoje, Vence amanhã, Vence 2
 * dias, Vence 3 dias, Pendentes e Pagas. A classificação é sempre calculada a partir
 * de `data_vencimento`: o backend não guarda "em que coluna a conta está", e não
 * deveria — a coluna é uma leitura do prazo, que muda sozinha com a passagem do dia.
 *
 * Arrastar um card para **Pagas** dispara `pagarConta`; mover entre as outras colunas
 * é apenas visual, porque mudar de coluna significaria reescrever o vencimento e não
 * é isso que o gesto promete. Clicar no corpo do card abre `ContaPagarEditModal`.
 *
 * Vive em `components/` porque tem dois consumidores: a tela de Contas a Pagar, onde é
 * uma das duas visões, e a rota dedicada `/contas-kanban`. Recebe as contas já
 * filtradas por quem o usa — o recorte de período é decisão da tela, não do quadro.
 */
import { useMemo, useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { DragDropContext, Droppable, Draggable } from '@hello-pangea/dnd';
import { AlertCircle, CalendarDays, CheckCircle2, GripVertical } from 'lucide-react';

import { pagarConta } from '../../services/financeiro';
import { useToast } from '../../context/ToastContext';
import { Badge } from '../ui/Badge';
import ContaPagarEditModal from '../ContaPagarEditModal';
import { COLUMNS, agruparPorColuna } from '../../lib/contasKanban';

// ─── Helpers ──────────────────────────────────────────────────────────────────

const formatCurrency = (val) =>
  new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(val ?? 0)

const formatDueDate = (dateStr) => {
  if (!dateStr || typeof dateStr !== 'string') return 'Sem data'
  const parts = dateStr.split('-')
  if (parts.length < 3) return dateStr
  const [, month, day] = parts
  return `${day}/${month}`
}

// ─── Colunas do Kanban ────────────────────────────────────────────────────────

// ─── Card de Conta (Kanban item) ──────────────────────────────────────────────

const ContaCard = ({ conta, provided, snapshot, colId, onEdit }) => {
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
          className="-ml-1 -mt-0.5 flex min-h-6 min-w-6 items-center justify-center rounded p-1 text-muted-foreground/40 hover:text-muted-foreground cursor-grab active:cursor-grabbing"
          aria-label={`Arrastar ${conta.descricao}`}
        >
          <GripVertical className="h-4 w-4" aria-hidden="true" />
        </span>
        <div className="flex items-center gap-1.5">
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
      </div>

      {/* Corpo clicável: abre a edição. É um <button> nativo (e não o card
          inteiro com role="button") para não englobar a alça de arrastar,
          mantendo os dois controles operáveis por teclado de forma separada. */}
      <button
        type="button"
        onClick={() => onEdit(conta)}
        className="block w-full cursor-pointer rounded-lg text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-card"
        aria-label={`Editar ${conta.descricao}`}
      >
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
            <CalendarDays className="h-3 w-3" aria-hidden="true" />
            {formatDueDate(conta.data_vencimento)}
          </span>
          <span className={`text-sm font-bold ${isAtrasada ? 'text-red-500' : 'text-foreground'}`}>
            {formatCurrency(conta.valor)}
          </span>
        </div>
      </button>
    </div>
  )
}

// ─── Coluna Kanban ────────────────────────────────────────────────────────────

const KanbanColumn = ({ col, contas, provided, snapshot, onEdit }) => {
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
        className={`flex-1 space-y-3 p-3 pt-1 min-h-[200px] max-h-[calc(100vh-380px)] overflow-y-auto rounded-b-2xl transition-colors duration-200 ${
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
                onEdit={onEdit}
              />
            )}
          </Draggable>
        ))}
        {provided.placeholder}
      </div>
    </div>
  )
}

/**
 * @param {{contas: Array<Object>}} props
 * @returns {React.JSX.Element} Quadro com as colunas e os cards arrastáveis.
 */
export default function QuadroContasPagar({ contas = [] }) {
  const queryClient = useQueryClient();
  const { addToast } = useToast();
  const [editingConta, setEditingConta] = useState(null);

  // Feedback via toast em vez de estado local: o ToastContext já se auto-dispensa,
  // pausa no hover/foco e tem botão de fechar — um Alert local ficaria na tela
  // permanentemente por não ter caminho de limpeza.
  const pagarMutation = useMutation({
    mutationFn: pagarConta,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['contasPagar'] });
      addToast('Pagamento registrado com sucesso.', 'success');
    },
    onError: () => {
      // O card volta à coluna de origem na próxima revalidação; sem esta mensagem,
      // o usuário não teria como saber que o pagamento não foi registrado.
      queryClient.invalidateQueries({ queryKey: ['contasPagar'] });
      addToast('Não foi possível registrar o pagamento. Tente novamente.', 'error');
    },
  });

  const columnData = useMemo(() => agruparPorColuna(contas), [contas]);

  const onDragEnd = (result) => {
    const { source, destination, draggableId } = result;
    if (!destination) return;
    if (source.droppableId === destination.droppableId) return;

    if (destination.droppableId === 'pagas') {
      pagarMutation.mutate(Number(draggableId));
    }
  };

  return (
    <>
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
                  onEdit={setEditingConta}
                />
              )}
            </Droppable>
          ))}
        </div>
      </DragDropContext>

      <ContaPagarEditModal
        conta={editingConta}
        onClose={() => setEditingConta(null)}
        onSaved={() => addToast('Conta atualizada com sucesso.', 'success')}
        onError={() => addToast('Não foi possível salvar a conta. Tente novamente.', 'error')}
        onPaid={() => addToast('Pagamento registrado com sucesso.', 'success')}
        onPayError={() => addToast('Não foi possível registrar o pagamento. Tente novamente.', 'error')}
      />
    </>
  );
}
