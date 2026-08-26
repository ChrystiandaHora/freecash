import { Calendar } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/Card';
import { Button } from '../../components/ui/Button';
import { formatCurrency } from './formatters';

export default function ProjecaoMensalTable({ isLoading, monthlyData, onVerDetalhes }) {
  return (
    <Card className="border-border bg-card/65 backdrop-blur-md">
      <CardHeader>
        <CardTitle className="text-lg font-semibold flex items-center gap-2">
          <Calendar className="h-5 w-5 text-primary" /> Fluxo de Projeção Mensal
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="overflow-x-auto">
          <table className="w-full border-collapse text-left text-sm">
            <thead>
              <tr className="border-b border-border/80 text-muted-foreground text-xs font-semibold uppercase tracking-wider">
                <th className="py-3 px-4">Mês</th>
                <th className="py-3 px-3 text-right">Receitas (R+S)</th>
                <th className="py-3 px-3 text-right">Despesas (R+S)</th>
                <th className="py-3 px-3 text-right">Saldo do Mês</th>
                <th className="py-3 px-3 text-right">Saldo Acumulado</th>
                <th className="py-3 px-4 text-center">Simulações</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border/40">
              {isLoading ? (
                <tr>
                  <td colSpan="6" className="py-10 text-center text-muted-foreground text-xs">
                    Buscando contas a pagar e receitas...
                  </td>
                </tr>
              ) : (
                monthlyData.map((data) => {
                  const hasSimulations = data.activeSimulatedItems.length > 0;
                  return (
                    <tr
                      key={data.key}
                      className="hover:bg-muted/20 transition-colors duration-150"
                    >
                      <td className="py-3.5 px-4 font-semibold text-foreground">
                        {data.label}
                      </td>
                      <td className="py-3.5 px-3 text-right text-xs">
                        <span className="text-muted-foreground font-medium block">
                          R: {formatCurrency(data.realRevenues)}
                        </span>
                        {data.simRevenues > 0 && (
                          <span className="text-emerald-500 font-bold block text-xs">
                            S: +{formatCurrency(data.simRevenues)}
                          </span>
                        )}
                      </td>
                      <td className="py-3.5 px-3 text-right text-xs">
                        <span className="text-muted-foreground font-medium block">
                          R: {formatCurrency(data.realExpenses)}
                        </span>
                        {data.simExpenses > 0 && (
                          <span className="text-red-500 font-bold block text-xs">
                            S: +{formatCurrency(data.simExpenses)}
                          </span>
                        )}
                      </td>
                      <td className="py-3.5 px-3 text-right">
                        <div className="text-xs">
                          <span className={`font-semibold block ${data.realNet >= 0 ? 'text-emerald-500/80' : 'text-red-500/80'}`}>
                            R: {formatCurrency(data.realNet)}
                          </span>
                          <span className={`font-bold block ${data.simNet >= 0 ? 'text-emerald-500' : 'text-red-500'}`}>
                            Proj: {formatCurrency(data.simNet)}
                          </span>
                        </div>
                      </td>
                      <td className="py-3.5 px-3 text-right">
                        <div className="text-xs">
                          <span className="text-muted-foreground block">
                            R: {formatCurrency(data.accumulatedReal)}
                          </span>
                          <span className={`font-bold block text-sm ${data.accumulatedSim >= 0 ? 'text-emerald-500' : 'text-red-500'}`}>
                            Proj: {formatCurrency(data.accumulatedSim)}
                          </span>
                        </div>
                      </td>
                      <td className="py-3.5 px-4 text-center">
                        {hasSimulations ? (
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => onVerDetalhes(data)}
                            className="h-7 rounded px-2.5 text-xs bg-amber-500/5 hover:bg-amber-500/10 text-amber-600 dark:text-amber-400 border-amber-500/20"
                          >
                            Ver ({data.activeSimulatedItems.length})
                          </Button>
                        ) : (
                          <span className="text-xs text-muted-foreground/40">—</span>
                        )}
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </CardContent>
    </Card>
  );
}
