import { useEffect, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { ArrowLeft, Loader2, Save, Layers } from 'lucide-react';

import api from '../../services/api';
import { Button } from '../../components/ui/Button';
import { Input } from '../../components/ui/Input';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/Card';

export default function AtivosClassesForm() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const queryClient = useQueryClient();

  const type = searchParams.get('type') || 'classe'; // 'classe' | 'categoria' | 'subcategoria'
  const id = searchParams.get('id');
  const parentId = searchParams.get('parentId');
  const parentName = searchParams.get('parentName');
  const initialValue = searchParams.get('initialValue') || '';
  const isEdit = !!id;

  const [nome, setNome] = useState(initialValue);
  const [error, setError] = useState('');

  useEffect(() => {
    if (initialValue) {
      setNome(initialValue);
    }
  }, [initialValue]);

  const mutation = useMutation({
    mutationFn: async (val) => {
      if (type === 'classe') {
        if (isEdit) {
          return api.patch(`/api/investimentos/classes/${id}/`, { nome: val });
        } else {
          return api.post('/api/investimentos/classes/', { nome: val });
        }
      } else if (type === 'categoria') {
        if (isEdit) {
          return api.patch(`/api/investimentos/categorias/${id}/`, { nome: val });
        } else {
          return api.post('/api/investimentos/categorias/', { nome: val, classe: parseInt(parentId) });
        }
      } else if (type === 'subcategoria') {
        if (isEdit) {
          return api.patch(`/api/investimentos/subcategorias/${id}/`, { nome: val });
        } else {
          return api.post('/api/investimentos/subcategorias/', { nome: val, categoria: parseInt(parentId) });
        }
      }
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['classesAtivos'] });
      queryClient.invalidateQueries({ queryKey: ['categoriasAtivos'] });
      queryClient.invalidateQueries({ queryKey: ['subcategoriasAtivos'] });
      navigate('/investimentos/classes');
    },
    onError: (e) => {
      setError(e?.response?.data?.detail || e?.response?.data?.nome?.[0] || 'Erro ao salvar alteração.');
    }
  });

  const handleSubmit = (e) => {
    e.preventDefault();
    setError('');
    if (!nome.trim()) {
      setError('O nome não pode estar vazio.');
      return;
    }
    mutation.mutate(nome.trim());
  };

  const getTypeNameLabel = () => {
    if (type === 'classe') return 'Classe';
    if (type === 'categoria') return 'Categoria';
    return 'Subcategoria';
  };

  const title = isEdit 
    ? `Editar ${getTypeNameLabel()}`
    : `Nova ${getTypeNameLabel()}${parentName ? ` em "${parentName}"` : ''}`;

  return (
    <div className="mx-auto max-w-xl space-y-6">
      {/* Header */}
      <div className="flex items-center gap-4">
        <button
          onClick={() => navigate('/investimentos/classes')}
          className="rounded-lg p-2 text-muted-foreground hover:bg-muted hover:text-foreground transition-colors"
          title="Voltar"
        >
          <ArrowLeft className="h-5 w-5" />
        </button>
        <div>
          <h2 className="text-2xl font-bold tracking-tight text-foreground">
            {title}
          </h2>
          <p className="text-sm text-muted-foreground">
            Ajuste a estrutura da hierarquia ANBIMA para seus investimentos.
          </p>
        </div>
      </div>

      {/* Card Form */}
      <Card className="border-border/60 shadow-lg">
        <CardHeader className="bg-muted/10 pb-4">
          <CardTitle className="text-sm font-semibold uppercase tracking-wider text-muted-foreground flex items-center gap-2">
            <Layers className="h-4 w-4 text-muted-foreground" />
            Dados da Classificação
          </CardTitle>
        </CardHeader>
        <CardContent className="p-6">
          <form onSubmit={handleSubmit} className="space-y-6">
            <div className="space-y-1.5">
              <label className="text-sm font-medium text-foreground">
                Nome da {getTypeNameLabel()} *
              </label>
              <Input
                placeholder={`Ex: ${type === 'classe' ? 'Renda Variável' : type === 'categoria' ? 'Ações' : 'Ações Brasil'}`}
                value={nome}
                onChange={(e) => { setNome(e.target.value); setError(''); }}
                autoFocus
              />
              {error && <p className="text-xs text-red-500">{error}</p>}
            </div>

            {/* Actions */}
            <div className="flex justify-end gap-3 pt-4 border-t border-border/60">
              <Button
                type="button"
                variant="outline"
                onClick={() => navigate('/investimentos/classes')}
                disabled={mutation.isPending}
                className="rounded-xl"
              >
                Cancelar
              </Button>
              <Button
                type="submit"
                disabled={mutation.isPending}
                className="bg-primary hover:bg-primary/90 text-primary-foreground border-0 rounded-xl"
              >
                {mutation.isPending ? (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                ) : (
                  <Save className="mr-1.5 h-4 w-4" />
                )}
                Salvar
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
