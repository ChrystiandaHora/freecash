/**
 * Confirmação da troca de endereço de e-mail.
 *
 * O link chega no **novo** endereço e costuma ser aberto em outro navegador, sem
 * sessão — por isso esta rota fica fora de `PublicRoute` e de `ProtectedRoute`,
 * como a de verificação de conta. A autorização vem do token, que só pôde ser
 * gerado por quem já provou a senha atual.
 *
 * @module ConfirmarTrocaEmail
 * @component
 * @returns {React.JSX.Element}
 */
import { useEffect, useRef, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { AlertCircle, CheckCircle2, Loader2 } from 'lucide-react';

import { AuthPageShell } from '../components/auth/AuthPageShell';
import { Alert } from '../components/ui/Alert';
import { Button } from '../components/ui/Button';
import { useAuth } from '../context/AuthProvider';
import { extrairErros } from '../lib/apiErros';
import { confirmarTrocaEmail } from '../services/auth';

const ESTADO = {
  VERIFICANDO: 'verificando',
  SUCESSO: 'sucesso',
  ERRO: 'erro',
};

export default function ConfirmarTrocaEmail() {
  const { uid, token } = useParams();
  const navigate = useNavigate();
  const { isAuthenticated, recarregarPerfil } = useAuth();

  const [estado, setEstado] = useState(ESTADO.VERIFICANDO);
  const [mensagem, setMensagem] = useState('');

  const avisoRef = useRef(null);

  useEffect(() => {
    let ativo = true;

    const confirmar = async () => {
      try {
        const dados = await confirmarTrocaEmail({ uid, token });
        if (!ativo) return;
        setEstado(ESTADO.SUCESSO);
        setMensagem(dados?.detail || 'E-mail alterado com sucesso.');
        if (isAuthenticated) {
          recarregarPerfil();
        }
      } catch (err) {
        if (!ativo) return;
        const { geral } = extrairErros(
          err,
          'Não foi possível confirmar a troca. O link pode ter expirado.'
        );
        setEstado(ESTADO.ERRO);
        setMensagem(geral);
      }
    };

    confirmar();
    return () => {
      ativo = false;
    };
    // Depende só do par uid/token. Incluir `isAuthenticated` reexecutaria a
    // confirmação quando a sessão terminasse de carregar, gastando o token.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [uid, token]);

  useEffect(() => {
    if (estado !== ESTADO.VERIFICANDO) {
      avisoRef.current?.focus();
    }
  }, [estado]);

  if (estado === ESTADO.VERIFICANDO) {
    return (
      <AuthPageShell titulo="Confirmando seu novo e-mail" descricao="Isso leva apenas um instante">
        <div role="status" className="flex flex-col items-center gap-3 py-4">
          <Loader2 className="h-7 w-7 animate-spin text-primary" aria-hidden="true" />
          <p className="text-sm text-muted-foreground">Verificando o link...</p>
        </div>
      </AuthPageShell>
    );
  }

  const sucesso = estado === ESTADO.SUCESSO;

  return (
    <AuthPageShell
      titulo={sucesso ? 'E-mail alterado' : 'Não foi possível alterar'}
      descricao={
        sucesso
          ? 'Use o novo endereço para entrar e recuperar sua conta'
          : 'O link pode ter expirado ou a troca ter sido cancelada'
      }
      rodape={
        <Link
          to="/login"
          className="text-xs font-medium text-primary transition-colors hover:text-primary/80"
        >
          Ir para o login
        </Link>
      }
    >
      <Alert
        ref={avisoRef}
        tabIndex={-1}
        variant={sucesso ? 'success' : 'error'}
        icon={sucesso ? CheckCircle2 : AlertCircle}
        className="text-xs"
      >
        <span className="font-medium leading-relaxed">{mensagem}</span>
      </Alert>

      {isAuthenticated && (
        <Button
          type="button"
          onClick={() => navigate('/conta')}
          className="h-11 w-full rounded-xl font-semibold"
        >
          Voltar para minha conta
        </Button>
      )}
    </AuthPageShell>
  );
}
