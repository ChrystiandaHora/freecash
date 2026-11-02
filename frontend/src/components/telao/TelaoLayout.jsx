/**
 * Layout do telão: sem barra de navegação nem rodapé, para ocupar a tela inteira.
 *
 * Mantém o monitor de inatividade do app, mas pausado enquanto o documento está em tela
 * cheia: um telão na parede não recebe clique, e o logout de 15 minutos o derrubaria
 * a cada ciclo. Ao sair da tela cheia (Esc), o prazo recomeça do zero. A decisão está
 * registrada em A11Y-DECISIONS.md.
 *
 * Em tela cheia também pede o Wake Lock, para o monitor não apagar; onde a API não
 * existe, nada acontece.
 */
import { useEffect } from 'react';
import { Outlet } from 'react-router-dom';
import { ErrorBoundary } from '../ErrorBoundary';
import { ModalInatividade } from '../auth/ModalInatividade';
import { useInactivityTimer } from '../../hooks/useInactivityTimer';
import { useTelaCheia } from '../../hooks/useTelaCheia';

export default function TelaoLayout() {
  const { emTelaCheia } = useTelaCheia();
  const { mostrarAviso, segundosRestantes, estenderSessao, fecharAviso } = useInactivityTimer({
    pausado: emTelaCheia,
  });

  useEffect(() => {
    document.title = 'Telão de Investimentos · FreeCash';
  }, []);

  useEffect(() => {
    if (!emTelaCheia || !('wakeLock' in navigator)) return undefined;

    let trava = null;
    let ativo = true;
    const pedir = async () => {
      try {
        const nova = await navigator.wakeLock.request('screen');
        // Saiu da tela cheia enquanto o pedido estava em voo
        if (!ativo) return nova.release().catch(() => {});
        trava = nova;
      } catch {
        // Bateria fraca ou política do navegador: o telão funciona, só a tela pode apagar
      }
    };
    // O navegador solta a trava quando a aba some; ao voltar, é preciso pedir de novo
    const aoMudarVisibilidade = () => {
      if (ativo && document.visibilityState === 'visible') pedir();
    };

    pedir();
    document.addEventListener('visibilitychange', aoMudarVisibilidade);
    return () => {
      ativo = false;
      document.removeEventListener('visibilitychange', aoMudarVisibilidade);
      trava?.release().catch(() => {});
    };
  }, [emTelaCheia]);

  return (
    <div className="min-h-screen bg-background font-sans text-foreground">
      {/* O `id` é o que ui/Modal.jsx usa para devolver o foco, como no DashboardLayout */}
      <main id="conteudo-principal" tabIndex={-1} className="min-h-screen focus:outline-none">
        <ErrorBoundary>
          <Outlet />
        </ErrorBoundary>
      </main>

      <ModalInatividade
        isOpen={mostrarAviso}
        segundosRestantes={segundosRestantes}
        onEstender={estenderSessao}
        onFechar={fecharAviso}
      />
    </div>
  );
}
