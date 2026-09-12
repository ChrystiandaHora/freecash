/** Gerenciamento das carteiras de investimento (custódia por corretora ou banco). */
import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  AlertCircle,
  Archive,
  ArchiveRestore,
  Landmark,
  Pencil,
  Plus,
  RefreshCw,
  Trash2,
  Wallet,
} from 'lucide-react';

import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '../components/ui/Card';

const formatCurrency = (val) =>
  new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(val ?? 0);
import { Button } from '../components/ui/Button';
import { Alert } from '../components/ui/Alert';
import { Modal } from '../components/ui/Modal';
import CarteiraFormModal from '../components/CarteiraFormModal';
import { useToast } from '../context/ToastContext';
import {
  deleteCarteira,
  fetchCarteiras,
  updateCarteira,
} from '../services/investimentos';

/**
 * Confirmação de exclusão. Só aparece para carteira sem ordens — o backend recusa
 * as demais com 409, e o caminho delas é arquivar.
 */
function ExcluirCarteiraModal({ carteira, onConfirm, onClose, isPending }) {
  return (
    <Modal isOpen title="Confirmar exclusão" onClose={onClose} size="sm">
      <div className="flex flex-col items-center gap-4 text-center">
        <div className="flex h-14 w-14 items-center justify-center rounded-full bg-destructive/10">
          <Trash2 className="h-6 w-6 text-destructive" aria-hidden="true" />
        </div>
        <p className="text-sm text-muted-foreground">
          Excluir a carteira <span className="font-semibold text-foreground">"{carteira.nome}"</span>?
          Esta ação não pode ser desfeita.
        </p>
        <div className="flex w-full gap-3">
          <Button variant="outline" onClick={onClose} className="h-10 flex-1 rounded-xl text-xs">
            Cancelar
          </Button>
          <Button
            onClick={onConfirm}
            disabled={isPending}
            className="h-10 flex-1 rounded-xl border-0 bg-destructive text-xs text-destructive-foreground hover:bg-destructive/90"
          >
            {isPending ? <RefreshCw className="h-4 w-4 animate-spin" aria-hidden="true" /> : 'Excluir'}
          </Button>
        </div>
      </div>
    </Modal>
  );
}

