/**
 * Sistema de Notificações em Toast (ToastContext).
 *
 * Provedor de contexto que implementa um sistema de notificações temporárias
 * (toasts) posicionadas no canto inferior direito da tela. Cada notificação
 * é exibida por um tempo configurável e removida automaticamente após sua
 * expiração.
 *
 * Tipos de Toast suportados:
 * - `'success'` → Verde esmeralda com ícone de confirmação.
 * - `'error'`   → Vermelho destrutivo com ícone de alerta.
 * - `'warning'` → Âmbar com ícone de aviso triangular.
 * - `'info'`    → Cor primária com ícone informativo (padrão).
 *
 * Contexto Exportado: `{ addToast, removeToast }`
 *
 * @module ToastContext
 * @component
 *
 * @param {object}         props          - Props do componente.
 * @param {React.ReactNode} props.children - Árvore de componentes filhos que
 *                                          terão acesso ao contexto de toast.
 * @returns {JSX.Element} Provider com o container de toasts renderizado.
 *
 * @example
 * // Disparar um toast de sucesso em qualquer componente filho:
 * const { addToast } = useToast();
 * addToast('Operação realizada com sucesso!', 'success');
 */
import { createContext, useContext, useState, useCallback, useEffect, useRef } from 'react';
import { CheckCircle2, AlertCircle, Info, AlertTriangle, X } from 'lucide-react';

const ToastContext = createContext(null);

// Papel ARIA por tipo (WCAG 4.1.3): erro/aviso interrompem (assertive), sucesso/info só informam (polite).
const roleByType = {
  error: 'alert',
  warning: 'alert',
  success: 'status',
  info: 'status',
};

/** Intervalo de reavaliação do auto-dismiss. */
const TICK_MS = 250;
/** Folga concedida após o usuário soltar o toast, antes de dispensá-lo. */
const GRACE_MS = 750;
/** Teto de retenção por hover: além disso o toast sai mesmo com o ponteiro parado sobre ele. */
const MAX_HOVER_HOLD_FACTOR = 3;

/**
 * Como o usuário está retendo o toast, se estiver. Consultamos o DOM em vez de
 * confiar em eventos pareados de hover/foco, porque mouseleave é pouco confiável:
 * pode disparar com o foco de teclado ainda dentro do toast, e não dispara quando o
 * toast se reposiciona por outro ter sido removido sem o ponteiro se mover.
 */
const getHoldState = (id) => {
  const el = document.querySelector(`[data-toast-id="${id}"]`);
  if (!el) return { porFoco: false, porHover: false };
  return {
    // Foco de teclado é interação deliberada: retém sem teto, pois dispensar
    // destruiria o elemento focado e jogaria o foco no <body>.
    porFoco: el.contains(document.activeElement),
    // Hover pode ser acidental — a pilha fica no canto inferior direito, ponto
    // comum de repouso do mouse — então tem teto.
    porHover: el.matches(':hover'),
  };
};

