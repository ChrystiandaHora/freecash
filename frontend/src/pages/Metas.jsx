/**
 * Tela de Metas Financeiras.
 *
 * Materializa uma regra de bolso de finanças pessoais: a partir de dois números
 * — renda mensal e custo de vida mensal — deriva quatro alvos (patrimônio para
 * viver de renda, meta inicial de investimentos, reserva de emergência e limite
 * de gastos essenciais). A base de cálculo é sugerida pela média dos últimos
 * meses de lançamentos, mas pode ser sobrescrita e fica persistida.
 *
 * Além das quatro metas padrão, permite cadastrar metas personalizadas e
 * registrar aportes, com todo o acervo listado numa tabela filtrável.
 *
 * @component
 * @returns {React.JSX.Element} Painel e listagem de metas financeiras.
 */
import { useMemo, useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  Plus, RefreshCw, Loader2, Trash2, Pencil, PiggyBank, Target,
  Wallet, Sparkles, ShieldCheck, TrendingDown, Calculator, Save, CalendarClock,
  RotateCcw,
} from 'lucide-react'

import {
  fetchMetas, fetchPlanoMetas, updatePlanoMetas, gerarMetasPadrao, deleteMeta,
  updateMultiplicadores,
} from '../services/metas'
import { DataTable } from '../components/ui/DataTable'
import { Badge } from '../components/ui/Badge'
import { Alert } from '../components/ui/Alert'
import { Button } from '../components/ui/Button'
import { Input } from '../components/ui/Input'
import { Modal } from '../components/ui/Modal'
import { Progress } from '../components/ui/Progress'
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/Card'
import MetaFormModal from '../components/MetaFormModal'
import AporteMetaModal from '../components/AporteMetaModal'
import MetaCard from '../components/MetaCard'
import { useToast } from '../context/ToastContext'

// ─── Helpers ──────────────────────────────────────────────────────────────────

const formatCurrency = (val) =>
  new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(val ?? 0)

const formatDate = (dateStr) => {
  if (!dateStr || typeof dateStr !== 'string') return '—'
  const parts = dateStr.split('-')
  if (parts.length < 3) return dateStr
  const [year, month, day] = parts
  return `${day}/${month}/${year}`
}

/** Formata o multiplicador removendo zeros à direita (0.6000 → "0,6"). */
const formatMultiplicador = (val) => {
  if (val == null || val === '') return '—'
  const num = Number(val)
  if (!Number.isFinite(num)) return '—'
  return `×${num.toLocaleString('pt-BR', { maximumFractionDigits: 4 })}`
}

/** Ícone de cada meta padrão; personalizadas caem no alvo genérico. */
const ICONE_POR_TIPO = {
  patrimonio_renda: Sparkles,
  aporte_mensal: CalendarClock,
  reserva_emergencia: ShieldCheck,
  gasto_essencial: TrendingDown,
}

const TIPOS_PADRAO = [
  'patrimonio_renda',
  'aporte_mensal',
  'reserva_emergencia',
  'gasto_essencial',
]

/** Rótulo curto da origem automática, exibido como badge ao lado do progresso. */
const BADGE_POR_ORIGEM = {
  carteira: 'Valor de mercado',
  aportes_mes: 'Aportes do mês',
}

/** Explica se o alvo de cada meta padrão é um total ou se renova a cada mês. */
const PERIODICIDADE_POR_TIPO = {
  patrimonio_renda: 'total a acumular',
  aporte_mensal: 'a aportar todo mês',
  reserva_emergencia: 'total a acumular',
  gasto_essencial: 'teto por mês',
}

/**
 * Traduz uma meta em como ela deve ser apresentada.
 *
 * Metas de acúmulo comemoram ao chegar no alvo; metas de teto alertam ao
 * ultrapassá-lo. Sem essa distinção, um gasto essencial estourado apareceria
 * verde, como se fosse um progresso.
 */
