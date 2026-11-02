/**
 * Dados do telão e o ciclo de sincronização de cotações.
 *
 * A cada ciclo o telão pede `telao/sincronizar/`; o servidor decide se vai à fonte
 * externa e devolve `proxima_em`. O próximo pedido é agendado a partir dele (ver
 * `calcularAtrasoProximaSincronizacao`). Ao terminar, com ou sem sucesso, as queries
 * do telão são invalidadas: os dados antigos ficam na tela até os novos chegarem, então
 * nenhuma requisição bloqueia a visão.
 */
import { useCallback, useEffect, useRef, useState } from 'react';
import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { fetchDashboardInvestimentos, fetchTelao, sincronizarTelao } from '../services/investimentos';
import { RETENTATIVA_APOS_FALHA_MS, calcularAtrasoProximaSincronizacao } from '../lib/telao';
import { useSinais } from './useSinais';

/**
 * @param {number|string|null} carteiraId - Sem carteira, o consolidado.
 */
export function useTelao(carteiraId) {
  const queryClient = useQueryClient();
  const timeoutRef = useRef(null);
  // O timeout chama sempre a versão atual de `sincronizar`, sem reagendar a cada render
  const sincronizarRef = useRef(() => {});
  const [agendadoPara, setAgendadoPara] = useState(null);

  const telao = useQuery({
    queryKey: ['telao', carteiraId ?? 'todas'],
    queryFn: () => fetchTelao(carteiraId),
    placeholderData: keepPreviousData,
  });

  // Mesma chave da tela de investimentos: o cache serve as duas
  const dashboard = useQuery({
    queryKey: ['investimentosDashboard', carteiraId],
    queryFn: () => fetchDashboardInvestimentos(carteiraId),
    placeholderData: keepPreviousData,
  });

  const sinais = useSinais(carteiraId);

  const sincronizacao = useMutation({
    mutationFn: sincronizarTelao,
    retry: false,
    onSettled: () =>
      Promise.all(
        ['telao', 'investimentosDashboard', 'investimentosSinais'].map((chave) =>
          queryClient.invalidateQueries({ queryKey: [chave] })
        )
      ),
  });

  const { mutate } = sincronizacao;
  const sincronizar = useCallback(() => {
    clearTimeout(timeoutRef.current);
    mutate(undefined, {
      onSettled: (resultado, erro) => {
        const atraso = erro
          ? RETENTATIVA_APOS_FALHA_MS
          : calcularAtrasoProximaSincronizacao(resultado?.proxima_em);
        setAgendadoPara(Date.now() + atraso);
        timeoutRef.current = setTimeout(() => sincronizarRef.current(), atraso);
      },
    });
  }, [mutate]);

  useEffect(() => {
    sincronizarRef.current = sincronizar;
  }, [sincronizar]);

  useEffect(() => {
    sincronizar();
    return () => clearTimeout(timeoutRef.current);
  }, [sincronizar]);

  // Navegador que congelou timers em segundo plano: ao voltar, pede se o prazo venceu
  const emAndamento = sincronizacao.isPending;
  useEffect(() => {
    const aoMudarVisibilidade = () => {
      if (document.visibilityState !== 'visible' || emAndamento) return;
      if (agendadoPara !== null && Date.now() >= agendadoPara) sincronizarRef.current();
    };
    document.addEventListener('visibilitychange', aoMudarVisibilidade);
    return () => document.removeEventListener('visibilitychange', aoMudarVisibilidade);
  }, [agendadoPara, emAndamento]);

  return {
    telao,
    dashboard,
    sinais,
    sincronizacao: {
      resultado: sincronizacao.data,
      emAndamento,
      falhou: sincronizacao.isError,
      agendadoPara,
    },
  };
}
