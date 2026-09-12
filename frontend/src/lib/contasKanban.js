/**
 * Colunas do quadro de contas a pagar e a regra que classifica cada conta (sem DOM).
 *
 * A coluna é sempre *derivada* de `data_vencimento`: o backend não guarda "em que
 * coluna a conta está", e não deveria — a coluna é uma leitura do prazo, que muda
 * sozinha com a passagem do dia. Guardá-la exigiria reescrever a base todo dia à
 * meia-noite para continuar verdadeira.
 *
 * Vive em `lib/` porque tem dois consumidores (o quadro e a rota dedicada, que calcula
 * o KPI de atrasadas com o mesmo agrupamento) e porque as bordas de data merecem teste.
 */
import { AlertCircle, Clock, CheckCircle2 } from 'lucide-react';

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
    label: 'Vence Hoje',
    icon: Clock,
    color: 'text-rose-500 dark:text-rose-400',
    borderColor: 'border-border/40',
    bgColor: 'bg-muted/40',
    badgeVariant: 'urgent',
  },
  {
    id: 'amanha',
    label: 'Vence amanhã',
    icon: Clock,
    color: 'text-rose-500 dark:text-rose-400',
    borderColor: 'border-border/40',
    bgColor: 'bg-muted/40',
    badgeVariant: 'urgent',
  },
  {
    id: 'vence_2_dias',
    label: 'Vence 2 dias',
    icon: Clock,
    color: 'text-orange-500 dark:text-orange-400',
    borderColor: 'border-border/40',
    bgColor: 'bg-muted/40',
    badgeVariant: 'warning',
  },
  {
    id: 'vence_3_dias',
    label: 'Vence 3 dias',
    icon: Clock,
    color: 'text-orange-500 dark:text-orange-400',
    borderColor: 'border-border/40',
    bgColor: 'bg-muted/40',
    badgeVariant: 'warning',
  },
  {
    id: 'pendentes',
    label: 'Pendentes',
    icon: Clock,
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
  if (!conta) return 'pendentes'
  if (conta.pago) return 'pagas'

  if (!conta.data_vencimento || typeof conta.data_vencimento !== 'string') return 'pendentes'

  const today = new Date()
  today.setHours(0, 0, 0, 0)

  const parts = conta.data_vencimento.split('-')
  if (parts.length < 3) return 'pendentes'

  const [year, month, day] = parts
  const due = new Date(Number(year), Number(month) - 1, Number(day))
  due.setHours(0, 0, 0, 0)

  if (due < today) return 'atrasadas'

  const diffDays = Math.round((due - today) / (1000 * 60 * 60 * 24))

  if (diffDays === 0) return 'hoje'
  if (diffDays === 1) return 'amanha'
  if (diffDays === 2) return 'vence_2_dias'
  if (diffDays === 3) return 'vence_3_dias'

  return 'pendentes'
}

/**
 * Agrupa contas nas colunas do quadro.
 *
 * @param {Array<Object>} contas
 * @returns {Record<string, Array<Object>>} Contas por id de coluna.
 */
export function agruparPorColuna(contas = []) {
  const map = {};
  COLUMNS.forEach((col) => { map[col.id] = []; });
  contas.forEach((conta) => {
    const colId = getColumnId(conta);
    if (map[colId]) map[colId].push(conta);
  });
  return map;
}

export { COLUMNS, getColumnId };
