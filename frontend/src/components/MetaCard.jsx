/**
 * Cartão de acompanhamento de uma meta financeira.
 *
 * Usado tanto pelas quatro metas padrão quanto pelas metas personalizadas.
 * O estado nunca é comunicado apenas pela cor da barra: o valor, o percentual
 * e o texto de status aparecem escritos (WCAG 1.4.1).
 *
 * @component
 * @param {Object} props
 * @param {Object} props.meta - Meta serializada pela API.
 * @param {Object} props.avaliacao - Resultado de `avaliarMeta` para esta meta.
 * @param {React.ComponentType} props.icone - Ícone lucide exibido no título.
 * @param {string} [props.badgeOrigem] - Rótulo curto da origem automática do progresso.
 * @param {Function} [props.onAportar] - Quando informado, exibe o botão de aporte rápido.
 * @returns {React.JSX.Element}
 */
import { Plus, Wallet } from 'lucide-react'

import { Badge } from './ui/Badge'
import { Button } from './ui/Button'
import { Progress } from './ui/Progress'
import { Card, CardContent, CardHeader, CardTitle } from './ui/Card'

const formatCurrency = (val) =>
  new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(val ?? 0)

export default function MetaCard({ meta, avaliacao, icone: Icone, badgeOrigem, onAportar }) {
  return (
    <Card className="flex flex-col border border-border/40 bg-card text-card-foreground shadow-sm">
      <CardHeader className="pb-2">
        <CardTitle className="flex items-start gap-2 text-sm font-medium uppercase tracking-wider text-muted-foreground">
          <Icone className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
          <span>{meta.nome}</span>
        </CardTitle>
      </CardHeader>

      <CardContent className="flex flex-1 flex-col gap-3">
        <div>
          <p className="text-2xl font-bold text-foreground">{formatCurrency(avaliacao.alvo)}</p>
          <p className="mt-0.5 text-xs text-muted-foreground">{avaliacao.legendaAlvo}</p>
        </div>

        <Progress
          value={avaliacao.percentual}
          label={`${avaliacao.rotuloAtual} de ${meta.nome}`}
          variant={avaliacao.variant}
          valueLabel={`${formatCurrency(avaliacao.atual)} · ${avaliacao.percentual.toFixed(1)}%`}
        />

        <div className="flex flex-wrap items-center gap-2">
          <Badge
            variant={
              avaliacao.statusOk
                ? 'success'
                : meta.natureza === 'teto'
                  ? 'destructive'
                  : 'secondary'
            }
          >
            {avaliacao.statusTexto}
          </Badge>
          {badgeOrigem && (
            <Badge variant="default" className="gap-1">
              <Wallet className="h-3 w-3" aria-hidden="true" />
              {badgeOrigem}
            </Badge>
          )}
        </div>

        {onAportar && (
          // `mt-auto` alinha o botão na base mesmo com nomes de tamanhos
          // diferentes deixando os cartões da grade com alturas distintas.
          <Button
            type="button"
            variant="outline"
            size="sm"
            className="mt-auto w-full"
            onClick={() => onAportar(meta)}
            aria-label={`Guardar um valor em ${meta.nome}`}
          >
            <Plus className="mr-1.5 h-4 w-4" aria-hidden="true" />
            Guardar um valor
          </Button>
        )}
      </CardContent>
    </Card>
  )
}
