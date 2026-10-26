/**
 * Provedor do modo "ocultar valores", ligado pelo olho da barra do topo.
 *
 * A preferência é por dispositivo, em `localStorage`, como o tema: esconder os valores
 * no notebook do trabalho não deve afetar o celular. Só os valores em reais são
 * mascarados; percentuais e o desenho dos gráficos continuam visíveis para que a tela
 * ainda sirva para ler tendência (ver docs/privacidade-valores.md).
 *
 * As telas não leem este contexto direto: usam `useMoeda`, que entrega os formatadores
 * já ligados ao estado.
 */
import { createContext, useCallback, useContext, useMemo, useState } from 'react';

const PrivacidadeContext = createContext(null);

const CHAVE = 'ocultar-valores';

const lerPreferencia = () => localStorage.getItem(CHAVE) === 'true';

/**
 * @param {{children: React.ReactNode}} props
 */
export function PrivacidadeProvider({ children }) {
  const [valoresOcultos, setValoresOcultos] = useState(lerPreferencia);

  const alternarValores = useCallback(() => {
    const proximo = !valoresOcultos;
    setValoresOcultos(proximo);
    localStorage.setItem(CHAVE, String(proximo));
  }, [valoresOcultos]);

  const value = useMemo(
    () => ({ valoresOcultos, alternarValores }),
    [valoresOcultos, alternarValores]
  );

  return <PrivacidadeContext.Provider value={value}>{children}</PrivacidadeContext.Provider>;
}

/**
 * @returns {{valoresOcultos: boolean, alternarValores: () => void}}
 */
export function usePrivacidade() {
  const ctx = useContext(PrivacidadeContext);
  if (!ctx) throw new Error('usePrivacidade deve ser usado dentro de <PrivacidadeProvider>');
  return ctx;
}
