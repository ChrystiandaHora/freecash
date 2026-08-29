/**
 * Identificação da conta e saída de sessão.
 *
 * Era o rodapé da sidebar. Tem duas formas deliberadamente diferentes:
 *
 * - `menu` (header desktop): o avatar com a inicial fica sempre visível — é o
 *   que responde "estou logado?" num relance — e é um gatilho de *disclosure*
 *   que abre um painel com o username completo, o tema e o Sair, respondendo
 *   "qual conta?". Consolidar assim ENCOLHE a barra: o Sair (~90px) e o tema
 *   (~44px) saíram dela e o avatar custa ~46px. E tira o logout de um clique no
 *   canto, o que evita saída acidental.
 * - `stacked` (rodapé do painel mobile): avatar + nome + tema + Sair, tudo
 *   achatado e sempre visível. Ali há espaço de sobra e um popup dentro de outro
 *   painel seria aninhamento gratuito.
 *
 * O painel agrega o que é "meu": identidade, preferência de tema e sair. O tema
 * NÃO fecha o painel ao ser acionado — é um ciclo de três estados, e você precisa
 * ver o resultado e poder clicar de novo. O Sair fecha por navegar para /login.
 *
 * PADRÃO: disclosure, igual ao resto da navbar — sem `role="menu"/"menuitem"`.
 * Um menu ARIA obrigaria o contrato completo de teclado (setas, Home/End,
 * type-ahead) para dois itens, e implementar 60% dele é pior que não usá-lo,
 * porque a TA já anunciou um contrato que o widget não honra.
 *
 * Diferente dos painéis de navegação, este NUNCA abre por hover: é popup de
 * ação, não de navegação, então abrir sem intenção explícita seria hostil.
 *
 * @module components/nav/UserMenu
 */
import { LogOut, User, UserCog } from 'lucide-react';
import { Link, useNavigate } from 'react-router-dom';
import { cn } from '../../lib/utils';
import { Button } from '../ui/Button';
import { useAuth } from '../../context/AuthProvider';
import { ThemeToggle } from './ThemeToggle';

/**
 * @param {Object} props
 * @param {'menu' | 'stacked'} [props.variant='menu'] - `menu` no header; `stacked` no painel mobile.
 * @param {boolean} [props.isOpen] - Se o painel está aberto (só na variante `menu`).
 * @param {() => void} [props.onToggle] - Alterna o painel.
 * @param {() => void} [props.onClose] - Fecha o painel (usado quando o Tab sai dele).
 * @param {(el: HTMLButtonElement | null) => void} [props.triggerRef] - Callback ref do gatilho.
 * @param {(el: HTMLDivElement | null) => void} [props.panelRef] - Callback ref do painel.
 * @returns {React.JSX.Element}
 */
