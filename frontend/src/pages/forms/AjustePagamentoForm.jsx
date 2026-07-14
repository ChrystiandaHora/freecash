import React, { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { ArrowLeft, Loader2, Save, Plus, CreditCard, Wallet, Building2, Landmark, Coins, Check } from 'lucide-react';

import api from '../../services/api';
import { fetchContaBancaria } from '../../services/financeiro';
import { Button } from '../../components/ui/Button';
import { Input } from '../../components/ui/Input';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/Card';

const BANDEIRAS = [
  { value: 'VISA', label: 'Visa' },
  { value: 'MASTERCARD', label: 'Mastercard' },
  { value: 'ELO', label: 'Elo' },
  { value: 'AMEX', label: 'American Express' },
  { value: 'HIPERCARD', label: 'Hipercard' },
  { value: 'DINERS', label: 'Diners Club' },
  { value: 'OUTRO', label: 'Outro' },
];

const PRESET_COLORS = [
  { label: 'Nubank Roxo', value: '#820ad1' },
  { label: 'Inter Laranja', value: '#ff7a00' },
  { label: 'C6 Cinza', value: '#4a4a4a' },
  { label: 'Itaú Laranja', value: '#ec7000' },
  { label: 'Bradesco Vermelho', value: '#cc092f' },
  { label: 'BB Amarelo', value: '#f9dc2e' },
  { label: 'Caixa Azul', value: '#006caf' },
  { label: 'Santander Vermelho', value: '#ec0000' },
  { label: 'XP Verde', value: '#00b14f' },
  { label: 'Mercado Pago Azul', value: '#009ee3' },
  { label: 'PicPay Verde', value: '#21c25e' },
  { label: 'Padrão', value: '#6366f1' },
];

const ICONES = [
  { value: 'CreditCard', label: 'Cartão', Icon: CreditCard },
  { value: 'Wallet', label: 'Carteira', Icon: Wallet },
  { value: 'Building2', label: 'Banco', Icon: Building2 },
  { value: 'Landmark', label: 'Caixa', Icon: Landmark },
  { value: 'Coins', label: 'Moedas', Icon: Coins },
];

const IconMap = { CreditCard, Wallet, Building2, Landmark, Coins };

const EMPTY_FORM = {
  nome: '',
  bandeira: 'VISA',
  ultimos_digitos: '',
  limite: '',
  dia_fechamento: 1,
  dia_vencimento: 10,
  ativo: true,
  cor: '#6366f1',
  icone: 'CreditCard',
};

export default function AjustePagamentoForm() {
  const { id } = useParams();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const isEdit = !!id;

  const [form, setForm] = useState(EMPTY_FORM);
  const [error, setError] = useState('');

  // Fetch the account if in edit mode
  const { data: conta, isLoading: isFetching } = useQuery({
    queryKey: ['conta-bancaria', id],
    queryFn: () => fetchContaBancaria(id),
    enabled: isEdit,
  });

  useEffect(() => {
    if (conta) {
      setForm({
        nome: conta.nome || '',
        bandeira: conta.bandeira || 'VISA',
        ultimos_digitos: conta.ultimos_digitos || '',
        limite: conta.limite || '',
        dia_fechamento: conta.dia_fechamento ?? 1,
        dia_vencimento: conta.dia_vencimento ?? 10,
        ativo: conta.ativo ?? true,
        cor: conta.cor || '#6366f1',
        icone: conta.icone || 'CreditCard',
      });
    }
  }, [conta]);

  const createMutation = useMutation({
    mutationFn: (data) => api.post('/api/configuracoes/contas-bancarias/', data).then(r => r.data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['contas-bancarias'] });
      navigate('/pagamentos');
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, ...data }) => api.put(`/api/configuracoes/contas-bancarias/${id}/`, data).then(r => r.data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['contas-bancarias'] });
      navigate('/pagamentos');
    },
  });

  const handleChange = (e) => {
    const { name, value, type, checked } = e.target;
    setForm((prev) => ({ ...prev, [name]: type === 'checkbox' ? checked : value }));
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!form.nome.trim()) {
      setError('O nome é obrigatório.');
      return;
    }

    const payload = {
      nome: form.nome,
      bandeira: form.bandeira,
      ultimos_digitos: form.ultimos_digitos,
      limite: form.limite || null,
      dia_fechamento: parseInt(form.dia_fechamento) || 1,
      dia_vencimento: parseInt(form.dia_vencimento) || 10,
      ativo: form.ativo,
      cor: form.cor,
      icone: form.icone,
    };

    if (isEdit) {
      updateMutation.mutate({ id, ...payload });
    } else {
      createMutation.mutate(payload);
    }
  };

  if (isEdit && isFetching) {
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
          onClick={() => navigate('/pagamentos')}
          className="rounded-lg p-2 text-muted-foreground hover:bg-muted hover:text-foreground transition-colors"
          title="Voltar"
        >
          <ArrowLeft className="h-5 w-5" />
        </button>
        <div>
          <h2 className="text-2xl font-bold tracking-tight text-foreground">
            {isEdit ? 'Editar Cartão / Conta' : 'Novo Cartão / Conta'}
          </h2>
          <p className="text-sm text-muted-foreground">
            {isEdit ? 'Altere os dados da forma de pagamento' : 'Preencha os dados da nova forma de pagamento'}
          </p>
        </div>
      </div>

      {/* Card Form */}
      <Card className="border-border/60 shadow-lg">
        <CardHeader className="bg-muted/10 pb-4">
          <CardTitle className="text-sm font-semibold uppercase tracking-wider text-muted-foreground">
            Configurações Estéticas & Dados
          </CardTitle>
        </CardHeader>
        <CardContent className="p-6">
          <form onSubmit={handleSubmit} className="space-y-6">
            {/* Nome */}
            <div className="space-y-1.5">
              <label className="text-sm font-medium text-foreground">
                Nome <span className="text-red-500">*</span>
              </label>
              <Input
                id="input-nome-conta"
                name="nome"
                value={form.nome}
                onChange={handleChange}
                placeholder="Ex: Nubank, Inter, Itaú..."
                required
              />
              {error && <p className="text-xs text-red-500">{error}</p>}
            </div>

            {/* Bandeira + Últimos dígitos */}
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <div className="space-y-1.5">
                <label className="text-sm font-medium text-foreground">
                  Bandeira
                </label>
                <select
                  id="select-bandeira"
                  name="bandeira"
                  value={form.bandeira}
                  onChange={handleChange}
                  className="w-full h-10 px-3 rounded-lg border border-input bg-background text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-primary/40"
                >
                  {BANDEIRAS.map((b) => (
                    <option key={b.value} value={b.value}>{b.label}</option>
                  ))}
                </select>
              </div>

              <div className="space-y-1.5">
                <label className="text-sm font-medium text-foreground">
                  Últimos 4 dígitos
                </label>
                <Input
                  id="input-ultimos-digitos"
                  name="ultimos_digitos"
                  value={form.ultimos_digitos}
                  onChange={handleChange}
                  placeholder="0000"
                  maxLength={4}
                />
              </div>
            </div>

            {/* Limite + Fechamento + Vencimento */}
            <div className="grid grid-cols-3 gap-3">
              <div className="space-y-1.5">
                <label className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                  Limite (R$)
                </label>
                <Input
                  id="input-limite"
                  name="limite"
                  type="number"
                  value={form.limite}
                  onChange={handleChange}
                  placeholder="0,00"
                  step="0.01"
                  min="0"
                />
              </div>
              <div className="space-y-1.5">
                <label className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                  Fechamento
                </label>
                <Input
                  id="input-fechamento"
                  name="dia_fechamento"
                  type="number"
                  value={form.dia_fechamento}
                  onChange={handleChange}
                  min="1"
                  max="31"
                />
              </div>
              <div className="space-y-1.5">
                <label className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                  Vencimento
                </label>
                <Input
                  id="input-vencimento"
                  name="dia_vencimento"
                  type="number"
                  value={form.dia_vencimento}
                  onChange={handleChange}
                  min="1"
                  max="31"
                />
              </div>
            </div>

            {/* Ícone */}
            <div className="space-y-2">
              <label className="text-sm font-medium text-foreground">
                Ícone
              </label>
              <div className="flex gap-2 flex-wrap">
                {ICONES.map(({ value, label, Icon }) => (
                  <button
                    key={value}
                    type="button"
                    onClick={() => setForm((prev) => ({ ...prev, icone: value }))}
                    title={label}
                    className={`flex flex-col items-center gap-1 p-2.5 rounded-xl border transition-all ${
                      form.icone === value
                        ? 'border-primary bg-primary/10 text-primary'
                        : 'border-border bg-background text-muted-foreground hover:border-primary/50'
                    }`}
                  >
                    <Icon className="h-5 w-5" />
                    <span className="text-[10px] font-medium">{label}</span>
                  </button>
                ))}
              </div>
            </div>

            {/* Cor */}
            <div className="space-y-2">
              <label className="text-sm font-medium text-foreground">
                Cor de Identificação
              </label>
              <div className="flex flex-wrap gap-2">
                {PRESET_COLORS.map(({ value, label }) => (
                  <button
                    key={value}
                    type="button"
                    onClick={() => setForm((prev) => ({ ...prev, cor: value }))}
                    title={label}
                    className={`w-8 h-8 rounded-full border-2 transition-all hover:scale-110 ${
                      form.cor === value
                        ? 'border-slate-800 dark:border-white scale-110 shadow-md'
                        : 'border-transparent'
                    }`}
                    style={{ backgroundColor: value }}
                  />
                ))}
                {/* Custom Color Picker */}
                <label title="Cor personalizada" className="relative w-8 h-8 rounded-full border-2 border-dashed border-border cursor-pointer flex items-center justify-center hover:border-primary transition-colors bg-background">
                  <input
                    type="color"
                    value={form.cor}
                    onChange={(e) => setForm((prev) => ({ ...prev, cor: e.target.value }))}
                    className="absolute inset-0 w-full h-full opacity-0 cursor-pointer rounded-full"
                  />
                  <Plus className="h-3.5 w-3.5 text-muted-foreground" />
                </label>
              </div>

              {/* Preview */}
              <div
                className="mt-4 flex items-center gap-3 p-4 rounded-xl border transition-all"
                style={{ borderLeftColor: form.cor, borderLeftWidth: 4, backgroundColor: `${form.cor}10` }}
              >
                {React.createElement(IconMap[form.icone] || CreditCard, {
                  className: 'h-5 w-5 shrink-0',
                  style: { color: form.cor },
                })}
                <span className="text-sm font-semibold" style={{ color: form.cor }}>
                  {form.nome || 'Nome do cartão'}
                </span>
              </div>
            </div>

            {/* Actions */}
            <div className="flex justify-end gap-3 pt-4 border-t border-border/60">
              <Button
                variant="outline"
                type="button"
                onClick={() => navigate('/pagamentos')}
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
                {isSaving ? 'Salvando...' : 'Salvar'}
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
