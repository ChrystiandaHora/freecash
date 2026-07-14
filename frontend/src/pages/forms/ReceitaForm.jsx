import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { ArrowLeft, Loader2, Save, TrendingUp, Repeat, ArrowUpCircle } from 'lucide-react';

import { fetchReceita, createReceita, updateReceita } from '../../services/financeiro';
import { Button } from '../../components/ui/Button';
import { Input } from '../../components/ui/Input';
import { Select } from '../../components/ui/Select';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/Card';

const schema = z.object({
  descricao: z.string().min(3, 'Descrição obrigatória (mín. 3 caracteres)'),
  categoria: z.string().min(1, 'Informe a categoria'),
  valor: z.coerce.number().positive('Valor deve ser positivo'),
  data_recebimento: z.string().min(1, 'Data obrigatória'),
  tipo: z.enum(['unica', 'recorrente']),
  recorrencia: z.string().optional(),
  data_fim: z.string().optional(),
});

export default function ReceitaForm() {
  const { id } = useParams();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const isEdit = !!id;

  const [tipoSelecionado, setTipoSelecionado] = useState('unica');

  const { register, handleSubmit, reset, watch, setValue, formState: { errors, isSubmitting } } = useForm({
    resolver: zodResolver(schema),
    defaultValues: { tipo: 'unica' },
  });

  const watchTipo = watch('tipo');

  // Query to fetch single record when in edit mode
  const { data: receita, isLoading: isFetching } = useQuery({
    queryKey: ['receita', id],
    queryFn: () => fetchReceita(id),
    enabled: isEdit,
  });

  useEffect(() => {
    if (receita) {
      reset({
        descricao: receita.descricao,
        categoria: receita.categoria || '',
        valor: receita.valor,
        data_recebimento: receita.data_recebimento,
        tipo: receita.tipo === 'recorrente' ? 'recorrente' : 'unica',
        recorrencia: receita.recorrencia || '',
        data_fim: receita.data_fim || '',
      });
      setTipoSelecionado(receita.tipo === 'recorrente' ? 'recorrente' : 'unica');
    }
  }, [receita, reset]);

  const createMutation = useMutation({
    mutationFn: createReceita,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['receitas'] });
      navigate('/receitas');
    },
  });

  const updateMutation = useMutation({
    mutationFn: updateReceita,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['receitas'] });
      navigate('/receitas');
    },
  });

  const onSubmit = (values) => {
    if (isEdit) {
      updateMutation.mutate({ id, ...values });
    } else {
      createMutation.mutate(values);
    }
  };

  if (isEdit && isFetching) {
    return (
      <div className="flex h-96 items-center justify-center">
        <Loader2 className="h-8 w-8 text-primary animate-spin" />
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      {/* Header */}
      <div className="flex items-center gap-4">
        <button
          onClick={() => navigate('/receitas')}
          className="rounded-lg p-2 text-muted-foreground hover:bg-muted hover:text-foreground transition-colors"
          title="Voltar"
        >
          <ArrowLeft className="h-5 w-5" />
        </button>
        <div>
          <h2 className="text-2xl font-bold tracking-tight text-foreground">
            {isEdit ? 'Editar Receita' : 'Nova Receita'}
          </h2>
          <p className="text-sm text-muted-foreground">
            {isEdit ? 'Altere os dados da entrada financeira' : 'Cadastre uma entrada financeira única ou recorrente'}
          </p>
        </div>
      </div>

      {/* Card Form Container */}
      <Card className="border-border/60 shadow-lg">
        <CardHeader className="bg-muted/10 pb-4">
          <CardTitle className="text-sm font-semibold uppercase tracking-wider text-muted-foreground">
            Dados da Receita
          </CardTitle>
        </CardHeader>
        <CardContent className="p-6">
          <form onSubmit={handleSubmit(onSubmit)} className="space-y-6">
            {/* Tipo: Única ou Recorrente */}
            <div className="space-y-2">
              <label className="text-sm font-medium text-foreground">
                Tipo de Receita
              </label>
              <div className="flex gap-4">
                {[
                  { value: 'unica', label: 'Receita Única', Icon: ArrowUpCircle },
                  { value: 'recorrente', label: 'Recorrente', Icon: Repeat },
                ].map(({ value, label, Icon }) => (
                  <button
                    key={value}
                    type="button"
                    onClick={() => {
                      setValue('tipo', value);
                      setTipoSelecionado(value);
                    }}
                    className={`flex flex-1 items-center justify-center gap-2 rounded-xl border px-4 py-3 text-sm font-medium transition-all duration-200 ${
                      watchTipo === value
                        ? 'border-primary bg-primary/10 text-primary'
                        : 'border-border bg-background text-muted-foreground hover:border-primary/40'
                    }`}
                  >
                    <Icon className="h-4 w-4" />
                    {label}
                  </button>
                ))}
              </div>
            </div>

            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <div className="sm:col-span-2 space-y-1.5">
                <label className="text-sm font-medium text-foreground">
                  Descrição <span className="text-red-500">*</span>
                </label>
                <Input {...register('descricao')} placeholder="Ex: Salário, Freelance React..." />
                {errors.descricao && (
                  <p className="text-xs text-red-500">{errors.descricao.message}</p>
                )}
              </div>

              <div className="space-y-1.5">
                <label className="text-sm font-medium text-foreground">
                  Categoria <span className="text-red-500">*</span>
                </label>
                <Input {...register('categoria')} placeholder="Ex: Salário, Dividendos" />
                {errors.categoria && (
                  <p className="text-xs text-red-500">{errors.categoria.message}</p>
                )}
              </div>

              <div className="space-y-1.5">
                <label className="text-sm font-medium text-foreground">
                  Valor (R$) <span className="text-red-500">*</span>
                </label>
                <Input {...register('valor')} type="number" step="0.01" placeholder="0,00" />
                {errors.valor && (
                  <p className="text-xs text-red-500">{errors.valor.message}</p>
                )}
              </div>

              <div className={`space-y-1.5 ${watchTipo === 'recorrente' ? '' : 'sm:col-span-2'}`}>
                <label className="text-sm font-medium text-foreground">
                  Data de Recebimento <span className="text-red-500">*</span>
                </label>
                <Input {...register('data_recebimento')} type="date" />
                {errors.data_recebimento && (
                  <p className="text-xs text-red-500">{errors.data_recebimento.message}</p>
                )}
              </div>

              {watchTipo === 'recorrente' && (
                <div className="space-y-1.5">
                  <label className="text-sm font-medium text-foreground">
                    Frequência
                  </label>
                  <Select {...register('recorrencia')}>
                    <option value="">Selecione...</option>
                    <option value="mensal">Mensal</option>
                    <option value="quinzenal">Quinzenal</option>
                    <option value="semanal">Semanal</option>
                    <option value="anual">Anual</option>
                  </Select>
                </div>
              )}

              {watchTipo === 'recorrente' && (
                <div className="space-y-1.5">
                  <label className="text-sm font-medium text-foreground">
                    Repetir Até (opcional)
                  </label>
                  <Input {...register('data_fim')} type="date" />
                  <p className="text-[10px] text-muted-foreground">Deixe em branco para recorrência indefinida.</p>
                </div>
              )}
            </div>

            {(createMutation.isError || updateMutation.isError) && (
              <p className="text-sm text-red-500">Erro ao salvar receita. Tente novamente.</p>
            )}

            <div className="flex justify-end gap-3 pt-4 border-t border-border/60">
              <Button
                variant="outline"
                type="button"
                onClick={() => navigate('/receitas')}
                disabled={isSubmitting}
                className="rounded-xl"
              >
                Cancelar
              </Button>
              <Button
                type="submit"
                disabled={isSubmitting || createMutation.isPending || updateMutation.isPending}
                className="bg-primary hover:bg-primary/90 text-primary-foreground border-0 rounded-xl"
              >
                {(isSubmitting || createMutation.isPending || updateMutation.isPending) ? (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                ) : (
                  <Save className="mr-1.5 h-4 w-4" />
                )}
                Salvar Receita
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
