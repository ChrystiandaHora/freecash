/**
 * Modal de Aviso de Inatividade da Sessão.
 *
 * Exibido quando o usuário passa 14 minutos sem interação, com aviso
 * visual e contagem regressiva para proteger a conta contra acessos indevidos.
 */
import { Modal } from '../ui/Modal';
import { Button } from '../ui/Button';
import { ShieldAlert, Clock } from 'lucide-react';

export function ModalInatividade({ isOpen, segundosRestantes, onEstender, onEncerrar }) {
  return (
    <Modal
      isOpen={isOpen}
      onClose={onEstender}
      title="Sessão Expirando por Inatividade"
      size="sm"
    >
      <div className="flex flex-col items-center text-center space-y-4 py-2">
        <div className="w-14 h-14 rounded-2xl bg-amber-500/10 text-amber-500 flex items-center justify-center">
          <ShieldAlert className="w-8 h-8" aria-hidden="true" />
        </div>

        <div className="space-y-1.5">
          <p className="text-sm text-muted-foreground leading-relaxed">
            Por segurança financeira, sua sessão será encerrada automaticamente caso não haja interação.
          </p>
        </div>

        {/* Badge com contagem regressiva */}
        <div className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-muted/70 border border-border text-foreground font-medium text-sm">
          <Clock className="w-4 h-4 text-amber-500 animate-pulse" aria-hidden="true" />
          <span>
            Tempo restante:{' '}
            <strong className="text-amber-500 font-bold tabular-nums">
              {segundosRestantes} {segundosRestantes === 1 ? 'segundo' : 'segundos'}
            </strong>
          </span>
        </div>

        <div className="w-full flex flex-col sm:flex-row gap-2 pt-3">
          <Button
            type="button"
            variant="outline"
            className="flex-1 order-2 sm:order-1"
            onClick={onEncerrar}
          >
            Sair agora
          </Button>
          <Button
            type="button"
            variant="primary"
            className="flex-1 order-1 sm:order-2"
            onClick={onEstender}
          >
            Continuar conectado
          </Button>
        </div>
      </div>
    </Modal>
  );
}
