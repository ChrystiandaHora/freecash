/**
 * Tela de Conciliação Bancária (Revisão de Extratos Importados).
 * 
 * Permite listar extratos bancários importados, exibir tabelas colapsáveis das linhas de transações pendentes,
 * e fornecer ações rápidas em lote (Confirmar Inclusão ou Ignorar Lançamentos) sobre múltiplos itens selecionados.
 *
 * @component
 * @returns {React.JSX.Element} Painel administrativo contendo KPIs de pendências e listagem de extratos.
 */
import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  CheckCircle2,
  XCircle,
  Search,
  ChevronDown,
  ChevronUp,
  Loader2,
  RefreshCw,
  TrendingUp,
  TrendingDown,
  AlertCircle,
  CheckSquare,
  Square,
  FileText,
} from 'lucide-react';
import api from '../services/api';
import { Button } from '../components/ui/Button';

const fetchConciliacao = async () => {
  const res = await api.get('/api/ferramentas/conciliacao/');
  return res.data;
};

const processarLinhas = async (payload) => {
  const res = await api.post('/api/ferramentas/conciliacao/processar/', payload);
  return res.data;
};

function formatDate(dateStr) {
  if (!dateStr) return '—';
  const [y, m, d] = dateStr.split('-');
  return `${d}/${m}/${y}`;
}

function formatCurrency(value) {
  return new Intl.NumberFormat('pt-BR', {
    style: 'currency',
    currency: 'BRL',
  }).format(parseFloat(value) || 0);
}

