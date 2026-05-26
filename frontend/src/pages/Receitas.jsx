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
import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import {
  Plus, TrendingUp, CheckCircle2, Clock,
  Loader2, RefreshCw, ArrowUpCircle, Repeat, DollarSign, Filter
} from 'lucide-react';

import { fetchReceitas, createReceita } from '../services/financeiro';
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

// ─── Schema ───────────────────────────────────────────────────────────────────

const schema = z.object({
  descricao: z.string().min(3, 'Descrição obrigatória (mín. 3 caracteres)'),
  categoria: z.string().min(1, 'Informe a categoria'),
  valor: z.coerce.number().positive('Valor deve ser positivo'),
  data_recebimento: z.string().min(1, 'Data obrigatória'),
  tipo: z.enum(['unica', 'recorrente']),
  recorrencia: z.string().optional(),
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
  const queryClient = useQueryClient()
  const [modalOpen, setModalOpen] = useState(false)
  const [tipoSelecionado, setTipoSelecionado] = useState('unica')

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

  const createMutation = useMutation({
    mutationFn: createReceita,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['receitas'] })
      setModalOpen(false)
      reset()
    },
  })

  const onSubmit = (values) => createMutation.mutate(values)

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
          <Button onClick={() => setModalOpen(true)}>
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
        <Card className="glass border-emerald-500/20">
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

        <Card className="glass border-emerald-500/20">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground uppercase tracking-wider">
              Receitas Realizadas
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-bold text-emerald-500">{formatCurrency(totalRealizado)}</p>
            <p className="text-xs text-muted-foreground mt-1">{realizadas.length} recebida(s)</p>
          </CardContent>
        </Card>

        <Card className="glass">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground uppercase tracking-wider">
              Ainda Previstas
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-bold text-orange-500">
              {formatCurrency(previstas.reduce((a, r) => a + Number(r.valor ?? 0), 0))}
            </p>
            <p className="text-xs text-muted-foreground mt-1">{previstas.length} a receber</p>
          </CardContent>
        </Card>
      </div>

      {/* Error */}
      {isError && (
        <div className="rounded-xl border border-red-500/20 bg-red-500/5 p-4 text-sm text-red-600 dark:text-red-400">
          Não foi possível carregar as receitas. Verifique a conexão com a API.
        </div>
      )}

      {/* Tabela */}
      <DataTable
        columns={columns}
        data={receitas}
        isLoading={isLoading}
        pageSize={10}
        emptyMessage="Nenhuma receita cadastrada para o período selecionado."
      />

      {/* ─── Modal: Nova Receita ──────────────────────────────────────────────── */}
      <Modal
        isOpen={modalOpen}
        onClose={() => { setModalOpen(false); reset() }}
        title="Nova Receita"
        description="Cadastre uma entrada financeira única ou recorrente"
        size="md"
      >
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
          {/* Tipo: Única ou Recorrente */}
          <div>
            <label className="mb-2 block text-sm font-medium text-foreground">
              Tipo de Receita
            </label>
            <div className="flex gap-3">
              {[
                { value: 'unica', label: 'Receita Única', Icon: ArrowUpCircle },
                { value: 'recorrente', label: 'Recorrente', Icon: Repeat },
              ].map(({ value, label, Icon }) => (
                <button
                  key={value}
                  type="button"
                  onClick={() => { setValue('tipo', value); setTipoSelecionado(value) }}
                  className={`flex flex-1 items-center justify-center gap-2 rounded-lg border px-4 py-3 text-sm font-medium transition-all duration-200 ${
                    watchTipo === value
                      ? 'border-primary bg-primary/10 text-primary'
                      : 'border-border bg-background text-muted-foreground hover:border-primary/40'
                  }`}
                >
                  <Icon className="h-4 w-4" />
                  {label}
                </button>
              ))}
            </div>
          </div>

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div className="sm:col-span-2">
              <label className="mb-1.5 block text-sm font-medium text-foreground">
                Descrição <span className="text-red-500">*</span>
              </label>
              <Input {...register('descricao')} placeholder="Ex: Salário, Freelance React..." />
              {errors.descricao && (
                <p className="mt-1 text-xs text-red-500">{errors.descricao.message}</p>
              )}
            </div>

            <div>
              <label className="mb-1.5 block text-sm font-medium text-foreground">
                Categoria <span className="text-red-500">*</span>
              </label>
              <Input {...register('categoria')} placeholder="Ex: Salário, Dividendos" />
              {errors.categoria && (
                <p className="mt-1 text-xs text-red-500">{errors.categoria.message}</p>
              )}
            </div>

            <div>
              <label className="mb-1.5 block text-sm font-medium text-foreground">
                Valor (R$) <span className="text-red-500">*</span>
              </label>
              <Input {...register('valor')} type="number" step="0.01" placeholder="0,00" />
              {errors.valor && (
                <p className="mt-1 text-xs text-red-500">{errors.valor.message}</p>
              )}
            </div>

            <div className={watchTipo === 'recorrente' ? '' : 'sm:col-span-2'}>
              <label className="mb-1.5 block text-sm font-medium text-foreground">
                Data de Recebimento <span className="text-red-500">*</span>
              </label>
              <Input {...register('data_recebimento')} type="date" />
              {errors.data_recebimento && (
                <p className="mt-1 text-xs text-red-500">{errors.data_recebimento.message}</p>
              )}
            </div>

            {watchTipo === 'recorrente' && (
              <div>
                <label className="mb-1.5 block text-sm font-medium text-foreground">
                  Frequência
                </label>
                <Select {...register('recorrencia')}>
                  <option value="">Selecione...</option>
                  <option value="mensal">Mensal</option>
                  <option value="quinzenal">Quinzenal</option>
                  <option value="semanal">Semanal</option>
                  <option value="anual">Anual</option>
                </Select>
              </div>
            )}
          </div>

          {createMutation.isError && (
            <p className="text-sm text-red-500">Erro ao criar receita. Tente novamente.</p>
          )}

          <div className="flex justify-end gap-3 pt-2">
            <Button variant="outline" type="button" onClick={() => { setModalOpen(false); reset() }}>
              Cancelar
            </Button>
            <Button
              type="submit"
              disabled={isSubmitting || createMutation.isPending}
              className="bg-primary hover:bg-primary/90 text-primary-foreground border-0"
            >
              {(isSubmitting || createMutation.isPending) && (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              )}
              <TrendingUp className="mr-1.5 h-4 w-4" />
              Salvar Receita
            </Button>
          </div>
        </form>
      </Modal>
    </div>
  )
}
