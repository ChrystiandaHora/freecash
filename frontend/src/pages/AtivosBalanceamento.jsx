/**
 * Página do Balanceador de Ativos Inteligente.
 * 
 * Permite que o investidor redefina as metas de alocação de sua carteira por ativo
 * e calcule instantaneamente o "Aporte Mágico", indicando onde comprar para reequilibrar
 * as posições mais deficitárias sem necessidade de realizar vendas.
 *
 * @component
 * @returns {React.JSX.Element}
 */
import React, { useState, useCallback } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import api from '../services/api';
import {
  Scale,
  RefreshCw,
  AlertCircle,
  CheckCircle2,
  Save,
  Sliders,
  Coins,
  TrendingUp,
  ArrowRight,
  Minus,
  Plus
} from 'lucide-react';
import { Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter } from '../components/ui/Card';
import { Button } from '../components/ui/Button';
import { Input } from '../components/ui/Input';

/* ─────────────────────────── Helpers ─────────────────────────── */
const formatCurrency = (value) => {
  if (value === undefined || value === null) return 'R$ 0,00';
  return new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(value);
};

const formatPct = (value) => {
  const num = parseFloat(value) || 0;
  return num.toFixed(2).replace('.', ',') + '%';
};

/* ─────────────────────────── Slider component ─────────────────────────── */
/**
 * Componente de controle deslizante (Slider) customizado para ajuste de metas.
 *
 * @component
 * @param {Object} props - Propriedades do componente.
 * @param {number} props.id - ID único do ativo.
 * @param {number} props.value - O valor percentual atual da meta.
 * @param {Function} props.onChange - Callback disparado ao alterar o valor da meta.
 * @param {boolean} props.disabled - Flag que desabilita a interação com o controle.
 * @returns {React.JSX.Element}
 */
function MetaSlider({ id, value, onChange, disabled }) {
  return (
    <div className="relative flex items-center gap-3 w-full">
      <button
        type="button"
        disabled={disabled || value <= 0}
        onClick={() => onChange(Math.max(0, value - 0.5))}
        className="w-7 h-7 rounded-lg flex items-center justify-center border border-border bg-muted text-muted-foreground hover:bg-muted/80 transition-colors disabled:opacity-40 shrink-0"
      >
        <Minus className="h-3 w-3" />
      </button>

      <div className="flex-1 relative">
        {/* Track */}
        <div className="h-2 rounded-full bg-muted overflow-hidden">
          <div
            className="h-full rounded-full bg-primary transition-all duration-150"
            style={{ width: `${Math.min(100, value)}%` }}
          />
        </div>
        <input
          id={`slider-${id}`}
          type="range"
          min={0}
          max={100}
          step={0.5}
          value={value}
          disabled={disabled}
          onChange={(e) => onChange(parseFloat(e.target.value))}
          className="absolute inset-0 w-full h-full opacity-0 cursor-pointer disabled:cursor-not-allowed"
        />
      </div>

      <button
        type="button"
        disabled={disabled || value >= 100}
        onClick={() => onChange(Math.min(100, value + 0.5))}
        className="w-7 h-7 rounded-lg flex items-center justify-center border border-border bg-muted text-muted-foreground hover:bg-muted/80 transition-colors disabled:opacity-40 shrink-0"
      >
        <Plus className="h-3 w-3" />
      </button>

      <span className="w-14 text-right text-sm font-bold text-foreground tabular-nums shrink-0">
        {formatPct(value)}
      </span>
    </div>
  );
}

