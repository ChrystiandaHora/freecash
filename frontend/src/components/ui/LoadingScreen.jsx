/**
 * Tela de Carregamento Inteligente com Feedback de Wake-up (Cold Start).
 *
 * Exibe um carregamento discreto nos primeiros segundos e, se o servidor
 * demorar mais de 2.5s para responder (comum na primeira inicialização da nuvem),
 * orienta o usuário de forma transparente e acolhedora.
 */
import { useEffect, useState } from 'react';
import { Loader2, Cloud, ShieldCheck } from 'lucide-react';

export function LoadingScreen({ label = 'Iniciando sessão segura...' }) {
  const [acordandoServidor, setAcordandoServidor] = useState(false);

  useEffect(() => {
    // Se o backend demorar mais de 2.5s, provavelmente o container da nuvem está acordando
    const timer = setTimeout(() => {
      setAcordandoServidor(true);
    }, 2500);

    return () => clearTimeout(timer);
  }, []);

  return (
    <div
      role="status"
      aria-live="polite"
      className="min-h-screen flex flex-col items-center justify-center bg-background text-foreground px-4 transition-all duration-500"
    >
      {!acordandoServidor ? (
        // Estado inicial rápido (0s a 2.5s)
        <div className="flex flex-col items-center text-center animate-fade-in">
          <Loader2 className="h-9 w-9 text-primary animate-spin" aria-hidden="true" />
          <p className="text-sm font-semibold text-muted-foreground mt-4 uppercase tracking-wider">
            {label}
          </p>
        </div>
      ) : (
        // Estado de "Acordando o Servidor" (> 2.5s)
        <div className="max-w-md w-full p-6 rounded-2xl bg-card border border-border shadow-xl flex flex-col items-center text-center space-y-4 animate-in fade-in zoom-in-95 duration-300">
          <div className="relative flex items-center justify-center w-16 h-16 rounded-2xl bg-primary/10 text-primary mb-1">
            <Cloud className="w-8 h-8 animate-pulse" aria-hidden="true" />
            <span className="absolute -top-1 -right-1 flex h-3.5 w-3.5">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-primary opacity-75"></span>
              <span className="relative inline-flex rounded-full h-3.5 w-3.5 bg-primary"></span>
            </span>
          </div>

          <div className="space-y-1.5">
            <h2 className="text-lg font-bold text-foreground">
              Conectando aos Servidores Seguros
            </h2>
            <p className="text-sm text-muted-foreground leading-relaxed">
              O backend da nuvem está inicializando. No primeiro acesso após um período sem uso, isso pode levar cerca de <strong className="text-foreground">30 segundos</strong>.
            </p>
          </div>

          {/* Barra de progresso com animação contínua */}
          <div className="w-full bg-muted rounded-full h-2 overflow-hidden mt-2">
            <div className="bg-primary h-full w-2/5 rounded-full animate-[shimmer_2s_infinite_linear] bg-gradient-to-r from-primary/40 via-primary to-primary/40"></div>
          </div>

          <div className="flex items-center gap-1.5 text-xs text-muted-foreground/80 pt-1">
            <ShieldCheck className="w-4 h-4 text-emerald-500 shrink-0" aria-hidden="true" />
            <span>Seus dados financeiros permanecem protegidos e criptografados.</span>
          </div>
        </div>
      )}
    </div>
  );
}
