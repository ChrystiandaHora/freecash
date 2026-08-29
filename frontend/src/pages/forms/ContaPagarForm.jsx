import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { ArrowLeft, Loader2, Save, RotateCcw } from 'lucide-react';

import { fetchContaPagar, createContaPagar, updateContaPagar, desfazerPagamentoConta } from '../../services/financeiro';
import { Button } from '../../components/ui/Button';
import { Input } from '../../components/ui/Input';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/Card';

const schema = z.object({
  descricao: z.string().min(3, 'Descrição obrigatória (mín. 3 caracteres)'),
  categoria: z.string().min(1, 'Informe a categoria'),
  valor: z.coerce.number().positive('Valor deve ser positivo'),
  data_vencimento: z.string().min(1, 'Data de vencimento obrigatória'),
  // Vazio significa despesa avulsa; preenchido cria uma regra de despesa fixa.
  recorrencia: z.string().optional(),
  data_fim: z.string().optional(),
});

const FREQUENCIAS = [
  { valor: 'mensal', rotulo: 'Todo mês' },
  { valor: 'quinzenal', rotulo: 'A cada 15 dias' },
  { valor: 'semanal', rotulo: 'Toda semana' },
  { valor: 'anual', rotulo: 'Uma vez por ano' },
];

export default function ContaPagarForm() {
  const { id } = useParams();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const isEdit = !!id;

  const { register, handleSubmit, reset, formState: { errors, isSubmitting } } = useForm({
    resolver: zodResolver(schema),
  });

  // Despesa fixa só pode ser definida na criação: editar uma ocorrência já gerada
  // altera aquele lançamento, não a regra que o produziu.
  const [ehFixa, setEhFixa] = useState(false);

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
      // `recorrencia` e `data_fim` não participam da edição de uma ocorrência:
      // editar um lançamento gerado altera aquele registro, não a regra.
      const campos = { ...values };
      delete campos.recorrencia;
      delete campos.data_fim;
      updateMutation.mutate({ id, ...campos });
      return;
    }

    const dados = { ...values };
    if (!ehFixa) {
      delete dados.recorrencia;
      delete dados.data_fim;
    } else if (!dados.data_fim) {
      // String vazia viraria uma data inválida no servidor.
      delete dados.data_fim;
    }
    createMutation.mutate(dados);
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
          aria-label="Voltar"
        >
          <ArrowLeft className="h-5 w-5" aria-hidden="true" />
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
                <label htmlFor="conta-descricao" className="text-sm font-medium text-foreground">
                  Descrição <span className="text-red-500">*</span>
                </label>
                <Input
                  id="conta-descricao"
                  {...register('descricao')}
                  placeholder="Ex: Aluguel Março"
                  readOnly={isFaturaCartao}
                  className={isFaturaCartao ? "bg-muted cursor-not-allowed" : ""}
                  aria-invalid={!!errors.descricao}
                  aria-describedby={errors.descricao ? "conta-descricao-error" : undefined}
                />
                {errors.descricao && (
                  <p id="conta-descricao-error" role="alert" className="text-xs text-red-500">{errors.descricao.message}</p>
                )}
              </div>

              <div className="space-y-1.5">
                <label htmlFor="conta-categoria" className="text-sm font-medium text-foreground">
                  Categoria <span className="text-red-500">*</span>
                </label>
                <Input
                  id="conta-categoria"
                  {...register('categoria')}
                  placeholder="Ex: Moradia"
                  readOnly={isFaturaCartao}
                  className={isFaturaCartao ? "bg-muted cursor-not-allowed" : ""}
                  aria-invalid={!!errors.categoria}
                  aria-describedby={errors.categoria ? "conta-categoria-error" : undefined}
                />
                {errors.categoria && (
                  <p id="conta-categoria-error" role="alert" className="text-xs text-red-500">{errors.categoria.message}</p>
                )}
              </div>

              <div className="space-y-1.5">
                <label htmlFor="conta-valor" className="text-sm font-medium text-foreground">
                  Valor (R$) <span className="text-red-500">*</span>
                </label>
                <Input
                  id="conta-valor"
                  {...register('valor')}
                  type="number"
                  step="0.01"
                  placeholder="0,00"
                  readOnly={isFaturaCartao}
                  className={isFaturaCartao ? "bg-muted cursor-not-allowed" : ""}
                  aria-invalid={!!errors.valor}
                  aria-describedby={errors.valor ? "conta-valor-error" : undefined}
                />
                {errors.valor && (
                  <p id="conta-valor-error" role="alert" className="text-xs text-red-500">{errors.valor.message}</p>
                )}
              </div>

              <div className="sm:col-span-2 space-y-1.5">
                <label htmlFor="conta-vencimento" className="text-sm font-medium text-foreground">
                  Data de Vencimento <span className="text-red-500">*</span>
                </label>
                <Input
                  id="conta-vencimento"
                  {...register('data_vencimento')}
                  type="date"
                  readOnly={isFaturaCartao}
                  className={isFaturaCartao ? "bg-muted cursor-not-allowed" : ""}
                  aria-invalid={!!errors.data_vencimento}
                  aria-describedby={errors.data_vencimento ? "conta-vencimento-error" : undefined}
                />
                {errors.data_vencimento && (
                  <p id="conta-vencimento-error" role="alert" className="text-xs text-red-500">{errors.data_vencimento.message}</p>
                )}
              </div>

              {/* Despesa fixa. Só aparece na criação: editar uma ocorrência
                  altera aquele lançamento, não a regra que o gerou. É o que
                  permite ao Horizonte de Saldos projetar aluguel, assinaturas e
                  contas de consumo pelos doze meses da janela — sem isto, a
                  projeção enxergaria só as despesas lançadas mês a mês e a curva
                  subiria de forma irreal. */}
              {!isEdit && !isFaturaCartao && (
                <div className="sm:col-span-2 space-y-3 rounded-xl border border-border/50 p-4">
                  <div className="flex items-start gap-3">
                    <input
                      id="conta-eh-fixa"
                      type="checkbox"
                      checked={ehFixa}
                      onChange={(e) => setEhFixa(e.target.checked)}
                      className="mt-0.5 h-4 w-4 rounded border-border accent-primary"
                      aria-describedby="ajuda-conta-eh-fixa"
                    />
                    <div>
                      <label htmlFor="conta-eh-fixa" className="text-sm font-medium text-foreground">
                        É uma despesa fixa
                      </label>
                      <p id="ajuda-conta-eh-fixa" className="text-xs text-muted-foreground">
                        Repete automaticamente e entra na projeção do Horizonte de Saldos.
                      </p>
                    </div>
                  </div>

                  {ehFixa && (
                    <div className="grid gap-4 sm:grid-cols-2">
                      <div className="space-y-1.5">
                        <label htmlFor="conta-recorrencia" className="text-sm font-medium text-foreground">
                          Com que frequência?
                        </label>
                        <select
                          id="conta-recorrencia"
                          {...register('recorrencia')}
                          className="h-10 w-full rounded-xl border border-border bg-card px-3 text-sm text-foreground"
                        >
                          {FREQUENCIAS.map((f) => (
                            <option key={f.valor} value={f.valor}>{f.rotulo}</option>
                          ))}
                        </select>
                      </div>

                      <div className="space-y-1.5">
                        <label htmlFor="conta-data-fim" className="text-sm font-medium text-foreground">
                          Até quando?
                        </label>
                        <Input
                          id="conta-data-fim"
                          {...register('data_fim')}
                          type="date"
                          aria-describedby="ajuda-conta-data-fim"
                        />
                        <p id="ajuda-conta-data-fim" className="text-xs text-muted-foreground">
                          Deixe em branco se não tem data para acabar.
                        </p>
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>

            {(createMutation.isError || updateMutation.isError) && (
              <p role="alert" className="text-sm text-red-500">Erro ao salvar conta. Tente novamente.</p>
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
