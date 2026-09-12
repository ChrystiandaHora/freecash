/**
 * Modal de Cadastro e Edição de Carteira de Investimento.
 *
 * Uma carteira é a custódia numa corretora ou banco — onde os ativos estão
 * guardados, e não o que eles são. O campo de instituição é texto livre com uma
 * `<datalist>` de sugestões: uma enum fechada envelheceria mal (o repo já tem uma
 * lista de bancos para importar extrato, e ela não cobre corretora nenhuma).
 *
 * @param {Object} props
 * @param {boolean} props.isOpen - Controla a exibição do diálogo.
 * @param {Object|null} [props.carteira] - Carteira em edição; ausente significa criação.
 * @param {Function} props.onClose - Callback para fechar o diálogo.
 * @param {Function} [props.onSaved] - Disparado após salvar com sucesso.
 */
import { useEffect } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Loader2, Plus, Save } from 'lucide-react'

import { createCarteira, updateCarteira } from '../services/investimentos'
import { Button } from './ui/Button'
import { Input } from './ui/Input'
import { Modal } from './ui/Modal'

const INSTITUICOES_SUGERIDAS = [
  'XP', 'BTG Pactual', 'Rico', 'Clear', 'NuInvest', 'Inter', 'Itaú',
  'Bradesco', 'Banco do Brasil', 'Caixa', 'Santander', 'Avenue', 'Binance',
]

const PRESET_COLORS = [
  { label: 'Azul Padrão', value: '#2563eb' },
  { label: 'XP Verde', value: '#00b14f' },
  { label: 'BTG Azul Escuro', value: '#0a1e45' },
  { label: 'Inter Laranja', value: '#ff7a00' },
  { label: 'Nubank Roxo', value: '#820ad1' },
  { label: 'Itaú Laranja', value: '#ec7000' },
  { label: 'Bradesco Vermelho', value: '#cc092f' },
  { label: 'Mercado Pago Azul', value: '#009ee3' },
  { label: 'Sky Azul Claro', value: '#38bdf8' },
]

const schema = z.object({
  nome: z.string().min(2, 'Nome obrigatório (mín. 2 caracteres)'),
  instituicao: z.string().optional(),
  cor: z.string().optional(),
  considerar_no_saldo: z.boolean(),
})

