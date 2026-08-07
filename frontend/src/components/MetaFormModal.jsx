/**
 * Modal de Cadastro e Edição de Meta Financeira.
 *
 * Atende tanto metas personalizadas (valor-alvo digitado) quanto metas
 * derivadas de um múltiplo da renda mensal ou do custo de vida. Quando a base
 * é derivada, o valor-alvo passa a ser calculado e exibido apenas para leitura,
 * evitando que o número salvo divirja do múltiplo escolhido.
 *
 * @component
 * @param {Object} props
 * @param {boolean} props.isOpen - Controla a exibição do diálogo.
 * @param {Object|null} [props.meta] - Meta em edição; ausente significa criação.
 * @param {number|null} [props.rendaMensal] - Renda de referência para bases derivadas.
 * @param {number|null} [props.custoVidaMensal] - Custo de vida de referência para bases derivadas.
 * @param {Function} props.onClose - Callback para fechar o diálogo.
 * @param {Function} [props.onSaved] - Disparado após salvar com sucesso.
 * @param {Function} [props.onError] - Disparado quando a gravação falha.
 * @returns {React.JSX.Element}
 */
import { useEffect } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Loader2, Save } from 'lucide-react'

import { createMeta, updateMeta } from '../services/metas'
import { Button } from './ui/Button'
import { Input } from './ui/Input'
import { Select } from './ui/Select'
import { Modal } from './ui/Modal'

const formatCurrency = (val) =>
  new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(val ?? 0)

const schema = z
  .object({
    nome: z.string().min(3, 'Nome obrigatório (mín. 3 caracteres)'),
    natureza: z.enum(['acumulo', 'teto']),
    base_calculo: z.enum(['renda', 'custo_vida', 'manual']),
    origem_acumulado: z.enum(['manual', 'carteira', 'aportes_mes']),
    multiplicador: z.union([z.coerce.number(), z.literal('')]).optional(),
    valor_alvo: z.union([z.coerce.number(), z.literal('')]).optional(),
    valor_acumulado: z.coerce.number().min(0, 'Não pode ser negativo'),
    prazo: z.string().optional(),
    observacao: z.string().optional(),
  })
  .superRefine((values, ctx) => {
    if (values.base_calculo === 'manual') {
      if (!values.valor_alvo || Number(values.valor_alvo) <= 0) {
        ctx.addIssue({
          path: ['valor_alvo'],
          code: z.ZodIssueCode.custom,
          message: 'Informe um valor-alvo maior que zero',
        })
      }
      return
    }
    if (!values.multiplicador || Number(values.multiplicador) <= 0) {
      ctx.addIssue({
        path: ['multiplicador'],
        code: z.ZodIssueCode.custom,
        message: 'Informe um multiplicador maior que zero',
      })
    }
  })

