import { useId, useState } from 'react';
import { ChevronDown, FolderOpen } from 'lucide-react';
import { Button } from '../../components/ui/Button';
import { Badge } from '../../components/ui/Badge';
import { Modal } from '../../components/ui/Modal';
import ProjecaoMensalTable from './ProjecaoMensalTable';
import MapaDeCalorDiario from './MapaDeCalorDiario';
import { formatCurrency } from './formatters';

/**
 * Disclosure fechado por padrão: reúne a tabela mês a mês e o mapa de calor
 * diário, as duas ferramentas de análise mais granulares da tela. Ficam a um
 * clique de distância em vez de ocupar a vista inicial.
 */
export default function AnaliseDetalhada({
  isLoading,
  monthlyData,
  projecaoFutura,
  pontoDeVirada,
}) {
  const [expandido, setExpandido] = useState(false);
  const [selectedMonthDetails, setSelectedMonthDetails] = useState(null);
  const [heatmapMetric, setHeatmapMetric] = useState('acumulado'); // 'acumulado' | 'fluxo'
  const conteudoId = useId();

  return (
    <div>
      <Button
        variant="outline"
        aria-expanded={expandido}
        aria-controls={conteudoId}
        onClick={() => setExpandido((v) => !v)}
        className="flex w-full items-center justify-center gap-2 sm:w-auto"
      >
        {expandido ? 'Ocultar análise' : 'Ver análise'}
        <ChevronDown
          className={`h-4 w-4 transition-transform ${expandido ? 'rotate-180' : ''}`}
          aria-hidden="true"
        />
      </Button>

      {expandido && (
        <div id={conteudoId} className="mt-6 space-y-6">
          <ProjecaoMensalTable
            isLoading={isLoading}
            monthlyData={monthlyData}
            onVerDetalhes={setSelectedMonthDetails}
          />

          <MapaDeCalorDiario
            isLoading={isLoading}
            projecaoFutura={projecaoFutura}
            pontoDeVirada={pontoDeVirada}
            heatmapMetric={heatmapMetric}
            setHeatmapMetric={setHeatmapMetric}
          />
        </div>
      )}

      {selectedMonthDetails && (
        <Modal
          isOpen
          title={
            <span className="flex items-center gap-2">
              <FolderOpen className="h-5 w-5 text-amber-500" aria-hidden="true" /> Detalhes: {selectedMonthDetails.label}
            </span>
          }
          onClose={() => setSelectedMonthDetails(null)}
          size="sm"
        >
          <div className="space-y-4">
            <p className="text-xs text-muted-foreground">
              Abaixo estão os lançamentos simulados ativos que afetam a projeção deste mês específico:
            </p>

            <div className="space-y-3 max-h-[300px] overflow-y-auto pr-1">
              {selectedMonthDetails.activeSimulatedItems.map((item) => (
                <div
                  key={item.id}
                  className="p-3 rounded-lg border border-border bg-muted/40 flex justify-between items-center"
                >
                  <div className="space-y-0.5">
                    <div className="flex items-center gap-1.5">
                      <span className="text-sm font-semibold text-foreground">{item.descricao}</span>
                      <Badge className={item.tipo === 'R' ? 'bg-emerald-500/10 text-emerald-500 border border-emerald-500/20' : 'bg-red-500/10 text-red-500 border border-red-500/20'}>
                        {item.tipo === 'R' ? 'Entrada' : 'Saída'}
                      </Badge>
                    </div>
                    <div className="text-xs text-muted-foreground">
                      Categoria: <span className="text-foreground/80 font-medium">{item.categoria}</span>
                    </div>
                    <div className="text-xs text-amber-500/90 font-semibold uppercase">
                      {item.frequencia === 'unica' && 'Único'}
                      {item.frequencia === 'recorrente' && 'Recorrente'}
                      {item.frequencia === 'parcelada' && `Parcelado (${item.parcelas}x)`}
                    </div>
                  </div>
                  <div className="text-right">
                    <span className={`text-sm font-bold block ${item.tipo === 'R' ? 'text-emerald-500' : 'text-red-500'}`}>
                      {item.tipo === 'R' ? '+' : '-'}{formatCurrency(item.currentMonthVal)}
                    </span>
                  </div>
                </div>
              ))}
            </div>

            <div className="flex justify-end pt-2">
              <Button
                variant="secondary"
                onClick={() => setSelectedMonthDetails(null)}
                className="px-5"
              >
                Fechar
              </Button>
            </div>
          </div>
        </Modal>
      )}
    </div>
  );
}
