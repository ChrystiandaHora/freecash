/**
 * Tela de Extrato Mensal e Lançamento de Transações.
 *
 * Exibe de forma cronológica o histórico consolidado de receitas e despesas do usuário.
 * Implementa filtros rápidos de competência (mês/ano) e uma tabela padronizada com
 * ordenação, filtro por coluna e paginação.
 *
 * @component
 * @returns {React.JSX.Element} Tabela estruturada de extrato financeiro mensal.
 */
import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { RefreshCw, ArrowUp, ArrowDown } from 'lucide-react';

import { fetchTransacoes } from '../services/financeiro';
import { Button } from '../components/ui/Button';
import { Select } from '../components/ui/Select';
import { Alert } from '../components/ui/Alert';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/Card';
import { DataTable } from '../components/ui/DataTable';

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

// ─── Componente Principal ─────────────────────────────────────────────────────

export default function Transacoes() {
  const hoje = new Date()
  const [mes, setMes] = useState(String(hoje.getMonth() + 1).padStart(2, '0'))
  const [ano, setAno] = useState(String(hoje.getFullYear()))
  const [filteredTransacoes, setFilteredTransacoes] = useState(null)

  const { data: transacoes = [], isLoading, isError, refetch } = useQuery({
    queryKey: ['transacoes', mes, ano],
    queryFn: () => fetchTransacoes({ mes, ano }),
  })

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
            {isEntrada ? <ArrowUp className="h-3 w-3" /> : <ArrowDown className="h-3 w-3" />}
            {isEntrada ? 'Entrada' : 'Saída'}
          </span>
        )
      },
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
        <Button variant="outline" size="sm" onClick={() => refetch()}>
          <RefreshCw className="mr-1.5 h-4 w-4" />
          Atualizar
        </Button>
      </div>

      {/* Filtros de competência */}
      <div className="flex flex-wrap items-end gap-2">
        <div>
          <label className="mb-1.5 block text-xs font-medium text-muted-foreground uppercase tracking-wider">
            Mês
          </label>
          <Select value={mes} onChange={(e) => setMes(e.target.value)} className="w-36">
            {MONTHS.map((m, i) => (
              <option key={i} value={String(i + 1).padStart(2, '0')}>
                {m}
              </option>
            ))}
          </Select>
        </div>
        <div>
          <label className="mb-1.5 block text-xs font-medium text-muted-foreground uppercase tracking-wider">
            Ano
          </label>
          <Select value={ano} onChange={(e) => setAno(e.target.value)} className="w-24">
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
              <ArrowUp className="h-4 w-4 text-emerald-600 dark:text-emerald-400" />
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
              <ArrowDown className="h-4 w-4 text-rose-600 dark:text-rose-400" />
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
    </div>
  )
}
