/**
 * Botão de ciclo de tema: claro → escuro → automático.
 *
 * Só apresentação; o estado vive no ThemeProvider.
 *
 * Sem `title`: o atributo nativo falha a SC 1.4.13 (não é descartável por
 * Escape, não é hoverable e expira sozinho). Antes havia `title` E `aria-label`
 * com textos DIFERENTES no mesmo botão, o que dava dois candidatos concorrentes a
 * nome acessível (SC 2.5.3). Agora só `aria-label`.
 *
 * @module components/nav/ThemeToggle
 */
import { Moon, Sun, SunMoon } from 'lucide-react';
import { Button } from '../ui/Button';
import { useTheme } from '../../context/ThemeProvider';

/**
 * @returns {React.JSX.Element}
 */
export function ThemeToggle() {
  const { mode, cycleMode, resolvedTheme } = useTheme();

  const label =
    mode === 'light'
      ? 'Tema: claro. Clique para alternar'
      : mode === 'dark'
        ? 'Tema: escuro. Clique para alternar'
        : `Tema: automático, ${resolvedTheme === 'dark' ? 'modo noturno' : 'modo diurno'} por horário. Clique para alternar`;

  return (
    <Button
      variant="ghost"
      size="icon"
      onClick={cycleMode}
      className="rounded-xl text-muted-foreground hover:bg-muted/50"
      aria-label={label}
    >
      {mode === 'light' && <Sun className="h-[1.1rem] w-[1.1rem]" aria-hidden="true" />}
      {mode === 'dark' && <Moon className="h-[1.1rem] w-[1.1rem]" aria-hidden="true" />}
      {mode === 'auto' && <SunMoon className="h-[1.1rem] w-[1.1rem] text-primary" aria-hidden="true" />}
    </Button>
  );
}
