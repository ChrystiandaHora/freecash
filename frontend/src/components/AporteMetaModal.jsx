/**
 * Modal de Registro de Aporte em uma Meta.
 *
 * O valor informado é somado ao acumulado da meta e fica registrado no
 * histórico, exibido logo abaixo do formulário para dar contexto ao usuário.
 *
 * @component
 * @param {Object} props
 * @param {Object|null} props.meta - Meta que receberá o aporte; `null` mantém o diálogo fechado.
 * @param {Function} props.onClose - Callback para fechar o diálogo.
 * @param {Function} [props.onSaved] - Disparado após salvar com sucesso.
 * @param {Function} [props.onError] - Disparado quando a gravação falha.
 * @param {Function} [props.onAporteRemovido] - Recebe a meta atualizada após excluir um aporte.
 * @returns {React.JSX.Element}
 */
import { useEffect } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Loader2, PiggyBank, Trash2 } from 'lucide-react'

import { createAporteMeta, deleteAporteMeta } from '../services/metas'
import { Button } from './ui/Button'
import { Input } from './ui/Input'
import { Modal } from './ui/Modal'

const formatCurrency = (val) =>
  new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(val ?? 0)

const formatDate = (dateStr) => {
  if (!dateStr || typeof dateStr !== 'string') return '—'
  const parts = dateStr.split('-')
  if (parts.length < 3) return dateStr
  const [year, month, day] = parts
  return `${day}/${month}/${year}`
}

const hojeISO = () => new Date().toISOString().slice(0, 10)

const schema = z.object({
  valor: z.coerce.number().positive('Valor deve ser positivo'),
  data: z.string().min(1, 'Data obrigatória'),
  observacao: z.string().optional(),
})

export default function AporteMetaModal({ meta, onClose, onSaved, onError, onAporteRemovido }) {
  const queryClient = useQueryClient()
  const isOpen = !!meta

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm({ resolver: zodResolver(schema) })

  useEffect(() => {
    if (!isOpen) return
    reset({ valor: '', data: hojeISO(), observacao: '' })
  }, [isOpen, meta, reset])

  const aporteMutation = useMutation({
    mutationFn: (payload) => createAporteMeta({ metaId: meta.id, ...payload }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['metas'] })
      onSaved?.()
      onClose()
    },
    onError: () => onError?.(),
  })

  // Excluir não fecha o diálogo: quem está corrigindo um lançamento costuma
  // querer conferir o histórico logo em seguida.
  const removerMutation = useMutation({
    mutationFn: (aporteId) => deleteAporteMeta({ metaId: meta.id, aporteId }),
    onSuccess: (metaAtualizada) => {
      queryClient.invalidateQueries({ queryKey: ['metas'] })
      onAporteRemovido?.(metaAtualizada)
    },
  })

  const aportes = meta?.aportes ?? []
  const totalAportado = aportes.reduce((soma, a) => soma + Number(a.valor ?? 0), 0)

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title="Registrar Aporte"
      description={
        meta
          ? `O valor será somado ao acumulado de "${meta.nome}".`
          : 'O valor será somado ao acumulado da meta.'
      }
    >
      <form onSubmit={handleSubmit((v) => aporteMutation.mutate(v))} className="space-y-6">
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <div className="space-y-1.5">
            <label htmlFor="aporte-valor" className="text-sm font-medium text-foreground">
              Valor (R$) <span className="text-red-500">*</span>
            </label>
            <Input
              id="aporte-valor"
              {...register('valor')}
              type="number"
              step="0.01"
              placeholder="0,00"
              aria-invalid={!!errors.valor}
              aria-describedby={errors.valor ? 'aporte-valor-error' : undefined}
            />
            {errors.valor && (
              <p id="aporte-valor-error" role="alert" className="text-xs text-red-500">
                {errors.valor.message}
              </p>
            )}
          </div>

          <div className="space-y-1.5">
            <label htmlFor="aporte-data" className="text-sm font-medium text-foreground">
              Data <span className="text-red-500">*</span>
            </label>
            <Input
              id="aporte-data"
              {...register('data')}
              type="date"
              aria-invalid={!!errors.data}
              aria-describedby={errors.data ? 'aporte-data-error' : undefined}
            />
            {errors.data && (
              <p id="aporte-data-error" role="alert" className="text-xs text-red-500">
                {errors.data.message}
              </p>
            )}
          </div>

          <div className="space-y-1.5 sm:col-span-2">
            <label htmlFor="aporte-observacao" className="text-sm font-medium text-foreground">
              Observação (opcional)
            </label>
            <Input id="aporte-observacao" {...register('observacao')} placeholder="Ex: 13º salário" />
          </div>
        </div>

        {aportes.length > 0 && (
          <div className="space-y-2 rounded-xl border border-border/60 bg-muted/30 p-3">
            <div className="flex items-baseline justify-between gap-2">
              <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                Histórico de aportes
              </h3>
              <span className="text-xs text-muted-foreground">
                {aportes.length} lançamento{aportes.length > 1 ? 's' : ''} ·{' '}
                <strong className="text-foreground">{formatCurrency(totalAportado)}</strong>
              </span>
            </div>
            {/* Lista rolável: uma meta de longo prazo acumula dezenas de aportes
                e o diálogo não pode crescer além da altura da tela. */}
            <ul className="max-h-48 space-y-1 overflow-y-auto pr-1 text-sm">
              {aportes.map((aporte) => (
                <li key={aporte.id} className="flex items-center justify-between gap-2">
                  <span className="font-mono text-xs text-muted-foreground">
                    {formatDate(aporte.data)}
                  </span>
                  <span className="flex-1 truncate text-xs text-muted-foreground">
                    {aporte.observacao || '—'}
                  </span>
                  <span className="font-semibold tabular-nums text-emerald-700 dark:text-emerald-400">
                    {formatCurrency(Number(aporte.valor))}
                  </span>
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    className="h-7 w-7 shrink-0"
                    onClick={() => removerMutation.mutate(aporte.id)}
                    disabled={removerMutation.isPending}
                    title={`Excluir aporte de ${formatCurrency(Number(aporte.valor))} em ${formatDate(aporte.data)}`}
                    aria-label={`Excluir aporte de ${formatCurrency(Number(aporte.valor))} em ${formatDate(aporte.data)}`}
                  >
                    <Trash2 className="h-3.5 w-3.5 text-rose-600 dark:text-rose-400" aria-hidden="true" />
                  </Button>
                </li>
              ))}
            </ul>
          </div>
        )}

        {removerMutation.isError && (
          <p role="alert" className="text-sm text-red-500">
            Erro ao excluir o aporte. Tente novamente.
          </p>
        )}

        {aporteMutation.isError && (
          <p role="alert" className="text-sm text-red-500">
            Erro ao registrar o aporte. Tente novamente.
          </p>
        )}

        <div className="flex justify-end gap-3 border-t border-border/60 pt-4">
          <Button
            type="button"
            variant="outline"
            onClick={onClose}
            disabled={aporteMutation.isPending}
            className="rounded-xl"
          >
            Cancelar
          </Button>
          <Button
            type="submit"
            disabled={aporteMutation.isPending}
            className="rounded-xl border-0 bg-primary text-primary-foreground hover:bg-primary/90"
          >
            {aporteMutation.isPending ? (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" aria-hidden="true" />
            ) : (
              <PiggyBank className="mr-1.5 h-4 w-4" aria-hidden="true" />
            )}
            Registrar Aporte
          </Button>
        </div>
      </form>
    </Modal>
  )
}