export default function MetaFormModal({
  isOpen,
  meta,
  rendaMensal,
  custoVidaMensal,
  onClose,
  onSaved,
  onError,
}) {
  const queryClient = useQueryClient()
  const isEdicao = !!meta?.id

  const {
    register,
    handleSubmit,
    reset,
    watch,
    formState: { errors },
  } = useForm({
    resolver: zodResolver(schema),
    defaultValues: {
      nome: '',
      natureza: 'acumulo',
      base_calculo: 'manual',
      origem_acumulado: 'manual',
      multiplicador: '',
      valor_alvo: '',
      valor_acumulado: 0,
      prazo: '',
      observacao: '',
    },
  })

  // `isOpen` nas dependências: reabrir o diálogo após um cancelamento deve
  // recarregar os dados do servidor, e não manter o rascunho descartado.
  useEffect(() => {
    if (!isOpen) return
    reset({
      nome: meta?.nome ?? '',
      natureza: meta?.natureza ?? 'acumulo',
      base_calculo: meta?.base_calculo ?? 'manual',
      origem_acumulado: meta?.origem_acumulado ?? 'manual',
      multiplicador: meta?.multiplicador != null ? Number(meta.multiplicador) : '',
      valor_alvo: meta?.valor_alvo != null ? Number(meta.valor_alvo) : '',
      valor_acumulado: meta?.valor_acumulado != null ? Number(meta.valor_acumulado) : 0,
      prazo: meta?.prazo ?? '',
      observacao: meta?.observacao ?? '',
    })
  }, [isOpen, meta, reset])

  const baseCalculo = watch('base_calculo')
  const multiplicador = watch('multiplicador')
  const origemAcumulado = watch('origem_acumulado')
  const isDerivada = baseCalculo !== 'manual'
  const acumuladoDaCarteira = origemAcumulado !== 'manual'

  // Metas padrão dependem dos campos avançados, então abrem com eles à vista.
  // Uma meta nova ("juntar X para um celular") não precisa de nenhum deles.
  const avancadoAberto = isEdicao && meta?.tipo !== 'personalizada'

  const baseValor = baseCalculo === 'renda' ? rendaMensal : custoVidaMensal
  const alvoCalculado =
    isDerivada && baseValor != null && multiplicador !== '' && Number(multiplicador) > 0
      ? Number(baseValor) * Number(multiplicador)
      : null

  const saveMutation = useMutation({
    mutationFn: (payload) => (isEdicao ? updateMeta({ id: meta.id, ...payload }) : createMeta(payload)),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['metas'] })
      onSaved?.()
      onClose()
    },
    onError: () => onError?.(),
  })

  const onSubmit = (values) => {
    // Em bases derivadas o alvo vem do múltiplo; o backend rejeita alvo <= 0,
    // então enviamos o calculado (ou mantemos o atual quando falta a base).
    const valorAlvo = isDerivada
      ? (alvoCalculado ?? Number(meta?.valor_alvo ?? 0))
      : Number(values.valor_alvo)

    saveMutation.mutate({
      nome: values.nome,
      natureza: values.natureza,
      base_calculo: values.base_calculo,
      origem_acumulado: values.origem_acumulado,
      multiplicador: isDerivada ? Number(values.multiplicador) : null,
      valor_alvo: valorAlvo,
      valor_acumulado: Number(values.valor_acumulado),
      prazo: values.prazo || null,
      observacao: values.observacao ?? '',
    })
  }

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title={isEdicao ? 'Editar Meta' : 'Nova Meta'}
      description={
        isEdicao
          ? 'Altere os dados da meta e salve.'
          : 'Dê um nome e diga quanto quer juntar. Depois é só ir registrando aportes.'
      }
      size="lg"
    >
      <form onSubmit={handleSubmit(onSubmit)} className="space-y-6">
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <div className="space-y-1.5 sm:col-span-2">
            <label htmlFor="meta-nome" className="text-sm font-medium text-foreground">
              Nome da meta <span className="text-red-500">*</span>
            </label>
            <Input
              id="meta-nome"
              {...register('nome')}
              placeholder="Ex: Compra de celular"
              aria-invalid={!!errors.nome}
              aria-describedby={errors.nome ? 'meta-nome-error' : undefined}
            />
            {errors.nome && (
              <p id="meta-nome-error" role="alert" className="text-xs text-red-500">
                {errors.nome.message}
              </p>
            )}
          </div>

          {isDerivada ? (
            <div className="space-y-1.5">
              <label htmlFor="meta-alvo-calculado" className="text-sm font-medium text-foreground">
                Valor-alvo (calculado)
              </label>
              <Input
                id="meta-alvo-calculado"
                value={alvoCalculado != null ? formatCurrency(alvoCalculado) : '—'}
                readOnly
                className="bg-muted cursor-not-allowed"
                aria-describedby="meta-alvo-calculado-hint"
              />
              <p id="meta-alvo-calculado-hint" className="text-xs text-muted-foreground">
                Vem da base multiplicada pelo fator, nas opções avançadas.
              </p>
            </div>
          ) : (
            <div className="space-y-1.5">
              <label htmlFor="meta-valor-alvo" className="text-sm font-medium text-foreground">
                Quanto quero juntar (R$) <span className="text-red-500">*</span>
              </label>
              <Input
                id="meta-valor-alvo"
                {...register('valor_alvo')}
                type="number"
                step="0.01"
                placeholder="Ex: 5000,00"
                aria-invalid={!!errors.valor_alvo}
                aria-describedby={errors.valor_alvo ? 'meta-valor-alvo-error' : undefined}
              />
              {errors.valor_alvo && (
                <p id="meta-valor-alvo-error" role="alert" className="text-xs text-red-500">
                  {errors.valor_alvo.message}
                </p>
              )}
            </div>
          )}

          <div className="space-y-1.5">
            <label htmlFor="meta-acumulado" className="text-sm font-medium text-foreground">
              Quanto já tenho guardado (R$)
            </label>
            <Input
              id="meta-acumulado"
              {...register('valor_acumulado')}
              type="number"
              step="0.01"
              placeholder="0,00"
              readOnly={acumuladoDaCarteira}
              className={acumuladoDaCarteira ? 'bg-muted cursor-not-allowed' : ''}
              aria-invalid={!!errors.valor_acumulado}
              aria-describedby={
                errors.valor_acumulado ? 'meta-acumulado-error' : 'meta-acumulado-hint'
              }
            />
            {errors.valor_acumulado ? (
              <p id="meta-acumulado-error" role="alert" className="text-xs text-red-500">
                {errors.valor_acumulado.message}
              </p>
            ) : (
              <p id="meta-acumulado-hint" className="text-xs text-muted-foreground">
                {acumuladoDaCarteira
                  ? 'Ignorado enquanto a origem for automática; fica guardado caso você volte para manual.'
                  : 'Pode começar em zero: cada aporte registrado soma aqui.'}
              </p>
            )}
          </div>

          <div className="space-y-1.5">
            <label htmlFor="meta-prazo" className="text-sm font-medium text-foreground">
              Prazo (opcional)
            </label>
            <Input id="meta-prazo" {...register('prazo')} type="date" />
          </div>

          <div className="space-y-1.5 sm:col-span-2">
            <label htmlFor="meta-observacao" className="text-sm font-medium text-foreground">
              Observação (opcional)
            </label>
            <textarea
              id="meta-observacao"
              {...register('observacao')}
              rows={2}
              className="flex w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
              placeholder="Ex: modelo, cor e loja pretendidos"
            />
          </div>
        </div>

        {/* `<details>` nativo: operável por teclado e anunciado como expansível
            pelo leitor de tela, sem estado nem ARIA manual. Uma meta simples
            ("juntar X reais") não precisa de nada daqui. */}
        <details open={avancadoAberto} className="rounded-xl border border-border/60 bg-muted/20">
          <summary className="cursor-pointer rounded-xl px-3 py-2 text-sm font-medium text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring">
            Opções avançadas
            <span className="ml-1 font-normal text-muted-foreground">
              — derivar o alvo da renda e acompanhar a carteira
            </span>
          </summary>

          <div className="grid grid-cols-1 gap-4 border-t border-border/60 p-3 sm:grid-cols-2">
            <div className="space-y-1.5">
              <label htmlFor="meta-natureza" className="text-sm font-medium text-foreground">
                Natureza <span className="text-red-500">*</span>
              </label>
              <Select id="meta-natureza" {...register('natureza')}>
                <option value="acumulo">Acúmulo — quanto mais, melhor</option>
                <option value="teto">Teto mensal — não deve ser ultrapassado</option>
              </Select>
              <p className="text-xs text-muted-foreground">
                Metas de teto sinalizam alerta ao passar do limite, em vez de comemorar.
              </p>
            </div>

            <div className="space-y-1.5">
              <label htmlFor="meta-base" className="text-sm font-medium text-foreground">
                Base de cálculo <span className="text-red-500">*</span>
              </label>
              <Select id="meta-base" {...register('base_calculo')}>
                <option value="manual">Valor manual</option>
                <option value="renda">Múltiplo da renda mensal</option>
                <option value="custo_vida">Múltiplo do custo de vida</option>
              </Select>
            </div>

            {isDerivada && (
              <div className="space-y-1.5">
                <label htmlFor="meta-multiplicador" className="text-sm font-medium text-foreground">
                  Multiplicador <span className="text-red-500">*</span>
                </label>
                <Input
                  id="meta-multiplicador"
                  {...register('multiplicador')}
                  type="number"
                  step="0.01"
                  placeholder="Ex: 6"
                  aria-invalid={!!errors.multiplicador}
                  aria-describedby={
                    errors.multiplicador ? 'meta-multiplicador-error' : 'meta-multiplicador-hint'
                  }
                />
                {errors.multiplicador ? (
                  <p id="meta-multiplicador-error" role="alert" className="text-xs text-red-500">
                    {errors.multiplicador.message}
                  </p>
                ) : (
                  <p id="meta-multiplicador-hint" className="text-xs text-muted-foreground">
                    Base atual: {baseValor != null ? formatCurrency(baseValor) : 'não informada'}
                  </p>
                )}
              </div>
            )}

            <div className="space-y-1.5">
              <label htmlFor="meta-origem" className="text-sm font-medium text-foreground">
                Origem do progresso <span className="text-red-500">*</span>
              </label>
              <Select id="meta-origem" {...register('origem_acumulado')}>
                <option value="manual">Informado manualmente</option>
                <option value="carteira">Valor de mercado da carteira</option>
                <option value="aportes_mes">Aportes do mês na carteira</option>
              </Select>
              <p className="text-xs text-muted-foreground">
                As duas últimas acompanham seus investimentos sozinhas: o patrimônio total ou
                apenas o que você comprou neste mês.
              </p>
            </div>
          </div>
        </details>

        {saveMutation.isError && (
          <p role="alert" className="text-sm text-red-500">
            Erro ao salvar a meta. Verifique se já não existe outra meta com esse nome e tente novamente.
          </p>
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
            className="rounded-xl border-0 bg-primary text-primary-foreground hover:bg-primary/90"
          >
            {saveMutation.isPending ? (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" aria-hidden="true" />
            ) : (
              <Save className="mr-1.5 h-4 w-4" aria-hidden="true" />
            )}
            {isEdicao ? 'Salvar Alterações' : 'Criar Meta'}
          </Button>
        </div>
      </form>
    </Modal>
  )
}
