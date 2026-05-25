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
import React, { createContext, useContext, useState, useCallback } from 'react';
import { CheckCircle2, AlertCircle, Info, AlertTriangle, X } from 'lucide-react';

const ToastContext = createContext(null);

export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([]);

  const removeToast = useCallback((id) => {
    setToasts((prev) => prev.filter((toast) => toast.id !== id));
  }, []);

  const addToast = useCallback((message, type = 'info', duration = 4000) => {
    const id = Date.now() + Math.random().toString(36).substr(2, 9);
    
    setToasts((prev) => [...prev, { id, message, type, duration }]);

    if (duration > 0) {
      setTimeout(() => {
        removeToast(id);
      }, duration);
    }
  }, [removeToast]);

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
      <div className="fixed bottom-6 right-6 z-[9999] flex flex-col gap-3 max-w-sm w-full pointer-events-none">
        {toasts.map((toast) => {
          const config = getToastConfig(toast.type);
          return (
            <div
              key={toast.id}
              className={`w-full pointer-events-auto flex items-start gap-3 rounded-xl p-4 shadow-lg border backdrop-blur-md text-xs font-semibold text-foreground/90 transition-all transform animate-toast-in ${config.borderClass} ${config.bgClass}`}
              role="alert"
            >
              {config.icon}
              <div className="flex-1 leading-relaxed break-words pr-2">
                {toast.message}
              </div>
              <button
                onClick={() => removeToast(toast.id)}
                className="text-muted-foreground hover:text-foreground shrink-0 cursor-pointer p-0.5 hover:bg-muted/50 rounded-md transition-colors"
                aria-label="Fechar"
              >
                <X className="h-4 w-4" />
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
