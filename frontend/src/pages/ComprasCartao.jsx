/**
 * Tela de Gerenciamento de Compras do Cartão de Crédito.
 * 
 * Permite:
 * 1. Importar e conciliar faturas em PDF (Santander/Nubank).
 * 2. Visualizar histórico completo de compras individuais lançadas no cartão, com busca e filtros.
 * 3. Editar e excluir compras individuais de cartão diretamente no sistema via Modais.
 *
 * @component
 * @returns {React.JSX.Element}
 */
import { useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useDropzone } from 'react-dropzone';
import {
  CheckCircle2,
  Search,
  ChevronDown,
  ChevronUp,
  Loader2,
  RefreshCw,
  AlertCircle,
  FileText,
  UploadCloud,
  X,
  Edit,
  Trash2,
  Calendar,
  DollarSign,
  Plus,
  FileSpreadsheet
} from 'lucide-react';
import api from '../services/api';
import { Button } from '../components/ui/Button';
import { Select } from '../components/ui/Select';
import { Input } from '../components/ui/Input';
import { Modal } from '../components/ui/Modal';
import { Badge } from '../components/ui/Badge';
import { Alert } from '../components/ui/Alert';

const fetchComprasCartao = async (params = {}) => {
  const query = new URLSearchParams();
  if (params.cartao_uuid) query.set('cartao_uuid', params.cartao_uuid);
  if (params.mes) query.set('mes', params.mes);
  if (params.ano) query.set('ano', params.ano);
  const qs = query.toString() ? `?${query.toString()}` : '';
  const res = await api.get(`/api/financeiro/compras-cartao/${qs}`);
  return res.data;
};

const fetchCategorias = async () => {
  const res = await api.get('/api/categorias/');
  return res.data;
};

function formatDate(dateStr) {
  if (!dateStr) return '—';
  const [y, m, d] = dateStr.split('-');
  return `${d}/${m}/${y}`;
}

function formatCurrency(value) {
  return new Intl.NumberFormat('pt-BR', {
    style: 'currency',
    currency: 'BRL',
  }).format(parseFloat(value) || 0);
}

