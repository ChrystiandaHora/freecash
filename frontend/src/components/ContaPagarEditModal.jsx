/**
 * Modal de Edição Rápida de Conta a Pagar.
 *
 * Reproduz os campos e as regras de validação de `ContaPagarForm` em um diálogo,
 * permitindo editar um card sem sair da tela em que ele está (ex.: o Pipeline
 * Kanban). Faturas de cartão têm os campos em leitura apenas, pois seus valores
 * são calculados a partir das compras vinculadas.
 *
 * Além de salvar alterações, o diálogo oferece a ação **"Marcar como paga"**
 * (`PUT /api/financeiro/contas-pagar/{id}/pagar/`) para quitar a conta sem
 * precisar arrastar o card até a coluna "Pagas".
 *
 * @component
 * @param {Object} props
 * @param {Object|null} props.conta - Conta em edição; `null` mantém o diálogo fechado.
 * @param {Function} props.onClose - Callback para fechar o diálogo.
 * @param {Function} [props.onSaved] - Disparado após salvar com sucesso (ex.: toast).
 * @param {Function} [props.onError] - Disparado quando a gravação falha.
 * @param {Function} [props.onPaid] - Disparado após registrar o pagamento com sucesso.
 * @param {Function} [props.onPayError] - Disparado quando o registro do pagamento falha.
 * @returns {React.JSX.Element}
 */
import { useEffect } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Loader2, Save, CreditCard, CheckCircle2 } from 'lucide-react'

import { updateContaPagar, pagarConta } from '../services/financeiro'
import { Button } from './ui/Button'
import { Input } from './ui/Input'
import { Modal } from './ui/Modal'

const schema = z.object({
  descricao: z.string().min(3, 'Descrição obrigatória (mín. 3 caracteres)'),
  categoria: z.string().min(1, 'Informe a categoria'),
  valor: z.coerce.number().positive('Valor deve ser positivo'),
  data_vencimento: z.string().min(1, 'Data de vencimento obrigatória'),
})

