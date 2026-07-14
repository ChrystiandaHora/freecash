import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { ArrowLeft, Loader2, Save, TrendingUp, TrendingDown, Gift, RefreshCw, AlertCircle } from 'lucide-react';

import api from '../../services/api';
import { Button } from '../../components/ui/Button';
import { Input } from '../../components/ui/Input';
import { Select } from '../../components/ui/Select';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/Card';
import { Alert } from '../../components/ui/Alert';

const formatCurrency = (value) => {
  if (value === undefined || value === null) return 'R$ 0,00';
  return new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(value);
};

export default function OrdemForm() {
  const { id } = useParams();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const isEditing = !!id;

  const [tab, setTab] = useState('cv');
  const [form, setForm] = useState({
    ativo: '',
    tipo: 'C',
    data: new Date().toISOString().split('T')[0],
    quantidade: '',
    preco_unitario: '',
    taxas: '',
    valor_total_provento: '',
  });
  const [error, setError] = useState('');

  // Fetch assets (ativos)
  const { data: ativos = [], isLoading: isLoadingAtivos } = useQuery({
    queryKey: ['ativos'],
    queryFn: async () => {
      const res = await api.get('/api/investimentos/ativos/');
      return res.data;
    }
  });

  // Fetch transaction details if editing
  const { data: transacao, isLoading: isLoadingTransacao } = useQuery({
    queryKey: ['transacao', id],
    queryFn: async () => {
      const res = await api.get(`/api/investimentos/transacoes/${id}/`);
      return res.data;
    },
    enabled: isEditing,
  });

  useEffect(() => {
    if (isEditing && transacao) {
      setTab(transacao.tipo === 'D' ? 'proventos' : 'cv');
      setForm({
        ativo: transacao.ativo ?? '',
        tipo: transacao.tipo ?? 'C',
        data: transacao.data ?? '',
        quantidade: transacao.quantidade ?? '',
        preco_unitario: transacao.preco_unitario ?? '',
        taxas: transacao.taxas ?? '',
        valor_total_provento: transacao.tipo === 'D' ? transacao.preco_unitario : '',
      });
    }
  }, [transacao, isEditing]);

  const mutation = useMutation({
    mutationFn: async (payload) => {
      if (isEditing) {
        const res = await api.put(`/api/investimentos/transacoes/${id}/`, payload);
        return res.data;
      } else {
        const res = await api.post('/api/investimentos/transacoes/', payload);
        return res.data;
      }
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['ativos'] });
      queryClient.invalidateQueries({ queryKey: ['investimentosDashboard'] });
      queryClient.invalidateQueries({ queryKey: ['investimentosBalanceamento'] });
      queryClient.invalidateQueries({ queryKey: ['transacoesInvestimento'] });
      navigate('/investimentos/historico');
    },
    onError: (err) => {
      const apiErr = err.response?.data;
      if (typeof apiErr === 'object' && apiErr !== null) {
        setError(Object.entries(apiErr).map(([key, val]) => `${key}: ${val}`).join(' | '));
      } else {
        setError(isEditing ? 'Erro ao atualizar ordem.' : 'Erro ao registrar ordem.');
      }
    },
  });

  const handleChange = (key) => (e) => {
    setForm((f) => ({ ...f, [key]: e.target.value }));
    setError('');
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    setError('');

    if (!form.ativo) { setError('Selecione um ativo.'); return; }
    if (!form.data) { setError('Selecione a data da operação.'); return; }

    let payload = {};
    if (tab === 'proventos') {
      if (!form.valor_total_provento) {
        setError('Preencha o valor do provento.'); return;
      }
      payload = {
        ativo: parseInt(form.ativo),
        tipo: 'D',
        data: form.data,
        quantidade: 1,
        preco_unitario: parseFloat(form.valor_total_provento),
        taxas: 0,
      };
    } else {
      if (!form.quantidade || !form.preco_unitario) {
        setError('Preencha quantidade e preço unitário.'); return;
      }
      payload = {
        ativo: parseInt(form.ativo),
        tipo: form.tipo,
        data: form.data,
        quantidade: parseFloat(form.quantidade),
        preco_unitario: parseFloat(form.preco_unitario),
        taxas: parseFloat(form.taxas) || 0,
      };
    }
    mutation.mutate(payload);
  };

  if (isEditing && isLoadingTransacao) {
    return (
      <div className="flex h-96 items-center justify-center">
        <Loader2 className="h-8 w-8 text-primary animate-spin" />
      </div>
    );
  }

  const isPending = mutation.isPending;

  return (
    <div className="mx-auto max-w-xl space-y-6">
      {/* Header */}
      <div className="flex items-center gap-4">
        <button
          onClick={() => navigate('/investimentos/historico')}
          className="rounded-lg p-2 text-muted-foreground hover:bg-muted hover:text-foreground transition-colors"
          title="Voltar"
        >
          <ArrowLeft className="h-5 w-5" />
        </button>
        <div>
          <h2 className="text-2xl font-bold tracking-tight text-foreground">
            {isEditing ? 'Editar Ordem' : 'Registrar Nova Ordem'}
          </h2>
          <p className="text-sm text-muted-foreground">
            {isEditing ? 'Atualize os dados do lançamento da carteira.' : 'Lance compras, vendas ou recebimento de dividendos.'}
          </p>
        </div>
      </div>

      {/* Card Form */}
      <Card className="border-border/60 shadow-lg">
        {/* Tab Selector */}
        {!isEditing && (
          <div className="p-6 pb-2 shrink-0">
            <div className="flex bg-muted p-1 rounded-xl">
              {[{ id: 'cv', label: 'Compra / Venda' }, { id: 'proventos', label: 'Proventos / JCP' }].map((t) => (
                <button
                  key={t.id}
                  type="button"
                  onClick={() => { setTab(t.id); setError(''); }}
                  className={`flex-1 py-2.5 text-xs font-bold rounded-lg transition-all
                    ${tab === t.id ? 'bg-card shadow-sm text-primary' : 'text-muted-foreground hover:text-foreground'}`}
                >
                  {t.label}
                </button>
              ))}
            </div>
          </div>
        )}

        <CardContent className="p-6 space-y-4">
          <form onSubmit={handleSubmit} className="space-y-4">
            
            {/* Ativo */}
            <div className="space-y-1.5">
              <label className="text-sm font-semibold text-foreground">Ativo *</label>
              {isLoadingAtivos ? (
                <div className="flex items-center gap-2 text-xs text-muted-foreground">
                  <Loader2 className="h-3 w-3 animate-spin" /> Carregando ativos...
                </div>
              ) : (
                <Select
                  value={form.ativo}
                  onChange={handleChange('ativo')}
                  required
                >
                  <option value="">Selecione...</option>
                  {ativos.map((a) => (
                    <option key={a.id} value={a.id}>{a.ticker} — {a.nome}</option>
                  ))}
                </Select>
              )}
            </div>

            {/* Data */}
            <div className="space-y-1.5">
              <label className="text-sm font-semibold text-foreground">Data da Operação *</label>
              <Input type="date" value={form.data} onChange={handleChange('data')} required />
            </div>

            {tab === 'cv' ? (
              <>
                {/* Tipo C/V */}
                <div className="space-y-1.5">
                  <label className="text-sm font-semibold text-foreground">Tipo de Operação</label>
                  <div className="flex gap-3">
                    {[{ v: 'C', l: 'Compra', color: 'emerald' }, { v: 'V', l: 'Venda', color: 'rose' }].map(({ v, l, color }) => (
                      <button
                        key={v}
                        type="button"
                        onClick={() => setForm((f) => ({ ...f, tipo: v }))}
                        className={`flex-1 py-2.5 rounded-xl text-sm font-bold border-2 transition-all
                          ${form.tipo === v
                            ? `border-${color}-500 bg-${color}-500/10 text-${color}-600 dark:text-${color}-400`
                            : 'border-slate-200 dark:border-slate-700 text-slate-500 hover:border-slate-300'}`}
                      >
                        {l}
                      </button>
                    ))}
                  </div>
                </div>

                {/* Quantidade */}
                <div className="space-y-1.5">
                  <label className="text-sm font-semibold text-foreground">Quantidade *</label>
                  <Input 
                    type="number" 
                    placeholder="0" 
                    min="0" 
                    step="0.00000001" 
                    value={form.quantidade} 
                    onChange={handleChange('quantidade')} 
                    required 
                  />
                </div>

                {/* Preço Unitário */}
                <div className="space-y-1.5">
                  <label className="text-sm font-semibold text-foreground">Preço Unitário (R$) *</label>
                  <Input 
                    type="number" 
                    placeholder="0,00" 
                    min="0" 
                    step="0.01" 
                    value={form.preco_unitario} 
                    onChange={handleChange('preco_unitario')} 
                    required 
                  />
                </div>

                {/* Taxas */}
                <div className="space-y-1.5">
                  <label className="text-sm font-semibold text-foreground">Taxas / Corretagem (R$)</label>
                  <Input 
                    type="number" 
                    placeholder="0,00" 
                    min="0" 
                    step="0.01" 
                    value={form.taxas} 
                    onChange={handleChange('taxas')} 
                  />
                </div>

                {/* Preview total */}
                {form.quantidade && form.preco_unitario && (
                  <div className="p-4 rounded-xl bg-muted/30 flex justify-between items-center border border-border/40">
                    <span className="text-xs font-semibold text-muted-foreground">Valor total estimado:</span>
                    <span className="text-sm font-extrabold text-foreground">
                      {formatCurrency(
                        parseFloat(form.quantidade) * parseFloat(form.preco_unitario) +
                        (form.tipo === 'C' ? 1 : -1) * parseFloat(form.taxas || 0)
                      )}
                    </span>
                  </div>
                )}
              </>
            ) : (
              <>
                {/* Proventos */}
                <div className="space-y-1.5">
                  <label className="text-sm font-semibold text-foreground">Valor do provento recebido (R$) *</label>
                  <Input 
                    type="number" 
                    placeholder="0,00" 
                    min="0" 
                    step="0.01" 
                    value={form.valor_total_provento} 
                    onChange={handleChange('valor_total_provento')} 
                    required 
                  />
                </div>
                <p className="text-xs text-muted-foreground leading-relaxed">
                  Dividendos, JCP, Rendimentos de FII, Cupons, etc. O valor será registrado como tipo "Provento" e não altera sua quantidade de cotas.
                </p>
              </>
            )}

            {error && (
              <Alert variant="error" icon={AlertCircle} className="text-xs">
                <span className="font-semibold">{error}</span>
              </Alert>
            )}

            {/* Actions */}
            <div className="flex gap-3 pt-4 border-t border-border/60">
              <Button
                type="button"
                variant="outline"
                onClick={() => navigate('/investimentos/historico')}
                disabled={isPending}
                className="flex-1 rounded-xl"
              >
                Cancelar
              </Button>
              <Button
                type="submit"
                disabled={isPending}
                className="flex-1 bg-primary hover:bg-primary/95 text-primary-foreground border-0 font-semibold rounded-xl"
              >
                {isPending ? (
                  <Loader2 className="h-4 w-4 animate-spin mx-auto" />
                ) : (
                  <>
                    <Save className="mr-1.5 h-4 w-4 inline" />
                    {isEditing ? 'Salvar Alterações' : 'Registrar Ordem'}
                  </>
                )}
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
