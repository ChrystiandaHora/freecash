import { useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { ArrowLeft, Loader2, Save, DollarSign, RotateCcw } from 'lucide-react';

import { fetchContaPagar, createContaPagar, updateContaPagar, desfazerPagamentoConta } from '../../services/financeiro';
import { Button } from '../../components/ui/Button';
import { Input } from '../../components/ui/Input';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/Card';

const schema = z.object({
  descricao: z.string().min(3, 'Descrição obrigatória (mín. 3 caracteres)'),
  categoria: z.string().min(1, 'Informe a categoria'),
  valor: z.coerce.number().positive('Valor deve ser positivo'),
  data_vencimento: z.string().min(1, 'Data de vencimento obrigatória'),
});

export default function ContaPagarForm() {
  const { id } = useParams();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const isEdit = !!id;

  const { register, handleSubmit, reset, formState: { errors, isSubmitting } } = useForm({
    resolver: zodResolver(schema),
  });

  // Query to fetch single record when in edit mode
  const { data: conta, isLoading: isFetching } = useQuery({
    queryKey: ['conta-pagar', id],
    queryFn: () => fetchContaPagar(id),
    enabled: isEdit,
  });

  useEffect(() => {
    if (conta) {
      reset({
        descricao: conta.descricao,
        categoria: conta.categoria || '',
        valor: conta.valor,
        data_vencimento: conta.data_vencimento,
      });
    }
  }, [conta, reset]);

  const createMutation = useMutation({
    mutationFn: createContaPagar,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['contas-pagar'] });
      navigate('/contas-pagar');
    },
  });

  const updateMutation = useMutation({
    mutationFn: updateContaPagar,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['contas-pagar'] });
      navigate('/contas-pagar');
    },
  });

  const desfazerMutation = useMutation({
    mutationFn: desfazerPagamentoConta,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['contas-pagar'] });
      navigate('/contas-pagar');
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

  const isFaturaCartao = !!conta?.eh_fatura_cartao;

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      {/* Header */}
      <div className="flex items-center gap-4">
        <button
          onClick={() => navigate('/contas-pagar')}
          className="rounded-lg p-2 text-muted-foreground hover:bg-muted hover:text-foreground transition-colors"
          title="Voltar"
        >
          <ArrowLeft className="h-5 w-5" />
        </button>
        <div>
          <h2 className="text-2xl font-bold tracking-tight text-foreground">
            {isEdit ? 'Editar Conta a Pagar' : 'Nova Conta a Pagar'}
          </h2>
          <p className="text-sm text-muted-foreground">
            {isEdit ? 'Altere os dados da obrigação financeira' : 'Preencha os dados da obrigação financeira'}
          </p>
        </div>
      </div>

      {/* Card Form Container */}
      <Card className="border-border/60 shadow-lg">
        <CardHeader className="bg-muted/10 pb-4">
          <CardTitle className="text-sm font-semibold uppercase tracking-wider text-muted-foreground">
            Dados da Obrigação
          </CardTitle>
        </CardHeader>
        <CardContent className="p-6">
          <form onSubmit={handleSubmit(onSubmit)} className="space-y-6">
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <div className="sm:col-span-2 space-y-1.5">
                <label className="text-sm font-medium text-foreground">
                  Descrição <span className="text-red-500">*</span>
                </label>
                <Input
                  {...register('descricao')}
                  placeholder="Ex: Aluguel Março"
                  readOnly={isFaturaCartao}
                  className={isFaturaCartao ? "bg-muted cursor-not-allowed" : ""}
                />
                {errors.descricao && (
                  <p className="text-xs text-red-500">{errors.descricao.message}</p>
                )}
              </div>

              <div className="space-y-1.5">
                <label className="text-sm font-medium text-foreground">
                  Categoria <span className="text-red-500">*</span>
                </label>
                <Input
                  {...register('categoria')}
                  placeholder="Ex: Moradia"
                  readOnly={isFaturaCartao}
                  className={isFaturaCartao ? "bg-muted cursor-not-allowed" : ""}
                />
                {errors.categoria && (
                  <p className="text-xs text-red-500">{errors.categoria.message}</p>
                )}
              </div>

              <div className="space-y-1.5">
                <label className="text-sm font-medium text-foreground">
                  Valor (R$) <span className="text-red-500">*</span>
                </label>
                <Input
                  {...register('valor')}
                  type="number"
                  step="0.01"
                  placeholder="0,00"
                  readOnly={isFaturaCartao}
                  className={isFaturaCartao ? "bg-muted cursor-not-allowed" : ""}
                />
                {errors.valor && (
                  <p className="text-xs text-red-500">{errors.valor.message}</p>
                )}
              </div>

              <div className="sm:col-span-2 space-y-1.5">
                <label className="text-sm font-medium text-foreground">
                  Data de Vencimento <span className="text-red-500">*</span>
                </label>
                <Input
                  {...register('data_vencimento')}
                  type="date"
                  readOnly={isFaturaCartao}
                  className={isFaturaCartao ? "bg-muted cursor-not-allowed" : ""}
                />
                {errors.data_vencimento && (
                  <p className="text-xs text-red-500">{errors.data_vencimento.message}</p>
                )}
              </div>
            </div>

            {(createMutation.isError || updateMutation.isError) && (
              <p className="text-sm text-red-500">Erro ao salvar conta. Tente novamente.</p>
            )}

            {conta?.pago && (
              <div className="rounded-xl border border-amber-200 dark:border-amber-800 bg-amber-50 dark:bg-amber-950/20 p-4 flex items-center justify-between gap-3">
                <span className="text-sm text-amber-800 dark:text-amber-300">
                  Esta conta está marcada como <strong>paga</strong>. Deseja reverter o status?
                </span>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  className="shrink-0 border-amber-400 text-amber-700 hover:bg-amber-100 dark:border-amber-600 dark:text-amber-300 rounded-xl"
                  onClick={() => desfazerMutation.mutate(conta.id)}
                  disabled={desfazerMutation.isPending}
                >
                  {desfazerMutation.isPending ? (
                    <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" />
                  ) : (
                    <RotateCcw className="mr-1.5 h-3.5 w-3.5" />
                  )}
                  Desfazer Pagamento
                </Button>
              </div>
            )}

            <div className="flex justify-end gap-3 pt-4 border-t border-border/60">
              <Button
                variant="outline"
                type="button"
                onClick={() => navigate('/contas-pagar')}
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
                Salvar Conta
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
