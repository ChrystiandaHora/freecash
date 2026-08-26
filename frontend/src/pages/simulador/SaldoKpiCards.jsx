import { Activity, Sparkles } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/Card';
import { formatCurrency } from './formatters';

export default function SaldoKpiCards({ isLoading, kpis }) {
  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
      <Card className="relative overflow-hidden border-border bg-card/65 backdrop-blur-md transition-all hover:scale-[1.01]">
        <div className="absolute right-3 top-3 rounded-full bg-blue-500/10 p-2 text-blue-500">
          <Activity className="h-5 w-5" />
        </div>
        <CardHeader className="pb-2">
          <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">Saldo Mês Atual (Real)</span>
          <CardTitle className="text-2xl font-bold text-foreground">
            {isLoading ? '...' : formatCurrency(kpis.currentReal)}
          </CardTitle>
        </CardHeader>
        <CardContent className="pt-0">
          <span className="text-xs text-muted-foreground">Lançamento líquido real deste mês</span>
        </CardContent>
      </Card>

      <Card className="relative overflow-hidden border-primary/30 bg-primary/5 backdrop-blur-md transition-all hover:scale-[1.01]">
        <div className="absolute right-3 top-3 rounded-full bg-primary/10 p-2 text-primary">
          <Sparkles className="h-5 w-5" />
        </div>
        <CardHeader className="pb-2">
          <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">Saldo Mês Atual (Simulado)</span>
          <CardTitle className="text-2xl font-bold text-foreground">
            {isLoading ? '...' : formatCurrency(kpis.currentSim)}
          </CardTitle>
        </CardHeader>
        <CardContent className="pt-0">
          <span className="text-xs text-muted-foreground">Fluxo estimado deste mês</span>
        </CardContent>
      </Card>
    </div>
  );
}
