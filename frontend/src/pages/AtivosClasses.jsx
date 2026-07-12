/**
 * Página de Gerenciamento da Hierarquia ANBIMA de Ativos.
 * 
 * Permite a visualização em árvore colapsável e o gerenciamento CRUD de três níveis de agrupamentos:
 * Classe (Nível 1) → Categoria (Nível 2) → Subcategoria (Nível 3).
 * Integra-se às APIs do Django REST Framework para garantir unicidade e validação hierárquica.
 *
 * @component
 * @returns {React.JSX.Element}
 */
import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import api from '../services/api';
import {
  Layers,
  RefreshCw,
  AlertCircle,
  Plus,
  X,
  Pencil,
  Trash2,
  ChevronDown,
  ChevronRight,
  CheckCircle2,
  FolderOpen,
  Folder,
  Tag
} from 'lucide-react';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '../components/ui/Card';
import { Button } from '../components/ui/Button';
import { Input } from '../components/ui/Input';
import { Alert } from '../components/ui/Alert';

/* ─────────────────────────── Modal genérico ─────────────────────────── */
/**
 * Componente modal para edição ou criação rápida de nome de classes/categorias.
 *
 * @component
 * @param {Object} props - Propriedades do componente.
 * @param {string} props.title - Título exibido no cabeçalho da modal.
 * @param {string} props.placeholder - Marcador de posição para a caixa de texto input.
 * @param {string} [props.initialValue=''] - Valor de texto inicial preenchido.
 * @param {Function} props.onSave - Callback acionado ao enviar o formulário com dados válidos.
 * @param {Function} props.onClose - Callback de fechamento da modal.
 * @param {boolean} props.isPending - Flag que indica carregamento e desabilita botões.
 * @param {string} [props.error] - Mensagem de erro retornada pelo servidor.
 * @returns {React.JSX.Element}
 */
function QuickEditModal({ title, placeholder, initialValue = '', onSave, onClose, isPending, error }) {
  const [value, setValue] = useState(initialValue);
  const [localError, setLocalError] = useState('');

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!value.trim()) { setLocalError('O nome não pode estar vazio.'); return; }
    onSave(value.trim());
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-background/80 backdrop-blur-sm" onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <div className="bg-card rounded-2xl shadow-xl w-full max-w-sm border border-border/40">
        <div className="flex items-center justify-between p-5 border-b border-border/40">
          <h3 className="text-base font-bold text-foreground">{title}</h3>
          <button onClick={onClose} className="p-1.5 rounded-lg text-muted-foreground hover:bg-muted">
            <X className="h-4 w-4" />
          </button>
        </div>
        <form onSubmit={handleSubmit} className="p-5 space-y-4">
          <Input
            placeholder={placeholder}
            value={value}
            onChange={(e) => { setValue(e.target.value); setLocalError(''); }}
            className="h-10 text-sm rounded-xl"
            autoFocus
          />
          {(localError || error) && (
            <Alert variant="error" icon={AlertCircle} className="p-2.5 text-xs">
              <span className="font-semibold">{localError || error}</span>
            </Alert>
          )}
          <div className="flex gap-3">
            <Button type="button" variant="outline" onClick={onClose} className="flex-1 rounded-xl h-9 text-xs">Cancelar</Button>
            <Button type="submit" disabled={isPending} className="flex-1 rounded-xl h-9 text-xs bg-primary hover:bg-primary/90 text-primary-foreground border-0">
              {isPending ? <RefreshCw className="h-3.5 w-3.5 animate-spin" /> : 'Salvar'}
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}

/* ─────────────────────────── Delete Confirm ─────────────────────────── */
/**
 * Componente modal para confirmação de exclusão de elements de classificação.
 *
 * @component
 * @param {Object} props - Propriedades do componente.
 * @param {string} props.label - Nome textual do elemento a ser excluído.
 * @param {Function} props.onConfirm - Callback executado ao clicar no botão excluir.
 * @param {Function} props.onClose - Callback de cancelamento/fechamento.
 * @param {boolean} props.isPending - Flag de envio assíncrono.
 * @returns {React.JSX.Element}
 */
