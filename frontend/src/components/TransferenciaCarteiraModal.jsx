/**
 * Modal de Transferência de Custódia entre Carteiras.
 *
 * Portabilidade não é venda: o papel muda de corretora, mas o investidor não
 * realizou lucro nenhum. Por isso a operação tem endpoint próprio, que grava as
 * duas pernas de uma vez e não toca no preço médio — registrar isso como uma
 * venda seguida de compra deformaria a rentabilidade e o histórico de proventos.
 *
 * @param {Object} props
 * @param {boolean} props.isOpen - Controla a exibição do diálogo.
 * @param {Function} props.onClose - Callback para fechar o diálogo.
 * @param {Function} [props.onSaved] - Disparado após transferir com sucesso.
 */
import { useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ArrowRightLeft, Loader2 } from 'lucide-react'

import { fetchAtivos, transferirEntreCarteiras } from '../services/investimentos'
import { useCarteira } from '../context/CarteiraProvider'
import { Button } from './ui/Button'
import { Input } from './ui/Input'
import { Select } from './ui/Select'
import { Modal } from './ui/Modal'

/**
 * Casca que só monta o formulário quando o diálogo abre.
 *
 * Reabrir descarta o rascunho anterior — o comportamento dos demais formulários
 * do projeto — mas aqui isso vem de montar um componente novo, e não de um efeito
 * que zera o estado depois de o React já ter renderizado com o valor velho.
 */
export default function TransferenciaCarteiraModal({ isOpen, onClose, onSaved, ativoInicial = '', origemInicial = '' }) {
  if (!isOpen) return null
  return <FormularioTransferencia onClose={onClose} onSaved={onSaved} ativoInicial={ativoInicial} origemInicial={origemInicial} />
}