export default function AtivosCarteiras() {
  const queryClient = useQueryClient();
  const { addToast } = useToast();

  const [formAberto, setFormAberto] = useState(false);
  const [emEdicao, setEmEdicao] = useState(null);
  const [paraExcluir, setParaExcluir] = useState(null);

  const {
    data: carteiras = [],
    isLoading,
    isError,
    refetch,
  } = useQuery({ queryKey: ['carteiras'], queryFn: fetchCarteiras });

  const invalidar = () => {
    queryClient.invalidateQueries({ queryKey: ['carteiras'] });
    queryClient.invalidateQueries({ queryKey: ['investimentosDashboard'] });
  };

  const arquivarMutation = useMutation({
    mutationFn: ({ id, ativa }) => updateCarteira({ id, ativa }),
    onSuccess: (_, variaveis) => {
      invalidar();
      addToast(
        variaveis.ativa ? 'Carteira reativada.' : 'Carteira arquivada. O histórico foi preservado.',
        'success'
      );
    },
    onError: () => addToast('Não foi possível alterar a carteira.', 'error'),
  });

  const excluirMutation = useMutation({
    mutationFn: (id) => deleteCarteira(id),
    onSuccess: () => {
      invalidar();
      setParaExcluir(null);
      addToast('Carteira excluída.', 'success');
    },
    onError: (erro) => {
      setParaExcluir(null);
      addToast(
        erro?.response?.data?.detail ??
          'Não foi possível excluir a carteira. Arquive-a para tirá-la dos filtros.',
        'error'
      );
    },
  });

  const abrirCriacao = () => {
    setEmEdicao(null);
    setFormAberto(true);
  };

  const abrirEdicao = (carteira) => {
    setEmEdicao(carteira);
    setFormAberto(true);
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="flex items-center gap-2 text-xl font-semibold text-foreground">
            <Wallet className="h-5 w-5 text-primary" aria-hidden="true" />
            Carteiras
          </h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Uma carteira por corretora ou banco. Os ativos continuam únicos — o que muda é
            onde cada posição está custodiada.
          </p>
        </div>
        <Button onClick={abrirCriacao} className="rounded-xl">
          <Plus className="mr-1.5 h-4 w-4" aria-hidden="true" />
          Nova carteira
        </Button>
      </div>

      {isError && (
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" aria-hidden="true" />
          <span>
            Não foi possível carregar as carteiras.{' '}
            <button type="button" onClick={() => refetch()} className="underline">
              Tentar de novo
            </button>
          </span>
        </Alert>
      )}

      {isLoading ? (
        <p role="status" className="text-sm text-muted-foreground">Carregando carteiras…</p>
      ) : (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
          {carteiras.map((carteira) => (
            <Card
              key={carteira.id}
              className={carteira.ativa ? '' : 'opacity-70'}
            >
              <CardHeader className="pb-3">
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <CardTitle className="flex items-center gap-2 text-base">
                      {/* A cor acompanha o nome; nunca é o único portador do significado. */}
                      <span
                        aria-hidden="true"
                        className="inline-block h-3 w-3 shrink-0 rounded-full border border-border"
                        style={{ backgroundColor: carteira.cor || 'transparent' }}
                      />
                      <span className="truncate">{carteira.nome}</span>
                    </CardTitle>
                    <CardDescription className="mt-1 flex items-center gap-1.5 text-xs">
                      {carteira.instituicao ? (
                        <>
                          <Landmark className="h-3.5 w-3.5" aria-hidden="true" />
                          {carteira.instituicao}
                        </>
                      ) : (
                        'Sem instituição informada'
                      )}
                    </CardDescription>
                  </div>
                  {!carteira.ativa && (
                    <span className="shrink-0 rounded-full bg-muted px-2 py-0.5 text-[11px] font-medium text-muted-foreground">
                      Arquivada
                    </span>
                  )}
                </div>
              </CardHeader>

              <CardContent className="space-y-3">
                {/* O valor é a pergunta principal da tela; a contagem sozinha não respondia */}
                <dl className="rounded-xl border border-border/60 bg-muted/30 px-3 py-2">
                  <dt className="text-xs text-muted-foreground">Valor investido</dt>
                  <dd className="text-lg font-bold text-foreground tabular-nums">
                    {formatCurrency(carteira.valor_investido)}
                  </dd>
                </dl>

                <dl className="grid grid-cols-2 gap-2 text-xs">
                  <div>
                    <dt className="text-muted-foreground">Ativos com posição</dt>
                    <dd className="font-medium text-foreground">{carteira.total_ativos}</dd>
                  </div>
                  <div>
                    <dt className="text-muted-foreground">No saldo do Horizonte</dt>
                    <dd className="font-medium text-foreground">
                      {carteira.considerar_no_saldo ? 'Sim' : 'Não'}
                    </dd>
                  </div>
                </dl>

                <div className="flex flex-wrap gap-2 border-t border-border/60 pt-3">
                  <Button
                    variant="outline"
                    onClick={() => abrirEdicao(carteira)}
                    className="h-9 rounded-xl text-xs"
                  >
                    <Pencil className="mr-1.5 h-3.5 w-3.5" aria-hidden="true" />
                    Editar
                  </Button>

                  <Button
                    variant="outline"
                    onClick={() =>
                      arquivarMutation.mutate({ id: carteira.id, ativa: !carteira.ativa })
                    }
                    disabled={
                      arquivarMutation.isPending &&
                      arquivarMutation.variables?.id === carteira.id
                    }
                    className="h-9 rounded-xl text-xs"
                  >
                    {carteira.ativa ? (
                      <>
                        <Archive className="mr-1.5 h-3.5 w-3.5" aria-hidden="true" />
                        Arquivar
                      </>
                    ) : (
                      <>
                        <ArchiveRestore className="mr-1.5 h-3.5 w-3.5" aria-hidden="true" />
                        Reativar
                      </>
                    )}
                  </Button>

                  {/* `pode_excluir` usa o mesmo predicado do `destroy`; `total_ativos` divergia e dava 409 */}
                  {carteira.pode_excluir && (
                    <Button
                      variant="outline"
                      onClick={() => setParaExcluir(carteira)}
                      className="h-9 rounded-xl text-xs text-destructive hover:text-destructive"
                    >
                      <Trash2 className="mr-1.5 h-3.5 w-3.5" aria-hidden="true" />
                      Excluir
                    </Button>
                  )}
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      <CarteiraFormModal
        isOpen={formAberto}
        carteira={emEdicao}
        onClose={() => setFormAberto(false)}
        onSaved={() =>
          addToast(emEdicao ? 'Carteira atualizada.' : 'Carteira criada.', 'success')
        }
      />

      {paraExcluir && (
        <ExcluirCarteiraModal
          carteira={paraExcluir}
          isPending={excluirMutation.isPending}
          onClose={() => setParaExcluir(null)}
          onConfirm={() => excluirMutation.mutate(paraExcluir.id)}
        />
      )}
    </div>
  );
}