export function UserMenu({ variant = 'menu', isOpen, onToggle, onClose, triggerRef, panelRef }) {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  const handleLogout = async () => {
    await logout();
    navigate('/login');
  };

  const username = user?.username || 'Usuário';
  const initial = user?.username ? user.username.charAt(0).toUpperCase() : null;

  const avatar = (
    <span
      // Decorativo: a inicial é redundante com o nome, que existe como texto de
      // verdade tanto no painel quanto no rótulo do gatilho.
      aria-hidden="true"
      className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl border border-primary/20 bg-primary/10 text-sm font-bold text-primary shadow-sm dark:bg-primary/20"
    >
      {initial ?? <User className="h-4 w-4" />}
    </span>
  );

  // Acesso à edição da própria conta. É um `<Link>`, e não um botão com
  // `navigate()`: destino de navegação precisa ser link de verdade, para não
  // perder "abrir em nova aba", o menu de contexto e o rotor de links.
  const contaLink = (
    <Link
      to="/conta"
      onClick={onClose}
      className={cn(
        'flex min-h-11 w-full items-center gap-2 rounded-xl px-4 text-muted-foreground',
        'transition-colors hover:bg-muted hover:text-foreground',
        'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring'
      )}
    >
      <UserCog className="h-5 w-5 shrink-0" aria-hidden="true" />
      <span className="text-sm font-semibold">Minha conta</span>
    </Link>
  );

  const logoutButton = (
    <Button
      variant="ghost"
      onClick={handleLogout}
      className={cn(
        'flex min-h-11 w-full items-center gap-2 rounded-xl text-muted-foreground',
        'hover:bg-red-500/10 hover:text-red-500 dark:hover:bg-red-500/20',
        'justify-start px-4'
      )}
    >
      <LogOut className="h-5 w-5 shrink-0 text-red-500" aria-hidden="true" />
      <span className="text-sm font-semibold">Sair</span>
    </Button>
  );

  // ── Variante do painel mobile: achatada, sem popup ────────────────────────
  if (variant === 'stacked') {
    return (
      <div className="space-y-1">
        <div className="flex min-w-0 items-center gap-2.5 px-2 py-1">
          {avatar}
          <div className="min-w-0">
            <p className="truncate text-sm font-semibold text-foreground">{username}</p>
            <p className="text-xs text-muted-foreground">Sessão ativa</p>
          </div>
        </div>
        <div className="my-1 h-px bg-border/60" aria-hidden="true" />
        {contaLink}
        <ThemeToggle variant="row" />
        {logoutButton}
      </div>
    );
  }

  // ── Variante do header: disclosure ────────────────────────────────────────
  return (
    // `relative` cria o containing block do painel. Necessário: a barra tem
    // `backdrop-blur-md`, e `backdrop-filter` torna o elemento containing block
    // de descendentes ABSOLUTOS também (não só fixos) — sem este wrapper, o
    // `right-0` do painel se alinharia à borda da barra inteira, não ao avatar.
    <div className="relative" onBlur={(e) => {
      // Fecha quando o Tab sai do conjunto gatilho+painel.
      if (e.currentTarget.contains(e.relatedTarget)) return;
      if (isOpen) onClose?.();
    }}>
      <button
        type="button"
        ref={triggerRef}
        onClick={onToggle}
        aria-expanded={isOpen}
        aria-controls="account-menu-panel"
        // Botão sem texto visível, então o nome vem de `aria-label`. Inclui o
        // username: é o que torna a conta identificável por leitor de tela e no
        // foco, além do avatar que a identifica visualmente.
        aria-label={`Conta de ${username}`}
        className="inline-flex h-11 w-11 items-center justify-center rounded-xl transition-colors hover:bg-muted/50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-card"
      >
        {avatar}
      </button>

      {/* Sempre montado: `aria-controls` acima aponta para ele, e referência ARIA
          órfã é anti-padrão do A11Y.md. `inert` é o que o remove do foco e da
          árvore de TA quando fechado. */}
      <div
        id="account-menu-panel"
        ref={panelRef}
        inert={!isOpen}
        className={cn(
          'absolute right-0 top-full z-10 mt-2 w-60 origin-top-right rounded-xl border border-border/60',
          'bg-popover p-2 text-popover-foreground shadow-lg',
          'motion-safe:transition-[opacity,transform] motion-safe:duration-150',
          isOpen
            ? 'pointer-events-auto scale-100 opacity-100'
            : 'pointer-events-none scale-95 opacity-0'
        )}
      >
        <div className="flex items-center gap-2.5 px-2 py-2">
          {avatar}
          <div className="min-w-0">
            <p className="truncate text-sm font-semibold text-foreground">{username}</p>
            <p className="text-xs text-muted-foreground">Sessão ativa</p>
          </div>
        </div>
        <div className="my-1 h-px bg-border/60" aria-hidden="true" />
        {contaLink}
        <ThemeToggle variant="row" />
        {logoutButton}
      </div>
    </div>
  );
}
