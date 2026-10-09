/**
 * Tela de Detalhes e Acompanhamento de Evento Fora do Orçamento.
 *
 * Apresenta o consolidado financeiro do evento (viagem, reforma), incluindo:
 * - Indicadores de orçamento vs. executado e saldo restante.
 * - Barra de progresso visual de consumo do orçamento.
 * - Distribuição de despesas por categoria.
 * - Extrato completo de despesas vinculadas com ações de quitação e edição.
 *
 * @returns {React.JSX.Element} Painel detalhado do evento selecionado.
 */
import { useState, useMemo } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Sparkles, ArrowLeft, Plus, Calendar, DollarSign, Wallet, TrendingUp,
  Pencil, Trash2, CheckCircle2, RotateCcw, AlertCircle, RefreshCw,
  PieChart, Tag, Layers
} from 'lucide-react';

import {
  fetchEventoResumo,
  deleteEvento,
  pagarConta,
  desfazerPagamentoConta,
  deleteContaPagar
} from '../services/financeiro';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/Card';
import { Badge } from '../components/ui/Badge';
import { Button } from '../components/ui/Button';
import { Modal } from '../components/ui/Modal';
import { Progress } from '../components/ui/Progress';
import { Alert } from '../components/ui/Alert';
import { Input } from '../components/ui/Input';
import { useToast } from '../context/ToastContext';
import EventoFormModal from '../components/EventoFormModal';

// ─── Helpers ──────────────────────────────────────────────────────────────────

const formatCurrency = (val) =>
  new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(val ?? 0);

const formatDate = (dateStr) => {
  if (!dateStr || typeof dateStr !== 'string') return '—';
  const parts = dateStr.split('-');
  if (parts.length < 3) return dateStr;
  const [year, month, day] = parts;
  return `${day}/${month}/${year}`;
};

const getStatusTemporal = (inicio, fim) => {
  const hoje = new Date().toISOString().split('T')[0];
  if (fim && fim < hoje) {
    return { label: 'Concluído', variant: 'secondary' };
  }
  if (inicio && inicio > hoje) {
    return { label: 'Futuro', variant: 'outline' };
  }
  return { label: 'Em andamento', variant: 'success' };
};

// ─── Componente Principal ─────────────────────────────────────────────────────

