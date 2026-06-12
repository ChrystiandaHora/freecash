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
import React, { useState, useCallback } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useDropzone } from 'react-dropzone';
import {
  CheckCircle2,
  XCircle,
  Search,
  ChevronDown,
  ChevronUp,
  Loader2,
  RefreshCw,
  TrendingUp,
  TrendingDown,
  AlertCircle,
  CheckSquare,
  Square,
  FileText,
  UploadCloud,
  X,
  FileSpreadsheet,
  Edit,
  Trash2,
  Calendar,
  CreditCard,
  Tag,
  DollarSign
} from 'lucide-react';
import api from '../services/api';
import { Button } from '../components/ui/Button';
import { Select } from '../components/ui/Select';
import { Input } from '../components/ui/Input';
import { Modal } from '../components/ui/Modal';
import { Badge } from '../components/ui/Badge';

const fetchConciliacao = async () => {
  const res = await api.get('/api/ferramentas/conciliacao/');
  return res.data;
};

const processarLinhas = async (payload) => {
  const res = await api.post('/api/ferramentas/conciliacao/processar/', payload);
  return res.data;
};

const fetchContas = async () => {
  const res = await api.get('/api/contas/?tipo=D');
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
  const [activeTab, setActiveTab] = useState('conciliar'); // 'conciliar' | 'historico'

  // Tab 1: Conciliacao & Upload states
  const [selectedLinhas, setSelectedLinhas] = useState({});
  const [expandedExtratos, setExpandedExtratos] = useState({});
  const [selectedCard, setSelectedCard] = useState('');
  const [selectedBank, setSelectedBank] = useState('santander');
  const [selectedFile, setSelectedFile] = useState(null);
  const [isUploadPanelOpen, setIsUploadPanelOpen] = useState(false);
  const [uploadResult, setUploadResult] = useState(null);

  // Tab 2: Historico filters states
  const [searchTerm, setSearchTerm] = useState('');
  const [cardFilter, setCardFilter] = useState('');

  // Edit Modal states
  const [editingPurchase, setEditingPurchase] = useState(null);
  const [isEditModalOpen, setIsEditModalOpen] = useState(false);
  const [editDesc, setEditDesc] = useState('');
  const [editValue, setEditValue] = useState('');
  const [editDate, setEditDate] = useState('');
  const [editCardId, setEditCardId] = useState('');
  const [editCategoryId, setEditCategoryId] = useState('');

  // Delete Modal states
  const [deletingId, setDeletingId] = useState(null);
  const [isDeleteModalOpen, setIsDeleteModalOpen] = useState(false);

  // Queries
  const { data: conciliacaoData, isLoading: isConciliacaoLoading, isError: isConciliacaoError, refetch: refetchConciliacao } = useQuery({
    queryKey: ['conciliacao'],
    queryFn: () => fetchConciliacao(),
    enabled: activeTab === 'conciliar',
  });

  const { data: cartoesData } = useQuery({
    queryKey: ['cartoes'],
    queryFn: async () => {
      const res = await api.get('/api/financeiro/cartoes/');
      return res.data;
    }
  });
  const cartoes = cartoesData || [];

  const { data: contasData, isLoading: isContasLoading, isError: isContasError, refetch: refetchContas } = useQuery({
    queryKey: ['contas-cartao'],
    queryFn: () => fetchContas(),
    enabled: activeTab === 'historico',
  });
  const contas = contasData || [];

  const { data: categoriasData } = useQuery({
    queryKey: ['categorias'],
    queryFn: () => fetchCategorias(),
    enabled: activeTab === 'historico',
  });
  const categorias = (categoriasData || []).filter(cat => cat.tipo === 'D');

  // Mutations
  const processarMutation = useMutation({
    mutationFn: processarLinhas,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['conciliacao'] });
      queryClient.invalidateQueries({ queryKey: ['contas-cartao'] });
      queryClient.invalidateQueries({ queryKey: ['cartoes'] });
      setSelectedLinhas({});
    },
  });

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
      setUploadResult({ tipo: 'sucesso', msg: data.msg || 'Fatura importada com sucesso!' });
      setSelectedFile(null);
      queryClient.invalidateQueries({ queryKey: ['conciliacao'] });
      setTimeout(() => setUploadResult(null), 5000);
    },
    onError: (error) => {
      const msg = error?.response?.data?.erro || 'Erro ao processar fatura.';
      setUploadResult({ tipo: 'erro', msg });
    }
  });

  const updatePurchaseMutation = useMutation({
    mutationFn: async (payload) => {
      const { id, ...data } = payload;
      const res = await api.put(`/api/contas/${id}/`, data);
      return res.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['contas-cartao'] });
      queryClient.invalidateQueries({ queryKey: ['cartoes'] });
      queryClient.invalidateQueries({ queryKey: ['conciliacao'] });
      setIsEditModalOpen(false);
      setEditingPurchase(null);
    },
    onError: (err) => {
      alert('Erro ao atualizar compra: ' + (err?.response?.data?.erro || err.message));
    }
  });

  const deletePurchaseMutation = useMutation({
    mutationFn: async (id) => {
      await api.delete(`/api/contas/${id}/`);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['contas-cartao'] });
      queryClient.invalidateQueries({ queryKey: ['cartoes'] });
      queryClient.invalidateQueries({ queryKey: ['conciliacao'] });
      setIsDeleteModalOpen(false);
      setDeletingId(null);
    },
    onError: (err) => {
      alert('Erro ao excluir compra: ' + (err?.response?.data?.erro || err.message));
    }
  });

  // Tab 1 handlers
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

  const extratos = conciliacaoData?.extratos || [];

  const toggleExpandExtrato = (id) => {
    setExpandedExtratos((prev) => ({ ...prev, [id]: !prev[id] }));
  };

  const toggleLinha = (extratoId, linhaId) => {
    setSelectedLinhas((prev) => {
      const current = prev[extratoId] || new Set();
      const next = new Set(current);
      if (next.has(linhaId)) next.delete(linhaId);
      else next.add(linhaId);
      return { ...prev, [extratoId]: next };
    });
  };

  const toggleAllLinhas = (extratoId, linhas) => {
    const current = selectedLinhas[extratoId] || new Set();
    if (current.size === linhas.length) {
      setSelectedLinhas((prev) => ({ ...prev, [extratoId]: new Set() }));
    } else {
      setSelectedLinhas((prev) => ({
        ...prev,
        [extratoId]: new Set(linhas.map((l) => l.id)),
      }));
    }
  };

  const handleProcessar = (extratoId, acao) => {
    const ids = Array.from(selectedLinhas[extratoId] || []);
    if (!ids.length) return;
    processarMutation.mutate({ extrato_id: extratoId, linha_ids: ids, acao });
  };

  // Tab 2 handlers
  const handleOpenEditModal = (purchase) => {
    setEditingPurchase(purchase);
    setEditDesc(purchase.descricao);
    setEditValue(purchase.valor);
    setEditDate(purchase.data_compra || purchase.data_prevista);
    setEditCardId(purchase.cartao || '');
    setEditCategoryId(purchase.categoria || '');
    setIsEditModalOpen(true);
  };

  const handleSaveEdit = (e) => {
    e.preventDefault();
    if (!editDesc || !editValue || !editDate || !editCardId) {
      alert('Por favor, preencha todos os campos obrigatórios.');
      return;
    }
    updatePurchaseMutation.mutate({
      id: editingPurchase.id,
      tipo: 'D',
      descricao: editDesc,
      valor: editValue,
      data_compra: editDate,
      cartao: parseInt(editCardId),
      categoria: editCategoryId ? parseInt(editCategoryId) : null,
    });
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

  // Filter purchases for Tab 2
  const purchases = contas.filter(c => c.cartao !== null && c.eh_fatura_cartao === false);
  const filteredPurchases = purchases.filter(p => {
    const matchesSearch = p.descricao?.toLowerCase().includes(searchTerm.toLowerCase()) ||
                          p.categoria_detalhe?.nome?.toLowerCase().includes(searchTerm.toLowerCase());
    const matchesCard = cardFilter === '' || p.cartao_detalhe?.uuid === cardFilter;
    return matchesSearch && matchesCard;
  });

  const totalPendentes = extratos.reduce((sum, e) => sum + (e.linhas_pendentes || 0), 0);

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
        <Button
          id="btn-atualizar-compras"
          variant="outline"
          onClick={() => {
            if (activeTab === 'conciliar') refetchConciliacao();
            else refetchContas();
          }}
          disabled={isConciliacaoLoading || isContasLoading}
          className="gap-2 shrink-0 self-start sm:self-center"
        >
          <RefreshCw className={`h-4 w-4 ${(isConciliacaoLoading || isContasLoading) ? 'animate-spin' : ''}`} />
          Atualizar
        </Button>
      </div>

      {/* Tabs Controller */}
      <div className="flex border-b border-border/40 gap-6 mb-6">
        <button
          onClick={() => setActiveTab('conciliar')}
          className={`pb-3 text-sm font-semibold border-b-2 transition-all ${
            activeTab === 'conciliar'
              ? 'border-primary text-primary'
              : 'border-transparent text-muted-foreground hover:text-foreground'
          }`}
        >
          Importação e Conciliação
        </button>
        <button
          onClick={() => setActiveTab('historico')}
          className={`pb-3 text-sm font-semibold border-b-2 transition-all ${
            activeTab === 'historico'
              ? 'border-primary text-primary'
              : 'border-transparent text-muted-foreground hover:text-foreground'
          }`}
        >
          Histórico de Compras
        </button>
      </div>

      {/* ───────────────── TAB 1: CONCILIAÇÃO ───────────────── */}
      {activeTab === 'conciliar' && (
        <div className="space-y-6">
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
                    Extraia compras de faturas do Santander ou Nubank e concilie no cartão
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
                  <div
                    className={`flex items-start gap-2 p-3 rounded-lg border text-sm ${
                      uploadResult.tipo === 'sucesso'
                        ? 'bg-emerald-50 dark:bg-emerald-900/20 border-emerald-200 dark:border-emerald-800 text-emerald-800 dark:text-emerald-300'
                        : 'bg-red-50 dark:bg-red-900/20 border-red-200 dark:border-red-800 text-red-800 dark:text-red-300'
                    }`}
                  >
                    {uploadResult.tipo === 'sucesso' ? (
                      <CheckCircle2 className="h-4 w-4 shrink-0 mt-0.5" />
                    ) : (
                      <AlertCircle className="h-4 w-4 shrink-0 mt-0.5" />
                    )}
                    <p className="flex-1">{uploadResult.msg}</p>
                  </div>
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

          {/* Stats Bar */}
          <div className="grid grid-cols-3 gap-4">
            {[
              { label: 'Extratos importados', value: extratos.length, color: 'text-primary' },
              { label: 'Linhas pendentes', value: totalPendentes, color: 'text-amber-500' },
              {
                label: 'Linhas importadas',
                value: extratos.reduce((s, e) => s + (e.linhas_importadas || 0), 0),
                color: 'text-emerald-500',
              },
            ].map(({ label, value, color }) => (
              <div
                key={label}
                className="p-4 rounded-xl border border-border/40 bg-card text-center shadow-sm"
              >
                <p className={`text-2xl font-bold ${color}`}>{value}</p>
                <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">{label}</p>
              </div>
            ))}
          </div>

          {/* Loading / Error states */}
          {isConciliacaoLoading && (
            <div className="flex items-center justify-center py-16">
              <Loader2 className="h-8 w-8 animate-spin text-primary" />
            </div>
          )}

          {isConciliacaoError && (
            <div className="flex items-center gap-3 p-4 rounded-xl bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 text-red-700 dark:text-red-400">
              <AlertCircle className="h-5 w-5 shrink-0" />
              <p>Erro ao carregar dados de conciliação. Verifique a conexão com o servidor.</p>
            </div>
          )}

          {!isConciliacaoLoading && !isConciliacaoError && extratos.length === 0 && (
            <div className="flex flex-col items-center justify-center py-20 text-center">
              <div className="w-16 h-16 rounded-2xl bg-slate-100 dark:bg-slate-900 flex items-center justify-center mb-4">
                <FileText className="h-8 w-8 text-slate-400" />
              </div>
              <h3 className="text-lg font-semibold text-slate-700 dark:text-slate-200 mb-1">
                Nenhum extrato encontrado
              </h3>
              <p className="text-sm text-slate-500 dark:text-slate-400 max-w-sm">
                Importe um arquivo de extrato em PDF para iniciar a conciliação bancária das compras.
              </p>
            </div>
          )}

          {/* Extratos List */}
          <div className="space-y-4">
            {extratos.map((extrato) => {
              const isExpanded = expandedExtratos[extrato.id] ?? true;
              const linhas = extrato.linhas || [];
              const selected = selectedLinhas[extrato.id] || new Set();
              const allSelected = linhas.length > 0 && selected.size === linhas.length;
              const isPending = processarMutation.isPending;

              return (
                <div
                  key={extrato.id}
                  className="rounded-2xl border border-border/40 bg-card overflow-hidden shadow-sm"
                >
                  <div
                    className="flex items-center justify-between gap-4 p-4 cursor-pointer hover:bg-muted/40 transition-colors"
                    onClick={() => toggleExpandExtrato(extrato.id)}
                  >
                    <div className="flex items-center gap-3">
                      <div
                        className={`w-2.5 h-2.5 rounded-full shrink-0 ${
                          extrato.status === 'processado'
                            ? 'bg-emerald-500'
                            : extrato.status === 'erro'
                            ? 'bg-red-500'
                            : 'bg-amber-500 animate-pulse'
                        }`}
                      />
                      <div>
                        <p className="font-semibold text-foreground text-sm">
                          {extrato.arquivo_nome}
                        </p>
                        <div className="flex items-center gap-2 mt-0.5">
                          <span className="text-xs text-muted-foreground">
                            {extrato.banco_display}
                          </span>
                          <span className="text-border">·</span>
                          <span className="text-xs text-muted-foreground">
                            {formatDate(extrato.criada_em?.split('T')[0])}
                          </span>
                        </div>
                      </div>
                    </div>
                    <div className="flex items-center gap-3">
                      <div className="hidden sm:flex items-center gap-4 text-xs">
                        <span className="text-amber-600 dark:text-amber-400 font-semibold">
                          {extrato.linhas_pendentes} pendentes
                        </span>
                        <span className="text-emerald-600 dark:text-emerald-400 font-semibold">
                          {extrato.linhas_importadas} importadas
                        </span>
                      </div>
                      {isExpanded ? (
                        <ChevronUp className="h-4 w-4 text-muted-foreground" />
                      ) : (
                        <ChevronDown className="h-4 w-4 text-muted-foreground" />
                      )}
                    </div>
                  </div>

                  {isExpanded && linhas.length > 0 && (
                    <div className="border-t border-border/40">
                      <div className="flex items-center gap-3 px-4 py-2.5 bg-muted/60 text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                        <button
                          id={`btn-select-all-${extrato.id}`}
                          onClick={() => toggleAllLinhas(extrato.id, linhas)}
                          className="flex items-center gap-1.5 text-slate-500 hover:text-primary transition-colors"
                        >
                          {allSelected ? (
                            <CheckSquare className="h-4 w-4 text-primary" />
                          ) : (
                            <Square className="h-4 w-4" />
                          )}
                          Todos
                        </button>
                        <span className="flex-1">Descrição</span>
                        <span className="w-24 text-right">Valor</span>
                        <span className="w-24 text-right hidden sm:block">Data</span>
                        <span className="w-16 text-center">Tipo</span>
                      </div>

                      <div className="divide-y divide-border/30">
                        {linhas.map((linha) => {
                          const isChecked = selected.has(linha.id);
                          const isCredito = linha.tipo === 'C';

                          return (
                            <div
                              key={linha.id}
                              className={`flex items-center gap-3 px-4 py-3 transition-colors cursor-pointer
                                ${isChecked ? 'bg-primary/10' : 'hover:bg-muted/40'}
                              `}
                              onClick={() => toggleLinha(extrato.id, linha.id)}
                            >
                              {isChecked ? (
                                <CheckSquare className="h-4 w-4 text-primary shrink-0" />
                              ) : (
                                <Square className="h-4 w-4 text-muted-foreground/60 shrink-0" />
                              )}
                              <span className="flex-1 text-sm text-foreground truncate">
                                {linha.descricao}
                              </span>
                              <span
                                className={`w-24 text-right text-sm font-semibold ${
                                  isCredito ? 'text-emerald-600 dark:text-emerald-400' : 'text-red-500 dark:text-red-400'
                                }`}
                              >
                                {isCredito ? '+' : '-'}{formatCurrency(linha.valor)}
                              </span>
                              <span className="w-24 text-right text-xs text-muted-foreground hidden sm:block">
                                {formatDate(linha.data)}
                              </span>
                              <span className="w-16 flex justify-center">
                                {isCredito ? (
                                  <span className="flex items-center gap-1 text-xs text-emerald-600 dark:text-emerald-400 font-medium">
                                    <TrendingUp className="h-3.5 w-3.5" />
                                    Entrada
                                  </span>
                                ) : (
                                  <span className="flex items-center gap-1 text-xs text-red-500 dark:text-red-400 font-medium">
                                    <TrendingDown className="h-3.5 w-3.5" />
                                    Saída
                                  </span>
                                )}
                              </span>
                            </div>
                          );
                        })}
                      </div>

                      {selected.size > 0 && (
                        <div className="flex items-center justify-between gap-3 px-4 py-3 bg-primary/10 border-t border-primary/20">
                          <p className="text-sm text-foreground">
                            <span className="font-bold text-primary">{selected.size}</span> linha(s) selecionada(s)
                          </p>
                          <div className="flex gap-2">
                            <Button
                              id={`btn-ignorar-${extrato.id}`}
                              variant="outline"
                              size="sm"
                              className="gap-1.5 text-red-600 dark:text-red-400 border-red-300 dark:border-red-800 hover:bg-red-50 dark:hover:bg-red-900/20"
                              onClick={() => handleProcessar(extrato.id, 'ignorar')}
                              disabled={isPending}
                            >
                              {isPending ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <XCircle className="h-3.5 w-3.5" />}
                              Ignorar
                            </Button>
                            <Button
                              id={`btn-importar-${extrato.id}`}
                              size="sm"
                              className="gap-1.5"
                              onClick={() => handleProcessar(extrato.id, 'importar')}
                              disabled={isPending}
                            >
                              {isPending ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <CheckCircle2 className="h-3.5 w-3.5" />}
                              Confirmar Inclusão
                            </Button>
                          </div>
                        </div>
                      )}
                    </div>
                  )}

                  {isExpanded && linhas.length === 0 && (
                    <div className="border-t border-border/40 p-6 text-center">
                      <CheckCircle2 className="h-8 w-8 text-emerald-500 mx-auto mb-2" />
                      <p className="text-sm text-muted-foreground">
                        Todas as linhas deste extrato foram processadas.
                      </p>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* ───────────────── TAB 2: HISTÓRICO DE COMPRAS ───────────────── */}
      {activeTab === 'historico' && (
        <div className="space-y-6">
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
            <div className="flex items-center gap-3 p-4 rounded-xl bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 text-red-700 dark:text-red-400">
              <AlertCircle className="h-5 w-5 shrink-0" />
              <p>Erro ao carregar histórico de compras do cartão. Verifique a conexão com o servidor.</p>
            </div>
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
        </div>
      )}

      {/* ───────────────── MODAL: EDITAR COMPRA ───────────────── */}
      <Modal
        isOpen={isEditModalOpen}
        onClose={() => {
          setIsEditModalOpen(false);
          setEditingPurchase(null);
        }}
        title="Editar Compra do Cartão"
        description="Ajuste os dados da compra individual. O vencimento correspondente será calculado automaticamente."
        size="md"
      >
        <form onSubmit={handleSaveEdit} className="space-y-4">
          <div className="space-y-1.5">
            <label className="text-xs font-bold uppercase tracking-wider text-muted-foreground">
              Descrição *
            </label>
            <div className="relative">
              <FileText className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <Input
                type="text"
                required
                value={editDesc}
                onChange={(e) => setEditDesc(e.target.value)}
                className="pl-9"
              />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-1.5">
              <label className="text-xs font-bold uppercase tracking-wider text-muted-foreground">
                Valor (R$) *
              </label>
              <div className="relative">
                <DollarSign className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                <Input
                  type="number"
                  step="0.01"
                  required
                  value={editValue}
                  onChange={(e) => setEditValue(e.target.value)}
                  className="pl-9"
                />
              </div>
            </div>

            <div className="space-y-1.5">
              <label className="text-xs font-bold uppercase tracking-wider text-muted-foreground">
                Data da Compra *
              </label>
              <div className="relative">
                <Calendar className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                <Input
                  type="date"
                  required
                  value={editDate}
                  onChange={(e) => setEditDate(e.target.value)}
                  className="pl-9"
                />
              </div>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-1.5">
              <label className="text-xs font-bold uppercase tracking-wider text-muted-foreground">
                Cartão de Crédito *
              </label>
              <Select
                value={editCardId}
                onChange={(e) => setEditCardId(e.target.value)}
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
              <label className="text-xs font-bold uppercase tracking-wider text-muted-foreground">
                Categoria
              </label>
              <Select
                value={editCategoryId}
                onChange={(e) => setEditCategoryId(e.target.value)}
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

          <div className="flex justify-end gap-3 pt-4 border-t border-border/40 mt-6">
            <Button
              type="button"
              variant="outline"
              onClick={() => {
                setIsEditModalOpen(false);
                setEditingPurchase(null);
              }}
              disabled={updatePurchaseMutation.isPending}
            >
              Cancelar
            </Button>
            <Button
              type="submit"
              disabled={updatePurchaseMutation.isPending}
              className="gap-2"
            >
              {updatePurchaseMutation.isPending && <Loader2 className="h-4 w-4 animate-spin" />}
              Salvar Alterações
            </Button>
          </div>
        </form>
      </Modal>

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
