/** Sistema de notificações temporárias em toast (ToastContext). */
import { createContext, useContext, useState, useCallback, useEffect, useRef } from 'react';
import { CheckCircle2, AlertCircle, Info, AlertTriangle, X } from 'lucide-react';

const ToastContext = createContext(null);

const roleByType = {
  error: 'alert',
  warning: 'alert',
  success: 'status',
  info: 'status',
};

const TICK_MS = 250;
const GRACE_MS = 750;
const MAX_HOVER_HOLD_FACTOR = 3;

/** Avalia se o toast está sob foco de teclado ou cursor do mouse. */
const getHoldState = (id) => {
  const el = document.querySelector(`[data-toast-id="${id}"]`);
  if (!el) return { porFoco: false, porHover: false };
  return {
    porFoco: el.contains(document.activeElement),
    porHover: el.matches(':hover'),
  };
};

export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([]);
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
        prazo: agora + duration,
        prazoMaximo: agora + duration * MAX_HOVER_HOLD_FACTOR,
      });
    }
    setToasts((prev) => [...prev, { id, message, type, duration }]);
  }, []);

  /** Reavalia periodicamente o auto-dismiss respeitando hover e foco ativo. */
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
      
      {/* Live region persistente para leitores de tela */}
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