export default function ContaPagarEditModal({ conta, onClose, onSaved, onError, onPaid, onPayError }) {
  const queryClient = useQueryClient()
  const isOpen = !!conta
  const isFaturaCartao = !!conta?.eh_fatura_cartao
  const isPaga = !!conta?.pago

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm({ resolver: zodResolver(schema) })

  // `isOpen` entra nas dependências para que reabrir o mesmo card após um
  // cancelamento volte a exibir os valores do servidor, e não o rascunho antigo.
  useEffect(() => {
    if (!isOpen) return
    reset({
      descricao: conta.descricao ?? '',
      categoria: conta.categoria ?? '',
      valor: Number(conta.valor ?? 0),
      data_vencimento: conta.data_vencimento ?? '',
    })
  }, [isOpen, conta, reset])

  // Duas chaves em uso no app: o Kanban/Contas a Pagar usam 'contasPagar'
  // e os formulários dedicados usam 'contas-pagar'.
  const invalidateContas = () => {
    queryClient.invalidateQueries({ queryKey: ['contasPagar'] })
    queryClient.invalidateQueries({ queryKey: ['contas-pagar'] })
    queryClient.invalidateQueries({ queryKey: ['conta-pagar', String(conta.id)] })
  }

  const updateMutation = useMutation({
    mutationFn: updateContaPagar,
    onSuccess: () => {
      invalidateContas()
      onSaved?.()
      onClose()
    },
    onError: () => onError?.(),
  })

  const pagarMutation = useMutation({
    mutationFn: pagarConta,
    onSuccess: () => {
      invalidateContas()
      onPaid?.()
      onClose()
    },
    onError: () => onPayError?.(),
  })

  const isBusy = updateMutation.isPending || pagarMutation.isPending

  const onSubmit = (values) => {
    updateMutation.mutate({ id: conta.id, ...values })
  }

  const readOnlyClass = isFaturaCartao ? 'bg-muted cursor-not-allowed' : ''

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title="Editar Conta"
      description="Altere os dados da obrigação financeira e salve."
      size="lg"
    >
      <form onSubmit={handleSubmit(onSubmit)} className="space-y-6">
        {isFaturaCartao && (
          <p className="flex items-start gap-2 rounded-xl border border-blue-200 bg-blue-50 p-3 text-sm text-blue-800 dark:border-blue-800 dark:bg-blue-950/20 dark:text-blue-300">
            <CreditCard className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
            Esta é uma fatura de cartão: os campos são calculados a partir das compras
            vinculadas e não podem ser editados aqui.
          </p>
        )}

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <div className="space-y-1.5 sm:col-span-2">
            <label htmlFor="edit-conta-descricao" className="text-sm font-medium text-foreground">
              Descrição <span className="text-red-500">*</span>
            </label>
            <Input
              id="edit-conta-descricao"
              {...register('descricao')}
              placeholder="Ex: Aluguel Março"
              readOnly={isFaturaCartao}
              className={readOnlyClass}
              aria-invalid={!!errors.descricao}
              aria-describedby={errors.descricao ? 'edit-conta-descricao-error' : undefined}
            />
            {errors.descricao && (
              <p id="edit-conta-descricao-error" role="alert" className="text-xs text-red-500">
                {errors.descricao.message}
              </p>
            )}
          </div>

          <div className="space-y-1.5">
            <label htmlFor="edit-conta-categoria" className="text-sm font-medium text-foreground">
              Categoria <span className="text-red-500">*</span>
            </label>
            <Input
              id="edit-conta-categoria"
              {...register('categoria')}
              placeholder="Ex: Moradia"
              readOnly={isFaturaCartao}
              className={readOnlyClass}
              aria-invalid={!!errors.categoria}
              aria-describedby={errors.categoria ? 'edit-conta-categoria-error' : undefined}
            />
            {errors.categoria && (
              <p id="edit-conta-categoria-error" role="alert" className="text-xs text-red-500">
                {errors.categoria.message}
              </p>
            )}
          </div>

          <div className="space-y-1.5">
            <label htmlFor="edit-conta-valor" className="text-sm font-medium text-foreground">
              Valor (R$) <span className="text-red-500">*</span>
            </label>
            <Input
              id="edit-conta-valor"
              {...register('valor')}
              type="number"
              step="0.01"
              placeholder="0,00"
              readOnly={isFaturaCartao}
              className={readOnlyClass}
              aria-invalid={!!errors.valor}
              aria-describedby={errors.valor ? 'edit-conta-valor-error' : undefined}
            />
            {errors.valor && (
              <p id="edit-conta-valor-error" role="alert" className="text-xs text-red-500">
                {errors.valor.message}
              </p>
            )}
          </div>

          <div className="space-y-1.5 sm:col-span-2">
            <label htmlFor="edit-conta-vencimento" className="text-sm font-medium text-foreground">
              Data de Vencimento <span className="text-red-500">*</span>
            </label>
            <Input
              id="edit-conta-vencimento"
              {...register('data_vencimento')}
              type="date"
              readOnly={isFaturaCartao}
              className={readOnlyClass}
              aria-invalid={!!errors.data_vencimento}
              aria-describedby={errors.data_vencimento ? 'edit-conta-vencimento-error' : undefined}
            />
            {errors.data_vencimento && (
              <p id="edit-conta-vencimento-error" role="alert" className="text-xs text-red-500">
                {errors.data_vencimento.message}
              </p>
            )}
          </div>
        </div>

        {updateMutation.isError && (
          <p role="alert" className="text-sm text-red-500">
            Erro ao salvar a conta. Tente novamente.
          </p>
        )}

        {pagarMutation.isError && (
          <p role="alert" className="text-sm text-red-500">
            Erro ao registrar o pagamento. Tente novamente.
          </p>
        )}

        <div className="flex flex-col gap-3 border-t border-border/60 pt-4 sm:flex-row sm:items-center sm:justify-between">
          {/* Pagar fica separado das ações do formulário: é uma ação de estado
              (quitação) e não grava as alterações digitadas nos campos. */}
          {isPaga ? (
            <p className="flex items-center gap-1.5 text-sm font-medium text-emerald-600 dark:text-emerald-400">
              <CheckCircle2 className="h-4 w-4" aria-hidden="true" />
              Conta já paga
            </p>
          ) : (
            <Button
              type="button"
              onClick={() => pagarMutation.mutate(conta.id)}
              disabled={isBusy}
              className="rounded-xl border-0 bg-emerald-600 text-white hover:bg-emerald-700 dark:bg-emerald-600 dark:hover:bg-emerald-500"
            >
              {pagarMutation.isPending ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" aria-hidden="true" />
              ) : (
                <CheckCircle2 className="mr-1.5 h-4 w-4" aria-hidden="true" />
              )}
              Marcar como paga
            </Button>
          )}

          <div className="flex justify-end gap-3">
            <Button
              type="button"
              variant="outline"
              onClick={onClose}
              disabled={isBusy}
              className="rounded-xl"
            >
              Cancelar
            </Button>
            <Button
              type="submit"
              disabled={isBusy || isFaturaCartao}
              className="rounded-xl border-0 bg-primary text-primary-foreground hover:bg-primary/90"
            >
              {updateMutation.isPending ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" aria-hidden="true" />
              ) : (
                <Save className="mr-1.5 h-4 w-4" aria-hidden="true" />
              )}
              Salvar Alterações
            </Button>
          </div>
        </div>
      </form>
    </Modal>
  )
}