function FormularioTransferencia({ onClose, onSaved, ativoInicial = '', origemInicial = '' }) {
  const queryClient = useQueryClient()
  const { carteirasAtivas } = useCarteira()
  const [form, setForm] = useState(() => ({
    ativo: String(ativoInicial || ''),
    origem: String(origemInicial || ''),
    destino: '',
    quantidade: '',
    data: '',
  }))
  const [validacaoLocal, setValidacaoLocal] = useState('')

  const hoje = useMemo(() => new Date().toISOString().split('T')[0], [])

  // Busca ativos da carteira de origem se selecionada
  const { data: ativosNaOrigem = [] } = useQuery({
    queryKey: ['ativos', Number(form.origem) || null],
    queryFn: () => fetchAtivos(form.origem),
    enabled: !!form.origem,
  })

  const opcoesDeAtivo = form.origem ? ativosNaOrigem : []

  const posicaoDisponivel = useMemo(() => {
    const escolhido = ativosNaOrigem.find((a) => String(a.id) === String(form.ativo))
    return escolhido ? Number(escolhido.quantidade) : null
  }, [ativosNaOrigem, form.ativo])

  const transferirMutation = useMutation({
    mutationFn: transferirEntreCarteiras,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['transacoesInvestimento'] })
      queryClient.invalidateQueries({ queryKey: ['ativos'] })
      queryClient.invalidateQueries({ queryKey: ['investimentosDashboard'] })
      queryClient.invalidateQueries({ queryKey: ['carteiras'] })
      onSaved?.()
      onClose()
    },
    onError: (err) => {
      // Falha capturada e tratada com mensagem de fallback
      const data = err?.response?.data
      if (!data) {
        setValidacaoLocal('Erro de comunicação com o servidor ao registrar transferência.')
      }
    }
  })

  const atualizar = (campo) => (e) => {
    setValidacaoLocal('')
    setForm((atual) => ({ ...atual, [campo]: e.target.value }))
  }

  const onSubmit = (e) => {
    e.preventDefault()
    setValidacaoLocal('')

    if (!form.origem) {
      setValidacaoLocal('Selecione a carteira de origem.')
      return
    }
    if (!form.destino) {
      setValidacaoLocal('Selecione a carteira de destino.')
      return
    }
    if (form.origem === form.destino) {
      setValidacaoLocal('A carteira de destino deve ser diferente da origem.')
      return
    }
    if (!form.ativo) {
      setValidacaoLocal('Selecione o ativo a ser transferido.')
      return
    }
    const qtd = Number(form.quantidade)
    if (!qtd || qtd <= 0) {
      setValidacaoLocal('Informe uma quantidade válida maior que zero.')
      return
    }
    if (posicaoDisponivel != null && qtd > posicaoDisponivel) {
      setValidacaoLocal(`A quantidade informada (${qtd}) é maior que o saldo disponível na origem (${posicaoDisponivel}).`)
      return
    }

    transferirMutation.mutate({
      ativo: Number(form.ativo),
      origem: Number(form.origem),
      destino: Number(form.destino),
      quantidade: form.quantidade,
      ...(form.data ? { data: form.data } : {}),
    })
  }

  const errosApi = transferirMutation.error?.response?.data ?? null
  const mensagemDeErro = validacaoLocal || (errosApi
    ? typeof errosApi === 'string'
      ? errosApi
      : typeof errosApi === 'object'
        ? Object.entries(errosApi).map(([k, v]) => `${k !== 'detail' ? `${k}: ` : ''}${Array.isArray(v) ? v.join(' ') : v}`).join(' ')
        : 'Erro ao processar transferência.'
    : null)

  const temErroOrigem = Boolean(errosApi?.origem)
  const temErroDestino = Boolean(errosApi?.destino)
  const temErroAtivo = Boolean(errosApi?.ativo)
  const temErroQuantidade = Boolean(errosApi?.quantidade)

  return (
    <Modal
      isOpen
      onClose={onClose}
      title="Transferir entre carteiras"
      description="Muda a custódia do ativo sem registrar compra nem venda — o preço médio e a rentabilidade ficam como estão."
      size="lg"
    >
      <form onSubmit={onSubmit} className="space-y-6">
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <div className="space-y-1.5">
            <label htmlFor="transf-origem" className="text-sm font-medium text-foreground">
              Carteira de origem <span className="text-red-500" aria-hidden="true">*</span>
            </label>
            <Select
              id="transf-origem"
              value={form.origem}
              aria-invalid={temErroOrigem}
              aria-required="true"
              onChange={(e) => {
                setValidacaoLocal('')
                setForm((atual) => ({ ...atual, origem: e.target.value, ativo: '' }))
              }}
            >
              <option value="">Selecione a carteira de origem…</option>
              {carteirasAtivas.map((c) => (
                <option key={c.id} value={c.id}>{c.nome}</option>
              ))}
            </Select>
          </div>

          <div className="space-y-1.5">
            <label htmlFor="transf-destino" className="text-sm font-medium text-foreground">
              Carteira de destino <span className="text-red-500" aria-hidden="true">*</span>
            </label>
            <Select
              id="transf-destino"
              value={form.destino}
              aria-invalid={temErroDestino}
              aria-required="true"
              onChange={atualizar('destino')}
            >
              <option value="">Selecione a carteira de destino…</option>
              {carteirasAtivas
                .filter((c) => String(c.id) !== String(form.origem))
                .map((c) => (
                  <option key={c.id} value={c.id}>{c.nome}</option>
                ))}
            </Select>
          </div>

          <div className="space-y-1.5">
            <label htmlFor="transf-ativo" className="text-sm font-medium text-foreground">
              Ativo <span className="text-red-500" aria-hidden="true">*</span>
            </label>
            <Select
              id="transf-ativo"
              value={form.ativo}
              onChange={atualizar('ativo')}
              aria-invalid={temErroAtivo}
              aria-required="true"
              aria-describedby="transf-ativo-hint"
            >
              <option value="">
                {form.origem ? 'Selecione o ativo…' : 'Escolha a origem primeiro'}
              </option>
              {opcoesDeAtivo.map((a) => (
                <option key={a.id} value={a.id}>
                  {a.ticker} — {Number(a.quantidade)} cotas disponíveis
                </option>
              ))}
            </Select>
            <p id="transf-ativo-hint" className="text-xs text-muted-foreground">
              A lista mostra apenas o que está custodiado na carteira de origem.
            </p>
          </div>

          <div className="space-y-1.5">
            <div className="flex items-center justify-between">
              <label htmlFor="transf-quantidade" className="text-sm font-medium text-foreground">
                Quantidade <span className="text-red-500" aria-hidden="true">*</span>
              </label>
              {posicaoDisponivel != null && posicaoDisponivel > 0 && (
                <button
                  type="button"
                  onClick={() => setForm((atual) => ({ ...atual, quantidade: String(posicaoDisponivel) }))}
                  className="text-xs text-primary hover:underline font-bold"
                >
                  Usar tudo ({posicaoDisponivel})
                </button>
              )}
            </div>
            <Input
              id="transf-quantidade"
              type="number"
              step="any"
              min="0.00000001"
              max={posicaoDisponivel || undefined}
              value={form.quantidade}
              aria-invalid={temErroQuantidade}
              aria-required="true"
              onChange={atualizar('quantidade')}
              aria-describedby="transf-quantidade-hint"
            />
            <p id="transf-quantidade-hint" className="text-xs text-muted-foreground">
              {posicaoDisponivel != null
                ? `Disponível na origem: ${posicaoDisponivel}`
                : 'Escolha o ativo para ver o disponível.'}
            </p>
          </div>

          <div className="space-y-1.5 sm:col-span-2">
            <label htmlFor="transf-data" className="text-sm font-medium text-foreground">
              Data da transferência (opcional)
            </label>
            <Input
              id="transf-data"
              type="date"
              max={hoje}
              value={form.data}
              onChange={atualizar('data')}
            />
          </div>
        </div>

        {mensagemDeErro && (
          <div role="alert" className="p-3 rounded-xl bg-destructive/10 border border-destructive/20 text-sm font-medium text-destructive animate-fade-in">
            {mensagemDeErro}
          </div>
        )}

        <div className="flex justify-end gap-3 border-t border-border/60 pt-4">
          <Button
            type="button"
            variant="outline"
            onClick={onClose}
            disabled={transferirMutation.isPending}
            className="rounded-xl"
          >
            Cancelar
          </Button>
          <Button
            type="submit"
            disabled={transferirMutation.isPending}
            className="rounded-xl border-0 bg-primary text-primary-foreground hover:bg-primary/90 font-semibold"
          >
            {transferirMutation.isPending ? (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" aria-hidden="true" />
            ) : (
              <ArrowRightLeft className="mr-1.5 h-4 w-4" aria-hidden="true" />
            )}
            Transferir
          </Button>
        </div>
      </form>
    </Modal>
  )
}
