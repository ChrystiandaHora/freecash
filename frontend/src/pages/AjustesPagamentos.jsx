/**
 * Tela de Gerenciamento de Formas de Pagamento (Ajustes de Contas e Cartões).
 * 
 * Permite cadastrar, editar, excluir e desativar cartões de crédito e contas bancárias.
 * Oferece interface interativa para personalização estética de cartões contendo presets de cores
 * das principais instituições financeiras brasileiras (ex: Nubank, Inter, Itaú, Bradesco)
 * e seleção de ícones representativos.
 *
 * @component
 * @returns {React.JSX.Element} Painel administrativo contendo grid de cartões ativos e inativos.
 */
import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Plus,
  Pencil,
  Trash2,
  X,
  Check,
  Loader2,
  CreditCard,
  Wallet,
  Building2,
  Landmark,
  Coins,
  AlertCircle,
  RefreshCw,
  Power,
  PowerOff,
} from 'lucide-react';
import api from '../services/api';
import { Button } from '../components/ui/Button';
import { Input } from '../components/ui/Input';
import { Alert } from '../components/ui/Alert';

// ─── API helpers ───────────────────────────────────────────
const fetchContas = () =>
  api.get('/api/configuracoes/contas-bancarias/').then((r) => r.data);

const createConta = (data) =>
  api.post('/api/configuracoes/contas-bancarias/', data).then((r) => r.data);

const updateConta = ({ id, ...data }) =>
  api.put(`/api/configuracoes/contas-bancarias/${id}/`, data).then((r) => r.data);

const deleteConta = (id) =>
  api.delete(`/api/configuracoes/contas-bancarias/${id}/`).then((r) => r.data);

const toggleAtivoConta = (id) =>
  api.post(`/api/configuracoes/contas-bancarias/${id}/toggle_ativo/`).then((r) => r.data);

// ─── Palette options ──────────────────────────────────────
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

// ─── Empty form state ─────────────────────────────────────
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

// ─── CartaoCard Component ─────────────────────────────────
function CartaoCard({ conta, onEdit, onDelete, onToggleAtivo }) {
  const IconComponent = IconMap[conta.icone] || CreditCard;
  const cor = conta.cor || '#6366f1';

  return (
    <div
      className="relative flex flex-col gap-3 p-5 rounded-2xl border border-border/40 bg-card overflow-hidden transition-all hover:shadow-md hover:-translate-y-0.5"
      style={{ borderLeftColor: cor, borderLeftWidth: 4 }}
    >
      {/* Inactive Overlay */}
      {!conta.ativo && (
        <div className="absolute inset-0 bg-background/60 rounded-2xl z-10 flex items-center justify-center">
          <span className="text-xs font-bold uppercase tracking-widest text-muted-foreground bg-muted px-3 py-1 rounded-full border border-border/50">
            Desativado
          </span>
        </div>
      )}

      <div className="flex items-start gap-3">
        <div
          className="w-11 h-11 rounded-xl flex items-center justify-center shrink-0"
          style={{ backgroundColor: `${cor}20`, border: `1.5px solid ${cor}40` }}
        >
          <IconComponent className="h-5 w-5" style={{ color: cor }} />
        </div>
        <div className="flex-1 min-w-0">
          <p className="font-semibold text-foreground truncate">{conta.nome}</p>
          <p className="text-xs text-muted-foreground">
            {conta.bandeira}
            {conta.ultimos_digitos ? ` · ****${conta.ultimos_digitos}` : ''}
          </p>
        </div>
      </div>

      {(conta.limite || conta.dia_vencimento) && (
        <div className="grid grid-cols-2 gap-2 text-xs">
          {conta.limite && (
            <div className="bg-muted rounded-lg px-3 py-2">
              <p className="text-muted-foreground">Limite</p>
              <p className="font-semibold text-foreground">
                {new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(conta.limite)}
              </p>
            </div>
          )}
          {conta.dia_vencimento && (
            <div className="bg-muted rounded-lg px-3 py-2">
              <p className="text-muted-foreground">Vencimento</p>
              <p className="font-semibold text-foreground">Dia {conta.dia_vencimento}</p>
            </div>
          )}
        </div>
      )}

      {/* Actions */}
      <div className="flex gap-2 pt-1">
        <button
          id={`btn-toggle-ativo-${conta.id}`}
          onClick={() => onToggleAtivo(conta.id)}
          className={`flex-1 flex items-center justify-center gap-1.5 py-1.5 rounded-lg text-xs font-medium transition-colors
            ${conta.ativo
              ? 'text-amber-600 dark:text-amber-400 bg-amber-500/10 hover:bg-amber-500/20'
              : 'text-emerald-600 dark:text-emerald-400 bg-emerald-500/10 hover:bg-emerald-500/20'
            }
          `}
          title={conta.ativo ? 'Desativar' : 'Ativar'}
        >
          {conta.ativo ? <PowerOff className="h-3.5 w-3.5" /> : <Power className="h-3.5 w-3.5" />}
          {conta.ativo ? 'Desativar' : 'Ativar'}
        </button>
        <button
          id={`btn-editar-conta-${conta.id}`}
          onClick={() => onEdit(conta)}
          className="flex-1 flex items-center justify-center gap-1.5 py-1.5 rounded-lg text-xs font-medium text-blue-600 dark:text-blue-400 bg-blue-500/10 hover:bg-blue-500/20 transition-colors"
        >
          <Pencil className="h-3.5 w-3.5" />
          Editar
        </button>
        <button
          id={`btn-excluir-conta-${conta.id}`}
          onClick={() => onDelete(conta.id)}
          className="p-1.5 rounded-lg text-red-500 bg-red-500/10 hover:bg-red-500/20 transition-colors"
          title="Excluir"
        >
          <Trash2 className="h-3.5 w-3.5" />
        </button>
      </div>
    </div>
  );
}