export default function FerramentasConciliacao() {
  const queryClient = useQueryClient();
  const [selectedLinhas, setSelectedLinhas] = useState({});
  const [expandedExtratos, setExpandedExtratos] = useState({});

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ['conciliacao'],
    queryFn: () => fetchConciliacao(),
  });

  const processarMutation = useMutation({
    mutationFn: processarLinhas,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['conciliacao'] });
      setSelectedLinhas({});
    },
  });

  const extratos = data?.extratos || [];

  const toggleExpandExtrato = (id) => {
    setExpandedExtratos((prev) => ({ ...prev, [id]: !prev[id] }));
  };

  const toggleLinha = (extratoId, linhaId) => {
    setSelectedLinhas((prev) => {
      const current = prev[extratoId] || new Set();
      const next = new Set(current);
      if (next.has(linhaId)) next.delete(linhaId);
      else next.add(linhaId);
      return { ...prev, [extratoId]: next };
    });
  };

  const toggleAllLinhas = (extratoId, linhas) => {
    const current = selectedLinhas[extratoId] || new Set();
    if (current.size === linhas.length) {
      setSelectedLinhas((prev) => ({ ...prev, [extratoId]: new Set() }));
    } else {
      setSelectedLinhas((prev) => ({
        ...prev,
        [extratoId]: new Set(linhas.map((l) => l.id)),
      }));
    }
  };

  const handleProcessar = (extratoId, acao) => {
    const ids = Array.from(selectedLinhas[extratoId] || []);
    if (!ids.length) return;
    processarMutation.mutate({ extrato_id: extratoId, linha_ids: ids, acao });
  };

  const totalPendentes = extratos.reduce((sum, e) => sum + (e.linhas_pendentes || 0), 0);

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-3xl font-extrabold tracking-tight text-foreground">
            Conciliação Bancária
          </h1>
          <p className="text-slate-500 dark:text-slate-400 mt-1">
            Revise e confirme as transações importadas dos seus extratos
          </p>
        </div>
        <Button
          id="btn-atualizar-conciliacao"
          variant="outline"
          onClick={() => refetch()}
          disabled={isLoading}
          className="gap-2 shrink-0"
        >
          <RefreshCw className={`h-4 w-4 ${isLoading ? 'animate-spin' : ''}`} />
          Atualizar
        </Button>
      </div>

      {/* Stats Bar */}
      <div className="grid grid-cols-3 gap-4">
        {[
          { label: 'Extratos importados', value: extratos.length, color: 'text-primary' },
          { label: 'Linhas pendentes', value: totalPendentes, color: 'text-amber-500' },
          {
            label: 'Linhas importadas',
            value: extratos.reduce((s, e) => s + (e.linhas_importadas || 0), 0),
            color: 'text-emerald-500',
          },
        ].map(({ label, value, color }) => (
          <div
            key={label}
            className="p-4 rounded-xl border border-border/40 bg-card text-center shadow-sm"
          >
            <p className={`text-2xl font-bold ${color}`}>{value}</p>
            <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">{label}</p>
          </div>
        ))}
      </div>

      {/* Loading / Error */}
      {isLoading && (
        <div className="flex items-center justify-center py-16">
          <Loader2 className="h-8 w-8 animate-spin text-primary" />
        </div>
      )}

      {isError && (
        <div className="flex items-center gap-3 p-4 rounded-xl bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 text-red-700 dark:text-red-400">
          <AlertCircle className="h-5 w-5 shrink-0" />
          <p>Erro ao carregar dados de conciliação. Verifique a conexão com o servidor.</p>
        </div>
      )}

      {!isLoading && !isError && extratos.length === 0 && (
        <div className="flex flex-col items-center justify-center py-20 text-center">
          <div className="w-16 h-16 rounded-2xl bg-slate-100 dark:bg-slate-900 flex items-center justify-center mb-4">
            <FileText className="h-8 w-8 text-slate-400" />
          </div>
          <h3 className="text-lg font-semibold text-slate-700 dark:text-slate-200 mb-1">
            Nenhum extrato encontrado
          </h3>
          <p className="text-sm text-slate-500 dark:text-slate-400 max-w-sm">
            Importe um arquivo de extrato bancário para iniciar a conciliação.
          </p>
        </div>
      )}

      {/* Extratos List */}
      <div className="space-y-4">
        {extratos.map((extrato) => {
          const isExpanded = expandedExtratos[extrato.id] ?? true;
          const linhas = extrato.linhas || [];
          const selected = selectedLinhas[extrato.id] || new Set();
          const allSelected = linhas.length > 0 && selected.size === linhas.length;
          const isPending = processarMutation.isPending;

          return (
            <div
              key={extrato.id}
              className="rounded-2xl border border-border/40 bg-card overflow-hidden shadow-sm"
            >
              {/* Extrato Header */}
              <div
                className="flex items-center justify-between gap-4 p-4 cursor-pointer hover:bg-muted/40 transition-colors"
                onClick={() => toggleExpandExtrato(extrato.id)}
              >
                <div className="flex items-center gap-3">
                  <div
                    className={`w-2.5 h-2.5 rounded-full shrink-0 ${
                      extrato.status === 'processado'
                        ? 'bg-emerald-500'
                        : extrato.status === 'erro'
                        ? 'bg-red-500'
                        : 'bg-amber-500 animate-pulse'
                    }`}
                  />
                  <div>
                    <p className="font-semibold text-foreground text-sm">
                      {extrato.arquivo_nome}
                    </p>
                    <div className="flex items-center gap-2 mt-0.5">
                      <span className="text-xs text-muted-foreground">
                        {extrato.banco_display}
                      </span>
                      <span className="text-border">·</span>
                      <span className="text-xs text-muted-foreground">
                        {formatDate(extrato.criada_em?.split('T')[0])}
                      </span>
                    </div>
                  </div>
                </div>
                <div className="flex items-center gap-3">
                  <div className="hidden sm:flex items-center gap-4 text-xs">
                    <span className="text-amber-600 dark:text-amber-400 font-semibold">
                      {extrato.linhas_pendentes} pendentes
                    </span>
                    <span className="text-emerald-600 dark:text-emerald-400 font-semibold">
                      {extrato.linhas_importadas} importadas
                    </span>
                  </div>
                  {isExpanded ? (
                    <ChevronUp className="h-4 w-4 text-muted-foreground" />
                  ) : (
                    <ChevronDown className="h-4 w-4 text-muted-foreground" />
                  )}
                </div>
              </div>

              {/* Linhas Table */}
              {isExpanded && linhas.length > 0 && (
                <div className="border-t border-border/40">
                  {/* Table Header */}
                  <div className="flex items-center gap-3 px-4 py-2.5 bg-muted/60 text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                    <button
                      id={`btn-select-all-${extrato.id}`}
                      onClick={() => toggleAllLinhas(extrato.id, linhas)}
                      className="flex items-center gap-1.5 text-slate-500 hover:text-primary transition-colors"
                    >
                      {allSelected ? (
                        <CheckSquare className="h-4 w-4 text-primary" />
                      ) : (
                        <Square className="h-4 w-4" />
                      )}
                      Todos
                    </button>
                    <span className="flex-1">Descrição</span>
                    <span className="w-24 text-right">Valor</span>
                    <span className="w-24 text-right hidden sm:block">Data</span>
                    <span className="w-16 text-center">Tipo</span>
                  </div>

                  {/* Rows */}
                  <div className="divide-y divide-border/30">
                    {linhas.map((linha) => {
                      const isChecked = selected.has(linha.id);
                      const isCredito = linha.tipo === 'C';

                      return (
                        <div
                          key={linha.id}
                          className={`flex items-center gap-3 px-4 py-3 transition-colors cursor-pointer
                            ${isChecked
                              ? 'bg-primary/10'
                              : 'hover:bg-muted/40'
                            }
                          `}
                          onClick={() => toggleLinha(extrato.id, linha.id)}
                        >
                          {isChecked ? (
                            <CheckSquare className="h-4 w-4 text-primary shrink-0" />
                          ) : (
                            <Square className="h-4 w-4 text-muted-foreground/60 shrink-0" />
                          )}
                          <span className="flex-1 text-sm text-foreground truncate">
                            {linha.descricao}
                          </span>
                          <span
                            className={`w-24 text-right text-sm font-semibold ${
                              isCredito
                                ? 'text-emerald-600 dark:text-emerald-400'
                                : 'text-red-500 dark:text-red-400'
                            }`}
                          >
                            {isCredito ? '+' : '-'}{formatCurrency(linha.valor)}
                          </span>
                          <span className="w-24 text-right text-xs text-muted-foreground hidden sm:block">
                            {formatDate(linha.data)}
                          </span>
                          <span className="w-16 flex justify-center">
                            {isCredito ? (
                              <span className="flex items-center gap-1 text-xs text-emerald-600 dark:text-emerald-400 font-medium">
                                <TrendingUp className="h-3.5 w-3.5" />
                                Entrada
                              </span>
                            ) : (
                              <span className="flex items-center gap-1 text-xs text-red-500 dark:text-red-400 font-medium">
                                <TrendingDown className="h-3.5 w-3.5" />
                                Saída
                              </span>
                            )}
                          </span>
                        </div>
                      );
                    })}
                  </div>

                  {/* Action Bar */}
                  {selected.size > 0 && (
                    <div className="flex items-center justify-between gap-3 px-4 py-3 bg-primary/10 border-t border-primary/20">
                      <p className="text-sm text-foreground">
                        <span className="font-bold text-primary">{selected.size}</span> linha(s) selecionada(s)
                      </p>
                      <div className="flex gap-2">
                        <Button
                          id={`btn-ignorar-${extrato.id}`}
                          variant="outline"
                          size="sm"
                          className="gap-1.5 text-red-600 dark:text-red-400 border-red-300 dark:border-red-800 hover:bg-red-50 dark:hover:bg-red-900/20"
                          onClick={() => handleProcessar(extrato.id, 'ignorar')}
                          disabled={isPending}
                        >
                          {isPending ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <XCircle className="h-3.5 w-3.5" />}
                          Ignorar
                        </Button>
                        <Button
                          id={`btn-importar-${extrato.id}`}
                          size="sm"
                          className="gap-1.5"
                          onClick={() => handleProcessar(extrato.id, 'importar')}
                          disabled={isPending}
                        >
                          {isPending ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <CheckCircle2 className="h-3.5 w-3.5" />}
                          Confirmar Inclusão
                        </Button>
                      </div>
                    </div>
                  )}
                </div>
              )}

              {isExpanded && linhas.length === 0 && (
                <div className="border-t border-border/40 p-6 text-center">
                  <CheckCircle2 className="h-8 w-8 text-emerald-500 mx-auto mb-2" />
                  <p className="text-sm text-muted-foreground">
                    Todas as linhas deste extrato foram processadas.
                  </p>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
