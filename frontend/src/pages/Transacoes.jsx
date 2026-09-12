/**
 * Tela de Extrato Mensal e Lançamento de Transações.
 *
 * Exibe de forma cronológica o histórico consolidado de receitas e despesas do usuário.
 * Implementa filtros rápidos de competência (mês/ano) e uma tabela padronizada com
 * ordenação, filtro por coluna e paginação.
 *
 * Cada linha carrega liquidação, edição e exclusão. O verbo do botão muda conforme o
 * tipo, a mesma regra do Calendário de Pagamentos.
 *
 * @returns {React.JSX.Element} Tabela estruturada de extrato financeiro mensal.
 */
import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import {
  ArrowDown,
  ArrowUp,
  CheckCircle2,
  Circle,
  Pencil,
  RefreshCw,
  Trash2,
  Undo2,
} from 'lucide-react';

import { deleteContaPagar, deleteReceita, fetchTransacoes } from '../services/financeiro';
import { desfazerLiquidacao, liquidarLancamento } from '../services/planejamento';
import { Button } from '../components/ui/Button';
import { Select } from '../components/ui/Select';
import { Alert } from '../components/ui/Alert';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/Card';
import { DataTable } from '../components/ui/DataTable';
import { Modal } from '../components/ui/Modal';
import { useToast } from '../context/ToastContext';

// ─── Helpers ──────────────────────────────────────────────────────────────────

const formatCurrency = (val) =>
  new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(val ?? 0)

const formatDate = (dateStr) => {
  if (!dateStr) return '—'
  const [year, month, day] = dateStr.split('-')
  return `${day}/${month}/${year}`
}

const MONTHS = [
  'Janeiro', 'Fevereiro', 'Março', 'Abril', 'Maio', 'Junho',
  'Julho', 'Agosto', 'Setembro', 'Outubro', 'Novembro', 'Dezembro',
]

const currentYear = new Date().getFullYear()
const YEARS = Array.from({ length: 7 }, (_, i) => currentYear - 2 + i)

const ehEntrada = (tx) => tx?.tipo === 'entrada'

/** A fatura é gerada por signal a partir das compras; editá-la à mão desalinharia as duas. */
const ehFaturaConsolidada = (tx) => Boolean(tx?.eh_fatura_cartao)

// ─── Confirmação de exclusão ──────────────────────────────────────────────────

function DeleteConfirmModal({ transacao, onConfirm, onClose, isPending }) {
  return (
    <Modal isOpen title="Confirmar exclusão" onClose={onClose} size="sm">
      <div className="flex flex-col items-center gap-4 text-center">
        <div className="flex h-14 w-14 items-center justify-center rounded-full bg-destructive/10">
          <Trash2 className="h-6 w-6 text-destructive" aria-hidden="true" />
        </div>
        <p className="text-sm text-muted-foreground">
          Excluir{' '}
          <span className="font-semibold text-foreground">
            "{transacao.descricao || 'este lançamento'}"
          </span>{' '}
          de {formatCurrency(Math.abs(Number(transacao.valor ?? 0)))}? Esta ação não pode
          ser desfeita.
        </p>
        <div className="flex w-full gap-3">
          <Button variant="outline" onClick={onClose} className="h-10 flex-1 rounded-xl text-xs">
            Cancelar
          </Button>
          <Button
            onClick={onConfirm}
            disabled={isPending}
            className="h-10 flex-1 rounded-xl border-0 bg-destructive text-xs text-destructive-foreground hover:bg-destructive/90"
          >
            {isPending ? <RefreshCw className="h-4 w-4 animate-spin" aria-hidden="true" /> : 'Excluir'}
          </Button>
        </div>
      </div>
    </Modal>
  )
}

// ─── Componente Principal ─────────────────────────────────────────────────────