export default function ComprasCartao() {
  const queryClient = useQueryClient();
  const navigate = useNavigate();

  // Upload states
  const [selectedCard, setSelectedCard] = useState('');
  const [selectedBank, setSelectedBank] = useState('santander');
  const [selectedFile, setSelectedFile] = useState(null);
  const [isUploadPanelOpen, setIsUploadPanelOpen] = useState(false);
  const [uploadResult, setUploadResult] = useState(null);

  // Historico filters states
  const [searchTerm, setSearchTerm] = useState('');
  const [cardFilter, setCardFilter] = useState('');

  // Delete Modal states
  const [deletingId, setDeletingId] = useState(null);
  const [isDeleteModalOpen, setIsDeleteModalOpen] = useState(false);

  // Queries
  const { data: cartoesData } = useQuery({
    queryKey: ['cartoes'],
    queryFn: async () => {
      const res = await api.get('/api/financeiro/cartoes/');
      return res.data;
    }
  });
  const cartoes = cartoesData || [];

  const { data: contasData, isLoading: isContasLoading, isError: isContasError, refetch: refetchContas } = useQuery({
    queryKey: ['compras-cartao', cardFilter],
    queryFn: () => fetchComprasCartao({ cartao_uuid: cardFilter || undefined }),
  });
  const contas = contasData || [];

  const { data: categoriasData } = useQuery({
    queryKey: ['categorias'],
    queryFn: () => fetchCategorias(),
  });
  const categorias = (categoriasData || []).filter(cat => cat.tipo === 'D');

  // Mutations
  const importarExtratoMutation = useMutation({
    mutationFn: async ({ file, cartao, banco }) => {
      const formData = new FormData();
      formData.append('arquivo', file);
      formData.append('cartao', cartao);
      formData.append('banco', banco);
      const res = await api.post('/api/ferramentas/importar-extrato/', formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });
      return res.data;
    },
    onSuccess: (data) => {
      setUploadResult({ tipo: 'sucesso', msg: data.msg || 'Fatura processada com sucesso!' });
      setSelectedFile(null);
      queryClient.invalidateQueries({ queryKey: ['compras-cartao'] });
      queryClient.invalidateQueries({ queryKey: ['cartoes'] });
      queryClient.invalidateQueries({ queryKey: ['contas-pagar'] });
      setTimeout(() => setUploadResult(null), 5000);
    },
    onError: (error) => {
      const msg = error?.response?.data?.erro || 'Erro ao processar fatura.';
      setUploadResult({ tipo: 'erro', msg });
    }
  });



  // Upload dropzone handlers
  const onDrop = useCallback((acceptedFiles) => {
    if (acceptedFiles && acceptedFiles.length > 0) {
      setSelectedFile(acceptedFiles[0]);
      setUploadResult(null);
    }
  }, []);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: { 'application/pdf': ['.pdf'] },
    maxFiles: 1,
    multiple: false,
  });

  const handleOpenEditModal = (purchase) => {
    navigate(`/compras-cartao/editar/${purchase.id}`);
  };

  const handleOpenDeleteModal = (id) => {
    setDeletingId(id);
    setIsDeleteModalOpen(true);
  };

  const handleConfirmDelete = () => {
    if (deletingId) {
      deletePurchaseMutation.mutate(deletingId);
    }
  };

  const handleOpenAddModal = () => {
    navigate('/compras-cartao/novo');
  };

  // Filter purchases
  const filteredPurchases = contas.filter(p => {
    const matchesSearch = !searchTerm ||
      p.descricao?.toLowerCase().includes(searchTerm.toLowerCase()) ||
      p.categoria_detalhe?.nome?.toLowerCase().includes(searchTerm.toLowerCase());
    return matchesSearch;
  });

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-3xl font-extrabold tracking-tight text-foreground">
            Compras Cartão
          </h1>
          <p className="text-slate-500 dark:text-slate-400 mt-1">
            Importe faturas e gerencie todas as compras individuais dos seus cartões
          </p>
        </div>
        <div className="flex items-center gap-3 self-start sm:self-center shrink-0">
          <Button
            id="btn-nova-compra"
            onClick={handleOpenAddModal}
            className="gap-2 font-semibold"
          >
            <Plus className="h-4 w-4" />
            Nova Compra
          </Button>
          <Button
            id="btn-atualizar-compras"
            variant="outline"
            onClick={() => refetchContas()}
            disabled={isContasLoading}
            className="gap-2"
          >
            <RefreshCw className={`h-4 w-4 ${isContasLoading ? 'animate-spin' : ''}`} />
            Atualizar
          </Button>
        </div>
      </div>

      {/* Upload Fatura Card */}
      <div className="rounded-2xl border border-border/40 bg-card overflow-hidden shadow-sm">
        <div 
          className="flex items-center justify-between p-4 cursor-pointer hover:bg-muted/40 transition-colors"
          onClick={() => setIsUploadPanelOpen(!isUploadPanelOpen)}
        >
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-primary/10 flex items-center justify-center">
              <UploadCloud className="h-4 w-4 text-primary" />
            </div>
            <div>
              <p className="font-semibold text-foreground text-sm">
                Importar Nova Fatura em PDF
              </p>
              <p className="text-xs text-muted-foreground mt-0.5">
                Extraia compras de faturas do Santander ou Nubank diretamente para o histórico do cartão
              </p>
            </div>
          </div>
          {isUploadPanelOpen ? (
            <ChevronUp className="h-4 w-4 text-muted-foreground" />
          ) : (
            <ChevronDown className="h-4 w-4 text-muted-foreground" />
          )}
        </div>

        {isUploadPanelOpen && (
          <div className="p-5 border-t border-border/40 bg-card/50 space-y-4">
            <div className="grid sm:grid-cols-2 gap-4">
              <div className="space-y-1.5">
                <label className="text-xs font-bold uppercase tracking-wider text-muted-foreground">
                  Cartão de Crédito
                </label>
                <Select
                  value={selectedCard}
                  onChange={(e) => setSelectedCard(e.target.value)}
                >
                  <option value="">Selecione um cartão...</option>
                  {cartoes.map((c) => (
                    <option key={c.uuid} value={c.uuid}>
                      {c.nome} ({c.bandeira}) - Final {c.final}
                    </option>
                  ))}
                </Select>
              </div>

              <div className="space-y-1.5">
                <label className="text-xs font-bold uppercase tracking-wider text-muted-foreground">
                  Tipo de Fatura / Banco
                </label>
                <Select
                  value={selectedBank}
                  onChange={(e) => setSelectedBank(e.target.value)}
                >
                  <option value="santander">Santander (Layout Colunas)</option>
                  <option value="nubank">Nubank (Layout DD MMM)</option>
                  <option value="generico">Genérico (Fallback)</option>
                </Select>
              </div>
            </div>

            {/* Dropzone */}
            <div
              {...getRootProps()}
              className={`
                relative flex flex-col items-center justify-center gap-3 rounded-xl
                border-2 border-dashed p-6 text-center cursor-pointer transition-all duration-300
                ${isDragActive
                  ? 'border-primary bg-primary/5 dark:bg-primary/10'
                  : 'border-border bg-card hover:border-primary/50 hover:bg-primary/5 dark:hover:bg-primary/10'
                }
                ${selectedFile ? 'border-primary/60 bg-primary/5' : ''}
              `}
            >
              <input {...getInputProps()} />

              {selectedFile ? (
                <div className="flex flex-col items-center gap-2">
                  <FileSpreadsheet className="h-8 w-8 text-primary" />
                  <div>
                    <p className="text-sm font-semibold text-foreground">
                      {selectedFile.name}
                    </p>
                    <p className="text-xs text-muted-foreground">
                      {(selectedFile.size / 1024).toFixed(1)} KB
                    </p>
                  </div>
                  <button
                    type="button"
                    onClick={(e) => {
                      e.stopPropagation();
                      setSelectedFile(null);
                    }}
                    className="flex items-center gap-1 text-xs text-red-500 hover:text-red-600 transition-colors mt-1"
                  >
                    <X className="h-3.5 w-3.5" />
                    Remover arquivo
                  </button>
                </div>
              ) : (
                <div className="flex flex-col items-center gap-2">
                  <UploadCloud className="h-8 w-8 text-muted-foreground" />
                  <p className="text-sm font-semibold text-foreground">
                    {isDragActive ? 'Solte o arquivo PDF aqui' : 'Arraste e solte o PDF da fatura'}
                  </p>
                  <p className="text-xs text-muted-foreground">
                    ou clique para selecionar o arquivo
                  </p>
                </div>
              )}
            </div>

            {uploadResult && (
              <Alert
                variant={uploadResult.tipo === 'sucesso' ? 'success' : 'error'}
                icon={uploadResult.tipo === 'sucesso' ? CheckCircle2 : AlertCircle}
              >
                {uploadResult.msg}
              </Alert>
            )}

            <Button
              className="w-full gap-2"
              disabled={!selectedFile || !selectedCard || importarExtratoMutation.isPending}
              onClick={() => {
                importarExtratoMutation.mutate({
                  file: selectedFile,
                  cartao: selectedCard,
                  banco: selectedBank
                });
              }}
            >
              {importarExtratoMutation.isPending ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Processando Fatura...
                </>
              ) : (
                <>
                  <UploadCloud className="h-4 w-4" />
                  Processar Fatura
                </>
              )}
            </Button>
          </div>
        )}
      </div>

      {/* Filters Bar */}
      <div className="flex flex-col sm:flex-row gap-4 bg-card p-4 rounded-xl border border-border/40 shadow-sm">
        <div className="relative flex-grow">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input
            type="text"
            placeholder="Buscar por descrição ou categoria..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="pl-9"
          />
        </div>
        <div className="w-full sm:w-64">
          <Select
            value={cardFilter}
            onChange={(e) => setCardFilter(e.target.value)}
          >
            <option value="">Todos os Cartões</option>
            {cartoes.map((c) => (
              <option key={c.uuid} value={c.uuid}>
                {c.nome} (Final {c.final})
              </option>
            ))}
          </Select>
        </div>
      </div>

      {/* Loading / Error states */}
      {isContasLoading && (
        <div className="flex items-center justify-center py-16">
          <Loader2 className="h-8 w-8 animate-spin text-primary" />
        </div>
      )}

      {isContasError && (
        <Alert variant="error" icon={AlertCircle}>
          Erro ao carregar histórico de compras do cartão. Verifique a conexão com o servidor.
        </Alert>
      )}

      {!isContasLoading && !isContasError && filteredPurchases.length === 0 && (
        <div className="flex flex-col items-center justify-center py-20 text-center border border-dashed border-border/60 rounded-2xl bg-card/40">
          <div className="w-14 h-14 rounded-full bg-slate-100 dark:bg-slate-900 flex items-center justify-center mb-3">
            <Search className="h-6 w-6 text-slate-400" />
          </div>
          <h3 className="text-base font-semibold text-slate-700 dark:text-slate-200 mb-1">
            Nenhuma compra encontrada
          </h3>
          <p className="text-xs text-slate-500 dark:text-slate-400 max-w-sm">
            Tente redefinir seus filtros ou concilie lançamentos para povoar o histórico.
          </p>
        </div>
      )}

      {/* Purchases List */}
      {!isContasLoading && !isContasError && filteredPurchases.length > 0 && (
        <div className="rounded-2xl border border-border/40 bg-card overflow-hidden shadow-sm">
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="border-b border-border/40 bg-muted/50 text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                  <th className="px-4 py-3">Descrição</th>
                  <th className="px-4 py-3">Cartão</th>
                  <th className="px-4 py-3">Categoria</th>
                  <th className="px-4 py-3 text-right">Data Compra</th>
                  <th className="px-4 py-3 text-right">Fatura (Venc.)</th>
                  <th className="px-4 py-3 text-right">Valor</th>
                  <th className="px-4 py-3 text-center">Status</th>
                  <th className="px-4 py-3 text-center">Ações</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border/30">
                {filteredPurchases.map((p) => (
                  <tr key={p.id} className="hover:bg-muted/30 transition-colors text-sm">
                    <td className="px-4 py-3 font-medium text-foreground truncate max-w-xs">
                      {p.descricao}
                    </td>
                    <td className="px-4 py-3 text-xs text-muted-foreground">
                      {p.cartao_detalhe?.nome || '—'}
                    </td>
                    <td className="px-4 py-3">
                      <span className="inline-block text-xs px-2 py-0.5 rounded bg-muted text-muted-foreground font-medium">
                        {p.categoria_detalhe?.nome || 'default'}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-right text-xs text-muted-foreground">
                      {p.data_compra ? formatDate(p.data_compra) : '—'}
                    </td>
                    <td className="px-4 py-3 text-right text-xs text-muted-foreground">
                      {formatDate(p.data_prevista)}
                    </td>
                    <td className="px-4 py-3 text-right font-semibold text-red-500 dark:text-red-400">
                      {formatCurrency(p.valor)}
                    </td>
                    <td className="px-4 py-3 text-center">
                      {p.transacao_realizada ? (
                        <Badge variant="success">Pago</Badge>
                      ) : (
                        <Badge variant="secondary">Pendente</Badge>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex items-center justify-center gap-2">
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-8 w-8 rounded-lg hover:bg-primary/10 hover:text-primary text-muted-foreground"
                          onClick={() => handleOpenEditModal(p)}
                          title="Editar compra"
                        >
                          <Edit className="h-4 w-4" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-8 w-8 rounded-lg hover:bg-red-500/10 hover:text-red-500 text-muted-foreground"
                          onClick={() => handleOpenDeleteModal(p.id)}
                          title="Excluir compra"
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* ───────────────── MODAL: CONFIRMAR EXCLUSÃO ───────────────── */}
      <Modal
        isOpen={isDeleteModalOpen}
        onClose={() => {
          setIsDeleteModalOpen(false);
          setDeletingId(null);
        }}
        title="Confirmar Exclusão"
        description="Tem certeza que deseja excluir esta compra permanentemente? Essa ação não pode ser desfeita."
        size="sm"
      >
        <div className="flex justify-end gap-3 mt-4">
          <Button
            variant="outline"
            onClick={() => {
              setIsDeleteModalOpen(false);
              setDeletingId(null);
            }}
            disabled={deletePurchaseMutation.isPending}
          >
            Cancelar
          </Button>
          <Button
            variant="destructive"
            onClick={handleConfirmDelete}
            disabled={deletePurchaseMutation.isPending}
            className="gap-2"
          >
            {deletePurchaseMutation.isPending && <Loader2 className="h-4 w-4 animate-spin" />}
            Excluir Permanente
          </Button>
        </div>
      </Modal>
    </div>
  );
}
