/**
 * Hook customizado para Gerenciamento de Inatividade de Sessão.
 *
 * Monitora interações do usuário (cliques, toques, rolagem e teclado).
 * Se o usuário ficar inativo por 14 minutos, aciona um aviso com contagem regressiva.
 * Aos 15 minutos, encerra a sessão automaticamente por segurança financeira.
 *
 * Para testes locais rápidos:
 * Pode ser ativado no console do navegador via:
 * `window.ativarTesteInatividade(30)` (onde 30 são os segundos totais).
 */
import { useState, useEffect, useRef, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthProvider';

// Configurações padrão (em milissegundos)
const DEFAULT_INATIVIDADE_MS = 15 * 60 * 1000; // 15 minutos
const DEFAULT_AVISO_PREVIO_MS = 14 * 60 * 1000; // 14 minutos (avisa 1 minuto antes)

export function useInactivityTimer() {
  const { isAuthenticated, logout, recarregarPerfil } = useAuth();
  const navigate = useNavigate();

  const [mostrarAviso, setMostrarAviso] = useState(false);
  const [segundosRestantes, setSegundosRestantes] = useState(60);

  const ultimaAtividadeRef = useRef(Date.now());
  const timerCheckRef = useRef(null);
  const countdownIntervalRef = useRef(null);
  const avisoAtivoRef = useRef(false);

  // Permite configurar tempos menores para testes locais
  const configRef = useRef({
    totalMs: DEFAULT_INATIVIDADE_MS,
    avisoMs: DEFAULT_AVISO_PREVIO_MS,
  });

  // Função global de conveniência para testar facilmente no DevTools
  useEffect(() => {
    window.ativarTesteInatividade = (segundosTotais = 30) => {
      const totalMs = segundosTotais * 1000;
      const avisoMs = Math.max(5000, totalMs - 15000); // Avisa 15s antes ou mínimo 5s
      configRef.current = { totalMs, avisoMs };
      ultimaAtividadeRef.current = Date.now();
      setMostrarAviso(false);
      avisoAtivoRef.current = false;
      console.log(
        `%c[FreeCash]%c Modo teste de inatividade ativado: total de ${segundosTotais}s (aviso aos ${avisoMs / 1000}s).`,
        'color: #10b981; font-weight: bold;',
        'color: inherit;'
      );
    };

    window.desativarTesteInatividade = () => {
      configRef.current = {
        totalMs: DEFAULT_INATIVIDADE_MS,
        avisoMs: DEFAULT_AVISO_PREVIO_MS,
      };
      ultimaAtividadeRef.current = Date.now();
      setMostrarAviso(false);
      avisoAtivoRef.current = false;
      console.log(
        '%c[FreeCash]%c Teste de inatividade desativado: restaurado para 15 minutos padrão.',
        'color: #10b981; font-weight: bold;',
        'color: inherit;'
      );
    };

    return () => {
      delete window.ativarTesteInatividade;
      delete window.desativarTesteInatividade;
    };
  }, []);

  const encerrarSessao = useCallback(async () => {
    clearInterval(countdownIntervalRef.current);
    clearInterval(timerCheckRef.current);
    setMostrarAviso(false);
    avisoAtivoRef.current = false;

    try {
      await logout();
    } catch {
      // Ignora falhas de rede no logout forçado
    }

    navigate('/login?motivo=inatividade', { replace: true });
  }, [logout, navigate]);

  const estenderSessao = useCallback(async () => {
    ultimaAtividadeRef.current = Date.now();
    setMostrarAviso(false);
    avisoAtivoRef.current = false;
    clearInterval(countdownIntervalRef.current);

    // Faz um ping silencioso para renovar o token e manter o backend ativo
    try {
      await recarregarPerfil();
    } catch {
      // Falha tratada silenciosamente
    }
  }, [recarregarPerfil]);

  useEffect(() => {
    if (!isAuthenticated) {
      setMostrarAviso(false);
      avisoAtivoRef.current = false;
      clearInterval(timerCheckRef.current);
      clearInterval(countdownIntervalRef.current);
      return;
    }

    ultimaAtividadeRef.current = Date.now();

    // Registra eventos do usuário com throttling leve
    const registrarAtividade = () => {
      // Se o modal de aviso já estiver na tela, não reseta automaticamente pelo mouse,
      // para forçar o usuário a clicar no botão "Continuar conectado" conscientemente.
      if (!avisoAtivoRef.current) {
        ultimaAtividadeRef.current = Date.now();
      }
    };

    const eventos = ['mousedown', 'keydown', 'scroll', 'touchstart', 'click'];
    eventos.forEach((evento) => {
      window.addEventListener(evento, registrarAtividade, { passive: true });
    });

    // Loop de checagem periódica a cada 1 segundo
    timerCheckRef.current = setInterval(() => {
      const agora = Date.now();
      const tempoInativo = agora - ultimaAtividadeRef.current;
      const { totalMs, avisoMs } = configRef.current;

      // Se estourou o tempo total -> encerra imediatamente
      if (tempoInativo >= totalMs) {
        encerrarSessao();
        return;
      }

      // Se entrou na janela de aviso prévio
      if (tempoInativo >= avisoMs) {
        if (!avisoAtivoRef.current) {
          avisoAtivoRef.current = true;
          setMostrarAviso(true);

          const segundosFaltantes = Math.max(1, Math.ceil((totalMs - tempoInativo) / 1000));
          setSegundosRestantes(segundosFaltantes);

          // Inicia contagem regressiva visual segundo a segundo
          clearInterval(countdownIntervalRef.current);
          countdownIntervalRef.current = setInterval(() => {
            const atual = Date.now();
            const restante = Math.max(0, Math.ceil((configRef.current.totalMs - (atual - ultimaAtividadeRef.current)) / 1000));
            setSegundosRestantes(restante);
            if (restante <= 0) {
              clearInterval(countdownIntervalRef.current);
            }
          }, 1000);
        }
      } else {
        // Se voltou a ter atividade antes do aviso
        if (avisoAtivoRef.current) {
          avisoAtivoRef.current = false;
          setMostrarAviso(false);
          clearInterval(countdownIntervalRef.current);
        }
      }
    }, 1000);

    return () => {
      eventos.forEach((evento) => {
        window.removeEventListener(evento, registrarAtividade);
      });
      clearInterval(timerCheckRef.current);
      clearInterval(countdownIntervalRef.current);
    };
  }, [isAuthenticated, encerrarSessao]);

  return {
    mostrarAviso,
    segundosRestantes,
    estenderSessao,
    encerrarSessao,
  };
}
