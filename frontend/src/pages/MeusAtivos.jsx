/**
 * Tela de Cadastro e Listagem de Ativos Custodiados.
 * 
 * Permite o gerenciamento de ativos individuais na carteira do investidor (Ações, FIIs, Renda Fixa).
 * Disponibiliza interfaces interativas para criar, ler, atualizar e deletar (CRUD) ativos,
 * bem como iniciar ordens de compra/venda vinculadas a cada ticker.
 *
 * @component
 * @returns {React.JSX.Element} Visualização em tabela com modais flutuantes de cadastro operacional.
 */
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { 
  Plus, 
  Pencil, 
  Trash2, 
  Search, 
  Percent, 
  TrendingUp, 
  AlertCircle, 
  CheckCircle2, 
  RefreshCw, 
  Gem, 
  Calendar, 
  Eye, 
  EyeOff
} from 'lucide-react';

import { 
  fetchAtivos, 
  createAtivo, 
  updateAtivo, 
  deleteAtivo, 
  fetchSubcategoriasAtivos,
  atualizarCotacoes
} from '../services/investimentos';

import { Button } from '../components/ui/Button';
import { Input } from '../components/ui/Input';
import { Select } from '../components/ui/Select';
import { Modal } from '../components/ui/Modal';
import { DataTable } from '../components/ui/DataTable';
import { SectionLabel } from '../components/ui/SectionLabel';
import { Alert } from '../components/ui/Alert';

// Helper de formatação de moedas
const formatCurrency = (value) => {
  if (value === undefined || value === null) return 'R$ 0,00';
  return new Intl.NumberFormat('pt-BR', {
    style: 'currency',
    currency: 'BRL',
  }).format(value);
};

// Helper de formatação de porcentagens
const formatPercentage = (value) => {
  if (value === undefined || value === null) return '0,00%';
  const num = parseFloat(value);
  const formatted = num.toFixed(2).replace('.', ',');
  return num >= 0 ? `+${formatted}%` : `${formatted}%`;
};

