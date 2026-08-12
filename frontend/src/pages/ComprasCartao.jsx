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
  ChevronDown,
  ChevronUp,
  Loader2,
  RefreshCw,
  AlertCircle,
  UploadCloud,
  X,
  Edit,
  Trash2,
  Plus,
  FileSpreadsheet
} from 'lucide-react';
import api from '../services/api';
import { Button } from '../components/ui/Button';
import { Select } from '../components/ui/Select';
import { Modal } from '../components/ui/Modal';
import { Badge } from '../components/ui/Badge';
import { Alert } from '../components/ui/Alert';
import { DataTable } from '../components/ui/DataTable';
import { getCurrentMonthDateRange } from '../lib/utils';

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

  // Delete Modal states
  const [deletingId, setDeletingId] = useState(null);
  const [isDeleteModalOpen, setIsDeleteModalOpen] = useState(false);
  const [deleteError, setDeleteError] = useState(null);

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
    queryKey: ['compras-cartao'],
    queryFn: () => fetchComprasCartao(),
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

  const deletePurchaseMutation = useMutation({
    mutationFn: async (id) => {
      await api.delete(`/api/financeiro/compras-cartao/${id}/`);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['compras-cartao'] });
      queryClient.invalidateQueries({ queryKey: ['cartoes'] });
      queryClient.invalidateQueries({ queryKey: ['contas-pagar'] });
      setIsDeleteModalOpen(false);
      setDeletingId(null);
      setDeleteError(null);
    },
    onError: (error) => {
      setDeleteError(
        error?.response?.data?.detail || 'Erro ao excluir compra de cartão.'
      );
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
    setDeleteError(null);
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

  // ─── Colunas da tabela ─────────────────────────────────────────────────────
  const columns = [
    {
      key: 'data_compra',
      header: 'Data Compra',
      render: (val) => (
        <span className="text-xs text-muted-foreground">{val ? formatDate(val) : '—'}</span>
      ),
    },
    {
      key: 'descricao',
      header: 'Descrição',
      render: (val) => (
        <span className="font-medium text-foreground truncate max-w-xs block">{val}</span>
      ),
    },
    {
      key: 'cartao',
      header: 'Cartão',
      filterType: 'select',
      filterOptions: cartoes.map((c) => c.nome),
      filterAccessor: (row) => row.cartao_detalhe?.nome,
      render: (_, row) => (
        <span className="text-xs text-muted-foreground">{row.cartao_detalhe?.nome || '—'}</span>
      ),
    },
    {
      key: 'categoria',
      header: 'Categoria',
      filterType: 'select',
      filterOptions: categorias.map((cat) => cat.nome),
      filterAccessor: (row) => row.categoria_detalhe?.nome,
      render: (_, row) => (
        <span className="inline-block text-xs px-2 py-0.5 rounded bg-muted text-muted-foreground font-medium">
          {row.categoria_detalhe?.nome || 'default'}
        </span>
      ),
    },
    {
      key: 'data_vencimento',
      header: 'Fatura (Venc.)',
      render: (val) => (
        <span className="text-xs text-muted-foreground">{formatDate(val)}</span>
      ),
    },
    {
      key: 'valor',
      header: 'Valor',
      render: (val) => (
        <span className="font-semibold text-red-500 dark:text-red-400">{formatCurrency(val)}</span>
      ),
    },
    {
      key: 'pago',
      header: 'Status',
      filterType: 'boolean',
      filterTrueLabel: 'Pago',
      filterFalseLabel: 'Pendente',
      render: (val) =>
        val ? <Badge variant="success">Pago</Badge> : <Badge variant="secondary">Pendente</Badge>,
    },
    {
      key: 'acoes',
      header: 'Ações',
      sortable: false,
      render: (_, row) => (
        <div className="flex items-center justify-center gap-2">
          <Button
            variant="ghost"
            size="icon"
            className="h-8 w-8 rounded-lg hover:bg-primary/10 hover:text-primary text-muted-foreground"
            onClick={() => handleOpenEditModal(row)}
            title="Editar compra"
            aria-label={`Editar compra ${row.descricao}`}
          >
            <Edit className="h-4 w-4" aria-hidden="true" />
          </Button>
          <Button
            variant="ghost"
            size="icon"
            className="h-8 w-8 rounded-lg hover:bg-red-500/10 hover:text-red-500 text-muted-foreground"
            onClick={() => handleOpenDeleteModal(row.id)}
            title="Excluir compra"
            aria-label={`Excluir compra ${row.descricao}`}
          >
            <Trash2 className="h-4 w-4" aria-hidden="true" />
          </Button>
        </div>
      ),
    },
  ];

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
        {/* Botão nativo (era um div com onClick, inacessível por teclado) */}
        <button
          type="button"
          className="flex w-full items-center justify-between gap-3 p-4 text-left cursor-pointer hover:bg-muted/40 transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-inset"
          onClick={() => setIsUploadPanelOpen(!isUploadPanelOpen)}
          aria-expanded={isUploadPanelOpen}
          aria-controls="painel-importar-fatura"
        >
          <span className="flex items-center gap-3">
            <span className="w-8 h-8 rounded-lg bg-primary/10 flex items-center justify-center shrink-0">
              <UploadCloud className="h-4 w-4 text-primary" aria-hidden="true" />
            </span>
            <span className="block">
              <span className="block font-semibold text-foreground text-sm">
                Importar Nova Fatura em PDF
              </span>
              <span className="block text-xs text-muted-foreground mt-0.5">
                Extraia compras de faturas do Santander ou Nubank diretamente para o histórico do cartão
              </span>
            </span>
          </span>
          {isUploadPanelOpen ? (
            <ChevronUp className="h-4 w-4 text-muted-foreground shrink-0" aria-hidden="true" />
          ) : (
            <ChevronDown className="h-4 w-4 text-muted-foreground shrink-0" aria-hidden="true" />
          )}
        </button>

        {isUploadPanelOpen && (
          <div id="painel-importar-fatura" className="p-5 border-t border-border/40 bg-card/50 space-y-4">
            <div className="grid sm:grid-cols-2 gap-4">
              <div className="space-y-1.5">
                <label htmlFor="fatura-cartao" className="text-xs font-bold uppercase tracking-wider text-muted-foreground">
                  Cartão de Crédito
                </label>
                <Select
                  id="fatura-cartao"
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
                <label htmlFor="fatura-banco" className="text-xs font-bold uppercase tracking-wider text-muted-foreground">
                  Tipo de Fatura / Banco
                </label>
                <Select
                  id="fatura-banco"
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

      {/* Error */}
      {isContasError && (
        <Alert variant="error" icon={AlertCircle}>
          Erro ao carregar histórico de compras do cartão. Verifique a conexão com o servidor.
        </Alert>
      )}

      {/* Tabela */}
      <DataTable
        columns={columns}
        data={contas}
        isLoading={isContasLoading}
        pageSize={15}
        defaultFilters={{ data_vencimento: getCurrentMonthDateRange() }}
        emptyMessage="Nenhuma compra encontrada."
      />

      {/* ───────────────── MODAL: CONFIRMAR EXCLUSÃO ───────────────── */}
      <Modal
        isOpen={isDeleteModalOpen}
        onClose={() => {
          setIsDeleteModalOpen(false);
          setDeletingId(null);
          setDeleteError(null);
        }}
        title="Confirmar Exclusão"
        description="Tem certeza que deseja excluir esta compra permanentemente? Essa ação não pode ser desfeita."
        size="sm"
      >
        {deleteError && (
          <Alert variant="error" icon={AlertCircle} className="mt-4">
            {deleteError}
          </Alert>
        )}
        <div className="flex justify-end gap-3 mt-4">
          <Button
            variant="outline"
            onClick={() => {
              setIsDeleteModalOpen(false);
              setDeletingId(null);
              setDeleteError(null);
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