/* ─────────────────────────── Main Page ─────────────────────────── */
export default function AtivosBalanceamento() {
  const queryClient = useQueryClient();

  // Metas locais: { [id]: porcentagem }
  const [editingMetas, setEditingMetas] = useState({});
  const [isEditing, setIsEditing] = useState(false);
  const [metaError, setMetaError] = useState('');
  const [aporteValue, setAporteValue] = useState('');

  /* ── Query ── */
  const {
    data: balanceData,
    isLoading,
    isError,
    refetch,
  } = useQuery({
    queryKey: ['investimentosBalanceamento'],
    queryFn: async () => {
      const res = await api.get('/api/investimentos/balanceamento/');
      return res.data;
    },
  });

  /* ── Mutation ── */
  const saveMetasMutation = useMutation({
    mutationFn: async (payload) => {
      const res = await api.post('/api/investimentos/balanceamento/', { metas: payload });
      return res.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries(['investimentosBalanceamento']);
      setIsEditing(false);
      setEditingMetas({});
      setMetaError('');
    },
    onError: () => setMetaError('Erro ao salvar metas. Tente novamente.'),
  });

  /* ── Handlers ── */
  const handleStartEditing = () => {
    if (!balanceData) return;
    const initial = {};
    balanceData.classes.forEach((cls) => cls.ativos.forEach((at) => { initial[at.id] = at.meta_porcentagem; }));
    setEditingMetas(initial);
    setIsEditing(true);
    setMetaError('');
  };

  const handleMetaChange = useCallback((id, val) => {
    setEditingMetas((prev) => ({ ...prev, [id]: Math.max(0, Math.min(100, val)) }));
  }, []);

  const handleSaveMetas = () => {
    const total = Object.values(editingMetas).reduce((a, b) => a + b, 0);
    if (total > 0 && Math.abs(total - 100) > 0.01) {
      setMetaError(`A soma das metas deve ser 100%. Atual: ${total.toFixed(1).replace('.', ',')}%`);
      return;
    }
    const payload = Object.entries(editingMetas).map(([id, meta]) => ({ id: parseInt(id), meta }));
    saveMetasMutation.mutate(payload);
  };

  /* ── Computed: "Aporte Mágico" ── */
  const aporteNum = parseFloat(aporteValue.replace(',', '.')) || 0;
  const totalPatrimonio = balanceData?.total_patrimonio ?? 0;
  const allAtivos = (balanceData?.classes ?? []).flatMap((c) => c.ativos);
  const futuroPatrimonio = totalPatrimonio + aporteNum;

  const magicAllocation = allAtivos.map((at) => {
    const meta = (isEditing ? editingMetas[at.id] : at.meta_porcentagem) ?? 0;
    const valorIdeal = (meta / 100) * futuroPatrimonio;
    const aporte = Math.max(0, valorIdeal - at.valor_atual);
    return { ...at, meta, valorIdeal, aporte };
  });

  const somaAportes = magicAllocation.reduce((s, a) => s + a.aporte, 0);
  const somaEditingMetas = Object.values(editingMetas).reduce((a, b) => a + b, 0);
  const pctSumOk = Math.abs(somaEditingMetas - 100) < 0.01;

  /* ── Loading / Error states ── */
  if (isLoading) return (
    <div className="flex flex-col items-center justify-center min-h-[70vh] gap-4">
      <RefreshCw className="h-8 w-8 text-primary animate-spin" />
      <p className="text-sm font-semibold text-muted-foreground">Carregando dados de balanceamento...</p>
    </div>
  );

  if (isError) return (
    <div className="flex flex-col items-center justify-center min-h-[70vh] gap-4 text-center max-w-md mx-auto">
      <AlertCircle className="h-12 w-12 text-red-500" />
      <h3 className="text-xl font-bold text-slate-800 dark:text-slate-200">Erro ao carregar balanceamento</h3>
      <Button onClick={() => refetch()} className="mt-2">Tentar novamente</Button>
    </div>
  );

  return (
    <div className="space-y-8 animate-fade-in">

      {/* ── Header ── */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <div>
          <h1 className="text-3xl font-extrabold tracking-tight text-foreground">
            Balanceamento de Ativos
          </h1>
          <p className="text-muted-foreground mt-1">
            Configure metas percentuais e calcule o aporte ideal para reequilibrar sua carteira
          </p>
        </div>
        <div className="flex items-center gap-3 shrink-0">
          {isEditing ? (
            <>
              <Button
                variant="outline"
                onClick={() => { setIsEditing(false); setMetaError(''); }}
                disabled={saveMetasMutation.isPending}
                className="h-9 px-4 rounded-xl text-xs font-semibold"
              >
                Cancelar
              </Button>
              <Button
                onClick={handleSaveMetas}
                disabled={saveMetasMutation.isPending}
                className="h-9 px-4 rounded-xl text-xs font-semibold bg-primary hover:bg-primary/90 text-primary-foreground border-0 flex items-center gap-1.5"
              >
                {saveMetasMutation.isPending ? <RefreshCw className="h-3.5 w-3.5 animate-spin" /> : <Save className="h-3.5 w-3.5" />}
                Salvar Metas
              </Button>
            </>
          ) : (
            <Button
              onClick={handleStartEditing}
              className="h-9 px-4 rounded-xl text-xs font-semibold bg-primary hover:bg-primary/90 text-primary-foreground border-0 flex items-center gap-1.5"
            >
              <Sliders className="h-3.5 w-3.5" />
              Ajustar Metas
            </Button>
          )}
          <Button variant="outline" size="icon" onClick={() => refetch()} className="rounded-xl h-9 w-9 shrink-0">
            <RefreshCw className="h-4 w-4 text-muted-foreground" />
          </Button>
        </div>
      </div>

      {/* ── KPIs ── */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-5">
        <Card className="border border-border/40 bg-card shadow-sm relative overflow-hidden group">
          <CardHeader className="pb-1">
            <span className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider">Patrimônio atual</span>
          </CardHeader>
          <CardContent>
            <h3 className="text-2xl font-bold tracking-tight text-foreground">{formatCurrency(totalPatrimonio)}</h3>
          </CardContent>
        </Card>

        <Card className="border border-border/40 bg-card shadow-sm relative overflow-hidden group">
          <CardHeader className="pb-1">
            <span className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider">Ativos na carteira</span>
          </CardHeader>
          <CardContent>
            <h3 className="text-2xl font-bold tracking-tight text-foreground">{allAtivos.length}</h3>
          </CardContent>
        </Card>

        <Card className="border border-border/40 bg-card shadow-sm relative overflow-hidden group">
          <CardHeader className="pb-1">
            <span className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider">Soma das metas</span>
          </CardHeader>
          <CardContent>
            <h3 className={`text-2xl font-bold tracking-tight ${Math.abs(balanceData?.soma_metas - 100) < 0.01 ? 'text-primary' : 'text-amber-500'}`}>
              {formatPct(balanceData?.soma_metas ?? 0)}
            </h3>
          </CardContent>
        </Card>
      </div>

      {/* ── Alerts ── */}
      {metaError && (
        <div className="flex items-center gap-2.5 p-3.5 rounded-xl bg-destructive/10 border border-destructive/20 text-destructive text-xs">
          <AlertCircle className="h-4 w-4 shrink-0" />
          <p className="font-semibold">{metaError}</p>
        </div>
      )}
      {saveMetasMutation.isSuccess && (
        <div className="flex items-center gap-2.5 p-3.5 rounded-xl bg-emerald-500/10 border border-emerald-500/20 text-emerald-600 dark:text-emerald-400 text-xs">
          <CheckCircle2 className="h-4 w-4 shrink-0" />
          <p className="font-semibold">Metas salvas com sucesso!</p>
        </div>
      )}
      {isEditing && (
        <div className={`flex items-center justify-between p-3.5 rounded-xl border text-xs transition-colors ${pctSumOk ? 'bg-primary/10 border-primary/20 text-primary' : 'bg-amber-500/10 border-amber-500/20 text-amber-500'}`}>
          <span className="text-muted-foreground font-semibold">Soma das metas configuradas:</span>
          <span className={`font-extrabold text-base ${pctSumOk ? 'text-primary' : 'text-amber-500'}`}>
            {formatPct(somaEditingMetas)} / 100%
          </span>
        </div>
      )}

      {/* ── Slider Table per class ── */}
      {balanceData?.classes?.map((classe, idx) => (
        <Card key={idx} className="border border-border/40 bg-card shadow-sm">
          <CardHeader>
            <CardTitle className="text-base font-bold text-foreground flex items-center gap-2">
              <Scale className="h-4 w-4 text-primary" />
              {classe.nome}
            </CardTitle>
            <CardDescription className="text-xs">
              {classe.ativos.length} ativo{classe.ativos.length !== 1 ? 's' : ''} nesta classe
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-5">
              {classe.ativos.map((at) => {
                const localMeta = isEditing ? (editingMetas[at.id] ?? at.meta_porcentagem) : at.meta_porcentagem;
                const magicoItem = magicAllocation.find((m) => m.id === at.id);
                return (
                  <div key={at.id} className="space-y-2">
                    {/* Header row */}
                    <div className="flex items-center justify-between gap-4">
                      <div className="flex items-center gap-3 min-w-0">
                        <div className="w-9 h-9 rounded-xl bg-primary/10 flex items-center justify-center shrink-0">
                          <TrendingUp className="h-4 w-4 text-primary" />
                        </div>
                        <div className="min-w-0">
                          <p className="text-sm font-bold text-foreground truncate">{at.ticker}</p>
                          <p className="text-[11px] text-muted-foreground truncate max-w-[200px]">{at.nome}</p>
                        </div>
                      </div>
                      <div className="text-right shrink-0">
                        <p className="text-xs font-bold text-foreground">{formatCurrency(at.valor_atual)}</p>
                        <p className="text-[10px] text-muted-foreground">atual • {formatPct(at.perc_atual)} carteira</p>
                      </div>
                    </div>

                    {/* Slider */}
                    <MetaSlider
                      id={at.id}
                      value={localMeta}
                      onChange={(v) => handleMetaChange(at.id, v)}
                      disabled={!isEditing}
                    />

                    {/* Aporte info */}
                    {magicoItem && magicoItem.aporte > 0.01 && (
                      <div className="flex items-center gap-2 text-[11px] text-primary bg-primary/5 rounded-lg px-3 py-1.5">
                        <ArrowRight className="h-3 w-3 shrink-0" />
                        <span className="font-semibold">Aporte sugerido: {formatCurrency(magicoItem.aporte)}</span>
                        <span className="text-muted-foreground">→ saldo ideal: {formatCurrency(magicoItem.valorIdeal)}</span>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </CardContent>
        </Card>
      ))}

      {/* ── Aporte Mágico Calculator ── */}
      <Card className="border border-primary/20 bg-card shadow-sm">
        <CardHeader>
          <CardTitle className="text-base font-bold text-foreground flex items-center gap-2">
            <Coins className="h-4 w-4 text-amber-500" />
            Calculadora de Aporte Mágico
          </CardTitle>
          <CardDescription className="text-xs">
            Informe quanto deseja aportar e veja a distribuição automática baseada nos déficits da carteira
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-5">
          <div className="flex items-center gap-4 flex-col sm:flex-row">
            <div className="flex-1">
              <label className="block text-xs font-semibold text-muted-foreground mb-1.5 uppercase tracking-wider">
                Quanto você quer aportar hoje?
              </label>
              <div className="relative">
                <span className="absolute left-3 top-1/2 -translate-y-1/2 text-sm font-bold text-primary">R$</span>
                <Input
                  type="number"
                  placeholder="0,00"
                  value={aporteValue}
                  onChange={(e) => setAporteValue(e.target.value)}
                  className="pl-10 h-12 text-lg font-bold"
                  min="0"
                  step="100"
                />
              </div>
            </div>
            {aporteNum > 0 && (
              <div className="text-right shrink-0">
                <p className="text-[10px] text-muted-foreground uppercase tracking-wider font-semibold">Patrimônio futuro</p>
                <p className="text-xl font-extrabold text-foreground">{formatCurrency(futuroPatrimonio)}</p>
              </div>
            )}
          </div>

          {aporteNum > 0 && magicAllocation.length > 0 && (
            <div className="overflow-x-auto rounded-xl border border-border/40">
              <table className="w-full text-xs text-left border-collapse">
                <thead>
                  <tr className="border-b border-border/40 text-muted-foreground font-semibold bg-muted/40">
                    <th className="py-3 px-4">Ativo</th>
                    <th className="py-3 px-4 text-right">Meta</th>
                    <th className="py-3 px-4 text-right">Saldo Atual</th>
                    <th className="py-3 px-4 text-right">Saldo Ideal</th>
                    <th className="py-3 px-4 text-right">Aportar</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border/20">
                  {magicAllocation.map((at) => (
                    <tr key={at.id} className="hover:bg-muted/40 transition-colors">
                      <td className="py-3 px-4">
                        <p className="font-bold text-foreground">{at.ticker}</p>
                        <p className="text-[10px] text-muted-foreground truncate max-w-[120px]">{at.nome}</p>
                      </td>
                      <td className="py-3 px-4 text-right font-semibold text-foreground">{formatPct(at.meta)}</td>
                      <td className="py-3 px-4 text-right text-muted-foreground">{formatCurrency(at.valor_atual)}</td>
                      <td className="py-3 px-4 text-right text-muted-foreground">{formatCurrency(at.valorIdeal)}</td>
                      <td className={`py-3 px-4 text-right font-extrabold ${at.aporte > 0.01 ? 'text-primary' : 'text-muted-foreground'}`}>
                        {at.aporte > 0.01 ? formatCurrency(at.aporte) : '—'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {aporteNum > 0 && somaAportes > 0.01 && (
            <div className={`flex items-center justify-between p-3.5 rounded-xl border text-xs ${somaAportes <= aporteNum + 0.01 ? 'bg-primary/10 border-primary/20 text-primary' : 'bg-amber-500/10 border-amber-500/20 text-amber-500'}`}>
              <span className="font-semibold">Total recomendado para aporte:</span>
              <span className="font-extrabold text-base">{formatCurrency(somaAportes)}</span>
            </div>
          )}
        </CardContent>
      </Card>

    </div>
  );
}
