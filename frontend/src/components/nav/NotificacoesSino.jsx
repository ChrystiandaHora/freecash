/**
 * Sino de notificações da barra superior.
 *
 * Reúne os avisos que antes tinham lugar próprio: o banner de e-mail não confirmado, que
 * aparecia no topo de todas as telas, e o indicador de sinais de rebalanceamento, que
 * era um ícone à parte na barra. O que entra e para onde leva fica em lib/notificacoes.
 *
 * Clicar numa notificação a marca como lida: ela continua na lista, em cinza, e sai do
 * contador até o assunto mudar. A não lida tem ponto e título em negrito, para a
 * diferença não depender só da cor (SC 1.4.1). O "lido" fica no `localStorage`, por
 * navegador — sem backend, para custar quase nada.
 *
 * Padrão de disclosure, como o resto da navbar — sem `role="menu"`. Fecha com Escape
 * (devolvendo o foco ao sino), com clique fora e quando o Tab sai do conjunto. O número
 * vai no nome acessível; o contador visual é `aria-hidden` para não ser lido duas vezes.
 */
import { useEffect, useId, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { Bell } from 'lucide-react';
import { cn } from '../../lib/utils';
import { lerLidas, marcarLida, montarNotificacoes, naoLidas } from '../../lib/notificacoes';
import { useAuth } from '../../context/AuthProvider';
import { useSinais } from '../../hooks/useSinais';

export function NotificacoesSino() {
  const { perfil } = useAuth();
  const { data: sinais } = useSinais();
  const [aberto, setAberto] = useState(false);
  const [lidas, setLidas] = useState(() => lerLidas());
  const raizRef = useRef(null);
  const gatilhoRef = useRef(null);
  const painelId = useId();

  const todas = montarNotificacoes(perfil, sinais?.sinais ?? []);
  const total = naoLidas(todas, lidas).length;
  const rotulo = total
    ? `Notificações: ${total} ${total === 1 ? 'nova' : 'novas'}`
    : 'Notificações';

  useEffect(() => {
    if (!aberto) return undefined;

    const aoTeclar = (event) => {
      if (event.key !== 'Escape') return;
      setAberto(false);
      gatilhoRef.current?.focus();
    };
    const aoTocarFora = (event) => {
      if (!raizRef.current?.contains(event.target)) setAberto(false);
    };

    document.addEventListener('keydown', aoTeclar);
    document.addEventListener('pointerdown', aoTocarFora);
    return () => {
      document.removeEventListener('keydown', aoTeclar);
      document.removeEventListener('pointerdown', aoTocarFora);
    };
  }, [aberto]);

  return (
    // `relative` ancora o painel no sino (ver o mesmo wrapper em UserMenu)
    <div
      ref={raizRef}
      className="relative"
      onBlur={(event) => {
        if (event.currentTarget.contains(event.relatedTarget)) return;
        setAberto(false);
      }}
    >
      <button
        type="button"
        ref={gatilhoRef}
        onClick={() => setAberto((valor) => !valor)}
        aria-expanded={aberto}
        aria-controls={painelId}
        aria-label={rotulo}
        className="relative inline-flex h-11 w-11 items-center justify-center rounded-xl text-muted-foreground transition-colors hover:bg-muted/50 hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
      >
        <Bell className="h-[1.1rem] w-[1.1rem]" aria-hidden="true" />
        {total > 0 && (
          <span
            aria-hidden="true"
            className="absolute right-1 top-1 min-w-4 rounded-full bg-primary px-1 text-center text-xs font-bold leading-4 text-primary-foreground"
          >
            {total}
          </span>
        )}
      </button>

      {/* Sempre montado, porque `aria-controls` aponta para ele; `inert` o tira do foco quando fechado */}
      <div
        id={painelId}
        inert={!aberto}
        className={cn(
          'absolute right-0 top-full z-10 mt-2 w-72 max-w-[calc(100vw-2rem)] origin-top-right rounded-xl border border-border/60',
          'bg-popover p-2 text-popover-foreground shadow-lg',
          'motion-safe:transition-[opacity,transform] motion-safe:duration-150',
          aberto
            ? 'pointer-events-auto scale-100 opacity-100'
            : 'pointer-events-none scale-95 opacity-0'
        )}
      >
        <h2 className="px-2 py-1.5 text-sm font-semibold text-foreground">Notificações</h2>
        <div className="my-1 h-px bg-border/60" aria-hidden="true" />

        {todas.length === 0 ? (
          <p className="px-2 py-3 text-sm text-muted-foreground">Nenhuma notificação.</p>
        ) : (
          <ul className="space-y-1">
            {todas.map((notificacao) => {
              const lida = lidas.includes(notificacao.assinatura);
              return (
                <li key={notificacao.id}>
                  <Link
                    to={notificacao.destino}
                    onClick={() => {
                      setLidas(marcarLida(notificacao, todas, lidas));
                      setAberto(false);
                    }}
                    className="flex min-h-11 gap-2 rounded-lg px-2 py-2 transition-colors hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                  >
                    <span
                      aria-hidden="true"
                      className={cn('mt-1.5 h-2 w-2 shrink-0 rounded-full', !lida && 'bg-primary')}
                    />
                    <span className="min-w-0">
                      <span
                        className={cn(
                          'block text-sm',
                          lida ? 'font-medium text-muted-foreground' : 'font-semibold text-foreground'
                        )}
                      >
                        {notificacao.titulo}
                        {lida && <span className="sr-only"> (lida)</span>}
                      </span>
                      <span className="block text-xs text-muted-foreground">{notificacao.texto}</span>
                    </span>
                  </Link>
                </li>
              );
            })}
          </ul>
        )}
      </div>
    </div>
  );
}
