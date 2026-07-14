import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { ArrowLeft, Loader2, Save, DollarSign, Calendar, CreditCard, Tag } from 'lucide-react';

import api from '../../services/api';
import { fetchCompraCartao } from '../../services/financeiro';
import { Button } from '../../components/ui/Button';
import { Input } from '../../components/ui/Input';
import { Select } from '../../components/ui/Select';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/Card';

export default function CompraCartaoForm() {
  const { id } = useParams();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const isEdit = !!id;

  const [desc, setDesc] = useState('');
  const [value, setValue] = useState('');
  const [date, setDate] = useState('');
  const [cardId, setCardId] = useState('');
  const [categoryId, setCategoryId] = useState('');
  const [validationError, setValidationError] = useState('');

  // Fetch single purchase if editing
  const { data: purchase, isLoading: isFetchingPurchase } = useQuery({
    queryKey: ['compra-cartao', id],
    queryFn: () => fetchCompraCartao(id),
    enabled: isEdit,
  });

  // Fetch cards
  const { data: cartoes = [] } = useQuery({
    queryKey: ['cartoes'],
    queryFn: async () => {
      const res = await api.get('/api/financeiro/cartoes/');
      return res.data;
    },
  });

  // Fetch categories
  const { data: categorias = [] } = useQuery({
    queryKey: ['categorias'],
    queryFn: async () => {
      const res = await api.get('/api/categorias/');
      return res.data;
    },
  });

  useEffect(() => {
    if (isEdit && purchase) {
      setDesc(purchase.descricao || '');
      setValue(purchase.valor || '');
      setDate(purchase.data_compra || '');
      setCardId(purchase.cartao || '');
      setCategoryId(purchase.categoria || '');
    } else if (!isEdit) {
      // Set today as default date
      setDate(new Date().toISOString().split('T')[0]);
    }
  }, [purchase, isEdit]);

  const createMutation = useMutation({
    mutationFn: async (payload) => {
      const res = await api.post('/api/financeiro/compras-cartao/', payload);
      return res.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['compras-cartao'] });
      queryClient.invalidateQueries({ queryKey: ['cartoes'] });
      queryClient.invalidateQueries({ queryKey: ['contas-pagar'] });
      navigate('/compras-cartao');
    },
    onError: (err) => {
      const msg = err?.response?.data?.detail || err?.response?.data?.erro || err.message;
      setValidationError('Erro ao cadastrar compra: ' + msg);
    }
  });

  const updateMutation = useMutation({
    mutationFn: async (payload) => {
      const { id, ...data } = payload;
      const res = await api.put(`/api/financeiro/compras-cartao/${id}/`, data);
      return res.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['compras-cartao'] });
      queryClient.invalidateQueries({ queryKey: ['cartoes'] });
      queryClient.invalidateQueries({ queryKey: ['contas-pagar'] });
      navigate('/compras-cartao');
    },
    onError: (err) => {
      const msg = err?.response?.data?.detail || err?.response?.data?.erro || err.message;
      setValidationError('Erro ao atualizar compra: ' + msg);
    }
  });

  const handleSubmit = (e) => {
    e.preventDefault();
    setValidationError('');

    if (!desc || !value || !date || !cardId) {
      setValidationError('Por favor, preencha todos os campos obrigatórios.');
      return;
    }

    const payload = {
      tipo: 'D',
      descricao: desc,
      valor: parseFloat(value),
      data_compra: date,
      cartao: parseInt(cardId),
      categoria: categoryId ? parseInt(categoryId) : null,
    };

    if (isEdit) {
      updateMutation.mutate({ id, ...payload });
    } else {
      createMutation.mutate(payload);
    }
  };

  if (isEdit && isFetchingPurchase) {
    return (
      <div className="flex h-96 items-center justify-center">
        <Loader2 className="h-8 w-8 text-primary animate-spin" />
      </div>
    );
  }

  const isSaving = createMutation.isPending || updateMutation.isPending;

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      {/* Header */}
      <div className="flex items-center gap-4">
        <button
          onClick={() => navigate('/compras-cartao')}
          className="rounded-lg p-2 text-muted-foreground hover:bg-muted hover:text-foreground transition-colors"
          title="Voltar"
        >
          <ArrowLeft className="h-5 w-5" />
        </button>
        <div>
          <h2 className="text-2xl font-bold tracking-tight text-foreground">
            {isEdit ? 'Editar Compra do Cartão' : 'Nova Compra do Cartão'}
          </h2>
          <p className="text-sm text-muted-foreground">
            {isEdit ? 'Ajuste os dados da compra individual.' : 'Cadastre uma nova compra individual de cartão de crédito.'}
          </p>
        </div>
      </div>

      {/* Card Form */}
      <Card className="border-border/60 shadow-lg">
        <CardHeader className="bg-muted/10 pb-4">
          <CardTitle className="text-sm font-semibold uppercase tracking-wider text-muted-foreground">
            Dados da Compra
          </CardTitle>
        </CardHeader>
        <CardContent className="p-6">
          <form onSubmit={handleSubmit} className="space-y-6">
            
            {/* Descrição */}
            <div className="space-y-1.5">
              <label className="text-sm font-medium text-foreground">
                Descrição <span className="text-red-500">*</span>
              </label>
              <Input
                type="text"
                required
                placeholder="Ex: Supermercado"
                value={desc}
                onChange={(e) => setDesc(e.target.value)}
              />
            </div>

            {/* Valor + Data da Compra */}
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <div className="space-y-1.5">
                <label className="text-sm font-medium text-foreground">
                  Valor (R$) <span className="text-red-500">*</span>
                </label>
                <div className="relative">
                  <DollarSign className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                  <Input
                    type="number"
                    step="0.01"
                    required
                    placeholder="0,00"
                    value={value}
                    onChange={(e) => setValue(e.target.value)}
                    className="pl-9"
                  />
                </div>
              </div>

              <div className="space-y-1.5">
                <label className="text-sm font-medium text-foreground">
                  Data da Compra <span className="text-red-500">*</span>
                </label>
                <div className="relative">
                  <Calendar className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                  <Input
                    type="date"
                    required
                    value={date}
                    onChange={(e) => setDate(e.target.value)}
                    className="pl-9"
                  />
                </div>
              </div>
            </div>

            {/* Cartão de Crédito + Categoria */}
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <div className="space-y-1.5">
                <label className="text-sm font-medium text-foreground">
                  Cartão de Crédito <span className="text-red-500">*</span>
                </label>
                <Select
                  value={cardId}
                  onChange={(e) => setCardId(e.target.value)}
                  required
                >
                  <option value="">Selecione...</option>
                  {cartoes.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.nome} ({c.bandeira})
                    </option>
                  ))}
                </Select>
              </div>

              <div className="space-y-1.5">
                <label className="text-sm font-medium text-foreground">
                  Categoria
                </label>
                <Select
                  value={categoryId}
                  onChange={(e) => setCategoryId(e.target.value)}
                >
                  <option value="">Sem Categoria (default)</option>
                  {categorias.map((cat) => (
                    <option key={cat.id} value={cat.id}>
                      {cat.nome}
                    </option>
                  ))}
                </Select>
              </div>
            </div>

            {validationError && (
              <p className="text-sm text-red-500">{validationError}</p>
            )}

            {/* Actions */}
            <div className="flex justify-end gap-3 pt-4 border-t border-border/60">
              <Button
                type="button"
                variant="outline"
                onClick={() => navigate('/compras-cartao')}
                disabled={isSaving}
                className="rounded-xl"
              >
                Cancelar
              </Button>
              <Button
                type="submit"
                disabled={isSaving}
                className="bg-primary hover:bg-primary/90 text-primary-foreground border-0 rounded-xl"
              >
                {isSaving ? (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                ) : (
                  <Save className="mr-1.5 h-4 w-4" />
                )}
                Salvar Compra
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
