/**
 * Tela de confirmação de endereço de e-mail.
 *
 * Esta rota fica **fora** de `PublicRoute` e de `ProtectedRoute`, ao contrário das
 * demais telas de identidade. O motivo é concreto: quem clica no link do e-mail
 * pode estar com sessão aberta, e o `PublicRoute` redirecionaria essa pessoa para
 * `/dashboard` sem nunca confirmar o e-mail — o link simplesmente não funcionaria
 * para quem já está logado, que é justamente o caso mais comum.
 *
 * A confirmação é enviada por `POST` a partir daqui, e o link do e-mail aponta
 * para esta página em vez de para a API, porque clientes de e-mail e filtros
 * corporativos pré-carregam URLs das mensagens: um `GET` no endpoint consumiria o
 * token antes de o usuário clicar.
 */
import { useEffect, useRef, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { AlertCircle, CheckCircle2, Loader2 } from 'lucide-react';

import { AuthPageShell } from '../components/auth/AuthPageShell';
import { Alert } from '../components/ui/Alert';
import { Button } from '../components/ui/Button';
import { useAuth } from '../context/AuthProvider';
import { extrairErros } from '../lib/apiErros';
import { confirmarEmail } from '../services/auth';

const ESTADO = {
  VERIFICANDO: 'verificando',
  SUCESSO: 'sucesso',
  ERRO: 'erro',
};

export default function VerificarEmail() {
  const { uid, token } = useParams();
  const navigate = useNavigate();
  const { isAuthenticated, recarregarPerfil } = useAuth();

  const [estado, setEstado] = useState(ESTADO.VERIFICANDO);
  const [mensagem, setMensagem] = useState('');

  const avisoRef = useRef(null);

  useEffect(() => {
    let ativo = true;

    const verificar = async () => {
      try {
        const dados = await confirmarEmail({ uid, token });
        if (!ativo) return;

        setEstado(ESTADO.SUCESSO);
        setMensagem(dados?.detail || 'E-mail confirmado com sucesso.');

        // Atualiza o estado da sessão para que o aviso de confirmação desapareça
        // sem exigir recarregamento da página.
        if (isAuthenticated) {
          recarregarPerfil();
        }
      } catch (err) {
        if (!ativo) return;
        const { geral } = extrairErros(
          err,
          'Não foi possível confirmar o e-mail. O link pode ter expirado.'
        );
        setEstado(ESTADO.ERRO);
        setMensagem(geral);
      }
    };

    verificar();
    return () => {
      ativo = false;
    };
    // Depende só do par uid/token: `recarregarPerfil` é estável (useCallback) e
    // incluir `isAuthenticated` reexecutaria a confirmação quando a sessão
    // terminasse de carregar, gastando o token numa segunda chamada.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [uid, token]);

  useEffect(() => {
    if (estado !== ESTADO.VERIFICANDO) {
      avisoRef.current?.focus();
    }
  }, [estado]);

  if (estado === ESTADO.VERIFICANDO) {
    return (
      <AuthPageShell titulo="Confirmando seu e-mail" descricao="Isso leva apenas um instante">
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
      titulo={sucesso ? 'E-mail confirmado' : 'Não foi possível confirmar'}
      descricao={
        sucesso
          ? 'Sua conta está pronta para recuperar a senha quando precisar'
          : 'O link pode ter expirado ou já ter sido usado'
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

      {isAuthenticated ? (
        <Button
          type="button"
          onClick={() => navigate('/dashboard')}
          className="h-11 w-full rounded-xl font-semibold"
        >
          Voltar ao painel
        </Button>
      ) : (
        !sucesso && (
          <p className="text-xs leading-relaxed text-muted-foreground">
            Entre na sua conta para pedir um novo link de confirmação.
          </p>
        )
      )}
    </AuthPageShell>
  );
}