function DeleteConfirmModal({ label, onConfirm, onClose, isPending }) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-background/80 backdrop-blur-sm">
      <div className="bg-card rounded-2xl shadow-xl w-full max-w-sm border border-border/40 p-6">
        <div className="flex flex-col items-center text-center gap-4">
          <div className="w-14 h-14 rounded-full bg-destructive/10 flex items-center justify-center">
            <Trash2 className="h-6 w-6 text-destructive" />
          </div>
          <div>
            <h3 className="text-base font-bold text-foreground">Confirmar exclusão</h3>
            <p className="text-sm text-muted-foreground mt-1">
              Tem certeza que deseja excluir <span className="font-semibold text-foreground">"{label}"</span>? Esta ação não pode ser desfeita.
            </p>
          </div>
          <div className="flex gap-3 w-full">
            <Button variant="outline" onClick={onClose} className="flex-1 rounded-xl h-10 text-xs">Cancelar</Button>
            <Button onClick={onConfirm} disabled={isPending} className="flex-1 rounded-xl h-10 text-xs bg-destructive hover:bg-destructive/90 text-destructive-foreground border-0">
              {isPending ? <RefreshCw className="h-4 w-4 animate-spin" /> : 'Excluir'}
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}

/* ─────────────────────────── Main Page ─────────────────────────── */
export default function AtivosClasses() {
  const queryClient = useQueryClient();

  // Modal state: { type: 'create-classe'|'edit-classe'|'delete-classe'|'create-cat'|'edit-cat'|'delete-cat'|'create-sub'|'edit-sub'|'delete-sub', data: {} }
  const [modal, setModal] = useState(null);
  const [expandedClasses, setExpandedClasses] = useState({});
  const [expandedCats, setExpandedCats] = useState({});
  const [mutError, setMutError] = useState('');
  const [successMsg, setSuccessMsg] = useState('');

  /* ── Queries ── */
  const { data: classes, isLoading: loadC, isError: errC, refetch: refetchC } = useQuery({
    queryKey: ['classesAtivos'],
    queryFn: async () => { const r = await api.get('/api/investimentos/classes/'); return r.data; },
  });

  const { data: categorias, isLoading: loadCat, refetch: refetchCat } = useQuery({
    queryKey: ['categoriasAtivos'],
    queryFn: async () => { const r = await api.get('/api/investimentos/categorias/'); return r.data; },
  });

  const { data: subcategorias, isLoading: loadSub, refetch: refetchSub } = useQuery({
    queryKey: ['subcategoriasAtivos'],
    queryFn: async () => { const r = await api.get('/api/investimentos/subcategorias/'); return r.data; },
  });

  const invalidateAll = () => {
    queryClient.invalidateQueries(['classesAtivos']);
    queryClient.invalidateQueries(['categoriasAtivos']);
    queryClient.invalidateQueries(['subcategoriasAtivos']);
  };

  const showSuccess = (msg) => {
    setSuccessMsg(msg);
    setTimeout(() => setSuccessMsg(''), 3000);
  };

  /* ── Mutations ── */
  const buildMutation = (fn, successMsg) => useMutation({
    mutationFn: fn,
    onSuccess: () => { invalidateAll(); setModal(null); setMutError(''); showSuccess(successMsg); },
    onError: (e) => setMutError(e?.response?.data?.detail || e?.response?.data?.nome?.[0] || 'Erro ao salvar.'),
  });

  const createClasseMut = buildMutation(
    (nome) => api.post('/api/investimentos/classes/', { nome }),
    'Classe criada!'
  );
  const updateClasseMut = buildMutation(
    ({ id, nome }) => api.patch(`/api/investimentos/classes/${id}/`, { nome }),
    'Classe atualizada!'
  );
  const deleteClasseMut = buildMutation(
    (id) => api.delete(`/api/investimentos/classes/${id}/`),
    'Classe excluída!'
  );

  const createCatMut = buildMutation(
    ({ nome, classe }) => api.post('/api/investimentos/categorias/', { nome, classe }),
    'Categoria criada!'
  );
  const updateCatMut = buildMutation(
    ({ id, nome }) => api.patch(`/api/investimentos/categorias/${id}/`, { nome }),
    'Categoria atualizada!'
  );
  const deleteCatMut = buildMutation(
    (id) => api.delete(`/api/investimentos/categorias/${id}/`),
    'Categoria excluída!'
  );

  const createSubMut = buildMutation(
    ({ nome, categoria }) => api.post('/api/investimentos/subcategorias/', { nome, categoria }),
    'Subcategoria criada!'
  );
  const updateSubMut = buildMutation(
    ({ id, nome }) => api.patch(`/api/investimentos/subcategorias/${id}/`, { nome }),
    'Subcategoria atualizada!'
  );
  const deleteSubMut = buildMutation(
    (id) => api.delete(`/api/investimentos/subcategorias/${id}/`),
    'Subcategoria excluída!'
  );

  const isLoading = loadC || loadCat || loadSub;

  const toggleClass = (id) => setExpandedClasses((p) => ({ ...p, [id]: !p[id] }));
  const toggleCat = (id) => setExpandedCats((p) => ({ ...p, [id]: !p[id] }));

  /* ── Helpers: get sub-entities ── */
  const getCategorias = (classeId) => (categorias ?? []).filter((c) => c.classe === classeId);
  const getSubcategorias = (catId) => (subcategorias ?? []).filter((s) => s.categoria === catId);

  /* ── Modal dispatcher ── */
  const openModal = (config) => { setMutError(''); setModal(config); };

  if (isLoading) return (
    <div className="flex flex-col items-center justify-center min-h-[70vh] gap-4">
      <RefreshCw className="h-8 w-8 text-primary animate-spin" />
      <p className="text-sm font-semibold text-muted-foreground">Carregando estrutura ANBIMA...</p>
    </div>
  );

  if (errC) return (
    <div className="flex flex-col items-center justify-center min-h-[70vh] gap-4 text-center">
      <AlertCircle className="h-12 w-12 text-red-500" />
      <h3 className="text-xl font-bold text-slate-800 dark:text-slate-200">Erro ao carregar classes</h3>
      <Button onClick={() => refetchC()}>Tentar novamente</Button>
    </div>
  );

  return (
    <div className="space-y-6 animate-fade-in">

      {/* ── Header ── */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <div>
          <h1 className="text-3xl font-extrabold tracking-tight text-foreground">
            Classes de Ativos
          </h1>
          <p className="text-muted-foreground mt-1">
            Gerencie a hierarquia ANBIMA: Classe → Categoria → Subcategoria
          </p>
        </div>
        <div className="flex items-center gap-3 shrink-0">
          <Button
            onClick={() => openModal({ type: 'create-classe' })}
            className="h-9 px-4 rounded-xl text-xs font-semibold bg-primary hover:bg-primary/90 text-primary-foreground border-0 flex items-center gap-1.5"
          >
            <Plus className="h-4 w-4" />
            Nova Classe
          </Button>
          <Button variant="outline" size="icon" onClick={() => { refetchC(); refetchCat(); refetchSub(); }} className="rounded-xl h-9 w-9 shrink-0">
            <RefreshCw className="h-4 w-4 text-muted-foreground" />
          </Button>
        </div>
      </div>

      {/* ── Success ── */}
      {successMsg && (
        <Alert variant="success" icon={CheckCircle2} className="p-3.5 text-xs">
          <span className="font-semibold">{successMsg}</span>
        </Alert>
      )}

      {/* ── Legend ── */}
      <div className="flex items-center gap-6 text-[11px] text-muted-foreground flex-wrap">
        <div className="flex items-center gap-1.5"><FolderOpen className="h-3.5 w-3.5 text-primary" /> Classe (Nível 1)</div>
        <div className="flex items-center gap-1.5"><Folder className="h-3.5 w-3.5 text-blue-500" /> Categoria (Nível 2)</div>
        <div className="flex items-center gap-1.5"><Tag className="h-3.5 w-3.5 text-amber-500" /> Subcategoria (Nível 3)</div>
      </div>

      {/* ── Tree View ── */}
      <Card className="border border-border/40 bg-card shadow-sm">
        <CardHeader>
          <CardTitle className="text-base font-bold text-foreground flex items-center gap-2">
            <Layers className="h-4 w-4 text-primary" />
            Árvore de Classificação
          </CardTitle>
          <CardDescription className="text-xs">
            Clique em uma classe ou categoria para expandir e gerenciar os sub-níveis
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-2">
          {(classes ?? []).length === 0 ? (
            <div className="py-16 text-center">
              <Layers className="h-10 w-10 mx-auto mb-3 text-muted-foreground/50" />
              <p className="font-semibold text-muted-foreground">Nenhuma classe cadastrada</p>
              <p className="text-xs text-muted-foreground mt-1">Comece criando uma classe como "Renda Fixa" ou "Renda Variável"</p>
              <Button
                className="mt-4 h-8 px-4 rounded-xl text-xs bg-primary hover:bg-primary/90 text-primary-foreground border-0"
                onClick={() => openModal({ type: 'create-classe' })}
              >
                <Plus className="h-3.5 w-3.5 mr-1" /> Criar primeira classe
              </Button>
            </div>
          ) : (
            (classes ?? []).map((classe) => {
              const isExpandedC = expandedClasses[classe.id];
              const cats = getCategorias(classe.id);

              return (
                <div key={classe.id} className="border border-border/40 rounded-xl overflow-hidden">
                  
                  {/* ── Classe row ── */}
                  <div className="flex items-center gap-3 px-4 py-3 bg-muted/30 hover:bg-muted/60 transition-colors">
                    <button onClick={() => toggleClass(classe.id)} className="flex items-center gap-2.5 flex-1 min-w-0 text-left">
                      <div className="w-8 h-8 rounded-lg bg-primary/10 flex items-center justify-center shrink-0">
                        {isExpandedC ? <FolderOpen className="h-4 w-4 text-primary" /> : <Folder className="h-4 w-4 text-primary" />}
                      </div>
                      <div className="min-w-0">
                        <p className="text-sm font-bold text-foreground truncate">{classe.nome}</p>
                        <p className="text-[10px] text-muted-foreground">{cats.length} categoria{cats.length !== 1 ? 's' : ''}</p>
                      </div>
                      {isExpandedC ? <ChevronDown className="h-4 w-4 text-muted-foreground shrink-0" /> : <ChevronRight className="h-4 w-4 text-muted-foreground shrink-0" />}
                    </button>
                    {/* Actions */}
                    <div className="flex items-center gap-1.5 shrink-0">
                      <button
                        onClick={() => openModal({ type: 'create-cat', data: { classeId: classe.id, classeNome: classe.nome } })}
                        className="p-1.5 rounded-lg text-muted-foreground hover:bg-primary/10 hover:text-primary transition-colors" title="Nova categoria"
                      >
                        <Plus className="h-3.5 w-3.5" />
                      </button>
                      <button
                        onClick={() => openModal({ type: 'edit-classe', data: { id: classe.id, nome: classe.nome } })}
                        className="p-1.5 rounded-lg text-muted-foreground hover:bg-primary/10 hover:text-primary transition-colors" title="Editar classe"
                      >
                        <Pencil className="h-3.5 w-3.5" />
                      </button>
                      <button
                        onClick={() => openModal({ type: 'delete-classe', data: { id: classe.id, nome: classe.nome } })}
                        className="p-1.5 rounded-lg text-muted-foreground hover:bg-destructive/10 hover:text-destructive transition-colors" title="Excluir classe"
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </button>
                    </div>
                  </div>

                  {/* ── Categorias (collapsed) ── */}
                  {isExpandedC && (
                    <div className="px-4 pb-3 space-y-2 mt-2">
                      {cats.length === 0 ? (
                        <div className="ml-10 text-xs text-muted-foreground py-2 italic">
                          Nenhuma categoria. Clique em + para adicionar.
                        </div>
                      ) : (
                        cats.map((cat) => {
                          const isExpandedCat = expandedCats[cat.id];
                          const subs = getSubcategorias(cat.id);

                          return (
                            <div key={cat.id} className="ml-8 border border-border/30 rounded-xl overflow-hidden">
                              {/* ── Categoria row ── */}
                              <div className="flex items-center gap-3 px-4 py-2.5 bg-muted/20 hover:bg-muted/40 transition-colors">
                                <button onClick={() => toggleCat(cat.id)} className="flex items-center gap-2.5 flex-1 min-w-0 text-left">
                                  <div className="w-7 h-7 rounded-lg bg-blue-500/10 flex items-center justify-center shrink-0">
                                    {isExpandedCat ? <FolderOpen className="h-3.5 w-3.5 text-blue-500" /> : <Folder className="h-3.5 w-3.5 text-blue-500" />}
                                  </div>
                                  <div className="min-w-0">
                                    <p className="text-xs font-bold text-foreground truncate">{cat.nome}</p>
                                    <p className="text-[9px] text-muted-foreground">{subs.length} sub-categoria{subs.length !== 1 ? 's' : ''}</p>
                                  </div>
                                  {isExpandedCat ? <ChevronDown className="h-3.5 w-3.5 text-muted-foreground shrink-0" /> : <ChevronRight className="h-3.5 w-3.5 text-muted-foreground shrink-0" />}
                                </button>
                                <div className="flex items-center gap-1 shrink-0">
                                  <button onClick={() => openModal({ type: 'create-sub', data: { catId: cat.id, catNome: cat.nome } })}
                                    className="p-1.5 rounded-lg text-muted-foreground hover:bg-primary/10 hover:text-primary transition-colors" title="Nova subcategoria">
                                    <Plus className="h-3 w-3" />
                                  </button>
                                  <button onClick={() => openModal({ type: 'edit-cat', data: { id: cat.id, nome: cat.nome } })}
                                    className="p-1.5 rounded-lg text-muted-foreground hover:bg-primary/10 hover:text-primary transition-colors" title="Editar">
                                    <Pencil className="h-3 w-3" />
                                  </button>
                                  <button onClick={() => openModal({ type: 'delete-cat', data: { id: cat.id, nome: cat.nome } })}
                                    className="p-1.5 rounded-lg text-muted-foreground hover:bg-destructive/10 hover:text-destructive transition-colors" title="Excluir">
                                    <Trash2 className="h-3 w-3" />
                                  </button>
                                </div>
                              </div>

                              {/* ── Subcategorias ── */}
                              {isExpandedCat && (
                                <div className="px-4 pb-2 space-y-1.5 mt-1.5">
                                  {subs.length === 0 ? (
                                    <div className="ml-9 text-[11px] text-muted-foreground py-1.5 italic">
                                      Nenhuma subcategoria. Clique em + para adicionar.
                                    </div>
                                  ) : (
                                    subs.map((sub) => (
                                      <div key={sub.id} className="ml-9 flex items-center gap-3 px-3 py-2 rounded-lg bg-muted border border-border/30">
                                        <div className="w-6 h-6 rounded-md bg-amber-500/10 flex items-center justify-center shrink-0">
                                          <Tag className="h-3 w-3 text-amber-500" />
                                        </div>
                                        <span className="flex-1 text-xs font-medium text-foreground truncate">{sub.nome}</span>
                                        <div className="flex items-center gap-1 shrink-0">
                                          <button onClick={() => openModal({ type: 'edit-sub', data: { id: sub.id, nome: sub.nome } })}
                                            className="p-1 rounded-md text-muted-foreground hover:text-primary hover:bg-primary/10 transition-colors" title="Editar">
                                            <Pencil className="h-3 w-3" />
                                          </button>
                                          <button onClick={() => openModal({ type: 'delete-sub', data: { id: sub.id, nome: sub.nome } })}
                                            className="p-1 rounded-md text-muted-foreground hover:text-destructive hover:bg-destructive/10 transition-colors" title="Excluir">
                                            <Trash2 className="h-3 w-3" />
                                          </button>
                                        </div>
                                      </div>
                                    ))
                                  )}
                                </div>
                              )}
                            </div>
                          );
                        })
                      )}
                    </div>
                  )}
                </div>
              );
            })
          )}
        </CardContent>
      </Card>

      {/* ── Modals ── */}
      {modal?.type === 'create-classe' && (
        <QuickEditModal
          title="Nova Classe de Ativo"
          placeholder="Ex: Renda Variável"
          onSave={(nome) => createClasseMut.mutate(nome)}
          onClose={() => setModal(null)}
          isPending={createClasseMut.isPending}
          error={mutError}
        />
      )}
      {modal?.type === 'edit-classe' && (
        <QuickEditModal
          title="Editar Classe"
          placeholder="Nome da classe"
          initialValue={modal.data.nome}
          onSave={(nome) => updateClasseMut.mutate({ id: modal.data.id, nome })}
          onClose={() => setModal(null)}
          isPending={updateClasseMut.isPending}
          error={mutError}
        />
      )}
      {modal?.type === 'delete-classe' && (
        <DeleteConfirmModal
          label={modal.data.nome}
          onConfirm={() => deleteClasseMut.mutate(modal.data.id)}
          onClose={() => setModal(null)}
          isPending={deleteClasseMut.isPending}
        />
      )}
      {modal?.type === 'create-cat' && (
        <QuickEditModal
          title={`Nova Categoria em "${modal.data.classeNome}"`}
          placeholder="Ex: Ações Nacionais"
          onSave={(nome) => createCatMut.mutate({ nome, classe: modal.data.classeId })}
          onClose={() => setModal(null)}
          isPending={createCatMut.isPending}
          error={mutError}
        />
      )}
      {modal?.type === 'edit-cat' && (
        <QuickEditModal
          title="Editar Categoria"
          placeholder="Nome da categoria"
          initialValue={modal.data.nome}
          onSave={(nome) => updateCatMut.mutate({ id: modal.data.id, nome })}
          onClose={() => setModal(null)}
          isPending={updateCatMut.isPending}
          error={mutError}
        />
      )}
      {modal?.type === 'delete-cat' && (
        <DeleteConfirmModal
          label={modal.data.nome}
          onConfirm={() => deleteCatMut.mutate(modal.data.id)}
          onClose={() => setModal(null)}
          isPending={deleteCatMut.isPending}
        />
      )}
      {modal?.type === 'create-sub' && (
        <QuickEditModal
          title={`Nova Subcategoria em "${modal.data.catNome}"`}
          placeholder="Ex: Soberano, Crédito Privado..."
          onSave={(nome) => createSubMut.mutate({ nome, categoria: modal.data.catId })}
          onClose={() => setModal(null)}
          isPending={createSubMut.isPending}
          error={mutError}
        />
      )}
      {modal?.type === 'edit-sub' && (
        <QuickEditModal
          title="Editar Subcategoria"
          placeholder="Nome da subcategoria"
          initialValue={modal.data.nome}
          onSave={(nome) => updateSubMut.mutate({ id: modal.data.id, nome })}
          onClose={() => setModal(null)}
          isPending={updateSubMut.isPending}
          error={mutError}
        />
      )}
      {modal?.type === 'delete-sub' && (
        <DeleteConfirmModal
          label={modal.data.nome}
          onConfirm={() => deleteSubMut.mutate(modal.data.id)}
          onClose={() => setModal(null)}
          isPending={deleteSubMut.isPending}
        />
      )}
    </div>
  );
}
