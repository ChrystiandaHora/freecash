/**
 * Aviso persistente para contas com e-mail ainda não confirmado.
 *
 * Existe porque o produto permite entrar antes de confirmar o e-mail. Bloquear o
 * login de quem não confirmou seria pior: a conta já nasce com o ecossistema
 * financeiro provisionado, e a pessoa não conseguiria entrar nem para pedir um
 * novo link — o reenvio precisaria ser um endpoint aberto, que serviria para
 * descobrir quem tem conta e para disparar mensagens contra terceiros.
 *
 * O aviso trata dois casos distintos, e a diferença importa: a conta pode ter um
 * e-mail pendente de confirmação, ou pode não ter e-mail nenhum — o caso das
 * contas criadas antes de o endereço passar a ser obrigatório. Na segunda
 * situação não há o que reenviar, e prometer um reenvio seria enganoso.
 *
 * @returns {React.JSX.Element | null} O aviso, ou nada quando não há o que avisar.
 */
import { useState } from 'react';
import { AlertCircle, Loader2, MailWarning } from 'lucide-react';

import { Alert } from '../ui/Alert';
import { useAuth } from '../../context/AuthProvider';
import { extrairErros } from '../../lib/apiErros';
import { reenviarConfirmacaoEmail } from '../../services/auth';

export function EmailVerificationBanner() {
  const { perfil, recarregarPerfil } = useAuth();
  const [enviando, setEnviando] = useState(false);
  const [aviso, setAviso] = useState('');
  const [erro, setErro] = useState('');

  // Sem perfil carregado não há afirmação a fazer: manter a tela silenciosa é
  // melhor que exibir um aviso possivelmente falso.
  if (!perfil || perfil.email_verificado) {
    return null;
  }

  const semEmail = !perfil.email;

  const reenviar = async () => {
    setEnviando(true);
    setAviso('');
    setErro('');
    try {
      const dados = await reenviarConfirmacaoEmail();
      setAviso(dados?.detail || 'Enviamos um novo link de confirmação.');
      await recarregarPerfil();
    } catch (err) {
      const { geral } = extrairErros(
        err,
        'Não foi possível reenviar agora. Tente novamente em alguns minutos.'
      );
      setErro(geral);
    } finally {
      setEnviando(false);
    }
  };

  if (aviso) {
    return (
      <Alert variant="success" className="text-xs">
        <span className="font-medium leading-relaxed">{aviso}</span>
      </Alert>
    );
  }

  return (
    <Alert
      variant="warning"
      icon={erro ? AlertCircle : MailWarning}
      className="text-xs"
    >
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between sm:gap-4">
        <span className="font-medium leading-relaxed">
          {erro
            ? erro
            : semEmail
              ? 'Sua conta não tem e-mail cadastrado. Sem ele, não é possível recuperar o acesso caso você esqueça a senha.'
              : `Confirme seu e-mail (${perfil.email}) para garantir a recuperação da sua senha.`}
        </span>

        {!semEmail && (
          <button
            type="button"
            onClick={reenviar}
            disabled={enviando}
            className="inline-flex shrink-0 items-center justify-center gap-1.5 rounded-lg border border-current/30 px-3 py-1.5 font-semibold transition-colors hover:bg-current/10 disabled:opacity-60"
          >
            {enviando ? (
              <>
                <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden="true" />
                <span>Enviando...</span>
              </>
            ) : (
              <span>Reenviar confirmação</span>
            )}
          </button>
        )}
      </div>
    </Alert>
  );
}
