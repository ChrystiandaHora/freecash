import { AlertCircle, Calendar, Layers, Trash2 } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/Card';
import { Button } from '../../components/ui/Button';
import { Badge } from '../../components/ui/Badge';
import { formatCurrency } from './formatters';

export default function SimulacoesAtivasList({ simuladas, onRemove, onLimparTudo }) {
  return (
    <Card className="border-border bg-card/65 backdrop-blur-md">
      <CardHeader className="flex flex-row items-center justify-between pb-2">
        <CardTitle className="text-lg font-semibold flex items-center gap-2">
          <Layers className="h-5 w-5 text-amber-500" /> Simulações Ativas
        </CardTitle>
        {simuladas.length > 0 && (
          <Button
            variant="link"
            size="sm"
            onClick={onLimparTudo}
            className="text-muted-foreground hover:text-destructive text-xs"
          >
            Limpar Tudo
          </Button>
        )}
      </CardHeader>
      <CardContent className="max-h-[350px] overflow-y-auto pr-1 space-y-3">
        {simuladas.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-6 text-center text-muted-foreground">
            <AlertCircle className="h-8 w-8 mb-2 text-muted-foreground/50" />
            <p className="text-xs">Nenhum lançamento simulado ativo.</p>
            <p className="text-xs mt-1">Use o formulário acima para planejar cenários.</p>
          </div>
        ) : (
          simuladas.map((item) => (
            <div
              key={item.id}
              className="flex items-center justify-between p-3 rounded-lg border border-border bg-muted/30 hover:bg-muted/60 transition-all duration-200"
            >
              <div className="space-y-1">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-semibold text-foreground">{item.descricao}</span>
                  <Badge
                    variant="secondary"
                    className={item.tipo === 'R' ? 'bg-emerald-500/10 text-emerald-500' : 'bg-red-500/10 text-red-500'}
                  >
                    {item.tipo === 'R' ? 'Entrada' : 'Saída'}
                  </Badge>
                </div>
                <div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-muted-foreground">
                  <span className="font-semibold text-foreground/80">
                    {formatCurrency(item.valor)}
                    {item.frequencia === 'parcelada' && ` (${item.parcelas}x de ${formatCurrency(item.valor / item.parcelas)})`}
                  </span>
                  <span>•</span>
                  <span>{item.categoria}</span>
                  <span>•</span>
                  <span className="flex items-center gap-1 font-medium text-amber-500/95">
                    <Calendar className="h-3 w-3" />
                    {item.frequencia === 'unica' && `Único (${item.mesInicio}, dia ${item.dia ?? 1})`}
                    {item.frequencia === 'recorrente' && `Recorrente (desde ${item.mesInicio}, dia ${item.dia ?? 1})`}
                    {item.frequencia === 'parcelada' && `Parcelado (${item.parcelas}x desde ${item.mesInicio}, dia ${item.dia ?? 1})`}
                  </span>
                </div>
              </div>
              <Button
                variant="ghost"
                size="icon"
                onClick={() => onRemove(item.id)}
                className="text-muted-foreground hover:text-destructive active:scale-95"
              >
                <Trash2 className="h-4 w-4" />
              </Button>
            </div>
          ))
        )}
      </CardContent>
    </Card>
  );
}
