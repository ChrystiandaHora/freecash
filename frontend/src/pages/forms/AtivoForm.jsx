import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { ArrowLeft, Loader2, Save, Calendar, TrendingUp, RefreshCw, HelpCircle, Archive } from 'lucide-react';

import { fetchAtivo, createAtivo, updateAtivo, fetchSubcategoriasAtivos } from '../../services/investimentos';
import { Button } from '../../components/ui/Button';
import { Input } from '../../components/ui/Input';
import { Select } from '../../components/ui/Select';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/Card';

const initialFormState = {
  ticker: '',
  nome: '',
  cnpj: '',
  subcategoria: '',
  quantidade_inicial: '',
  preco_medio_inicial: '',
  data_compra: '',
  emissor: '',
  data_vencimento: '',
  indexador: '',
  taxa: '',
  moeda: 'BRL',
  ativo: true,
  meta_porcentagem: 0,
};

export default function AtivoForm() {
  const { id } = useParams();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const isEdit = !!id;

  const [formData, setFormData] = useState(initialFormState);
  const [showPosicaoInicial, setShowPosicaoInicial] = useState(false);
  const [errorMessage, setErrorMessage] = useState('');

  // Fetch subcategories
  const { data: subcategorias = [], isLoading: loadingSubs } = useQuery({
    queryKey: ['subcategoriasAtivos'],
    queryFn: () => fetchSubcategoriasAtivos(),
  });

  // Fetch asset details if in edit mode
  const { data: assetData, isLoading: isFetchingAsset } = useQuery({
    queryKey: ['ativo', id],
    queryFn: () => fetchAtivo(id),
    enabled: isEdit,
  });

  useEffect(() => {
    if (isEdit && assetData) {
      setFormData({
        id: assetData.id,
        ticker: assetData.ticker || '',
        nome: assetData.nome || '',
        cnpj: assetData.cnpj || '',
        subcategoria: assetData.subcategoria || '',
        quantidade_inicial: '',
        preco_medio_inicial: '',
        data_compra: '',
        emissor: assetData.emissor || '',
        data_vencimento: assetData.data_vencimento || '',
        indexador: assetData.indexador || '',
        taxa: assetData.taxa || '',
        moeda: assetData.moeda || 'BRL',
        ativo: assetData.ativo ?? true,
        meta_porcentagem: parseFloat(assetData.meta_porcentagem || 0),
      });
    } else if (!isEdit) {
      setFormData(initialFormState);
    }
  }, [assetData, isEdit]);

  // Compute if selected subcategory is fixed income / alternative
  const selectedSub = subcategorias.find(sc => sc.id === parseInt(formData.subcategoria));
  const classeNome = selectedSub?.categoria_detalhe?.classe_detalhe?.nome || "";
  const isRendaFixaOuAlternativo = 
    classeNome.toLowerCase().includes("fixa") || 
    classeNome.toLowerCase().includes("alternativo");

  const createMutation = useMutation({
    mutationFn: (payload) => createAtivo(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['ativos'] });
      navigate('/investimentos/ativos');
    },
    onError: (err) => {
      const msg = err?.response?.data?.detail || err?.response?.data?.erro || err.message;
      setErrorMessage('Erro ao cadastrar ativo: ' + msg);
    }
  });

  const updateMutation = useMutation({
    mutationFn: (payload) => updateAtivo(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['ativos'] });
      navigate('/investimentos/ativos');
    },
    onError: (err) => {
      const msg = err?.response?.data?.detail || err?.response?.data?.erro || err.message;
      setErrorMessage('Erro ao salvar alterações: ' + msg);
    }
  });

  const handleSubmit = (e) => {
    e.preventDefault();
    setErrorMessage('');

    if (!formData.ticker.trim()) {
      setErrorMessage('O Ticker é obrigatório (ex: PETR4).');
      return;
    }
    if (!formData.subcategoria) {
      setErrorMessage('Selecione uma Subclasse para o ativo.');
      return;
    }

    const payload = {
      ticker: formData.ticker.trim().toUpperCase(),
      nome: formData.nome.trim() || formData.ticker.trim().toUpperCase(),
      cnpj: formData.cnpj ? formData.cnpj.trim() : null,
      subcategoria: parseInt(formData.subcategoria),
      data_vencimento: formData.data_vencimento || null,
      emissor: formData.emissor.trim() || null,
      indexador: formData.indexador.trim() || null,
      taxa: formData.taxa ? formData.taxa.trim() : null,
      moeda: formData.moeda,
      ativo: formData.ativo,
      meta_porcentagem: parseFloat(formData.meta_porcentagem || 0),
    };

    if (isEdit) {
      payload.id = formData.id;
      updateMutation.mutate(payload);
    } else {
      if (showPosicaoInicial && formData.quantidade_inicial && formData.preco_medio_inicial) {
        payload.quantidade_inicial = parseFloat(formData.quantidade_inicial);
        payload.preco_medio_inicial = parseFloat(formData.preco_medio_inicial);
        payload.data_compra = formData.data_compra || null;
      }
      createMutation.mutate(payload);
    }
  };

  if (isEdit && isFetchingAsset) {
    return (
      <div className="flex h-96 items-center justify-center">
        <Loader2 className="h-8 w-8 text-primary animate-spin" />
      </div>
    );
  }

  const isPending = createMutation.isPending || updateMutation.isPending;

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      {/* Header */}
      <div className="flex items-center gap-4">
        <button
          onClick={() => navigate('/investimentos/ativos')}
          className="rounded-lg p-2 text-muted-foreground hover:bg-muted hover:text-foreground transition-colors"
          title="Voltar"
        >
          <ArrowLeft className="h-5 w-5" />
        </button>
        <div>
          <h2 className="text-2xl font-bold tracking-tight text-foreground">
            {isEdit ? `Editar Ativo: ${formData.ticker}` : 'Cadastrar Novo Ativo'}
          </h2>
          <p className="text-sm text-muted-foreground">
            {isEdit ? 'Altere os parâmetros do ativo selecionado.' : 'Preencha os dados cadastrais básicos do seu investimento.'}
          </p>
        </div>
      </div>

      {/* Card Form */}
      <Card className="border-border/60 shadow-lg">
        <CardHeader className="bg-muted/10 pb-4">
          <CardTitle className="text-sm font-semibold uppercase tracking-wider text-muted-foreground">
            Ficha Cadastral do Ativo
          </CardTitle>
        </CardHeader>
        <CardContent className="p-6">
          <form onSubmit={handleSubmit} className="space-y-6">
            
            {errorMessage && (
              <p className="text-sm text-red-500">{errorMessage}</p>
            )}

            {/* Dados Principais */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="space-y-1.5">
                <label className="text-sm font-medium text-foreground">Ticker *</label>
                <Input
                  placeholder="Ex: PETR4, IVVB11, CDB..."
                  value={formData.ticker}
                  onChange={(e) => setFormData({ ...formData, ticker: e.target.value.toUpperCase() })}
                  className="uppercase font-bold"
                  required
                />
              </div>

              <div className="space-y-1.5">
                <label className="text-sm font-medium text-foreground">Nome Comercial</label>
                <Input
                  placeholder="Ex: Petrobras PN, S&P 500 ETF..."
                  value={formData.nome}
                  onChange={(e) => setFormData({ ...formData, nome: e.target.value })}
                />
              </div>

              <div className="space-y-1.5">
                <label className="text-sm font-medium text-foreground">CNPJ do Fundo (Opcional)</label>
                <Input
                  placeholder="Apenas números (Ex: 12987743000186)"
                  value={formData.cnpj || ''}
                  onChange={(e) => setFormData({ ...formData, cnpj: e.target.value })}
                  className="font-semibold"
                />
              </div>

              <div className="space-y-1.5">
                <label className="text-sm font-medium text-foreground">Subclasse de Ativo *</label>
                {subcategorias.length > 0 ? (
                  <Select
                    value={formData.subcategoria}
                    onChange={(e) => setFormData({ ...formData, subcategoria: e.target.value })}
                    required
                  >
                    <option value="">Selecione...</option>
                    {subcategorias.map(sc => (
                      <option key={sc.id} value={sc.id}>
                        {sc.categoria_detalhe?.classe_detalhe?.nome} — {sc.nome}
                      </option>
                    ))}
                  </Select>
                ) : (
                  <div className="p-3 border border-amber-500/20 bg-amber-500/5 text-amber-600 rounded-xl text-xs flex flex-col gap-1.5">
                    <span className="font-semibold">Nenhuma Subclasse Encontrada!</span>
                    <a href="/investimentos/classes" className="text-primary hover:underline font-bold">
                      Criar Classes e Subcategorias primeiro →
                    </a>
                  </div>
                )}
              </div>

              <div className="space-y-1.5">
                <label className="text-sm font-medium text-foreground">Taxa / Taxa de Adm. (%)</label>
                <Input
                  type="number"
                  step="0.0001"
                  placeholder="Ex: 6.5, 110 ou 0.5 (opcional)"
                  value={formData.taxa}
                  onChange={(e) => setFormData({ ...formData, taxa: e.target.value })}
                  className="font-semibold"
                />
              </div>

              <div className="space-y-1.5">
                <label className="text-sm font-medium text-foreground">Meta de Alocação (%)</label>
                <Input
                  type="number"
                  step="0.1"
                  min="0"
                  max="100"
                  placeholder="Ex: 15.0"
                  value={formData.meta_porcentagem || ''}
                  onChange={(e) => setFormData({ ...formData, meta_porcentagem: e.target.value })}
                  className="font-semibold"
                />
              </div>
            </div>

            {/* Dados Opcionais de Renda Fixa */}
            {isRendaFixaOuAlternativo && (
              <div className="border-t border-border/40 pt-6 animate-fade-in space-y-4">
                <h4 className="text-sm font-semibold text-foreground flex items-center gap-1.5">
                  <Calendar className="h-4 w-4 text-muted-foreground" />
                  Detalhes Adicionais (Renda Fixa/Alternativos)
                </h4>
                
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div className="space-y-1.5">
                    <label className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">Emissor</label>
                    <Input
                      placeholder="Ex: Banco Itaú, Tesouro Nacional"
                      value={formData.emissor}
                      onChange={(e) => setFormData({ ...formData, emissor: e.target.value })}
                    />
                  </div>

                  <div className="space-y-1.5">
                    <label className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">Data de Vencimento</label>
                    <Input
                      type="date"
                      value={formData.data_vencimento}
                      onChange={(e) => setFormData({ ...formData, data_vencimento: e.target.value })}
                    />
                  </div>

                  <div className="space-y-1.5 sm:col-span-2">
                    <label className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">Indexador</label>
                    <Input
                      placeholder="Ex: IPCA, CDI, SELIC"
                      value={formData.indexador}
                      onChange={(e) => setFormData({ ...formData, indexador: e.target.value })}
                    />
                  </div>
                </div>
              </div>
            )}

            {/* Posição Inicial (Só aparece se NÃO estiver editando) */}
            {!isEdit && (
              <div className="border border-border/60 rounded-xl overflow-hidden bg-muted/10">
                <button
                  type="button"
                  onClick={() => setShowPosicaoInicial(!showPosicaoInicial)}
                  className="w-full flex items-center justify-between px-4 py-3 bg-muted/20 hover:bg-muted/30 transition-colors text-xs font-bold uppercase tracking-wider text-muted-foreground"
                >
                  <span className="flex items-center gap-1.5">
                    <TrendingUp className="h-3.5 w-3.5 text-muted-foreground" />
                    Estabelecer Posição Inicial (Opcional)
                  </span>
                  <span>{showPosicaoInicial ? 'Recolher [-]' : 'Expandir [+]'}</span>
                </button>

                {showPosicaoInicial && (
                  <div className="p-4 space-y-4 border-t border-border/60 bg-card">
                    <p className="text-[11px] text-muted-foreground leading-relaxed">
                      Informe suas cotas iniciais para preencher o saldo inicial. Isso registrará automaticamente uma transação de compra inicial no histórico.
                    </p>
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                      <div className="space-y-1.5">
                        <label className="text-[10px] font-bold text-muted-foreground uppercase tracking-wider">Quantidade</label>
                        <Input
                          type="number"
                          step="any"
                          min="0.0001"
                          placeholder="Ex: 100"
                          value={formData.quantidade_inicial}
                          onChange={(e) => setFormData({ ...formData, quantidade_inicial: e.target.value })}
                        />
                      </div>

                      <div className="space-y-1.5">
                        <label className="text-[10px] font-bold text-muted-foreground uppercase tracking-wider">P. Unitário (R$)</label>
                        <Input
                          type="number"
                          step="any"
                          min="0.01"
                          placeholder="Ex: 34.50"
                          value={formData.preco_medio_inicial}
                          onChange={(e) => setFormData({ ...formData, preco_medio_inicial: e.target.value })}
                          className="font-semibold"
                        />
                      </div>

                      <div className="space-y-1.5">
                        <label className="text-[10px] font-bold text-muted-foreground uppercase tracking-wider">Data de Aquisição</label>
                        <Input
                          type="date"
                          value={formData.data_compra}
                          onChange={(e) => setFormData({ ...formData, data_compra: e.target.value })}
                        />
                      </div>
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* Switch de Ativo/Inativo (Só na Edição) */}
            {isEdit && (
              <div className="flex items-center justify-between p-4 rounded-xl border border-border/60 bg-muted/10">
                <div>
                  <span className="text-xs font-bold text-foreground flex items-center gap-1.5">
                    <Archive className="h-4 w-4 text-muted-foreground" />
                    Arquivar Ativo
                  </span>
                  <span className="text-[10px] text-muted-foreground mt-0.5 block">
                    Mantenha ativos liquidados salvos ativando esta caixa para não distorcer o balanceamento ativo.
                  </span>
                </div>
                <label className="relative inline-flex items-center cursor-pointer">
                  <input 
                    type="checkbox" 
                    checked={!formData.ativo}
                    onChange={(e) => setFormData({ ...formData, ativo: !e.target.checked })}
                    className="sr-only peer"
                  />
                  <div className="w-11 h-6 bg-slate-200 peer-focus:outline-none dark:bg-slate-700 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-slate-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-primary" />
                </label>
              </div>
            )}

            {/* Footer Buttons */}
            <div className="flex justify-end gap-3 pt-4 border-t border-border/60">
              <Button
                variant="outline"
                type="button"
                onClick={() => navigate('/investimentos/ativos')}
                disabled={isPending}
                className="rounded-xl"
              >
                Cancelar
              </Button>
              <Button
                type="submit"
                disabled={isPending}
                className="bg-primary hover:bg-primary/95 text-primary-foreground border-0 font-bold rounded-xl"
              >
                {isPending ? (
                  <RefreshCw className="mr-2 h-4 w-4 animate-spin" />
                ) : (
                  <Save className="mr-1.5 h-4 w-4" />
                )}
                {isEdit ? 'Salvar Alterações' : 'Cadastrar Ativo'}
              </Button>
            </div>

          </form>
        </CardContent>
      </Card>
    </div>
  );
}
