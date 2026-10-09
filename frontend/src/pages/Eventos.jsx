/**
 * Tela de Gestão de Eventos Fora do Orçamento Mensal.
 *
 * Permite cadastrar, gerenciar e acompanhar despesas extraordinárias de grandes ocasiões
 * (viagens, reformas, festas) com teto orçamentário e isolamento das médias mensais e DRE.
 *
 * @returns {React.JSX.Element} Painel com KPIs consolidados e cards interativos dos eventos.
 */
import { useState, useMemo } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import {
  Sparkles, Plus, Calendar, DollarSign, Wallet, TrendingUp,
  Pencil, Trash2, ArrowRight, RefreshCw, AlertCircle,
  Search
} from 'lucide-react';

import { fetchEventos, deleteEvento } from '../services/financeiro';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/Card';
import { Badge } from '../components/ui/Badge';
import { Button } from '../components/ui/Button';
import { Input } from '../components/ui/Input';
import { Modal } from '../components/ui/Modal';
import { Progress } from '../components/ui/Progress';
import { Alert } from '../components/ui/Alert';
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

export default function Eventos() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { addToast } = useToast();

  const [busca, setBusca] = useState('');
  const [modalFormOpen, setModalFormOpen] = useState(false);
  const [eventoEmEdicao, setEventoEmEdicao] = useState(null);
  const [eventoParaExcluir, setEventoParaExcluir] = useState(null);

  const {
    data: eventos = [],
    isLoading,
    isRefetching,
    refetch,
    error,
  } = useQuery({
    queryKey: ['eventos'],
    queryFn: () => fetchEventos(),
  });

  const deleteMutation = useMutation({
    mutationFn: (id) => deleteEvento(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['eventos'] });
      queryClient.invalidateQueries({ queryKey: ['dashboard'] });
      addToast('Evento excluído com sucesso.', 'success');
      setEventoParaExcluir(null);
    },
    onError: (err) => {
      const msg =
        err?.response?.data?.detail ||
        'Não foi possível excluir o evento. Verifique se existem lançamentos vinculados.';
      addToast(msg, 'error');
    },
  });

  // ─── Agregados e KPIs ───────────────────────────────────────────────────────

  const { totalOrcado, totalGasto, totalPrevisto, totalEventos, eventosAtivos } = useMemo(() => {
    let orcado = 0;
    let gasto = 0;
    let previsto = 0;
    let ativos = 0;

    eventos.forEach((ev) => {
      if (ev.orcamento != null) orcado += Number(ev.orcamento);
      gasto += Number(ev.total_gasto || 0);
      previsto += Number(ev.total_previsto || 0);

      const status = getStatusTemporal(ev.inicio, ev.fim);
      if (status.label === 'Em andamento') ativos += 1;
    });

    return {
      totalOrcado: orcado,
      totalGasto: gasto,
      totalPrevisto: previsto,
      totalEventos: eventos.length,
      eventosAtivos: ativos,
    };
  }, [eventos]);

  // ─── Filtragem ──────────────────────────────────────────────────────────────

  const eventosFiltrados = useMemo(() => {
    if (!busca.trim()) return eventos;
    const termo = busca.toLowerCase();
    return eventos.filter((ev) => ev.nome.toLowerCase().includes(termo));
  }, [eventos, busca]);

  // ─── Handlers ───────────────────────────────────────────────────────────────

  const handleNovoEvento = () => {
    setEventoEmEdicao(null);
    setModalFormOpen(true);
  };

  const handleEditarEvento = (evento, e) => {
    e?.stopPropagation();
    setEventoEmEdicao(evento);
    setModalFormOpen(true);
  };

  const handleConfirmarExclusao = () => {
    if (!eventoParaExcluir) return;
    deleteMutation.mutate(eventoParaExcluir.id);
  };

  return (
    <div className="space-y-6">
      {/* ─── Header ────────────────────────────────────────────────────────── */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-foreground flex items-center gap-2">
            <Sparkles className="h-6 w-6 text-primary" />
            Eventos
          </h1>
          <p className="text-sm text-muted-foreground mt-1">
            Controle de despesas extraordinárias (viagens, reformas, festas) sem distorcer médias mensais e DRE.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="icon"
            onClick={() => refetch()}
            disabled={isLoading || isRefetching}
            aria-label="Atualizar lista de eventos"
            title="Atualizar"
          >
            <RefreshCw className={`h-4 w-4 ${isRefetching ? 'animate-spin' : ''}`} />
          </Button>
          <Button onClick={handleNovoEvento} className="gap-2">
            <Plus className="h-4 w-4" />
            Novo Evento
          </Button>
        </div>
      </div>

      {/* ─── Cards de Métricas Consolidadas ─────────────────────────────────── */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
              Total de Eventos
            </CardTitle>
            <Calendar className="h-4 w-4 text-primary" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold tracking-tight text-foreground">
              {totalEventos}
            </div>
            <p className="text-xs text-muted-foreground mt-1">
              {eventosAtivos} em andamento atualmente
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
              Orçamento Previsto
            </CardTitle>
            <DollarSign className="h-4 w-4 text-blue-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold tracking-tight text-foreground">
              {formatCurrency(totalOrcado)}
            </div>
            <p className="text-xs text-muted-foreground mt-1">
              Soma dos tetos planejados
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
              Total Realizado
            </CardTitle>
            <Wallet className="h-4 w-4 text-emerald-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold tracking-tight text-foreground">
              {formatCurrency(totalGasto)}
            </div>
            <p className="text-xs text-muted-foreground mt-1">
              {totalPrevisto > totalGasto
                ? `${formatCurrency(totalPrevisto)} incluindo pendentes`
                : 'Todas as despesas já liquidadas'}
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
              Saldo Restante Global
            </CardTitle>
            <TrendingUp className="h-4 w-4 text-purple-500" />
          </CardHeader>
          <CardContent>
            {totalOrcado > 0 ? (
              <>
                <div
                  className={`text-2xl font-bold tracking-tight ${
                    totalOrcado - totalPrevisto >= 0 ? 'text-emerald-600 dark:text-emerald-400' : 'text-red-600 dark:text-red-400'
                  }`}
                >
                  {formatCurrency(totalOrcado - totalPrevisto)}
                </div>
                <p className="text-xs text-muted-foreground mt-1">
                  Disponível nos tetos estipulados
                </p>
              </>
            ) : (
              <>
                <div className="text-2xl font-bold tracking-tight text-muted-foreground">
                  —
                </div>
                <p className="text-xs text-muted-foreground mt-1">
                  Sem orçamentos definidos
                </p>
              </>
            )}
          </CardContent>
        </Card>
      </div>

      {/* ─── Barra de Busca e Filtros ───────────────────────────────────────── */}
      <div className="flex items-center gap-3">
        <div className="relative flex-1 max-w-sm">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input
            value={busca}
            onChange={(e) => setBusca(e.target.value)}
            placeholder="Buscar por nome do evento..."
            className="pl-9"
          />
        </div>
      </div>

      {/* ─── Listagem de Cards ──────────────────────────────────────────────── */}
      {error && (
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <span>Erro ao carregar eventos. Tente recarregar a página.</span>
        </Alert>
      )}

      {isLoading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {[1, 2, 3].map((i) => (
            <div
              key={i}
              className="h-64 rounded-xl border border-border/60 bg-card p-6 animate-pulse space-y-4"
            >
              <div className="h-6 w-1/2 bg-muted rounded" />
              <div className="h-4 w-1/3 bg-muted rounded" />
              <div className="h-12 bg-muted rounded mt-6" />
              <div className="h-8 bg-muted rounded mt-4" />
            </div>
          ))}
        </div>
      ) : eventosFiltrados.length === 0 ? (
        <Card className="border-dashed p-12 text-center">
          <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-full bg-primary/10 mb-4">
            <Sparkles className="h-7 w-7 text-primary" />
          </div>
          <h2 className="text-lg font-semibold text-foreground">
            {busca ? 'Nenhum evento encontrado' : 'Nenhum evento cadastrado'}
          </h2>
          <p className="text-sm text-muted-foreground max-w-md mx-auto mt-2 leading-relaxed">
            {busca
              ? `Não foram encontrados eventos correspondentes a "${busca}".`
              : 'Cadastre ocasiões extraordinárias como viagens ou reformas. As despesas deduzem do saldo bancário mas ficam fora das médias mensais e DRE.'}
          </p>
          {!busca && (
            <Button onClick={handleNovoEvento} className="mt-6 gap-2">
              <Plus className="h-4 w-4" />
              Criar Primeiro Evento
            </Button>
          )}
        </Card>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {eventosFiltrados.map((evento) => {
            const statusTemporal = getStatusTemporal(evento.inicio, evento.fim);
            const orcamento = evento.orcamento != null ? Number(evento.orcamento) : null;
            const totalPrevisto = Number(evento.total_previsto || 0);
            const totalGasto = Number(evento.total_gasto || 0);
            const saldoRestante = orcamento != null ? orcamento - totalPrevisto : null;
            const pct = orcamento && orcamento > 0 ? (totalPrevisto / orcamento) * 100 : null;

            return (
              <Card
                key={evento.id}
                className="group relative flex flex-col justify-between overflow-hidden border-border/60 hover:border-primary/50 transition-all duration-200 hover:shadow-md"
              >
                <div>
                  {/* Cabeçalho do Card */}
                  <CardHeader className="pb-3">
                    <div className="flex items-start justify-between gap-2">
                      <div className="space-y-1">
                        <CardTitle
                          className="text-lg font-bold text-foreground group-hover:text-primary transition-colors cursor-pointer"
                          onClick={() => navigate(`/eventos/${evento.id}`)}
                        >
                          {evento.nome}
                        </CardTitle>
                        <p className="text-xs text-muted-foreground flex items-center gap-1">
                          <Calendar className="h-3.5 w-3.5" />
                          {formatDate(evento.inicio)}
                          {evento.fim ? ` a ${formatDate(evento.fim)}` : ' em diante'}
                        </p>
                      </div>
                      <div className="flex flex-col items-end gap-1.5">
                        <Badge variant={statusTemporal.variant}>
                          {statusTemporal.label}
                        </Badge>
                        {evento.fora_dos_relatorios ? (
                          <Badge variant="default" className="text-[10px] py-0">
                            Fora do DRE
                          </Badge>
                        ) : (
                          <Badge variant="secondary" className="text-[10px] py-0">
                            No Orçamento
                          </Badge>
                        )}
                      </div>
                    </div>
                  </CardHeader>

                  {/* Conteúdo / Métricas */}
                  <CardContent className="space-y-4 pb-4">
                    <div className="grid grid-cols-2 gap-2 text-sm pt-1">
                      <div className="rounded-lg bg-muted/40 p-2.5">
                        <span className="text-[11px] font-medium text-muted-foreground block">
                          Orçamento
                        </span>
                        <span className="text-sm font-semibold text-foreground">
                          {orcamento != null ? formatCurrency(orcamento) : 'Sem teto'}
                        </span>
                      </div>
                      <div className="rounded-lg bg-muted/40 p-2.5">
                        <span className="text-[11px] font-medium text-muted-foreground block">
                          Realizado (Pago)
                        </span>
                        <span className="text-sm font-semibold text-emerald-600 dark:text-emerald-400">
                          {formatCurrency(totalGasto)}
                        </span>
                      </div>
                    </div>

                    {/* Barra de Progresso do Orçamento */}
                    {orcamento != null && orcamento > 0 && (
                      <div className="space-y-1.5 pt-1">
                        <Progress
                          value={pct}
                          max={100}
                          label="Execução do Orçamento"
                          valueLabel={`${pct.toFixed(0)}%`}
                          variant={pct > 100 ? 'danger' : pct >= 80 ? 'warning' : 'success'}
                        />
                        <div className="flex justify-between items-center text-xs pt-0.5">
                          <span className="text-muted-foreground">Saldo Restante:</span>
                          <span
                            className={`font-semibold tabular-nums ${
                              saldoRestante >= 0
                                ? 'text-emerald-600 dark:text-emerald-400'
                                : 'text-red-600 dark:text-red-400'
                            }`}
                          >
                            {formatCurrency(saldoRestante)}
                          </span>
                        </div>
                      </div>
                    )}

                    <div className="flex items-center justify-between text-xs text-muted-foreground pt-1 border-t border-border/40">
                      <span>{evento.qtd_lancamentos || 0} lançamentos vinculados</span>
                      {totalPrevisto > totalGasto && (
                        <span className="text-amber-600 dark:text-amber-400 font-medium">
                          +{formatCurrency(totalPrevisto - totalGasto)} pendente
                        </span>
                      )}
                    </div>
                  </CardContent>
                </div>

                {/* Rodapé de Ações */}
                <div className="flex items-center justify-between border-t border-border/60 bg-muted/20 px-4 py-3">
                  <div className="flex items-center gap-1">
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-8 w-8 text-muted-foreground hover:text-foreground"
                      onClick={(e) => handleEditarEvento(evento, e)}
                      title="Editar Evento"
                      aria-label={`Editar ${evento.nome}`}
                    >
                      <Pencil className="h-4 w-4" />
                    </Button>
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-8 w-8 text-muted-foreground hover:text-red-600 dark:hover:text-red-400"
                      onClick={(e) => {
                        e.stopPropagation();
                        setEventoParaExcluir(evento);
                      }}
                      title="Excluir Evento"
                      aria-label={`Excluir ${evento.nome}`}
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </div>

                  <div className="flex items-center gap-2">
                    <Button
                      variant="outline"
                      size="sm"
                      className="gap-1 text-xs h-8"
                      onClick={() => navigate(`/contas-pagar/novo?evento=${evento.id}`)}
                      title="Adicionar despesa a este evento"
                    >
                      <Plus className="h-3.5 w-3.5" />
                      Despesa
                    </Button>
                    <Button
                      variant="default"
                      size="sm"
                      className="gap-1 text-xs h-8"
                      onClick={() => navigate(`/eventos/${evento.id}`)}
                    >
                      Detalhes
                      <ArrowRight className="h-3.5 w-3.5" />
                    </Button>
                  </div>
                </div>
              </Card>
            );
          })}
        </div>
      )}

      {/* ─── Modal de Criação / Edição ───────────────────────────────────────── */}
      <EventoFormModal
        isOpen={modalFormOpen}
        evento={eventoEmEdicao}
        onClose={() => {
          setModalFormOpen(false);
          setEventoEmEdicao(null);
        }}
        onSaved={() => {
          refetch();
        }}
      />

      {/* ─── Modal de Confirmação de Exclusão ─────────────────────────────────── */}
      <Modal
        isOpen={!!eventoParaExcluir}
        onClose={() => setEventoParaExcluir(null)}
        title="Excluir Evento"
        size="md"
      >
        <div className="space-y-4">
          <p className="text-sm text-foreground">
            Tem certeza que deseja excluir o evento{' '}
            <strong className="text-foreground">{eventoParaExcluir?.nome}</strong>?
          </p>

          {eventoParaExcluir?.qtd_lancamentos > 0 ? (
            <Alert variant="destructive">
              <AlertCircle className="h-4 w-4" />
              <div className="text-xs leading-relaxed">
                Este evento possui{' '}
                <strong>{eventoParaExcluir.qtd_lancamentos} despesa(s)</strong> vinculada(s).
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
              onClick={() => setEventoParaExcluir(null)}
              disabled={deleteMutation.isPending}
            >
              Cancelar
            </Button>
            <Button
              type="button"
              variant="destructive"
              onClick={handleConfirmarExclusao}
              disabled={deleteMutation.isPending || eventoParaExcluir?.qtd_lancamentos > 0}
              className="gap-2"
            >
              {deleteMutation.isPending ? 'Excluindo...' : 'Confirmar Exclusão'}
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  );
}