export default function MeusAtivos() {
  const queryClient = useQueryClient();
  const navigate = useNavigate();

  const columns = [
    {
      key: 'ticker',
      header: 'Ticker',
      className: 'px-5 py-3.5',
      cellClassName: 'px-5 py-3.5 font-bold text-foreground',
    },
    {
      key: 'quantidade',
      header: 'Quantidade',
      className: 'px-5 py-3.5 text-left',
      cellClassName: 'px-5 py-3.5 text-left font-bold text-foreground/80',
      render: (val) => parseFloat(val || 0).toString().replace('.', ','),
    },
    {
      key: 'preco_medio',
      header: 'P. Médio',
      className: 'px-5 py-3.5 text-left',
      cellClassName: 'px-5 py-3.5 text-left text-muted-foreground',
      render: (val) => formatCurrency(val),
    },
    {
      key: 'cotacao_atual',
      header: 'Cotação',
      className: 'px-5 py-3.5 text-left',
      cellClassName: 'px-5 py-3.5 text-left text-muted-foreground font-semibold',
      render: (val) => formatCurrency(val),
    },
    {
      key: 'valor_total_atual',
      header: 'Valor Atual',
      className: 'px-5 py-3.5 text-left',
      cellClassName: 'px-5 py-3.5 text-left font-extrabold text-foreground',
      render: (val) => formatCurrency(parseFloat(val || 0)),
    },
    {
      key: 'rentabilidade_percentual',
      header: 'Retorno',
      className: 'px-5 py-3.5 text-left',
      cellClassName: 'px-5 py-3.5 text-left font-bold',
      render: (val) => {
        const rentabilidadePerc = parseFloat(val || 0);
        return (
          <span className={rentabilidadePerc >= 0 ? 'text-primary' : 'text-rose-500'}>
            {formatPercentage(rentabilidadePerc)}
          </span>
        );
      },
    },
    {
      key: 'acoes',
      header: 'Ações',
      sortable: false,
      className: 'px-5 py-3.5 text-center',
      cellClassName: 'px-5 py-3.5 text-center',
      render: (_, row) => (
        <div className="flex items-center justify-center gap-2">
          <Button 
            variant="ghost" 
            size="icon"
            onClick={() => navigate(`/investimentos/ativos/${row.id}`)}
            className="h-8 w-8 rounded-lg hover:bg-muted text-muted-foreground hover:text-foreground"
            title="Visualizar Detalhes"
          >
            <Eye className="h-3.5 w-3.5" />
          </Button>
          <Button 
            variant="ghost" 
            size="icon"
            onClick={() => openEditModal(row)}
            className="h-8 w-8 rounded-lg hover:bg-muted text-muted-foreground hover:text-foreground"
            title="Editar Ativo"
          >
            <Pencil className="h-3.5 w-3.5" />
          </Button>
          <Button 
            variant="ghost" 
            size="icon"
            onClick={() => openDeleteModal(row)}
            className="h-8 w-8 rounded-lg hover:bg-destructive/10 text-muted-foreground hover:text-destructive"
            title="Excluir Ativo"
          >
            <Trash2 className="h-3.5 w-3.5" />
          </Button>
        </div>
      ),
    },
  ];
  
  // Estados de Filtros e Abas
  const [searchTerm, setSearchTerm] = useState('');
  const [filterSubcategoria, setFilterSubcategoria] = useState('');
  const [activeTab, setActiveTab] = useState('ativos'); // 'ativos' | 'arquivados'
  
  // Estados de Modais
  const [isDeleteOpen, setIsDeleteOpen] = useState(false);
  const [activeAtivo, setActiveAtivo] = useState(null);
  
  // Estado de Mensagens e Erros locais
  const [errorMessage, setErrorMessage] = useState('');
  const [successMessage, setSuccessMessage] = useState('');
  const [globalError, setGlobalError] = useState('');

  /* ── Queries ── */
  const { data: ativos = [], isLoading: loadingAtivos, isError: errorAtivos } = useQuery({
    queryKey: ['ativos'],
    queryFn: () => fetchAtivos(),
    refetchOnWindowFocus: false,
  });
  
  const { data: subcategorias = [], isLoading: loadingSubs } = useQuery({
    queryKey: ['subcategoriasAtivos'],
    queryFn: () => fetchSubcategoriasAtivos()
  });

  /* ── Mutations ── */
  const handleShowSuccess = (msg) => {
    setSuccessMessage(msg);
    setTimeout(() => setSuccessMessage(''), 4000);
  };



  const deleteMutation = useMutation({
    mutationFn: (id) => deleteAtivo(id),
    onSuccess: () => {
      queryClient.invalidateQueries(['ativos']);
      setIsDeleteOpen(false);
      setActiveAtivo(null);
      handleShowSuccess('Ativo removido com sucesso!');
    },
    onError: () => {
      setErrorMessage('Erro ao remover ativo. Verifique se existem transações vinculadas.');
    }
  });

  const updateQuotesMutation = useMutation({
    mutationFn: () => atualizarCotacoes(),
    onMutate: () => {
      setGlobalError('');
      setSuccessMessage('');
    },
    onSuccess: (data) => {
      queryClient.invalidateQueries(['ativos']);
      queryClient.invalidateQueries(['investimentosDashboard']);
      queryClient.invalidateQueries(['investimentosBalanceamento']);
      
      const count = data?.count || 0;
      const errors = data?.errors || [];
      
      if (count > 0 && errors.length === 0) {
        handleShowSuccess(`${count} cotações atualizadas com sucesso!`);
      } else if (count > 0 && errors.length > 0) {
        handleShowSuccess(`${count} cotações atualizadas com sucesso!`);
        setGlobalError(`Falha em alguns ativos: ${errors.slice(0, 3).join(' | ')}${errors.length > 3 ? '...' : ''}`);
      } else if (errors.length > 0) {
        setGlobalError(`Falha ao atualizar cotações: ${errors.slice(0, 3).join(' | ')}${errors.length > 3 ? '...' : ''}`);
      } else {
        handleShowSuccess('Nenhuma cotação nova encontrada ou nenhum ativo com ticker.');
      }
    },
    onError: () => {
      setGlobalError('Erro ao comunicar com o servidor de cotações.');
    }
  });

  /* ── Handlers de Modais ── */
  const openCreateModal = () => {
    navigate('/investimentos/ativos/novo');
  };

  const openEditModal = (ativo) => {
    navigate(`/investimentos/ativos/editar/${ativo.id}`);
  };

  const openDeleteModal = (ativo) => {
    setActiveAtivo(ativo);
    setErrorMessage('');
    setGlobalError('');
    setSuccessMessage('');
    setIsDeleteOpen(true);
  };



  const handleDeleteConfirm = () => {
    if (activeAtivo) {
      deleteMutation.mutate(activeAtivo.id);
    }
  };

  /* ── Cálculos de Métricas ── */
  const activeAtivosList = ativos.filter(a => a.ativo);
  const totalPatrimonio = activeAtivosList.reduce((sum, item) => sum + parseFloat(item.valor_total_atual || 0), 0);
  const totalMeta = activeAtivosList.reduce((sum, item) => sum + parseFloat(item.meta_porcentagem || 0), 0);
  const totalInvestido = activeAtivosList.reduce((sum, item) => sum + (parseFloat(item.quantidade || 0) * parseFloat(item.preco_medio || 0)), 0);

  // Lista Filtrada
  const filteredAtivos = ativos.filter(ativo => {
    // Filtragem de Aba (Ativos x Arquivados)
    const matchesTab = activeTab === 'ativos' ? ativo.ativo : !ativo.ativo;
    if (!matchesTab) return false;

    // Busca por Texto (Ticker ou Nome)
    const matchesSearch = 
      ativo.ticker.toLowerCase().includes(searchTerm.toLowerCase()) ||
      ativo.nome.toLowerCase().includes(searchTerm.toLowerCase());
    
    // Filtro por Subcategoria
    const matchesSub = filterSubcategoria === '' || ativo.subcategoria === parseInt(filterSubcategoria);

    return matchesSearch && matchesSub;
  });

  if (loadingAtivos || loadingSubs) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[70vh] gap-4">
        <RefreshCw className="h-8 w-8 text-primary animate-spin" />
        <p className="text-sm font-semibold text-muted-foreground">
          Carregando inventário de ativos...
        </p>
      </div>
    );
  }

  if (errorAtivos) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[70vh] gap-4 text-center max-w-md mx-auto">
        <AlertCircle className="h-12 w-12 text-destructive" />
        <h3 className="text-xl font-bold text-foreground">Falha ao ler ativos</h3>
        <p className="text-sm text-muted-foreground">
          Não conseguimos obter comunicação com o servidor de carteiras.
        </p>
        <Button onClick={() => queryClient.invalidateQueries(['ativos'])} className="mt-2">
          Tentar Novamente
        </Button>
      </div>
    );
  }

  return (
    <div className="space-y-6 animate-fade-in text-foreground">
      
      {/* Cabeçalho */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-foreground flex items-center gap-2">
            <Gem className="h-6 w-6 text-primary" />
            Meus Ativos
          </h1>
          <p className="text-xs text-muted-foreground">
            Gerencie seu portfólio de ações, renda fixa, fundos e criptoativos.
          </p>
        </div>
        
        <div className="flex items-center gap-3 self-start sm:self-auto">
          <Button 
            onClick={() => updateQuotesMutation.mutate()}
            disabled={updateQuotesMutation.isLoading}
            variant="outline"
            className="rounded-xl h-10 px-4 gap-2 font-semibold transition-all border border-border/40 hover:bg-accent hover:text-accent-foreground text-foreground shadow-sm active:scale-98"
          >
            <RefreshCw className={`h-4 w-4 ${updateQuotesMutation.isLoading ? 'animate-spin' : ''}`} />
            {updateQuotesMutation.isLoading ? 'Atualizando...' : 'Atualizar Cotações'}
          </Button>

          <Button 
            onClick={openCreateModal}
            className="rounded-xl h-10 px-4 gap-2 bg-primary hover:bg-primary/95 text-primary-foreground font-semibold border-0 shadow-lg shadow-primary/20 transition-all active:scale-98"
          >
            <Plus className="h-4 w-4" />
            Cadastrar Ativo
          </Button>
        </div>
      </div>

      {/* Banner de Sucesso */}
      {successMessage && (
        <Alert variant="success" icon={CheckCircle2} className="animate-in fade-in duration-300">
          <span className="text-sm font-semibold">{successMessage}</span>
        </Alert>
      )}

      {/* Banner de Erro Global */}
      {globalError && (
        <Alert variant="error" icon={AlertCircle} className="animate-in fade-in duration-300">
          <span className="text-sm font-semibold">{globalError}</span>
        </Alert>
      )}

      {/* Grid de Métricas SaaS Flat */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
        
        <div className="bg-card border border-border/40 shadow-sm text-card-foreground rounded-xl p-6 relative overflow-hidden transition-all hover:shadow-md">
          <div className="absolute -right-4 -bottom-4 h-16 w-16 opacity-5 text-foreground">
            <TrendingUp className="h-full w-full" />
          </div>
          <p className="text-[10px] font-bold text-muted-foreground uppercase tracking-wider">Patrimônio Alocado</p>
          <h3 className="text-2xl font-bold tracking-tight text-foreground mt-2">
            {formatCurrency(totalPatrimonio)}
          </h3>
          <p className="text-xs text-muted-foreground mt-1">
            Total investido originalmente: <span className="font-semibold text-foreground/80">{formatCurrency(totalInvestido)}</span>
          </p>
        </div>

        <div className="bg-card border border-border/40 shadow-sm text-card-foreground rounded-xl p-6 relative overflow-hidden transition-all hover:shadow-md">
          <div className="absolute -right-4 -bottom-4 h-16 w-16 opacity-5 text-foreground">
            <Gem className="h-full w-full" />
          </div>
          <p className="text-[10px] font-bold text-muted-foreground uppercase tracking-wider">Ativos em Carteira</p>
          <h3 className="text-2xl font-bold tracking-tight text-foreground mt-2">
            {ativos.filter(a => a.ativo).length} ativos
          </h3>
          <p className="text-xs text-muted-foreground mt-1">
            Arquivados/Liquidados: <span className="font-semibold text-foreground/80">{ativos.filter(a => !a.ativo).length}</span>
          </p>
        </div>

        <div className="bg-card border border-border/40 shadow-sm text-card-foreground rounded-xl p-6 relative overflow-hidden transition-all hover:shadow-md">
          <div className="absolute -right-4 -bottom-4 h-16 w-16 opacity-5 text-foreground">
            <Percent className="h-full w-full" />
          </div>
          <p className="text-[10px] font-bold text-muted-foreground uppercase tracking-wider">Metas Configuradas</p>
          <h3 className="text-2xl font-bold tracking-tight text-foreground mt-2">
            {totalMeta.toFixed(1).replace('.', ',')}%
          </h3>
          <div className="mt-1">
            {Math.abs(totalMeta - 100) > 0.01 ? (
              <span className="inline-flex items-center gap-1.5 text-xs font-semibold text-amber-500">
                <AlertCircle className="h-3.5 w-3.5" /> A soma ideal das metas é 100%
              </span>
            ) : (
              <span className="inline-flex items-center gap-1.5 text-xs font-semibold text-primary">
                <CheckCircle2 className="h-3.5 w-3.5" /> Distribuição ideal alinhada (100%)
              </span>
            )}
          </div>
        </div>

      </div>

      {/* Caixa de Visualização Principal */}
      <div className="bg-card border border-border/40 shadow-sm text-card-foreground rounded-xl p-6 space-y-6">
        
        {/* Barra de Filtros e Abas */}
        <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4">
          
          {/* Abas */}
          <div className="flex border-b border-border/40 self-start">
            <button
              onClick={() => { setActiveTab('ativos'); setSearchTerm(''); }}
              className={`px-4 py-2 text-xs font-bold uppercase tracking-wider border-b-2 transition-all gap-2 flex items-center ${activeTab === 'ativos' ? 'border-primary text-primary' : 'border-transparent text-muted-foreground hover:text-foreground'}`}
            >
              <Gem className="h-3.5 w-3.5" />
              Ativos ({ativos.filter(a => a.ativo).length})
            </button>
            <button
              onClick={() => { setActiveTab('arquivados'); setSearchTerm(''); }}
              className={`px-4 py-2 text-xs font-bold uppercase tracking-wider border-b-2 transition-all gap-2 flex items-center ${activeTab === 'arquivados' ? 'border-primary text-primary' : 'border-transparent text-muted-foreground hover:text-foreground'}`}
            >
              <EyeOff className="h-3.5 w-3.5" />
              Arquivados ({ativos.filter(a => !a.ativo).length})
            </button>
          </div>

          {/* Filtros */}
          <div className="flex flex-col sm:flex-row gap-3 flex-1 lg:max-w-xl">
            
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <Input
                placeholder="Buscar por Ticker ou Nome..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="pl-9 h-10 text-xs rounded-xl"
              />
            </div>

            <div className="w-full sm:w-56">
              <Select
                value={filterSubcategoria}
                onChange={(e) => setFilterSubcategoria(e.target.value)}
                className="h-10 text-xs rounded-xl"
              >
                <option value="">Todas as Classes</option>
                {subcategorias.map(sc => (
                  <option key={sc.id} value={sc.id}>
                    {sc.categoria_detalhe?.classe_detalhe?.nome} — {sc.nome}
                  </option>
                ))}
              </Select>
            </div>

          </div>

        </div>

        {/* Tabela de Ativos */}
        <DataTable
          columns={columns}
          data={filteredAtivos}
          pageSize={20}
          emptyMessage="Nenhum ativo encontrado nesta aba."
        />

      </div>



      {/* MODAL 3: CONFIRMAR EXCLUSÃO */}
      <Modal
        isOpen={isDeleteOpen}
        onClose={() => setIsDeleteOpen(false)}
        title="Confirmar Exclusão"
        description=""
        size="sm"
      >
        <div className="flex flex-col items-center text-center gap-4">
          <div className="w-14 h-14 rounded-full bg-destructive/10 flex items-center justify-center animate-pulse">
            <Trash2 className="h-6 w-6 text-destructive" />
          </div>
          <div>
            <h3 className="text-base font-bold text-foreground">Remover Ativo Permanente</h3>
            <p className="text-xs text-muted-foreground mt-1.5 leading-relaxed">
              Tem certeza que deseja excluir o ativo <span className="font-bold text-foreground">{activeAtivo?.ticker}</span>? 
              Se houver transações (compras, vendas ou proventos) vinculadas no histórico, o banco bloqueará a ação para manter a integridade dos seus relatórios.
            </p>
          </div>

          {errorMessage && (
            <Alert variant="error" icon={AlertCircle} className="w-full text-xs">
              <span className="font-semibold leading-relaxed">{errorMessage}</span>
            </Alert>
          )}

          <div className="flex gap-3 w-full pt-2">
            <Button 
              variant="outline" 
              onClick={() => setIsDeleteOpen(false)} 
              className="flex-1 rounded-xl h-10 text-xs"
            >
              Cancelar
            </Button>
            <Button 
              onClick={handleDeleteConfirm} 
              disabled={deleteMutation.isPending} 
              className="flex-1 rounded-xl h-10 text-xs bg-destructive hover:bg-destructive/95 text-destructive-foreground border-0 font-bold"
            >
              {deleteMutation.isPending ? <RefreshCw className="h-4 w-4 animate-spin mx-auto" /> : 'Remover'}
            </Button>
          </div>
        </div>
      </Modal>



    </div>
  );
}