const avaliarMeta = (meta, gastoEssencialMes) => {
  const alvo = Number(meta.valor_alvo ?? 0)
  const eTeto = meta.natureza === 'teto'
  // Numa meta de teto o que progride é o gasto do mês, não um acumulado.
  // `valor_acumulado_efetivo` já resolve a origem: manual ou valor de mercado
  // da carteira de investimentos.
  const atual = eTeto
    ? Number(gastoEssencialMes ?? 0)
    : Number(meta.valor_acumulado_efetivo ?? meta.valor_acumulado ?? 0)
  const percentual = alvo > 0 ? (atual / alvo) * 100 : 0

  // Legenda sob o valor-alvo: a fórmula, quando derivado; a periodicidade,
  // quando o alvo foi digitado pelo usuário.
  const legendaAlvo =
    meta.base_calculo !== 'manual'
      ? `${meta.base_calculo_display} ${formatMultiplicador(meta.multiplicador)}`
      : eTeto
        ? 'Teto por mês'
        : 'Total a juntar'

  if (eTeto) {
    const estourou = percentual > 100
    return {
      atual,
      alvo,
      percentual,
      legendaAlvo,
      variant: estourou ? 'danger' : percentual >= 85 ? 'warning' : 'success',
      rotuloAtual: 'Gasto do mês',
      statusTexto: estourou
        ? `Acima do limite em ${formatCurrency(atual - alvo)}`
        : `Folga de ${formatCurrency(alvo - atual)}`,
      statusOk: !estourou,
    }
  }

  const concluida = percentual >= 100
  const eMensal = meta.origem_acumulado === 'aportes_mes'
  const rotulosPorOrigem = {
    carteira: 'Patrimônio na carteira',
    aportes_mes: 'Aportado neste mês',
  }

  return {
    atual,
    alvo,
    percentual,
    legendaAlvo,
    variant: concluida ? 'success' : 'default',
    rotuloAtual: rotulosPorOrigem[meta.origem_acumulado] ?? 'Guardado',
    // Numa meta mensal o alvo se renova todo mês, então o texto precisa deixar
    // claro que o que falta (ou o que foi batido) é referente a este mês.
    statusTexto: concluida
      ? eMensal
        ? 'Meta do mês atingida'
        : 'Meta atingida'
      : eMensal
        ? `Faltam ${formatCurrency(alvo - atual)} neste mês`
        : `Faltam ${formatCurrency(alvo - atual)}`,
    statusOk: concluida,
  }
}

// ─── Componente Principal ─────────────────────────────────────────────────────

