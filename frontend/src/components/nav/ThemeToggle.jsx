/**
 * Botão de ciclo de tema: claro → escuro → automático.
 *
 * Só apresentação; o estado vive no ThemeProvider.
 *
 * Duas formas, para dois contextos:
 * - `icon` (tela de login): botão quadrado só com o ícone, num canto fixo.
 * - `row` (painel de conta): linha de largura total com ícone + rótulo visível,
 *   igual ao Sair que fica logo abaixo.
 *
 * Sem `title`: o atributo nativo falha a SC 1.4.13 (não é descartável por
 * Escape, não é hoverable e expira sozinho). Antes havia `title` E `aria-label`
 * com textos DIFERENTES no mesmo botão, o que dava dois candidatos concorrentes
 * a nome acessível (SC 2.5.3).
 */
import { Moon, Sun, SunMoon } from 'lucide-react';
import { cn } from '../../lib/utils';
import { Button } from '../ui/Button';
import { useTheme } from '../../context/ThemeProvider';

/** Rótulo curto do modo, usado como texto VISÍVEL na forma `row`. */
const MODE_LABEL = { light: 'Claro', dark: 'Escuro', auto: 'Automático' };

/**
 * @param {Object} props
 * @param {'icon' | 'row'} [props.variant='icon'] - Forma do controle.
 */
export function ThemeToggle({ variant = 'icon' }) {
  const { mode, cycleMode, resolvedTheme } = useTheme();

  const icon =
    mode === 'light' ? (
      <Sun className="h-[1.1rem] w-[1.1rem] shrink-0" aria-hidden="true" />
    ) : mode === 'dark' ? (
      <Moon className="h-[1.1rem] w-[1.1rem] shrink-0" aria-hidden="true" />
    ) : (
      <SunMoon className="h-[1.1rem] w-[1.1rem] shrink-0 text-primary" aria-hidden="true" />
    );

  // Contexto que o modo automático precisa: qual tema ele resolveu AGORA.
  const autoDetail = resolvedTheme === 'dark' ? 'modo noturno' : 'modo diurno';

  if (variant === 'row') {
    return (
      <Button
        variant="ghost"
        onClick={cycleMode}
        className="flex min-h-11 w-full items-center justify-start gap-2 rounded-xl px-4 text-muted-foreground hover:bg-muted/60 hover:text-foreground"
      >
        {icon}
        {/* Nome acessível composto por CONTEÚDO, não por `aria-label`: assim o
            texto visível ("Tema: Claro") fica garantidamente como prefixo
            literal do nome acessível, que é o que a SC 2.5.3 Label in Name
            exige — quem usa comando de voz e diz "clique Tema" acerta. Um
            `aria-label` aqui substituiria o texto visível, anti-padrão do
            A11Y.md. */}
        <span className="text-sm font-semibold">
          Tema: {MODE_LABEL[mode]}
          <span className="sr-only">
            {mode === 'auto' ? `, ${autoDetail} por horário` : ''}. Clique para alternar
          </span>
        </span>
      </Button>
    );
  }

  return (
    <Button
      variant="ghost"
      size="icon"
      onClick={cycleMode}
      className={cn('rounded-xl text-muted-foreground hover:bg-muted/50')}
      aria-label={
        mode === 'auto'
          ? `Tema: automático, ${autoDetail} por horário. Clique para alternar`
          : `Tema: ${MODE_LABEL[mode].toLowerCase()}. Clique para alternar`
      }
    >
      {icon}
    </Button>
  );
}
