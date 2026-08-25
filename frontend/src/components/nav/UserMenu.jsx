/**
 * Identificação do usuário e saída de sessão.
 *
 * Era o rodapé da sidebar. Agora tem duas formas deliberadamente diferentes:
 *
 * - `bar` (header desktop): **apenas** o botão Sair, com o texto visível. Sem
 *   avatar e sem nome — num header cuja função é navegar, a identidade da conta
 *   não é informação de navegação, e ocupava ~150px que a barra usa melhor para
 *   caber os cinco grupos numa tela menor.
 * - `stacked` (rodapé do painel mobile): avatar + nome + Sair. É onde a
 *   identificação da conta continua existindo, com espaço de sobra.
 *
 * @module components/nav/UserMenu
 */
import { LogOut, User } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { cn } from '../../lib/utils';
import { Button } from '../ui/Button';
import { useAuth } from '../../context/AuthProvider';

/**
 * @param {Object} props
 * @param {'bar' | 'stacked'} [props.variant='bar'] - `bar` para o header; `stacked` para o painel mobile.
 * @returns {React.JSX.Element}
 */
export function UserMenu({ variant = 'bar' }) {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  const handleLogout = async () => {
    await logout();
    navigate('/login');
  };

  const initial = user?.username ? user.username.charAt(0).toUpperCase() : null;
  const isStacked = variant === 'stacked';

  return (
    <div className={cn('flex items-center gap-3', isStacked && 'justify-between')}>
      {/* Identificação da conta só na variante empilhada (painel mobile). */}
      {isStacked && user && (
        <div className="flex min-w-0 items-center gap-2.5">
          <div
            className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl border border-primary/20 bg-primary/10 text-sm font-bold text-primary shadow-sm dark:bg-primary/20"
            aria-hidden="true"
          >
            {initial ?? <User className="h-4 w-4" />}
          </div>
          {/* A inicial do avatar é decorativa (aria-hidden), então o nome precisa
              existir como texto de verdade — é ele que carrega a informação. */}
          <p className="min-w-0 truncate text-sm font-semibold text-foreground">
            {user.username || 'Usuário'}
          </p>
        </div>
      )}

      <Button
        variant="ghost"
        onClick={handleLogout}
        className={cn(
          'flex min-h-11 items-center gap-2 rounded-xl text-muted-foreground',
          'hover:bg-red-500/10 hover:text-red-500 dark:hover:bg-red-500/20',
          isStacked ? 'justify-start px-4' : 'px-3'
        )}
      >
        <LogOut className="h-5 w-5 shrink-0 text-red-500" aria-hidden="true" />
        {/* O nome da conta entra no nome acessível por CONTEÚDO (`sr-only`), não
            por `aria-label`.
            Duas razões: (1) `aria-label` substituindo texto visível é
            anti-padrão explícito do A11Y.md; (2) compondo por conteúdo, o texto
            visível "Sair" fica garantidamente como prefixo literal do nome
            acessível ("Sair da conta chrystian"), que é o que a SC 2.5.3 Label in
            Name exige — quem usa comando de voz e diz "clique Sair" acerta.
            No desktop este é o único lugar onde a conta logada é identificável,
            já que o rodapé do painel mobile fica `display:none` acima de 1024px. */}
        <span className="text-sm font-semibold">
          Sair
          {user?.username && <span className="sr-only"> da conta {user.username}</span>}
        </span>
      </Button>
    </div>
  );
}