// ─── Main Page ─────────────────────────────────────────────
export default function AjustesPagamentos() {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const [deleteConfirm, setDeleteConfirm] = useState(null);

  const { data: contas = [], isLoading, isError, refetch } = useQuery({
    queryKey: ['contas-bancarias'],
    queryFn: () => fetchContas(),
  });

  const deleteMutation = useMutation({
    mutationFn: deleteConta,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['contas-bancarias'] });
      setDeleteConfirm(null);
    },
  });

  const toggleAtivoMutation = useMutation({
    mutationFn: toggleAtivoConta,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['contas-bancarias'] });
    },
  });

  const handleEdit = (conta) => {
    navigate(`/pagamentos/editar/${conta.id}`);
  };

  const handleNew = () => {
    navigate('/pagamentos/novo');
  };
  const ativas = contas.filter((c) => c.ativo);
  const inativas = contas.filter((c) => !c.ativo);

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-3xl font-extrabold tracking-tight text-foreground">
            Formas de Pagamento
          </h1>
          <p className="text-slate-500 dark:text-slate-400 mt-1">
            Gerencie seus cartões e contas bancárias com cores e ícones personalizados
          </p>
        </div>
        <div className="flex gap-2 shrink-0">
          <Button
            id="btn-atualizar-contas"
            variant="outline"
            onClick={() => refetch()}
            disabled={isLoading}
            className="gap-2"
          >
            <RefreshCw className={`h-4 w-4 ${isLoading ? 'animate-spin' : ''}`} />
          </Button>
          <Button id="btn-novo-cartao" onClick={handleNew} className="gap-2">
            <Plus className="h-4 w-4" />
            Novo Cartão
          </Button>
        </div>
      </div>

      {/* Error */}
      {isError && (
        <Alert variant="error" icon={AlertCircle}>
          Erro ao carregar cartões. Verifique a conexão com o servidor.
        </Alert>
      )}

      {/* Loading */}
      {isLoading && (
        <div className="flex justify-center py-16">
          <Loader2 className="h-8 w-8 animate-spin text-primary" />
        </div>
      )}

      {/* Empty State */}
      {!isLoading && !isError && contas.length === 0 && (
        <div className="flex flex-col items-center justify-center py-20 text-center">
          <div className="w-16 h-16 rounded-2xl bg-slate-100 dark:bg-slate-900 flex items-center justify-center mb-4">
            <CreditCard className="h-8 w-8 text-slate-400" />
          </div>
          <h3 className="text-lg font-semibold text-slate-700 dark:text-slate-200 mb-1">
            Nenhum cartão ou conta cadastrado
          </h3>
          <p className="text-sm text-slate-500 dark:text-slate-400 mb-4 max-w-sm">
            Adicione seus cartões de crédito e contas bancárias para ter controle total do seu financeiro.
          </p>
          <Button id="btn-add-primeiro-cartao" onClick={handleNew} className="gap-2">
            <Plus className="h-4 w-4" />
            Adicionar Cartão
          </Button>
        </div>
      )}

      {/* Ativos */}
      {ativas.length > 0 && (
        <div className="space-y-3">
          <h2 className="text-xs font-bold uppercase tracking-widest text-slate-500 dark:text-slate-400">
            Ativos ({ativas.length})
          </h2>
          <div className="grid sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
            {ativas.map((conta) => (
              <CartaoCard
                key={conta.id}
                conta={conta}
                onEdit={handleEdit}
                onDelete={(id) => setDeleteConfirm(id)}
                onToggleAtivo={(id) => toggleAtivoMutation.mutate(id)}
              />
            ))}
          </div>
        </div>
      )}

      {/* Inativos */}
      {inativas.length > 0 && (
        <div className="space-y-3">
          <h2 className="text-xs font-bold uppercase tracking-widest text-slate-500 dark:text-slate-400">
            Desativados ({inativas.length})
          </h2>
          <div className="grid sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
            {inativas.map((conta) => (
              <CartaoCard
                key={conta.id}
                conta={conta}
                onEdit={handleEdit}
                onDelete={(id) => setDeleteConfirm(id)}
                onToggleAtivo={(id) => toggleAtivoMutation.mutate(id)}
              />
            ))}
          </div>
        </div>
      )}



      {/* Delete Confirm */}
      {deleteConfirm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-sm">
          <div className="w-full max-w-sm bg-white dark:bg-slate-900 rounded-2xl p-6 shadow-2xl border border-slate-200/50 dark:border-slate-800/50 space-y-4">
            <div className="flex items-center gap-3 text-red-600 dark:text-red-400">
              <AlertCircle className="h-6 w-6 shrink-0" />
              <h3 className="font-bold text-lg">Confirmar Exclusão</h3>
            </div>
            <p className="text-sm text-slate-600 dark:text-slate-400">
              Tem certeza que deseja excluir este cartão? Esta ação não pode ser desfeita.
            </p>
            <div className="flex gap-3">
              <Button
                id="btn-cancelar-delete"
                variant="outline"
                onClick={() => setDeleteConfirm(null)}
                className="flex-1"
              >
                Cancelar
              </Button>
              <Button
                id="btn-confirmar-delete"
                onClick={() => deleteMutation.mutate(deleteConfirm)}
                disabled={deleteMutation.isPending}
                className="flex-1 gap-2 bg-red-600 hover:bg-red-700 text-white border-red-600"
              >
                {deleteMutation.isPending ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <Trash2 className="h-4 w-4" />
                )}
                Excluir
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
