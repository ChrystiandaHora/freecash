/**
 * Hook reativo de media query.
 *
 * Usa `useSyncExternalStore` em vez do par `useState(() => mql.matches)` +
 * `useEffect(subscribe)`: aquele padrão tem uma janela de tearing entre a
 * primeira renderização e a montagem do efeito, na qual um `change` é perdido.
 *
 * @module hooks/useMediaQuery
 */
import { useCallback, useMemo, useSyncExternalStore } from 'react';

/**
 * Largura a partir da qual a navbar horizontal aparece.
 *
 * Espelha o prefixo `lg:` do Tailwind. O Tailwind v4 não expõe seus breakpoints
 * ao JS, então a duplicação é inevitável — se um mudar, mude o outro.
 *
 * Era 1280px quando a barra ainda carregava relógio e nome de usuário (~1220px
 * de conteúdo). Com os dois removidos o cluster direito caiu para 199px, e a
 * largura mínima medida passou a ~905px: a 1024 sobram 143px, sem overflow
 * horizontal. Isso devolve a navegação horizontal ao iPad em paisagem.
 *
 * O que paga essa folga: o wordmark "FreeCash" só aparece a partir de `xl`
 * (abaixo disso fica o ícone sozinho) e os gatilhos usam `px-3` em vez de `px-4`.
 */
export const DESKTOP_NAV_QUERY = '(min-width: 1024px)';

/**
 * Ponteiro capaz de hover de verdade (mouse/trackpad), não toque nem caneta.
 *
 * `(pointer: coarse)` sozinho classificaria errado laptops híbridos; e a
 * consulta precisa ser reativa porque um usuário de Surface troca de modalidade
 * no meio da sessão.
 */
export const FINE_HOVER_QUERY = '(hover: hover) and (pointer: fine)';

/**
 * @param {string} query - Media query CSS.
 * @returns {boolean} Se a query casa no momento.
 */
export function useMediaQuery(query) {
  const mql = useMemo(
    () => (typeof window === 'undefined' ? null : window.matchMedia(query)),
    [query]
  );

  const subscribe = useCallback(
    (onChange) => {
      if (!mql) return () => {};
      mql.addEventListener('change', onChange);
      return () => mql.removeEventListener('change', onChange);
    },
    [mql]
  );

  return useSyncExternalStore(
    subscribe,
    () => (mql ? mql.matches : false),
    () => false
  );
}