export default function Transacoes() {
  const hoje = new Date()
  const [mes, setMes] = useState(String(hoje.getMonth() + 1).padStart(2, '0'))
  const [ano, setAno] = useState(String(hoje.getFullYear()))
  const [filteredTransacoes, setFilteredTransacoes] = useState(null)
  const [paraExcluir, setParaExcluir] = useState(null)
  const { addToast } = useToast()
  const navigate = useNavigate()
  const queryClient = useQueryClient()

  const { data: transacoes = [], isLoading, isError, isFetching, refetch } = useQuery({
    queryKey: ['transacoes', mes, ano],
    queryFn: () => fetchTransacoes({ mes, ano }),
  })

  /** Invalida tudo que depende de um lançamento ter mudado de estado. */
  const invalidar = () => {
    queryClient.invalidateQueries({ queryKey: ['transacoes'] })
    queryClient.invalidateQueries({ queryKey: ['dashboard'] })
    queryClient.invalidateQueries({ queryKey: ['saldoAtual'] })
  }

  const handleAtualizar = async () => {
    try {
      await refetch()
      addToast('Dados atualizados.', 'success')
    } catch {
      addToast('Não foi possível atualizar os dados.', 'error')
    }
  }

  const liquidarMutation = useMutation({
    mutationFn: (tx) =>
      tx.transacao_realizada ? desfazerLiquidacao(tx.id) : liquidarLancamento(tx.id),
    onSuccess: (_, tx) => {
      invalidar()
      if (tx.transacao_realizada) {
        // O extrato só lista despesas pagas, então desfazer tira a linha da tela
        addToast(
          ehEntrada(tx)
            ? 'Receita voltou para pendente.'
            : 'Despesa voltou para pendente e saiu do extrato — ela está em Contas a Pagar.',
          'success'
        )
      } else {
        addToast(
          ehEntrada(tx) ? 'Receita marcada como recebida.' : 'Despesa marcada como paga.',
          'success'
        )
      }
    },
    onError: () => addToast('Não foi possível atualizar o lançamento.', 'error'),
  })

  const excluirMutation = useMutation({
    mutationFn: (tx) => (ehEntrada(tx) ? deleteReceita(tx.id) : deleteContaPagar(tx.id)),
    onSuccess: () => {
      invalidar()
      setParaExcluir(null)
      addToast('Lançamento excluído.', 'success')
    },
    onError: (erro) => {
      setParaExcluir(null)
      addToast(
        erro?.response?.data?.detail ?? 'Não foi possível excluir o lançamento.',
        'error'
      )
    },
  })

  const handleEditar = (tx) => {
    if (tx.cartao) navigate(`/compras-cartao/editar/${tx.id}`)
    else if (ehEntrada(tx)) navigate(`/receitas/editar/${tx.id}`)
    else navigate(`/contas-pagar/editar/${tx.id}`)
  }

  // KPIs (calculados dinamicamente com base nos filtros da tabela)
  const transacoesParaKpis = filteredTransacoes ?? transacoes

  const totalEntradas = transacoesParaKpis
    .filter((tx) => tx.tipo === 'entrada')
    .reduce((a, tx) => a + Math.abs(Number(tx.valor ?? 0)), 0)

  const totalSaidas = transacoesParaKpis
    .filter((tx) => tx.tipo === 'saida')
    .reduce((a, tx) => a + Math.abs(Number(tx.valor ?? 0)), 0)

  const saldo = totalEntradas - totalSaidas

  // ─── Colunas da tabela ─────────────────────────────────────────────────────
  const columns = [
    {
      key: 'data',
      header: 'Data',
      render: (val) => (
        <span className="font-mono text-xs text-muted-foreground">{formatDate(val)}</span>
      ),
    },
    {
      key: 'descricao',
      header: 'Descrição',
      render: (val) => <span className="font-medium text-foreground">{val || 'Sem descrição'}</span>,
    },
    {
      key: 'categoria',
      header: 'Categoria',
      filterType: 'select',
      render: (val) => <span className="text-muted-foreground">{val || '—'}</span>,
    },
    {
      key: 'tipo',
      header: 'Tipo',
      filterType: 'select',
      filterOptions: [
        { value: 'entrada', label: 'Entrada' },
        { value: 'saida', label: 'Saída' },
      ],
      render: (val) => {
        const isEntrada = val === 'entrada'
        return (
          <span
            className={`inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-xs font-semibold ${
              isEntrada
                ? 'bg-emerald-500/10 text-emerald-500'
                : 'bg-rose-500/10 text-rose-500'
            }`}
          >
            {isEntrada ? <ArrowUp className="h-3 w-3" aria-hidden="true" /> : <ArrowDown className="h-3 w-3" aria-hidden="true" />}
            {isEntrada ? 'Entrada' : 'Saída'}
          </span>
        )
      },
    },
    {
      // A situação nunca é comunicada só por cor: o ícone tem forma própria
      // (círculo cheio x vazio) e o texto ao lado diz a palavra.
      key: 'transacao_realizada',
      header: 'Situação',
      filterType: 'select',
      filterOptions: [
        { value: 'true', label: 'Concluído' },
        { value: 'false', label: 'Pendente' },
      ],
      filterAccessor: (row) => String(Boolean(row.transacao_realizada)),
      render: (val, row) =>
        val ? (
          <span className="inline-flex items-center gap-1.5 text-xs font-semibold text-emerald-600 dark:text-emerald-400">
            <CheckCircle2 className="h-3.5 w-3.5" aria-hidden="true" />
            {ehEntrada(row) ? 'Recebido' : 'Pago'}
          </span>
        ) : (
          <span className="inline-flex items-center gap-1.5 text-xs font-semibold text-muted-foreground">
            <Circle className="h-3.5 w-3.5" aria-hidden="true" />
            Pendente
          </span>
        ),
    },
    {
      key: 'valor',
      header: 'Valor',
      render: (val, row) => {
        const isEntrada = row.tipo === 'entrada'
        const valor = Math.abs(Number(val ?? 0))
        return (
          <span className={`font-semibold ${isEntrada ? 'text-emerald-500' : 'text-rose-500'}`}>
            {isEntrada ? '+' : '-'} {formatCurrency(valor)}
          </span>
        )
      },
    },
    {
      key: 'acoes',
      header: 'Ações',
      sortable: false,
      render: (_, row) => {
        if (ehFaturaConsolidada(row)) {
          return (
            <span
              className="text-xs text-muted-foreground"
              title="A fatura é gerada a partir das compras do período — edite as compras, não a fatura."
            >
              Fatura consolidada
            </span>
          )
        }

        const concluido = Boolean(row.transacao_realizada)
        const verbo = concluido
          ? 'Voltar para pendente'
          : ehEntrada(row)
            ? 'Marcar como recebido'
            : 'Marcar como pago'

        return (
          <div className="flex items-center gap-1">
            <Button
              variant="outline"
              size="icon"
              onClick={() => liquidarMutation.mutate(row)}
              disabled={liquidarMutation.isPending && liquidarMutation.variables?.id === row.id}
              className="h-8 w-8 rounded-lg"
              title={verbo}
              aria-label={`${verbo}: ${row.descricao || 'lançamento'}`}
            >
              {concluido ? (
                <Undo2 className="h-3.5 w-3.5 text-muted-foreground" aria-hidden="true" />
              ) : (
                <CheckCircle2 className="h-3.5 w-3.5 text-muted-foreground" aria-hidden="true" />
              )}
            </Button>
            <Button
              variant="outline"
              size="icon"
              onClick={() => handleEditar(row)}
              className="h-8 w-8 rounded-lg"
              title="Editar"
              aria-label={`Editar ${row.descricao || 'lançamento'}`}
            >
              <Pencil className="h-3.5 w-3.5 text-muted-foreground" aria-hidden="true" />
            </Button>
            <Button
              variant="outline"
              size="icon"
              onClick={() => setParaExcluir(row)}
              className="group h-8 w-8 rounded-lg hover:border-destructive/30 hover:bg-destructive/10"
              title="Excluir"
              aria-label={`Excluir ${row.descricao || 'lançamento'}`}
            >
              <Trash2 className="h-3.5 w-3.5 text-muted-foreground transition-colors group-hover:text-destructive" aria-hidden="true" />
            </Button>
          </div>
        )
      },
    },
  ]

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-3xl font-extrabold tracking-tight text-foreground">
            Transações
          </h1>
          <p className="text-slate-500 dark:text-slate-400 mt-1">
            Extrato consolidado de entradas e saídas
          </p>
        </div>
        <Button variant="outline" size="sm" onClick={handleAtualizar} disabled={isFetching}>
          <RefreshCw className={`mr-1.5 h-4 w-4 ${isFetching ? 'animate-spin' : ''}`} aria-hidden="true" />
          Atualizar
        </Button>
      </div>

      {/* Filtros de competência */}
      <div className="flex flex-wrap items-end gap-2">
        <div>
          <label htmlFor="transacoes-mes" className="mb-1.5 block text-xs font-medium text-muted-foreground uppercase tracking-wider">
            Mês
          </label>
          <Select id="transacoes-mes" value={mes} onChange={(e) => setMes(e.target.value)} className="w-36">
            {MONTHS.map((m, i) => (
              <option key={i} value={String(i + 1).padStart(2, '0')}>
                {m}
              </option>
            ))}
          </Select>
        </div>
        <div>
          <label htmlFor="transacoes-ano" className="mb-1.5 block text-xs font-medium text-muted-foreground uppercase tracking-wider">
            Ano
          </label>
          <Select id="transacoes-ano" value={ano} onChange={(e) => setAno(e.target.value)} className="w-24">
            {YEARS.map((y) => (
              <option key={y} value={String(y)}>
                {y}
              </option>
            ))}
          </Select>
        </div>

        {/* Botão de Reset Mês Atual */}
        {(Number(mes) !== hoje.getMonth() + 1 || Number(ano) !== hoje.getFullYear()) && (
          <Button
            variant="ghost"
            size="sm"
            onClick={() => {
              setMes(String(hoje.getMonth() + 1).padStart(2, '0'));
              setAno(String(hoje.getFullYear()));
            }}
            className="text-xs text-muted-foreground hover:text-foreground h-10 px-3"
          >
            Mês Atual
          </Button>
        )}
      </div>

      {/* KPIs */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <Card className="bg-card border border-emerald-500/30 shadow-sm text-card-foreground">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground uppercase tracking-wider flex items-center gap-1.5">
              <ArrowUp className="h-4 w-4 text-emerald-600 dark:text-emerald-400" aria-hidden="true" />
              Entradas
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-bold text-emerald-600 dark:text-emerald-400">{formatCurrency(totalEntradas)}</p>
          </CardContent>
        </Card>

        <Card className="bg-card border border-rose-500/30 shadow-sm text-card-foreground">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground uppercase tracking-wider flex items-center gap-1.5">
              <ArrowDown className="h-4 w-4 text-rose-600 dark:text-rose-400" aria-hidden="true" />
              Saídas
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-bold text-rose-600 dark:text-rose-400">{formatCurrency(totalSaidas)}</p>
          </CardContent>
        </Card>

        <Card className={`bg-card shadow-sm text-card-foreground border ${saldo >= 0 ? 'border-emerald-500/30' : 'border-rose-500/30'}`}>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground uppercase tracking-wider">
              Saldo do Período
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className={`text-2xl font-bold ${saldo >= 0 ? 'text-emerald-600 dark:text-emerald-400' : 'text-rose-600 dark:text-rose-400'}`}>
              {saldo >= 0 ? '+' : ''}{formatCurrency(saldo)}
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Error */}
      {isError && (
        <Alert variant="error">
          Não foi possível carregar as transações. Verifique a conexão com a API.
        </Alert>
      )}

      {/* Tabela */}
      <DataTable
        columns={columns}
        data={transacoes}
        isLoading={isLoading}
        pageSize={15}
        emptyMessage={`Nenhuma transação em ${MONTHS[Number(mes) - 1]} de ${ano}.`}
        onFilteredDataChange={setFilteredTransacoes}
      />

      {paraExcluir && (
        <DeleteConfirmModal
          transacao={paraExcluir}
          isPending={excluirMutation.isPending}
          onClose={() => setParaExcluir(null)}
          onConfirm={() => excluirMutation.mutate(paraExcluir)}
        />
      )}
    </div>
  )
}
