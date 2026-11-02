/**
 * Estado e controle da Fullscreen API do documento.
 *
 * O botão que entra no telão chama `entrar()` no próprio clique: o navegador só aceita
 * tela cheia a partir de um gesto do usuário. Sem a API (iPhone, por exemplo),
 * `suportado` é false e o telão abre fora da tela cheia.
 */
import { useCallback, useSyncExternalStore } from 'react';

function assinar(aoMudar) {
  document.addEventListener('fullscreenchange', aoMudar);
  return () => document.removeEventListener('fullscreenchange', aoMudar);
}

const lerEmTelaCheia = () => Boolean(document.fullscreenElement);

/**
 * @returns {{
 *   emTelaCheia: boolean,
 *   suportado: boolean,
 *   entrar: () => Promise<boolean>,
 *   sair: () => Promise<void>,
 * }}
 */
export function useTelaCheia() {
  const emTelaCheia = useSyncExternalStore(assinar, lerEmTelaCheia, () => false);
  const suportado = typeof document !== 'undefined' && Boolean(document.fullscreenEnabled);

  const entrar = useCallback(async () => {
    if (!document.fullscreenEnabled) return false;
    if (document.fullscreenElement) return true;
    try {
      await document.documentElement.requestFullscreen();
      return true;
    } catch {
      // Recusa do navegador (sem gesto, política do site): o telão segue fora da tela cheia
      return false;
    }
  }, []);

  const sair = useCallback(async () => {
    if (!document.fullscreenElement) return;
    try {
      await document.exitFullscreen();
    } catch {
      // Já saiu por Esc entre a checagem e a chamada
    }
  }, []);

  return { emTelaCheia, suportado, entrar, sair };
}