export default function EventoDetalhe() {
  const { id } = useParams();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { addToast } = useToast();

  const [buscaDespesa, setBuscaDespesa] = useState('');
  const [modalFormOpen, setModalFormOpen] = useState(false);
  const [modalExcluirEvento, setModalExcluirEvento] = useState(false);
  const [despesaParaExcluir, setDespesaParaExcluir] = useState(null);

  const {
    data,
    isLoading,
    isRefetching,
    refetch,
    error,
  } = useQuery({
    queryKey: ['evento-resumo', id],
    queryFn: () => fetchEventoResumo(id),
    enabled: !!id,
  });

  const evento = data?.evento;
  const totalRealizado = data?.total_realizado ?? 0;
  const totalPrevisto = data?.total_previsto ?? 0;
  const saldoRestante = data?.saldo_restante;
  const categorias = data?.categorias ?? [];
  const lancamentos = useMemo(() => data?.lancamentos ?? [], [data?.lancamentos]);

  // ─── Mutations ──────────────────────────────────────────────────────────────

  const deleteEventoMutation = useMutation({
    mutationFn: () => deleteEvento(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['eventos'] });
      queryClient.invalidateQueries({ queryKey: ['dashboard'] });
      addToast('Evento excluído com sucesso.', 'success');
      navigate('/eventos');
    },
    onError: (err) => {
      const msg =
        err?.response?.data?.detail ||
        'Não foi possível excluir o evento. Desvincule ou exclua as despesas associadas.';
      addToast(msg, 'error');
    },
  });

  const pagarMutation = useMutation({
    mutationFn: (contaId) => pagarConta(contaId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['evento-resumo', id] });
      queryClient.invalidateQueries({ queryKey: ['eventos'] });
      queryClient.invalidateQueries({ queryKey: ['contasPagar'] });
      queryClient.invalidateQueries({ queryKey: ['dashboard'] });
      addToast('Despesa marcada como paga!', 'success');
    },
    onError: () => addToast('Erro ao registrar pagamento.', 'error'),
  });

  const desfazerPagamentoMutation = useMutation({
    mutationFn: (contaId) => desfazerPagamentoConta(contaId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['evento-resumo', id] });
      queryClient.invalidateQueries({ queryKey: ['eventos'] });
      queryClient.invalidateQueries({ queryKey: ['contasPagar'] });
      queryClient.invalidateQueries({ queryKey: ['dashboard'] });
      addToast('Pagamento desfeito.', 'success');
    },
    onError: () => addToast('Erro ao desfazer pagamento.', 'error'),
  });

  const deleteDespesaMutation = useMutation({
    mutationFn: (contaId) => deleteContaPagar(contaId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['evento-resumo', id] });
      queryClient.invalidateQueries({ queryKey: ['eventos'] });
      queryClient.invalidateQueries({ queryKey: ['contasPagar'] });
      queryClient.invalidateQueries({ queryKey: ['dashboard'] });
      addToast('Despesa excluída.', 'success');
      setDespesaParaExcluir(null);
    },
    onError: () => addToast('Erro ao excluir despesa.', 'error'),
  });

  // ─── Lançamentos Filtrados ──────────────────────────────────────────────────

  const lancamentosFiltrados = useMemo(() => {
    if (!buscaDespesa.trim()) return lancamentos;
    const termo = buscaDespesa.toLowerCase();
    return lancamentos.filter(
      (l) =>
        l.descricao?.toLowerCase().includes(termo) ||
        l.categoria_nome?.toLowerCase().includes(termo)
    );
  }, [lancamentos, buscaDespesa]);

  if (isLoading) {
    return (
      <div className="space-y-6">
        <div className="h-8 w-48 bg-muted rounded animate-pulse" />
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="h-28 bg-muted rounded-xl animate-pulse" />
          ))}
        </div>
      </div>
    );
  }

  if (error || !evento) {
    return (
      <div className="space-y-4">
        <Button variant="ghost" onClick={() => navigate('/eventos')} className="gap-2">
          <ArrowLeft className="h-4 w-4" />
          Voltar para Eventos
        </Button>
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <span>Evento não encontrado ou erro ao carregar os dados.</span>
        </Alert>
      </div>
    );
  }

  const statusTemporal = getStatusTemporal(evento.inicio, evento.fim);
  const orcamento = evento.orcamento != null ? Number(evento.orcamento) : null;
  const pct = orcamento && orcamento > 0 ? (totalPrevisto / orcamento) * 100 : null;

  return (
    <div className="space-y-6">
      {/* ─── Botão Voltar e Cabeçalho ───────────────────────────────────────── */}
      <div className="space-y-3">
        <Button
          variant="ghost"
          size="sm"
          onClick={() => navigate('/eventos')}
          className="gap-2 text-muted-foreground hover:text-foreground -ml-2"
        >
          <ArrowLeft className="h-4 w-4" />
          Voltar para Eventos
        </Button>

        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div className="space-y-1">
            <div className="flex flex-wrap items-center gap-2">
              <h1 className="text-2xl font-bold tracking-tight text-foreground flex items-center gap-2">
                <Sparkles className="h-6 w-6 text-primary" />
                {evento.nome}
              </h1>
              <Badge variant={statusTemporal.variant}>
                {statusTemporal.label}
              </Badge>
              {evento.fora_dos_relatorios ? (
                <Badge variant="default">Isolado do DRE e Médias</Badge>
              ) : (
                <Badge variant="secondary">No Orçamento Mensal</Badge>
              )}
            </div>

            <p className="text-sm text-muted-foreground flex items-center gap-1.5 pt-0.5">
              <Calendar className="h-4 w-4" />
              Período: {formatDate(evento.inicio)}
              {evento.fim ? ` a ${formatDate(evento.fim)}` : ' em diante'}
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <Button
              variant="outline"
              size="icon"
              onClick={() => refetch()}
              disabled={isRefetching}
              title="Atualizar dados"
              aria-label="Atualizar dados do evento"
            >
              <RefreshCw className={`h-4 w-4 ${isRefetching ? 'animate-spin' : ''}`} />
            </Button>
            <Button
              variant="outline"
              onClick={() => setModalFormOpen(true)}
              className="gap-2"
            >
              <Pencil className="h-4 w-4" />
              Editar
            </Button>
            <Button
              variant="outline"
              className="text-red-600 hover:text-red-700 dark:text-red-400 gap-2 hover:bg-red-50 dark:hover:bg-red-950/20"
              onClick={() => setModalExcluirEvento(true)}
            >
              <Trash2 className="h-4 w-4" />
              Excluir
            </Button>
            <Button
              onClick={() => navigate(`/contas-pagar/novo?evento=${evento.id}`)}
              className="gap-2"
            >
              <Plus className="h-4 w-4" />
              Adicionar Despesa
            </Button>
          </div>
        </div>
      </div>

      {/* ─── Cards de KPIs do Evento ────────────────────────────────────────── */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
              Orçamento Estipulado
            </CardTitle>
            <DollarSign className="h-4 w-4 text-blue-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold tracking-tight text-foreground">
              {orcamento != null ? formatCurrency(orcamento) : 'Sem teto fixo'}
            </div>
            <p className="text-xs text-muted-foreground mt-1">
              Limite planejado para o evento
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
              Total Realizado (Pago)
            </CardTitle>
            <Wallet className="h-4 w-4 text-emerald-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold tracking-tight text-emerald-600 dark:text-emerald-400">
              {formatCurrency(totalRealizado)}
            </div>
            <p className="text-xs text-muted-foreground mt-1">
              Despesas já liquidadas no caixa
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
              Total Comprometido
            </CardTitle>
            <TrendingUp className="h-4 w-4 text-amber-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold tracking-tight text-foreground">
              {formatCurrency(totalPrevisto)}
            </div>
            <p className="text-xs text-muted-foreground mt-1">
              {totalPrevisto > totalRealizado
                ? `${formatCurrency(totalPrevisto - totalRealizado)} a pagar ainda`
                : '100% das despesas já pagas'}
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
              Saldo Restante
            </CardTitle>
            <Sparkles className="h-4 w-4 text-purple-500" />
          </CardHeader>
          <CardContent>
            {orcamento != null ? (
              <>
                <div
                  className={`text-2xl font-bold tracking-tight ${
                    saldoRestante >= 0
                      ? 'text-emerald-600 dark:text-emerald-400'
                      : 'text-red-600 dark:text-red-400'
                  }`}
                >
                  {formatCurrency(saldoRestante)}
                </div>
                <p className="text-xs text-muted-foreground mt-1">
                  {saldoRestante >= 0 ? 'Disponível dentro do teto' : 'Orçamento estourado'}
                </p>
              </>
            ) : (
              <>
                <div className="text-2xl font-bold tracking-tight text-muted-foreground">
                  —
                </div>
                <p className="text-xs text-muted-foreground mt-1">
                  Sem teto estipulado
                </p>
              </>
            )}
          </CardContent>
        </Card>
      </div>

      {/* ─── Barra de Progresso Geral ───────────────────────────────────────── */}
      {orcamento != null && orcamento > 0 && (
        <Card className="p-5">
          <div className="space-y-2">
            <Progress
              value={pct}
              max={100}
              label={`Consumo do Orçamento (${formatCurrency(totalPrevisto)} de ${formatCurrency(orcamento)})`}
              valueLabel={`${pct.toFixed(1)}%`}
              variant={pct > 100 ? 'danger' : pct >= 80 ? 'warning' : 'success'}
            />
            {pct > 100 && (
              <p className="text-xs text-red-600 dark:text-red-400 font-medium">
                Atenção: Os gastos totais excederam o teto planejado em {formatCurrency(totalPrevisto - orcamento)}.
              </p>
            )}
          </div>
        </Card>
      )}

      {/* ─── Grid de Categorias e Lista de Despesas ──────────────────────────── */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Coluna 1: Breakdown por Categoria */}
        <div className="lg:col-span-1 space-y-4">
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-base font-semibold text-foreground flex items-center gap-2">
                <PieChart className="h-4 w-4 text-primary" />
                Gastos por Categoria
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              {categorias.length === 0 ? (
                <p className="text-xs text-muted-foreground text-center py-4">
                  Nenhuma despesa vinculada para categorização.
                </p>
              ) : (
                categorias.map((cat, idx) => {
                  const catPct = totalPrevisto > 0 ? (cat.total / totalPrevisto) * 100 : 0;
                  return (
                    <div key={idx} className="space-y-1.5">
                      <div className="flex items-center justify-between text-xs">
                        <span className="font-medium text-foreground flex items-center gap-1.5">
                          <Tag className="h-3 w-3 text-muted-foreground" />
                          {cat.categoria}
                        </span>
                        <span className="tabular-nums font-semibold text-foreground">
                          {formatCurrency(cat.total)} ({catPct.toFixed(0)}%)
                        </span>
                      </div>
                      <div className="h-2 rounded-full bg-muted overflow-hidden">
                        <div
                          className="h-full bg-primary/80 transition-all rounded-full"
                          style={{ width: `${Math.min(catPct, 100)}%` }}
                        />
                      </div>
                    </div>
                  );
                })
              )}
            </CardContent>
          </Card>
        </div>

        {/* Coluna 2 e 3: Tabela de Lançamentos */}
        <div className="lg:col-span-2 space-y-4">
          <Card>
            <CardHeader className="pb-3">
              <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
                <CardTitle className="text-base font-semibold text-foreground flex items-center gap-2">
                  <Layers className="h-4 w-4 text-primary" />
                  Despesas do Evento ({lancamentos.length})
                </CardTitle>
                <div className="w-full sm:w-64">
                  <Input
                    placeholder="Filtrar lançamentos..."
                    value={buscaDespesa}
                    onChange={(e) => setBuscaDespesa(e.target.value)}
                    className="h-8 text-xs"
                  />
                </div>
              </div>
            </CardHeader>
            <CardContent className="p-0">
              {lancamentosFiltrados.length === 0 ? (
                <div className="p-8 text-center space-y-3">
                  <p className="text-sm text-muted-foreground">
                    {buscaDespesa
                      ? 'Nenhuma despesa encontrada com esse filtro.'
                      : 'Nenhuma despesa cadastrada neste evento ainda.'}
                  </p>
                  {!buscaDespesa && (
                    <Button
                      size="sm"
                      onClick={() => navigate(`/contas-pagar/novo?evento=${evento.id}`)}
                      className="gap-2"
                    >
                      <Plus className="h-4 w-4" />
                      Cadastrar Primeira Despesa
                    </Button>
                  )}
                </div>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-xs text-left">
                    <thead className="bg-muted/50 border-y border-border/60 text-muted-foreground uppercase text-[10px] tracking-wider">
                      <tr>
                        <th className="py-2.5 px-4">Status</th>
                        <th className="py-2.5 px-4">Descrição</th>
                        <th className="py-2.5 px-4">Categoria</th>
                        <th className="py-2.5 px-4">Vencimento</th>
                        <th className="py-2.5 px-4 text-right">Valor</th>
                        <th className="py-2.5 px-4 text-center">Ações</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-border/40">
                      {lancamentosFiltrados.map((item) => {
                        const pago = item.transacao_realizada ?? item.pago;
                        return (
                          <tr
                            key={item.id}
                            className="hover:bg-muted/30 transition-colors"
                          >
                            <td className="py-2.5 px-4 whitespace-nowrap">
                              <Badge
                                variant={pago ? 'success' : 'secondary'}
                                className="text-[10px]"
                              >
                                {pago ? 'Pago' : 'Pendente'}
                              </Badge>
                            </td>
                            <td className="py-2.5 px-4 font-medium text-foreground">
                              {item.descricao}
                            </td>
                            <td className="py-2.5 px-4 text-muted-foreground whitespace-nowrap">
                              {item.categoria_nome || '—'}
                            </td>
                            <td className="py-2.5 px-4 text-muted-foreground whitespace-nowrap">
                              {formatDate(item.data_prevista || item.data_vencimento)}
                            </td>
                            <td className="py-2.5 px-4 text-right font-semibold tabular-nums text-foreground whitespace-nowrap">
                              {formatCurrency(item.valor)}
                            </td>
                            <td className="py-2.5 px-4 text-center whitespace-nowrap">
                              <div className="flex items-center justify-center gap-1">
                                {!pago ? (
                                  <Button
                                    size="sm"
                                    variant="ghost"
                                    className="h-7 w-7 p-0 text-emerald-600 hover:text-emerald-700 hover:bg-emerald-50 dark:hover:bg-emerald-950/20"
                                    onClick={() => pagarMutation.mutate(item.id)}
                                    title="Marcar como Pago"
                                    aria-label={`Marcar ${item.descricao} como pago`}
                                  >
                                    <CheckCircle2 className="h-3.5 w-3.5" />
                                  </Button>
                                ) : (
                                  <Button
                                    size="sm"
                                    variant="ghost"
                                    className="h-7 w-7 p-0 text-amber-600 hover:text-amber-700 hover:bg-amber-50 dark:hover:bg-amber-950/20"
                                    onClick={() => desfazerPagamentoMutation.mutate(item.id)}
                                    title="Desfazer Pagamento"
                                    aria-label={`Desfazer pagamento de ${item.descricao}`}
                                  >
                                    <RotateCcw className="h-3.5 w-3.5" />
                                  </Button>
                                )}
                                <Button
                                  size="sm"
                                  variant="ghost"
                                  className="h-7 w-7 p-0 text-muted-foreground hover:text-foreground hover:bg-muted"
                                  onClick={() => navigate(`/contas-pagar/editar/${item.id}`)}
                                  title="Editar Despesa"
                                  aria-label={`Editar ${item.descricao}`}
                                >
                                  <Pencil className="h-3.5 w-3.5" />
                                </Button>
                                <Button
                                  size="sm"
                                  variant="ghost"
                                  className="h-7 w-7 p-0 text-rose-500 hover:text-rose-600 hover:bg-rose-50 dark:hover:bg-rose-950/20"
                                  onClick={() => setDespesaParaExcluir(item)}
                                  title="Excluir Despesa"
                                  aria-label={`Excluir ${item.descricao}`}
                                >
                                  <Trash2 className="h-3.5 w-3.5" />
                                </Button>
                              </div>
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      </div>

      {/* ─── Modal de Edição do Evento ───────────────────────────────────────── */}
      <EventoFormModal
        isOpen={modalFormOpen}
        evento={evento}
        onClose={() => setModalFormOpen(false)}
        onSaved={() => {
          refetch();
        }}
      />

      {/* ─── Modal de Exclusão do Evento ─────────────────────────────────────── */}
      <Modal
        isOpen={modalExcluirEvento}
        onClose={() => setModalExcluirEvento(false)}
        title="Excluir Evento"
        size="md"
      >
        <div className="space-y-4">
          <p className="text-sm text-foreground">
            Tem certeza que deseja excluir o evento{' '}
            <strong className="text-foreground">{evento.nome}</strong>?
          </p>

          {lancamentos.length > 0 ? (
            <Alert variant="destructive">
              <AlertCircle className="h-4 w-4" />
              <div className="text-xs leading-relaxed">
                Este evento possui{' '}
                <strong>{lancamentos.length} despesa(s)</strong> vinculada(s).
                Por segurança, o banco de dados protege eventos com lançamentos. Você precisa desvincular ou excluir as despesas antes de remover o evento.
              </div>
            </Alert>
          ) : (
            <p className="text-xs text-muted-foreground">
              Esta ação removerá o evento do sistema. Como não há despesas vinculadas, nenhum lançamento financeiro será afetado.
            </p>
          )}

          <div className="flex justify-end gap-3 pt-3 border-t border-border/40">
            <Button
              type="button"
              variant="outline"
              onClick={() => setModalExcluirEvento(false)}
              disabled={deleteEventoMutation.isPending}
            >
              Cancelar
            </Button>
            <Button
              type="button"
              variant="destructive"
              onClick={() => deleteEventoMutation.mutate()}
              disabled={deleteEventoMutation.isPending || lancamentos.length > 0}
              className="gap-2"
            >
              {deleteEventoMutation.isPending ? 'Excluindo...' : 'Confirmar Exclusão'}
            </Button>
          </div>
        </div>
      </Modal>

      {/* ─── Modal de Exclusão de Despesa ────────────────────────────────────── */}
      <Modal
        isOpen={!!despesaParaExcluir}
        onClose={() => setDespesaParaExcluir(null)}
        title="Excluir Despesa"
        size="sm"
      >
        <div className="space-y-4">
          <p className="text-sm text-foreground">
            Tem certeza que deseja excluir o lançamento{' '}
            <strong className="text-foreground">{despesaParaExcluir?.descricao}</strong> no valor de{' '}
            <strong className="text-foreground">{formatCurrency(despesaParaExcluir?.valor)}</strong>?
          </p>

          <div className="flex justify-end gap-3 pt-3 border-t border-border/40">
            <Button
              type="button"
              variant="outline"
              onClick={() => setDespesaParaExcluir(null)}
              disabled={deleteDespesaMutation.isPending}
            >
              Cancelar
            </Button>
            <Button
              type="button"
              variant="destructive"
              onClick={() => deleteDespesaMutation.mutate(despesaParaExcluir.id)}
              disabled={deleteDespesaMutation.isPending}
              className="gap-2"
            >
              {deleteDespesaMutation.isPending ? 'Excluindo...' : 'Confirmar'}
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  );
}
