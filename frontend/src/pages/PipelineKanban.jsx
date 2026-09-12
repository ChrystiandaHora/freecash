/**
 * Rota dedicada ao quadro Kanban das contas a pagar.
 *
 * O quadro em si vive em `components/contas/QuadroContasPagar` — a tela de Contas a
 * Pagar o usa como uma das suas duas visões. Aqui ficam só o recorte de dados (mês
 * corrente, no servidor) e os KPIs do período.
 *
 * @returns {JSX.Element} Quadro Kanban de gerenciamento de contas a pagar.
 */
import { useQuery } from '@tanstack/react-query';
import { RefreshCw, DollarSign } from 'lucide-react';

import { fetchContasPagar } from '../services/financeiro';
import { useToast } from '../context/ToastContext';
import { Alert } from '../components/ui/Alert';
import { Button } from '../components/ui/Button';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/Card';
import QuadroContasPagar from '../components/contas/QuadroContasPagar';
import { COLUMNS, agruparPorColuna } from '../lib/contasKanban';

const formatCurrency = (val) =>
  new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(val ?? 0)

// ─── Componente Principal ─────────────────────────────────────────────────────

export default function PipelineKanban() {
  const { addToast } = useToast()

  const hoje = new Date()

  const { data: contas = [], isLoading, isError, isFetching, refetch } = useQuery({
    queryKey: ['contasPagar', hoje.getMonth() + 1, hoje.getFullYear()],
    queryFn: () => fetchContasPagar({ mes: hoje.getMonth() + 1, ano: hoje.getFullYear() }),
  })

  const handleAtualizar = async () => {
    try {
      await refetch()
      addToast('Dados atualizados.', 'success')
    } catch {
      addToast('Não foi possível atualizar os dados.', 'error')
    }
  }

  // Mesmo agrupamento que o quadro usa: dois critérios de "atrasada" dariam dois números
  const columnData = agruparPorColuna(contas)

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
        <div role="status" aria-busy="true" className="flex gap-4 overflow-x-auto pb-4">
          <span className="sr-only">Carregando contas a pagar...</span>
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
            Clique em um card para editar ou arraste para a coluna "Pagas" para quitá-lo
          </p>
        </div>
        <Button variant="outline" size="sm" onClick={handleAtualizar} disabled={isFetching}>
          <RefreshCw className={`mr-1.5 h-4 w-4 ${isFetching ? 'animate-spin' : ''}`} />
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
        <Alert variant="error">
          Não foi possível carregar as contas. Verifique a conexão com a API.
        </Alert>
      )}

      {/* Instruções */}
      <div className="flex items-center gap-2 rounded-xl border border-primary/20 bg-primary/5 px-4 py-2.5 text-sm text-primary">
        <DollarSign className="h-4 w-4 shrink-0" />
        <p>
          Arraste um card para a coluna <strong>"Pagas"</strong> para registrar o pagamento, ou
          clique no card para editá-lo e usar o botão <strong>"Marcar como paga"</strong>.
        </p>
      </div>

      {/* O quadro traz consigo o drag-and-drop e o modal de edição do card */}
      <QuadroContasPagar contas={contas} />
    </div>
  )
}
