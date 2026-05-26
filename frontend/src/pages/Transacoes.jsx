/**
 * Tela de Extrato Mensal e Lançamento de Transações.
 * 
 * Exibe de forma cronológica o histórico consolidado de receitas e despesas do usuário.
 * Implementa filtros rápidos de competência (mês/ano), paginação inteligente e ações rápidas
 * de liquidação/pagamento direto na listagem.
 *
 * @component
 * @returns {React.JSX.Element} Tabela estruturada de extrato financeiro mensal.
 */
import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { RefreshCw, ArrowUp, ArrowDown, Search } from 'lucide-react';

import { fetchTransacoes } from '../services/financeiro';
import { Button } from '../components/ui/Button';
import { Input } from '../components/ui/Input';
import { Select } from '../components/ui/Select';
import { Badge } from '../components/ui/Badge';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/Card';

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

// Agrupa array de transações por dia
const groupByDay = (transactions) => {
  const map = {}
  for (const tx of transactions) {
    const day = tx.data?.substring(0, 10) ?? 'sem-data'
    if (!map[day]) map[day] = []
    map[day].push(tx)
  }
  // Ordena os dias mais recentes primeiro
  return Object.entries(map).sort(([a], [b]) => b.localeCompare(a))
}

// ─── Componentes Auxiliares ───────────────────────────────────────────────────

const SkeletonRows = () => (
  <div className="space-y-6">
    {Array.from({ length: 3 }).map((_, g) => (
      <div key={g}>
        <div className="h-4 w-24 animate-pulse rounded bg-muted mb-3" />
        <div className="rounded-xl border border-border/60 divide-y divide-border/40">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="flex items-center justify-between px-4 py-3">
              <div className="flex items-center gap-3">
                <div className="h-9 w-9 rounded-full animate-pulse bg-muted" />
                <div>
                  <div className="h-3.5 w-40 animate-pulse rounded bg-muted mb-1.5" />
                  <div className="h-3 w-24 animate-pulse rounded bg-muted" />
                </div>
              </div>
              <div className="h-4 w-20 animate-pulse rounded bg-muted" />
            </div>
          ))}
        </div>
      </div>
    ))}
  </div>
)

// ─── Componente Principal ─────────────────────────────────────────────────────

