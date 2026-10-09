/**
 * Modal de Cadastro e Edição de Evento Fora do Orçamento.
 *
 * Permite cadastrar ou editar ocasiões extraordinárias (viagens, reformas, festas)
 * definindo o período, orçamento planejado e se as despesas devem ser
 * excluídas dos relatórios mensais (DRE, médias históricas e metas).
 *
 * @param {Object} props
 * @param {boolean} props.isOpen - Se a modal está visível.
 * @param {Object|null} [props.evento] - Evento em edição (ou null para novo).
 * @param {Function} props.onClose - Callback de fechamento.
 * @param {Function} [props.onSaved] - Callback chamado após salvar com sucesso.
 */
import { useEffect } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { Loader2, Save, Sparkles } from 'lucide-react';

import { createEvento, updateEvento } from '../services/financeiro';
import { Button } from './ui/Button';
import { Input } from './ui/Input';
import { Modal } from './ui/Modal';
import { useToast } from '../context/ToastContext';

const schema = z
  .object({
    nome: z.string().min(2, 'Nome do evento é obrigatório (mínimo 2 caracteres)'),
    inicio: z.string().min(1, 'Data de início é obrigatória'),
    fim: z.string().optional(),
    orcamento: z.union([z.coerce.number().min(0, 'Orçamento não pode ser negativo'), z.literal('')]).optional(),
    fora_dos_relatorios: z.boolean(),
  })
  .superRefine((data, ctx) => {
    if (data.inicio && data.fim && data.fim < data.inicio) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        path: ['fim'],
        message: 'A data final não pode ser anterior à data de início',
      });
    }
  });

