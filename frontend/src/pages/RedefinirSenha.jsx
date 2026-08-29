/**
 * Tela de definição de nova senha, aberta a partir do link enviado por e-mail.
 *
 * O `uid` e o `token` chegam pela URL. O token é de uso único sem nenhuma tabela
 * de controle: o gerador do Django inclui o hash da senha e o `last_login` no
 * valor assinado, então a própria troca de senha o invalida.
 *
 * Concluída a troca, o servidor revoga as sessões abertas da conta — se a senha
 * anterior havia vazado, o invasor é desconectado junto. Por isso esta tela leva
 * ao login em vez de entrar automaticamente.
 *
 * @module RedefinirSenha
 * @component
 * @returns {React.JSX.Element}
 */
import { useEffect, useRef, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { AlertCircle, CheckCircle2, Loader2 } from 'lucide-react';

import { AuthPageShell } from '../components/auth/AuthPageShell';
import { Alert } from '../components/ui/Alert';
import { Button } from '../components/ui/Button';
import { PasswordInput } from '../components/ui/PasswordInput';
import { extrairErros } from '../lib/apiErros';
import { confirmarResetSenha } from '../services/auth';

export default function RedefinirSenha() {
  const { uid, token } = useParams();
  const navigate = useNavigate();

  const [senha, setSenha] = useState('');
  const [confirmar, setConfirmar] = useState('');
  const [erro, setErro] = useState('');
  const [errosCampo, setErrosCampo] = useState({});
  const [concluido, setConcluido] = useState(false);
  const [carregando, setCarregando] = useState(false);

  const avisoRef = useRef(null);
  useEffect(() => {
    if (erro || concluido) {
      avisoRef.current?.focus();
    }
  }, [erro, concluido]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setErro('');
    setErrosCampo({});

    if (!senha || !confirmar) {
      setErro('Preencha os dois campos de senha.');
      return;
    }

    // Espelha o MinimumLengthValidator do servidor para dar retorno imediato; os
    // demais validadores (senha comum, numérica, parecida com o usuário) rodam lá.
    if (senha.length < 8) {
      setErrosCampo({ nova_senha: 'A senha deve ter no mínimo 8 caracteres.' });
      setErro('Verifique os campos destacados.');
      return;
    }

    if (senha !== confirmar) {
      setErrosCampo({ confirmar: 'As senhas não coincidem.' });
      setErro('Verifique os campos destacados.');
      return;
    }

    setCarregando(true);
    try {
      await confirmarResetSenha({
        uid,
        token,
        nova_senha: senha,
        confirmar,
      });
      setConcluido(true);
    } catch (err) {
      const { porCampo, geral } = extrairErros(
        err,
        'Não foi possível alterar a senha. O link pode ter expirado.'
      );
      setErrosCampo(porCampo);
      setErro(geral || 'Verifique os campos destacados.');
    } finally {
      setCarregando(false);
    }
  };

  if (concluido) {
    return (
      <AuthPageShell titulo="Senha alterada" descricao="Sua conta já está com a nova senha">
        <Alert ref={avisoRef} tabIndex={-1} variant="success" icon={CheckCircle2} className="text-xs">
          <span className="font-medium leading-relaxed">
            Senha alterada com sucesso. Por segurança, encerramos as sessões que
            estavam abertas nesta conta — entre novamente com a nova senha.
          </span>
        </Alert>
        <Button
          type="button"
          onClick={() => navigate('/login')}
          className="h-11 w-full rounded-xl font-semibold"
        >
          Ir para o login
        </Button>
      </AuthPageShell>
    );
  }

  return (
    <AuthPageShell
      titulo="Definir nova senha"
      descricao="Escolha uma senha que você não use em outros serviços"
      rodape={
        <Link
          to="/esqueci-senha"
          className="text-xs font-medium text-primary transition-colors hover:text-primary/80"
        >
          Pedir um novo link
        </Link>
      }
    >
      <form onSubmit={handleSubmit} className="space-y-4">
        {erro && (
          <Alert ref={avisoRef} tabIndex={-1} variant="error" icon={AlertCircle} className="text-xs">
            <span className="font-medium leading-relaxed">{erro}</span>
          </Alert>
        )}

        <div className="space-y-1.5">
          <label
            htmlFor="nova-senha"
            className="text-xs font-semibold uppercase tracking-wide text-muted-foreground"
          >
            Nova senha
          </label>
          <PasswordInput
            id="nova-senha"
            autoComplete="new-password"
            placeholder="••••••••"
            value={senha}
            onChange={(e) => setSenha(e.target.value)}
            className="rounded-xl"
            disabled={carregando}
            aria-invalid={!!errosCampo.nova_senha}
            aria-describedby={
              errosCampo.nova_senha ? 'erro-nova-senha' : 'ajuda-nova-senha'
            }
          />
          {errosCampo.nova_senha ? (
            <p id="erro-nova-senha" className="text-xs text-red-700 dark:text-red-400">
              {errosCampo.nova_senha}
            </p>
          ) : (
            <p id="ajuda-nova-senha" className="text-xs text-muted-foreground">
              No mínimo 8 caracteres. Evite senhas comuns e parecidas com seu nome de usuário.
            </p>
          )}
        </div>

        <div className="space-y-1.5">
          <label
            htmlFor="confirmar-nova-senha"
            className="text-xs font-semibold uppercase tracking-wide text-muted-foreground"
          >
            Confirmar nova senha
          </label>
          <PasswordInput
            id="confirmar-nova-senha"
            autoComplete="new-password"
            placeholder="••••••••"
            value={confirmar}
            onChange={(e) => setConfirmar(e.target.value)}
            className="rounded-xl"
            disabled={carregando}
            aria-invalid={!!errosCampo.confirmar}
            aria-describedby={errosCampo.confirmar ? 'erro-confirmar-nova-senha' : undefined}
          />
          {errosCampo.confirmar && (
            <p id="erro-confirmar-nova-senha" className="text-xs text-red-700 dark:text-red-400">
              {errosCampo.confirmar}
            </p>
          )}
        </div>

        <Button
          type="submit"
          className="flex h-11 w-full items-center justify-center gap-2 rounded-xl font-semibold"
          disabled={carregando}
        >
          {carregando ? (
            <>
              <Loader2 className="h-4 w-4 animate-spin text-primary-foreground" aria-hidden="true" />
              <span>Salvando...</span>
            </>
          ) : (
            <span>Alterar minha senha</span>
          )}
        </Button>
      </form>
    </AuthPageShell>
  );
}