export default function Metas() {
  const queryClient = useQueryClient()
  const { addToast } = useToast()

  const [rendaInput, setRendaInput] = useState('')
  const [custoInput, setCustoInput] = useState('')
  const [planoSincronizado, setPlanoSincronizado] = useState(null)
  const [multiplicadorInputs, setMultiplicadorInputs] = useState({})
  const [metasSincronizadas, setMetasSincronizadas] = useState(null)
  const [metaEmEdicao, setMetaEmEdicao] = useState(null)
  const [formAberto, setFormAberto] = useState(false)
  const [metaParaAporte, setMetaParaAporte] = useState(null)
  const [deleteId, setDeleteId] = useState(null)
  const [actionError, setActionError] = useState('')

  const {
    data: planoData,
    isLoading: isLoadingPlano,
    isError: isErrorPlano,
    refetch: refetchPlano,
  } = useQuery({ queryKey: ['metas-plano'], queryFn: fetchPlanoMetas })

  const {
    data: metas = [],
    isLoading: isLoadingMetas,
    isError: isErrorMetas,
    refetch: refetchMetas,
  } = useQuery({ queryKey: ['metas'], queryFn: fetchMetas })

  const plano = planoData?.plano
  const sugestoes = planoData?.sugestoes
  const gastoEssencialMes = planoData?.gasto_essencial_mes ?? 0
  const multiplicadoresPadrao = planoData?.multiplicadores_padrao ?? {}

  // Ressincroniza os campos quando o servidor devolve um plano diferente. O
  // ajuste durante a renderização (e não num efeito) evita o render em cascata;
  // a identidade de `plano` só muda quando os dados realmente mudam, graças ao
  // structural sharing do TanStack Query.
  if (plano && plano !== planoSincronizado) {
    setPlanoSincronizado(plano)
    setRendaInput(plano.renda_mensal != null ? String(Number(plano.renda_mensal)) : '')
    setCustoInput(plano.custo_vida_mensal != null ? String(Number(plano.custo_vida_mensal)) : '')
  }

  // Mesma técnica para os multiplicadores: recarrega os campos quando a lista
  // de metas muda de verdade (salvar, recalcular, editar em outro lugar).
  if (metas.length && metas !== metasSincronizadas) {
    setMetasSincronizadas(metas)
    setMultiplicadorInputs(
      Object.fromEntries(
        metas
          .filter((m) => m.multiplicador != null)
          .map((m) => [m.tipo, String(Number(m.multiplicador))])
      )
    )
  }

  const salvarPlanoMutation = useMutation({
    mutationFn: updatePlanoMetas,
    onMutate: () => setActionError(''),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['metas-plano'] })
      addToast('Base de cálculo salva.', 'success')
    },
    onError: () => setActionError('Não foi possível salvar a base de cálculo. Tente novamente.'),
  })

  const gerarMutation = useMutation({
    mutationFn: gerarMetasPadrao,
    onMutate: () => setActionError(''),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['metas'] })
      addToast('Metas padrão recalculadas.', 'success')
    },
    onError: () =>
      setActionError(
        'Não foi possível gerar as metas. Salve a renda mensal e o custo de vida antes de continuar.'
      ),
  })

  const deleteMutation = useMutation({
    mutationFn: deleteMeta,
    onMutate: () => setActionError(''),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['metas'] })
      setDeleteId(null)
      addToast('Meta excluída.', 'success')
    },
    onError: () => {
      setDeleteId(null)
      setActionError('Não foi possível excluir a meta. Tente novamente.')
    },
  })

  const multiplicadoresMutation = useMutation({
    mutationFn: updateMultiplicadores,
    onMutate: () => setActionError(''),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['metas'] })
      addToast('Multiplicadores salvos e alvos recalculados.', 'success')
    },
    onError: () =>
      setActionError(
        'Não foi possível salvar os multiplicadores. Verifique se todos são maiores que zero.'
      ),
  })

  const handleSalvarMultiplicadores = (event) => {
    event.preventDefault()
    multiplicadoresMutation.mutate(multiplicadorInputs)
  }

  const restaurarMultiplicadoresPadrao = () => {
    // Só preenche os campos: nada é gravado até o usuário confirmar em salvar.
    setMultiplicadorInputs((prev) =>
      Object.fromEntries(
        Object.keys(prev).map((tipo) => [
          tipo,
          multiplicadoresPadrao[tipo] != null
            ? String(Number(multiplicadoresPadrao[tipo]))
            : prev[tipo],
        ])
      )
    )
  }

  const handleSalvarPlano = (event) => {
    event.preventDefault()
    salvarPlanoMutation.mutate({
      renda_mensal: rendaInput === '' ? null : Number(rendaInput),
      custo_vida_mensal: custoInput === '' ? null : Number(custoInput),
    })
  }

  const abrirNovaMeta = () => {
    setMetaEmEdicao(null)
    setFormAberto(true)
  }

  const abrirEdicao = (meta) => {
    setMetaEmEdicao(meta)
    setFormAberto(true)
  }

  const rendaAtual = plano?.renda_mensal != null ? Number(plano.renda_mensal) : null
  const custoAtual = plano?.custo_vida_mensal != null ? Number(plano.custo_vida_mensal) : null

  const metasPadrao = useMemo(
    () =>
      TIPOS_PADRAO.map((tipo) => metas.find((m) => m.tipo === tipo)).filter(Boolean),
    [metas]
  )

  // Tudo que não é uma das quatro de referência — inclusive uma meta padrão que
  // o usuário tenha excluído e recriado por conta própria.
  const metasPersonalizadas = useMemo(
    () => metas.filter((m) => !TIPOS_PADRAO.includes(m.tipo)),
    [metas]
  )

  // ─── Colunas ───────────────────────────────────────────────────────────────
  const columns = [
    {
      key: 'nome',
      header: 'Meta',
      sortable: true,
      filterable: true,
      filterType: 'text',
      render: (val, row) => (
        <div className="min-w-[12rem]">
          <p className="font-medium text-foreground">{val}</p>
          {row.observacao && (
            <p className="mt-0.5 text-xs text-muted-foreground line-clamp-2">{row.observacao}</p>
          )}
        </div>
      ),
    },
    {
      key: 'natureza',
      header: 'Natureza',
      sortable: true,
      filterable: true,
      filterType: 'select',
      render: (val, row) => (
        <Badge variant={val === 'teto' ? 'warning' : 'secondary'}>{row.natureza_display}</Badge>
      ),
    },
    {
      key: 'base_calculo',
      header: 'Base',
      sortable: true,
      filterable: true,
      filterType: 'select',
      render: (val, row) => (
        <span className="text-sm text-muted-foreground">
          {row.base_calculo_display}
          {val !== 'manual' && (
            <span className="ml-1 font-mono text-xs">{formatMultiplicador(row.multiplicador)}</span>
          )}
        </span>
      ),
    },
    {
      key: 'valor_alvo',
      header: 'Valor-alvo',
      sortable: true,
      className: 'text-right',
      render: (val) => (
        <span className="font-semibold tabular-nums text-foreground">
          {formatCurrency(Number(val))}
        </span>
      ),
    },
    {
      key: 'valor_acumulado_efetivo',
      header: 'Acumulado',
      sortable: true,
      className: 'text-right',
      render: (val, row) => (
        <div className="flex flex-col items-end gap-0.5">
          <span className="tabular-nums text-emerald-700 dark:text-emerald-400">
            {formatCurrency(Number(val))}
          </span>
          {BADGE_POR_ORIGEM[row.origem_acumulado] && (
            <Badge variant="default" className="gap-1">
              <Wallet className="h-3 w-3" aria-hidden="true" />
              {BADGE_POR_ORIGEM[row.origem_acumulado]}
            </Badge>
          )}
        </div>
      ),
    },
    {
      key: 'progresso_percentual',
      header: 'Progresso',
      sortable: true,
      render: (_val, row) => {
        const avaliacao = avaliarMeta(row, gastoEssencialMes)
        return (
          <div className="min-w-[10rem]">
            <Progress
              value={avaliacao.percentual}
              label={`Progresso de ${row.nome}`}
              variant={avaliacao.variant}
              valueLabel={`${avaliacao.percentual.toFixed(1)}%`}
            />
          </div>
        )
      },
    },
    {
      key: 'prazo',
      header: 'Prazo',
      sortable: true,
      filterable: true,
      filterType: 'date',
      render: (val) => (
        <span className="font-mono text-xs text-muted-foreground">{formatDate(val)}</span>
      ),
    },
    {
      key: 'acoes',
      header: 'Ações',
      className: 'text-right',
      render: (_val, row) => (
        <div className="flex justify-end gap-1">
          <Button
            variant="ghost"
            size="icon"
            onClick={() => setMetaParaAporte(row)}
            title={`Registrar aporte em ${row.nome}`}
            aria-label={`Registrar aporte em ${row.nome}`}
          >
            <PiggyBank className="h-4 w-4" aria-hidden="true" />
          </Button>
          <Button
            variant="ghost"
            size="icon"
            onClick={() => abrirEdicao(row)}
            title={`Editar ${row.nome}`}
            aria-label={`Editar ${row.nome}`}
          >
            <Pencil className="h-4 w-4" aria-hidden="true" />
          </Button>
          <Button
            variant="ghost"
            size="icon"
            onClick={() => setDeleteId(row.id)}
            title={`Excluir ${row.nome}`}
            aria-label={`Excluir ${row.nome}`}
          >
            <Trash2 className="h-4 w-4 text-rose-600 dark:text-rose-400" aria-hidden="true" />
          </Button>
        </div>
      ),
    },
  ]

  const metaParaExcluir = metas.find((m) => m.id === deleteId)

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-3xl font-extrabold tracking-tight text-foreground">Metas</h1>
          <p className="mt-1 text-slate-500 dark:text-slate-400">
            Defina seus alvos financeiros a partir da sua renda e do seu custo de vida
          </p>
        </div>
        <div className="flex gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => {
              refetchPlano()
              refetchMetas()
            }}
          >
            <RefreshCw className="mr-1.5 h-4 w-4" aria-hidden="true" />
            Atualizar
          </Button>
          <Button onClick={abrirNovaMeta}>
            <Plus className="mr-1.5 h-4 w-4" aria-hidden="true" />
            Nova Meta
          </Button>
        </div>
      </div>

      {/* Erros */}
      {(isErrorPlano || isErrorMetas) && (
        <Alert variant="error">
          Não foi possível carregar as metas. Verifique a conexão com a API.
        </Alert>
      )}
      {actionError && <Alert variant="error">{actionError}</Alert>}

      {/* ─── Base de cálculo ────────────────────────────────────────────────── */}
      <Card className="border border-border/40 bg-card text-card-foreground shadow-sm">
        <CardHeader className="pb-3">
          <CardTitle className="flex items-center gap-2 text-sm font-medium uppercase tracking-wider text-muted-foreground">
            <Calculator className="h-4 w-4" aria-hidden="true" />
            Base de cálculo
          </CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSalvarPlano} className="space-y-4">
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <div className="space-y-1.5">
                <label htmlFor="plano-renda" className="text-sm font-medium text-foreground">
                  Renda mensal (R$)
                </label>
                <Input
                  id="plano-renda"
                  type="number"
                  step="0.01"
                  placeholder="0,00"
                  value={rendaInput}
                  onChange={(e) => setRendaInput(e.target.value)}
                  aria-describedby="plano-renda-hint"
                />
                <p id="plano-renda-hint" className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                  <span>
                    Média dos últimos {sugestoes?.meses ?? 3} meses:{' '}
                    {formatCurrency(sugestoes?.renda_mensal)}
                  </span>
                  <button
                    type="button"
                    onClick={() => setRendaInput(String(sugestoes?.renda_mensal ?? 0))}
                    className="rounded-md px-2 py-0.5 font-medium text-primary underline underline-offset-2 hover:bg-primary/10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                  >
                    Usar esse valor
                  </button>
                </p>
              </div>

              <div className="space-y-1.5">
                <label htmlFor="plano-custo" className="text-sm font-medium text-foreground">
                  Custo de vida mensal (R$)
                </label>
                <Input
                  id="plano-custo"
                  type="number"
                  step="0.01"
                  placeholder="0,00"
                  value={custoInput}
                  onChange={(e) => setCustoInput(e.target.value)}
                  aria-describedby="plano-custo-hint"
                />
                <p id="plano-custo-hint" className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                  <span>
                    Média dos últimos {sugestoes?.meses ?? 3} meses:{' '}
                    {formatCurrency(sugestoes?.custo_vida_mensal)}
                  </span>
                  <button
                    type="button"
                    onClick={() => setCustoInput(String(sugestoes?.custo_vida_mensal ?? 0))}
                    className="rounded-md px-2 py-0.5 font-medium text-primary underline underline-offset-2 hover:bg-primary/10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                  >
                    Usar esse valor
                  </button>
                </p>
              </div>
            </div>

            <div className="flex flex-wrap justify-end gap-2 border-t border-border/60 pt-4">
              <Button type="submit" variant="outline" disabled={salvarPlanoMutation.isPending}>
                {salvarPlanoMutation.isPending ? (
                  <Loader2 className="mr-1.5 h-4 w-4 animate-spin" aria-hidden="true" />
                ) : (
                  <Save className="mr-1.5 h-4 w-4" aria-hidden="true" />
                )}
                Salvar base
              </Button>
              <Button
                type="button"
                onClick={() => gerarMutation.mutate()}
                disabled={gerarMutation.isPending}
              >
                {gerarMutation.isPending ? (
                  <Loader2 className="mr-1.5 h-4 w-4 animate-spin" aria-hidden="true" />
                ) : (
                  <Target className="mr-1.5 h-4 w-4" aria-hidden="true" />
                )}
                Gerar / recalcular metas padrão
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>

      {/* ─── Cards das metas padrão ─────────────────────────────────────────── */}
      {isLoadingPlano || isLoadingMetas ? (
        <div
          role="status"
          aria-busy="true"
          className="flex items-center justify-center rounded-xl border border-border/40 bg-card p-10"
        >
          <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" aria-hidden="true" />
          <span className="sr-only">Carregando metas…</span>
        </div>
      ) : metasPadrao.length === 0 ? (
        <Alert variant="info" title="Nenhuma meta padrão gerada ainda">
          Preencha a renda mensal e o custo de vida acima e clique em
          {' '}<strong>Gerar / recalcular metas padrão</strong> para criar as quatro metas de
          referência.
        </Alert>
      ) : (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
          {metasPadrao.map((meta) => (
            <MetaCard
              key={meta.id}
              meta={meta}
              avaliacao={avaliarMeta(meta, gastoEssencialMes)}
              icone={ICONE_POR_TIPO[meta.tipo] ?? Target}
              badgeOrigem={BADGE_POR_ORIGEM[meta.origem_acumulado]}
              // Aporte manual só faz sentido onde o progresso é manual: nas
              // metas que leem a carteira, o número vem dos investimentos.
              onAportar={meta.origem_acumulado === 'manual' ? setMetaParaAporte : undefined}
            />
          ))}
        </div>
      )}

      {/* ─── Minhas metas (personalizadas) ──────────────────────────────────── */}
      {!isLoadingMetas && (
        <section aria-labelledby="titulo-minhas-metas" className="space-y-4">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h2
              id="titulo-minhas-metas"
              className="text-lg font-bold tracking-tight text-foreground"
            >
              Minhas metas
            </h2>
            <Button variant="outline" size="sm" onClick={abrirNovaMeta}>
              <Plus className="mr-1.5 h-4 w-4" aria-hidden="true" />
              Nova meta
            </Button>
          </div>

          {metasPersonalizadas.length === 0 ? (
            <Alert variant="info" title="Nenhuma meta sua ainda">
              Crie um objetivo próprio — uma viagem, a troca do celular, o que for — defina
              quanto quer juntar e vá registrando o que guardar. O progresso aparece aqui.
            </Alert>
          ) : (
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
              {metasPersonalizadas.map((meta) => (
                <MetaCard
                  key={meta.id}
                  meta={meta}
                  avaliacao={avaliarMeta(meta, gastoEssencialMes)}
                  icone={ICONE_POR_TIPO[meta.tipo] ?? Target}
                  badgeOrigem={BADGE_POR_ORIGEM[meta.origem_acumulado]}
                  onAportar={meta.origem_acumulado === 'manual' ? setMetaParaAporte : undefined}
                />
              ))}
            </div>
          )}
        </section>
      )}

      {/* ─── Multiplicadores das metas padrão (editáveis) ───────────────────── */}
      {metasPadrao.length > 0 && (
        <Card className="border border-border/40 bg-card text-card-foreground shadow-sm">
          <CardHeader className="pb-2">
            <CardTitle className="flex items-center gap-2 text-sm font-medium uppercase tracking-wider text-muted-foreground">
              <Calculator className="h-4 w-4" aria-hidden="true" />
              Como os alvos são calculados
            </CardTitle>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleSalvarMultiplicadores} className="space-y-4">
              <p className="text-xs text-muted-foreground">
                Cada alvo é a sua base multiplicada por um fator. Ajuste os fatores se os
                valores de referência não fizerem sentido para o seu caso.
              </p>

              <ul className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                {metasPadrao
                  .filter((meta) => meta.base_calculo !== 'manual')
                  .map((meta) => {
                    const fator = Number(multiplicadorInputs[meta.tipo])
                    const base = meta.base_calculo === 'renda' ? rendaAtual : custoAtual
                    const previa =
                      base != null && Number.isFinite(fator) && fator > 0 ? base * fator : null
                    const inputId = `multiplicador-${meta.tipo}`

                    return (
                      <li key={meta.id} className="flex flex-col gap-1.5">
                        <label htmlFor={inputId} className="text-sm font-medium text-foreground">
                          {meta.nome}
                        </label>
                        <div className="flex items-center gap-2">
                          <span className="shrink-0 text-xs text-muted-foreground">
                            {meta.base_calculo_display} ×
                          </span>
                          <Input
                            id={inputId}
                            type="number"
                            step="0.01"
                            min="0"
                            className="w-28"
                            value={multiplicadorInputs[meta.tipo] ?? ''}
                            onChange={(e) =>
                              setMultiplicadorInputs((prev) => ({
                                ...prev,
                                [meta.tipo]: e.target.value,
                              }))
                            }
                            aria-describedby={`${inputId}-previa`}
                          />
                          <span
                            id={`${inputId}-previa`}
                            className="text-sm font-semibold tabular-nums text-foreground"
                          >
                            = {previa != null ? formatCurrency(previa) : '—'}
                          </span>
                        </div>
                        <span className="text-xs text-muted-foreground">
                          {PERIODICIDADE_POR_TIPO[meta.tipo] ?? 'total a acumular'} · padrão{' '}
                          {formatMultiplicador(multiplicadoresPadrao[meta.tipo])}
                        </span>
                      </li>
                    )
                  })}
              </ul>

              <div className="flex flex-wrap justify-end gap-2 border-t border-border/60 pt-4">
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  onClick={restaurarMultiplicadoresPadrao}
                  disabled={multiplicadoresMutation.isPending}
                >
                  <RotateCcw className="mr-1.5 h-4 w-4" aria-hidden="true" />
                  Restaurar padrões
                </Button>
                <Button type="submit" size="sm" disabled={multiplicadoresMutation.isPending}>
                  {multiplicadoresMutation.isPending ? (
                    <Loader2 className="mr-1.5 h-4 w-4 animate-spin" aria-hidden="true" />
                  ) : (
                    <Save className="mr-1.5 h-4 w-4" aria-hidden="true" />
                  )}
                  Salvar multiplicadores
                </Button>
              </div>
            </form>
          </CardContent>
        </Card>
      )}

      {/* ─── Tabela de todas as metas ───────────────────────────────────────── */}
      <DataTable
        columns={columns}
        data={metas}
        isLoading={isLoadingMetas}
        pageSize={10}
        caption="Metas financeiras cadastradas"
        emptyMessage="Nenhuma meta cadastrada."
      />

      {/* ─── Modais ─────────────────────────────────────────────────────────── */}
      <MetaFormModal
        isOpen={formAberto}
        meta={metaEmEdicao}
        rendaMensal={rendaAtual}
        custoVidaMensal={custoAtual}
        onClose={() => {
          setFormAberto(false)
          setMetaEmEdicao(null)
        }}
        onSaved={() => addToast('Meta salva.', 'success')}
        onError={() => setActionError('Não foi possível salvar a meta. Tente novamente.')}
      />

      <AporteMetaModal
        meta={metaParaAporte}
        onClose={() => setMetaParaAporte(null)}
        onSaved={() => addToast('Aporte registrado.', 'success')}
        onError={() => setActionError('Não foi possível registrar o aporte. Tente novamente.')}
        // O diálogo segue aberto após excluir, então precisa da meta recém-lida
        // para o histórico e o total refletirem a remoção na hora.
        onAporteRemovido={(metaAtualizada) => {
          setMetaParaAporte(metaAtualizada)
          addToast('Aporte excluído.', 'success')
        }}
      />

      <Modal
        isOpen={!!deleteId}
        onClose={() => setDeleteId(null)}
        title="Confirmar Exclusão"
        description={
          metaParaExcluir
            ? `A meta "${metaParaExcluir.nome}" e todo o seu histórico de aportes serão excluídos permanentemente. Deseja continuar?`
            : 'Esta ação excluirá permanentemente a meta e seus aportes. Deseja continuar?'
        }
      >
        <div className="flex justify-end gap-3">
          <Button variant="outline" onClick={() => setDeleteId(null)}>
            Cancelar
          </Button>
          <Button
            onClick={() => deleteMutation.mutate(deleteId)}
            disabled={deleteMutation.isPending}
            className="border-0 bg-rose-600 text-white hover:bg-rose-700"
          >
            {deleteMutation.isPending ? (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" aria-hidden="true" />
            ) : (
              <Trash2 className="mr-2 h-4 w-4" aria-hidden="true" />
            )}
            Confirmar Exclusão
          </Button>
        </div>
      </Modal>
    </div>
  )
}