export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([]);
  // Prazos absolutos de cada toast, fora do state para não re-renderizar a cada tick.
  const timersRef = useRef(new Map());

  const removeToast = useCallback((id) => {
    timersRef.current.delete(id);
    setToasts((prev) => prev.filter((toast) => toast.id !== id));
  }, []);

  const addToast = useCallback((message, type = 'info', duration = 4000) => {
    const id = `${Date.now()}-${Math.random().toString(36).slice(2, 11)}`;
    if (duration > 0) {
      const agora = Date.now();
      timersRef.current.set(id, {
        // Prazos absolutos (em vez de decrementar um contador) para que reinícios
        // do intervalo não estendam indefinidamente a vida do toast.
        prazo: agora + duration,
        prazoMaximo: agora + duration * MAX_HOVER_HOLD_FACTOR,
      });
    }
    setToasts((prev) => [...prev, { id, message, type, duration }]);
  }, []);

  /**
   * Um único tick reavalia todos os toasts, em vez de um setTimeout por toast.
   * A checagem de retenção acontece a cada ciclo, o que trata de forma uniforme
   * hover, foco de teclado e reposicionamento da pilha — casos em que depender de
   * mouseenter/mouseleave pareados deixava o toast preso na tela ou o dispensava
   * com o foco ainda dentro dele (SC 2.2.1 e perda de foco).
   */
  useEffect(() => {
    if (toasts.length === 0) return;

    const intervalId = setInterval(() => {
      const agora = Date.now();
      const expirados = [];

      timersRef.current.forEach((estado, id) => {
        const { porFoco, porHover } = getHoldState(id);

        if (porFoco) return; // retenção sem teto
        if (porHover && agora < estado.prazoMaximo) {
          // Empurra o prazo enquanto o ponteiro estiver sobre o toast, respeitando o teto.
          estado.prazo = agora + GRACE_MS;
          return;
        }
        if (agora >= estado.prazo) expirados.push(id);
      });

      if (expirados.length === 0) return;
      expirados.forEach((id) => timersRef.current.delete(id));
      setToasts((prev) => prev.filter((toast) => !expirados.includes(toast.id)));
    }, TICK_MS);

    return () => clearInterval(intervalId);
  }, [toasts.length]);

  // Mapear tipos para tokens visuais e ícones
  const getToastConfig = (type) => {
    switch (type) {
      case 'success':
        return {
          icon: <CheckCircle2 className="h-5 w-5 text-emerald-500 shrink-0 mt-0.5" />,
          borderClass: 'border-l-4 border-l-emerald-500 border-border/40',
          bgClass: 'bg-card/95 border-border/40',
        };
      case 'error':
        return {
          icon: <AlertCircle className="h-5 w-5 text-destructive shrink-0 mt-0.5" />,
          borderClass: 'border-l-4 border-l-destructive border-border/40',
          bgClass: 'bg-card/95 border-border/40',
        };
      case 'warning':
        return {
          icon: <AlertTriangle className="h-5 w-5 text-amber-500 shrink-0 mt-0.5" />,
          borderClass: 'border-l-4 border-l-amber-500 border-border/40',
          bgClass: 'bg-card/95 border-border/40',
        };
      case 'info':
      default:
        return {
          icon: <Info className="h-5 w-5 text-primary shrink-0 mt-0.5" />,
          borderClass: 'border-l-4 border-l-primary border-border/40',
          bgClass: 'bg-card/95 border-border/40',
        };
    }
  };

  return (
    <ToastContext.Provider value={{ addToast, removeToast }}>
      {children}
      
      {/* Container Absoluto no Canto Inferior Direito */}
      {/* A live region fica no container PERSISTENTE, não no toast: um nó com
          role="status" inserido junto com seu próprio texto costuma não ser
          anunciado por NVDA/JAWS. Com o container já presente na árvore, a
          inserção do toast é percebida como mudança de conteúdo. O role por
          toast (alert para erros) continua valendo para a urgência. */}
      <div
        aria-live="polite"
        aria-atomic="false"
        className="fixed bottom-6 right-6 z-[9999] flex flex-col gap-3 max-w-sm w-full pointer-events-none"
      >
        {toasts.map((toast) => {
          const config = getToastConfig(toast.type);
          return (
            <div
              key={toast.id}
              data-toast-id={toast.id}
              className={`w-full pointer-events-auto flex items-start gap-3 rounded-xl p-4 shadow-lg border backdrop-blur-md text-xs font-semibold text-foreground/90 transition-all transform animate-toast-in ${config.borderClass} ${config.bgClass}`}
              role={roleByType[toast.type] ?? 'status'}
            >
              {/* A pausa por hover/foco é resolvida pelo tick, que consulta
                  :hover e o foco ativo — não precisa de handlers aqui. */}
              {config.icon}
              <div className="flex-1 leading-relaxed break-words pr-2">
                {toast.message}
              </div>
              <button
                onClick={() => removeToast(toast.id)}
                className="text-muted-foreground hover:text-foreground shrink-0 cursor-pointer p-1.5 hover:bg-muted/50 rounded-md transition-colors"
                aria-label="Fechar"
              >
                <X className="h-4 w-4" aria-hidden="true" />
              </button>
            </div>
          );
        })}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast() {
  const context = useContext(ToastContext);
  if (!context) {
    throw new Error('useToast deve ser usado dentro de um ToastProvider');
  }
  return context;
}
