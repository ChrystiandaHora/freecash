/**
 * Provedor de tema da aplicação (claro / escuro / automático).
 *
 * Extraído do DashboardLayout porque o botão de tema passou a viver na navbar, e
 * porque a Login mantinha uma segunda implementação divergente. Unificar corrigiu
 * dois bugs reais:
 *
 * 1. A Login lia `localStorage['theme']` com `if (saved) return saved`, devolvendo
 *    'auto' — que comparado a 'dark' dava falso e forçava o tema claro. Pior: o
 *    toggle de lá gravava 'light'/'dark', DESTRUINDO a preferência 'auto' de quem
 *    passasse pela tela de login.
 * 2. O intervalo de 60s do modo automático mutava `documentElement.classList`
 *    direto, sem tocar estado React. Depois da virada das 18:00 o `aria-label` e o
 *    ícone do botão ficavam obsoletos — diziam "modo diurno" às 19h. Agora o
 *    intervalo atualiza `resolvedTheme` em estado, e o DOM segue uma única fonte.
 */
import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';

const ThemeContext = createContext(null);

const MODES = ['light', 'dark', 'auto'];

/**
 * Tema resolvido do modo automático, por horário local:
 * 06:00–17:59 → claro, 18:00–05:59 → escuro.
 *
 * @returns {'light' | 'dark'}
 */
const getAutoTheme = () => {
  const hours = new Date().getHours();
  return hours >= 6 && hours < 18 ? 'light' : 'dark';
};

const readStoredMode = () => {
  const saved = localStorage.getItem('theme');
  return MODES.includes(saved) ? saved : 'auto';
};

/**
 * @param {{children: React.ReactNode}} props
 */
export function ThemeProvider({ children }) {
  const [mode, setModeState] = useState(readStoredMode);
  const [autoTheme, setAutoTheme] = useState(getAutoTheme);

  const resolvedTheme = mode === 'auto' ? autoTheme : mode;

  // Aplica a classe `.dark` — o `@custom-variant dark` do index.css depende dela.
  useEffect(() => {
    const root = window.document.documentElement;
    root.classList.toggle('dark', resolvedTheme === 'dark');
  }, [resolvedTheme]);

  // Reavalia o horário no modo automático. Atualiza ESTADO (não o DOM direto),
  // para que o rótulo acessível do botão nunca fique defasado do tema aplicado.
  useEffect(() => {
    if (mode !== 'auto') return;
    const interval = setInterval(() => setAutoTheme(getAutoTheme()), 60000);
    return () => clearInterval(interval);
  }, [mode]);

  const setMode = useCallback((next) => {
    if (!MODES.includes(next)) return;
    setModeState(next);
    setAutoTheme(getAutoTheme());
    localStorage.setItem('theme', next);
  }, []);

  const cycleMode = useCallback(() => {
    setMode(MODES[(MODES.indexOf(mode) + 1) % MODES.length]);
  }, [mode, setMode]);

  const value = useMemo(
    () => ({ mode, setMode, cycleMode, resolvedTheme }),
    [mode, setMode, cycleMode, resolvedTheme]
  );

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

/**
 * @returns {{mode: 'light'|'dark'|'auto', setMode: Function, cycleMode: Function, resolvedTheme: 'light'|'dark'}}
 */
export function useTheme() {
  const ctx = useContext(ThemeContext);
  if (!ctx) throw new Error('useTheme deve ser usado dentro de <ThemeProvider>');
  return ctx;
}