export default function EventoFormModal({ isOpen, evento, onClose, onSaved }) {
  const queryClient = useQueryClient();
  const { addToast } = useToast();
  const isEdicao = !!evento?.id;

  const {
    register,
    handleSubmit,
    reset,
    watch,
    formState: { errors },
  } = useForm({
    resolver: zodResolver(schema),
    defaultValues: {
      nome: '',
      inicio: '',
      fim: '',
      orcamento: '',
      fora_dos_relatorios: true,
    },
  });

  useEffect(() => {
    if (!isOpen) return;
    if (evento) {
      reset({
        nome: evento.nome || '',
        inicio: evento.inicio || '',
        fim: evento.fim || '',
        orcamento: evento.orcamento != null ? Number(evento.orcamento) : '',
        fora_dos_relatorios: evento.fora_dos_relatorios ?? true,
      });
    } else {
      const hoje = new Date().toISOString().split('T')[0];
      reset({
        nome: '',
        inicio: hoje,
        fim: '',
        orcamento: '',
        fora_dos_relatorios: true,
      });
    }
  }, [isOpen, evento, reset]);

  const foraDosRelatorios = watch('fora_dos_relatorios');

  const saveMutation = useMutation({
    mutationFn: (values) => {
      const payload = {
        nome: values.nome.trim(),
        inicio: values.inicio,
        fim: values.fim ? values.fim : null,
        orcamento: values.orcamento !== '' && values.orcamento != null ? Number(values.orcamento) : null,
        fora_dos_relatorios: values.fora_dos_relatorios,
      };
      return isEdicao ? updateEvento(evento.id, payload) : createEvento(payload);
    },
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['eventos'] });
      queryClient.invalidateQueries({ queryKey: ['evento', evento?.id] });
      queryClient.invalidateQueries({ queryKey: ['evento-resumo', evento?.id] });
      queryClient.invalidateQueries({ queryKey: ['dashboard'] });
      addToast(
        isEdicao ? 'Evento atualizado com sucesso!' : 'Evento criado com sucesso!',
        'success'
      );
      onSaved?.(data);
      onClose();
    },
    onError: (err) => {
      const errorMsg =
        err?.response?.data?.detail ||
        err?.response?.data?.nome?.[0] ||
        'Não foi possível salvar o evento. Verifique os dados e tente novamente.';
      addToast(errorMsg, 'error');
    },
  });

  const onSubmit = (values) => {
    saveMutation.mutate(values);
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title={isEdicao ? 'Editar Evento' : 'Novo Evento'}
      description={
        isEdicao
          ? 'Atualize os dados e o teto orçamentário do evento.'
          : 'Cadastre viagens, reformas ou ocasiões especiais para isolar do orçamento mensal.'
      }
      size="md"
    >
      <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
        <div className="space-y-1.5">
          <label htmlFor="evento-nome" className="text-sm font-medium text-foreground">
            Nome do evento <span className="text-red-500">*</span>
          </label>
          <Input
            id="evento-nome"
            {...register('nome')}
            placeholder="Ex: Viagem Santiago, Reforma da Cozinha..."
            aria-invalid={!!errors.nome}
            aria-describedby={errors.nome ? 'evento-nome-error' : undefined}
          />
          {errors.nome && (
            <p id="evento-nome-error" role="alert" className="text-xs text-red-500">
              {errors.nome.message}
            </p>
          )}
        </div>

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <div className="space-y-1.5">
            <label htmlFor="evento-inicio" className="text-sm font-medium text-foreground">
              Data de Início <span className="text-red-500">*</span>
            </label>
            <Input
              id="evento-inicio"
              type="date"
              {...register('inicio')}
              aria-invalid={!!errors.inicio}
              aria-describedby={errors.inicio ? 'evento-inicio-error' : undefined}
            />
            {errors.inicio && (
              <p id="evento-inicio-error" role="alert" className="text-xs text-red-500">
                {errors.inicio.message}
              </p>
            )}
          </div>

          <div className="space-y-1.5">
            <label htmlFor="evento-fim" className="text-sm font-medium text-foreground">
              Data de Término
            </label>
            <Input
              id="evento-fim"
              type="date"
              {...register('fim')}
              aria-invalid={!!errors.fim}
              aria-describedby={errors.fim ? 'evento-fim-error' : undefined}
            />
            {errors.fim && (
              <p id="evento-fim-error" role="alert" className="text-xs text-red-500">
                {errors.fim.message}
              </p>
            )}
          </div>
        </div>

        <div className="space-y-1.5">
          <label htmlFor="evento-orcamento" className="text-sm font-medium text-foreground">
            Orçamento Planejado (R$)
          </label>
          <Input
            id="evento-orcamento"
            type="number"
            step="0.01"
            placeholder="Ex: 5000,00 (opcional)"
            {...register('orcamento')}
            aria-invalid={!!errors.orcamento}
            aria-describedby={errors.orcamento ? 'evento-orcamento-error' : 'evento-orcamento-hint'}
          />
          <p id="evento-orcamento-hint" className="text-xs text-muted-foreground">
            Deixe em branco se não houver um teto fixo estipulado.
          </p>
          {errors.orcamento && (
            <p id="evento-orcamento-error" role="alert" className="text-xs text-red-500">
              {errors.orcamento.message}
            </p>
          )}
        </div>

        <div className="rounded-lg border border-border/60 bg-muted/30 p-3.5 space-y-2">
          <label className="flex items-start gap-3 cursor-pointer select-none">
            <input
              type="checkbox"
              id="evento-fora-dos-relatorios"
              {...register('fora_dos_relatorios')}
              className="mt-1 h-4 w-4 rounded border-border text-primary focus:ring-primary focus:ring-offset-background"
            />
            <div className="space-y-1">
              <span className="text-sm font-medium text-foreground flex items-center gap-1.5">
                <Sparkles className="h-4 w-4 text-primary" />
                Isolar dos relatórios mensais e metas
              </span>
              <p className="text-xs text-muted-foreground leading-relaxed">
                {foraDosRelatorios
                  ? 'Recomendado: os gastos deste evento deduzem do seu caixa real, mas NÃO inflam o DRE, a média de 6 meses nem a meta de custo de vida.'
                  : 'Atenção: as despesas deste evento serão contabilizadas nos relatórios mensais normais e no DRE.'}
              </p>
            </div>
          </label>
        </div>

        <div className="flex justify-end gap-3 pt-3 border-t border-border/40">
          <Button
            type="button"
            variant="outline"
            onClick={onClose}
            disabled={saveMutation.isPending}
          >
            Cancelar
          </Button>
          <Button
            type="submit"
            disabled={saveMutation.isPending}
            className="gap-2"
          >
            {saveMutation.isPending ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                Salvando...
              </>
            ) : (
              <>
                <Save className="h-4 w-4" />
                {isEdicao ? 'Salvar Alterações' : 'Criar Evento'}
              </>
            )}
          </Button>
        </div>
      </form>
    </Modal>
  );
}