export default function CarteiraFormModal({ isOpen, carteira, onClose, onSaved }) {
  const queryClient = useQueryClient()
  const isEdicao = !!carteira?.id

  const {
    register,
    handleSubmit,
    reset,
    setValue,
    watch,
    setError,
    formState: { errors },
  } = useForm({
    resolver: zodResolver(schema),
    defaultValues: {
      nome: '',
      instituicao: '',
      cor: '#2563eb',
      considerar_no_saldo: true,
    },
  })

  const corAtual = watch('cor') || '#2563eb'

  // `isOpen` nas dependências: reabrir após cancelar recarrega os dados salvos,
  // em vez de trazer de volta o rascunho descartado.
  useEffect(() => {
    if (!isOpen) return
    reset({
      nome: carteira?.nome ?? '',
      instituicao: carteira?.instituicao ?? '',
      cor: carteira?.cor || '#2563eb',
      considerar_no_saldo: carteira?.considerar_no_saldo ?? true,
    })
  }, [isOpen, carteira, reset])

  const saveMutation = useMutation({
    mutationFn: (payload) =>
      isEdicao ? updateCarteira({ id: carteira.id, ...payload }) : createCarteira(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['carteiras'] })
      onSaved?.()
      onClose()
    },
    onError: (err) => {
      const resp = err?.response?.data
      if (resp?.nome) {
        const msg = Array.isArray(resp.nome) ? resp.nome.join(' ') : resp.nome
        setError('nome', { message: msg })
      }
    }
  })

  const onSubmit = (values) => saveMutation.mutate(values)

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title={isEdicao ? 'Editar Carteira' : 'Nova Carteira'}
      description={
        isEdicao
          ? 'Altere os dados da carteira e salve.'
          : 'Uma carteira por corretora ou banco onde você tem investimentos.'
      }
      size="lg"
    >
      <form onSubmit={handleSubmit(onSubmit)} className="space-y-6">
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <div className="space-y-1.5">
            <label htmlFor="carteira-nome" className="text-sm font-medium text-foreground">
              Nome da carteira <span className="text-red-500" aria-hidden="true">*</span>
            </label>
            <Input
              id="carteira-nome"
              {...register('nome')}
              placeholder="Ex: Corretora principal"
              aria-required="true"
              aria-invalid={!!errors.nome}
              aria-describedby={errors.nome ? 'carteira-nome-error' : undefined}
            />
            {errors.nome && (
              <p id="carteira-nome-error" role="alert" className="text-xs text-red-500 font-semibold">
                {errors.nome.message}
              </p>
            )}
          </div>

          <div className="space-y-1.5">
            <label htmlFor="carteira-instituicao" className="text-sm font-medium text-foreground">
              Instituição
            </label>
            <Input
              id="carteira-instituicao"
              {...register('instituicao')}
              list="carteira-instituicoes"
              placeholder="Ex: XP, BTG, Inter"
              aria-describedby="carteira-instituicao-hint"
            />
            <datalist id="carteira-instituicoes">
              {INSTITUICOES_SUGERIDAS.map((nome) => (
                <option key={nome} value={nome} />
              ))}
            </datalist>
            <p id="carteira-instituicao-hint" className="text-xs text-muted-foreground">
              Sugestões são atalhos — pode escrever qualquer nome.
            </p>
          </div>

          <div className="space-y-2 sm:col-span-2">
            <span id="carteira-cor-label" className="text-sm font-medium text-foreground">
              Cor de identificação
            </span>
            <div role="radiogroup" aria-labelledby="carteira-cor-label" className="flex flex-wrap items-center gap-2">
              {PRESET_COLORS.map(({ value, label }) => (
                <button
                  key={value}
                  type="button"
                  role="radio"
                  aria-checked={corAtual.toLowerCase() === value.toLowerCase()}
                  onClick={() => setValue('cor', value, { shouldDirty: true })}
                  title={label}
                  aria-label={label}
                  className={`w-8 h-8 rounded-full border-2 transition-all hover:scale-110 ${
                    corAtual.toLowerCase() === value.toLowerCase()
                      ? 'border-primary ring-2 ring-primary/30 scale-110 shadow-md'
                      : 'border-transparent'
                  }`}
                  style={{ backgroundColor: value }}
                />
              ))}
              {/* Custom Color Picker */}
              <label
                title="Escolher cor personalizada"
                className="relative w-8 h-8 rounded-full border-2 border-dashed border-border/80 cursor-pointer flex items-center justify-center hover:border-primary transition-colors bg-background"
              >
                <input
                  type="color"
                  aria-label="Escolher cor personalizada"
                  value={corAtual}
                  onChange={(e) => setValue('cor', e.target.value, { shouldDirty: true })}
                  className="absolute inset-0 w-full h-full opacity-0 cursor-pointer rounded-full"
                />
                <Plus className="h-3.5 w-3.5 text-muted-foreground" aria-hidden="true" />
              </label>
            </div>
            <p className="text-xs text-muted-foreground">
              Identifica a carteira ao lado do nome nesta tela. Os gráficos usam uma paleta própria, validada para daltonismo e contraste — o que uma cor livre não teria como ser.
            </p>
          </div>

          <div className="space-y-1.5 sm:col-span-2">
            <span className="text-sm font-medium text-foreground">Horizonte de Saldos</span>
            <label
              htmlFor="carteira-considerar-saldo"
              className="flex items-start gap-2 rounded-xl border border-border/60 bg-muted/20 p-3 text-sm text-foreground cursor-pointer hover:bg-muted/30 transition-colors"
            >
              <input
                id="carteira-considerar-saldo"
                type="checkbox"
                {...register('considerar_no_saldo')}
                className="mt-0.5 h-4 w-4 rounded border-input text-primary focus:ring-primary/20 accent-primary"
                aria-describedby="carteira-considerar-saldo-hint"
              />
              <span>
                Contar como dinheiro disponível
                <span id="carteira-considerar-saldo-hint" className="block text-xs text-muted-foreground mt-0.5">
                  Ligue para reserva de emergência e renda fixa de liquidez diária. Desligue
                  para posições de longo prazo que você não pretende resgatar.
                </span>
              </span>
            </label>
          </div>
        </div>

        {saveMutation.isError && !errors.nome && (
          <div role="alert" className="p-3 rounded-xl bg-destructive/10 border border-destructive/20 text-sm font-medium text-destructive">
            Erro ao salvar a carteira. Verifique se já não existe outra com esse nome.
          </div>
        )}

        <div className="flex justify-end gap-3 border-t border-border/60 pt-4">
          <Button
            type="button"
            variant="outline"
            onClick={onClose}
            disabled={saveMutation.isPending}
            className="rounded-xl"
          >
            Cancelar
          </Button>
          <Button
            type="submit"
            disabled={saveMutation.isPending}
            className="rounded-xl border-0 bg-primary text-primary-foreground hover:bg-primary/90 font-semibold"
          >
            {saveMutation.isPending ? (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" aria-hidden="true" />
            ) : (
              <Save className="mr-1.5 h-4 w-4" aria-hidden="true" />
            )}
            {isEdicao ? 'Salvar Alterações' : 'Criar Carteira'}
          </Button>
        </div>
      </form>
    </Modal>
  )
}