export default function Transacoes() {
  const hoje = new Date()
  const [mes, setMes] = useState(String(hoje.getMonth() + 1).padStart(2, '0'))
  const [ano, setAno] = useState(String(hoje.getFullYear()))
  const [busca, setBusca] = useState('')

  const { data: transacoes = [], isLoading, isError, refetch } = useQuery({
    queryKey: ['transacoes', mes, ano],
    queryFn: () => fetchTransacoes({ mes, ano }),
  })

  // Filtro por texto
  const filtered = transacoes.filter((tx) => {
    if (!busca) return true
    const q = busca.toLowerCase()
    return (
      tx.descricao?.toLowerCase().includes(q) ||
      tx.categoria?.toLowerCase().includes(q) ||
      String(tx.valor).includes(q)
    )
  })

  // Agrupamento por dia
  const groups = groupByDay(filtered)

  // KPIs
  const totalEntradas = filtered
    .filter((tx) => tx.tipo === 'entrada')
    .reduce((a, tx) => a + Math.abs(Number(tx.valor ?? 0)), 0)

  const totalSaidas = filtered
    .filter((tx) => tx.tipo === 'saida')
    .reduce((a, tx) => a + Math.abs(Number(tx.valor ?? 0)), 0)

  const saldo = totalEntradas - totalSaidas



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

      {/* Filtros */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
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

        <div className="flex-1">
          <label className="mb-1.5 block text-xs font-medium text-muted-foreground uppercase tracking-wider">
            Buscar
          </label>
          <div className="relative">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              value={busca}
              onChange={(e) => setBusca(e.target.value)}
              placeholder="Pesquisar descrição, categoria..."
              className="pl-9"
            />
          </div>
        </div>
      </div>

      {/* KPIs */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <Card className="glass border-emerald-500/20">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground uppercase tracking-wider flex items-center gap-1.5">
              <ArrowUp className="h-4 w-4 text-emerald-500" />
              Entradas
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-bold text-emerald-500">{formatCurrency(totalEntradas)}</p>
          </CardContent>
        </Card>

        <Card className="glass border-rose-500/20">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground uppercase tracking-wider flex items-center gap-1.5">
              <ArrowDown className="h-4 w-4 text-rose-500" />
              Saídas
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-bold text-rose-500 dark:text-rose-400">{formatCurrency(totalSaidas)}</p>
          </CardContent>
        </Card>

        <Card className={`glass ${saldo >= 0 ? 'border-emerald-500/20' : 'border-rose-500/20'}`}>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground uppercase tracking-wider">
              Saldo do Período
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className={`text-2xl font-bold ${saldo >= 0 ? 'text-emerald-500' : 'text-rose-500'}`}>
              {saldo >= 0 ? '+' : ''}{formatCurrency(saldo)}
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Error */}
      {isError && (
        <div className="rounded-xl border border-red-500/20 bg-red-500/5 p-4 text-sm text-red-600 dark:text-red-400">
          Não foi possível carregar as transações. Verifique a conexão com a API.
        </div>
      )}

      {/* Lista agrupada por dia */}
      {isLoading ? (
        <SkeletonRows />
      ) : groups.length === 0 ? (
        <div className="rounded-xl border border-dashed border-border/60 py-16 text-center text-muted-foreground">
          {busca
            ? `Nenhum resultado para "${busca}"`
            : `Nenhuma transação em ${MONTHS[Number(mes) - 1]} de ${ano}.`}
        </div>
      ) : (
        <div className="space-y-6">
          {groups.map(([day, txs]) => {
            const dayTotal = txs.reduce((sum, tx) => {
              const val = Number(tx.valor ?? 0)
              return tx.tipo === 'entrada' ? sum + Math.abs(val) : sum - Math.abs(val)
            }, 0)

            return (
              <div key={day}>
                {/* Cabeçalho do dia */}
                <div className="flex items-center justify-between mb-2 px-1">
                  <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                    {formatDate(day)}
                  </p>
                  <span className={`text-xs font-semibold ${dayTotal >= 0 ? 'text-emerald-500' : 'text-rose-500'}`}>
                    {dayTotal >= 0 ? '+' : ''}{formatCurrency(dayTotal)}
                  </span>
                </div>

                {/* Transações do dia */}
                <div className="rounded-xl border border-border/60 bg-card divide-y divide-border/40 overflow-hidden">
                  {txs.map((tx, idx) => {
                    const isEntrada = tx.tipo === 'entrada'
                    const valor = Math.abs(Number(tx.valor ?? 0))

                    return (
                      <div
                        key={tx.id ?? idx}
                        className={`flex items-center justify-between px-4 py-3 transition-colors hover:bg-muted/30 border-l-4 ${
                          isEntrada ? 'border-l-emerald-500' : 'border-l-rose-500'
                        }`}
                      >
                        <div className="flex items-center gap-3">
                          {/* Ícone */}
                          <div className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-full ${
                            isEntrada
                              ? 'bg-emerald-500/10 text-emerald-500'
                              : 'bg-rose-500/10 text-rose-500'
                          }`}>
                            {isEntrada
                              ? <ArrowUp className="h-4 w-4" />
                              : <ArrowDown className="h-4 w-4" />}
                          </div>
                          <div>
                            <p className="font-medium text-sm text-foreground leading-tight">
                              {tx.descricao || 'Sem descrição'}
                            </p>
                            <p className="text-xs text-muted-foreground">{tx.categoria || '—'}</p>
                          </div>
                        </div>

                        <div className="flex items-center gap-3">
                          {tx.categoria && (
                            <Badge variant="secondary" className="hidden sm:inline-flex">
                              {tx.categoria}
                            </Badge>
                          )}
                          <span className={`font-semibold text-sm ${
                            isEntrada ? 'text-emerald-500' : 'text-rose-500'
                          }`}>
                            {isEntrada ? '+' : '-'} {formatCurrency(valor)}
                          </span>
                        </div>
                      </div>
                    )
                  })}
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
