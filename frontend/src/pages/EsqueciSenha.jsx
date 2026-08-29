/**
 * Tela de pedido de redefinição de senha.
 *
 * A resposta do servidor é deliberadamente a mesma exista ou não uma conta com o
 * endereço informado, e esta tela **precisa** preservar essa ambiguidade: exibir
 * "e-mail não encontrado" transformaria o formulário num verificador de contas, e
 * saber quem tem conta num sistema financeiro já é informação sensível.
 *
 * Por isso o estado de sucesso é sempre o mesmo, e a tela nunca afirma que a
 * mensagem foi enviada — apenas que, se a conta existir, ela chegará.
 */
import { useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { AlertCircle, ArrowLeft, Loader2, MailCheck } from 'lucide-react';

import { AuthPageShell } from '../components/auth/AuthPageShell';
import { Alert } from '../components/ui/Alert';
import { Button } from '../components/ui/Button';
import { Input } from '../components/ui/Input';
import { extrairErros } from '../lib/apiErros';
import { solicitarResetSenha } from '../services/auth';

export default function EsqueciSenha() {
  const [email, setEmail] = useState('');
  const [enviado, setEnviado] = useState(false);
  const [erro, setErro] = useState('');
  const [erroCampo, setErroCampo] = useState('');
  const [carregando, setCarregando] = useState(false);

  const avisoRef = useRef(null);

  // O foco vai para a mensagem quando ela aparece: sem isso, quem usa teclado ou
  // leitor de tela permanece no botão e não encontra o resultado da ação.
  useEffect(() => {
    if (erro || enviado) {
      avisoRef.current?.focus();
    }
  }, [erro, enviado]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setErro('');
    setErroCampo('');

    if (!email.trim()) {
      setErroCampo('Informe o e-mail da sua conta.');
      return;
    }

    setCarregando(true);
    try {
      await solicitarResetSenha(email.trim());
      setEnviado(true);
    } catch (err) {
      const { porCampo, geral } = extrairErros(
        err,
        'Não foi possível processar o pedido. Tente novamente em instantes.'
      );
      setErroCampo(porCampo.email || '');
      setErro(geral || (porCampo.email ? 'Verifique o e-mail informado.' : ''));
    } finally {
      setCarregando(false);
    }
  };

  const voltar = (
    <Link
      to="/login"
      className="inline-flex items-center gap-1.5 text-xs font-medium text-primary transition-colors hover:text-primary/80"
    >
      <ArrowLeft className="h-3.5 w-3.5" aria-hidden="true" />
      Voltar para o login
    </Link>
  );

  if (enviado) {
    return (
      <AuthPageShell
        titulo="Verifique seu e-mail"
        descricao="O próximo passo está na sua caixa de entrada"
        rodape={voltar}
      >
        <Alert ref={avisoRef} tabIndex={-1} variant="success" icon={MailCheck} className="text-xs">
          <span className="font-medium leading-relaxed">
            Se existir uma conta com esse e-mail, enviamos as instruções de
            redefinição de senha. O link vale por algumas horas e só pode ser usado
            uma vez.
          </span>
        </Alert>
        <p className="text-xs leading-relaxed text-muted-foreground">
          Não chegou? Confira a pasta de spam. Você pode pedir um novo link daqui a
          alguns minutos.
        </p>
      </AuthPageShell>
    );
  }

  return (
    <AuthPageShell
      titulo="Esqueci minha senha"
      descricao="Enviaremos um link para você escolher uma senha nova"
      rodape={voltar}
    >
      <form onSubmit={handleSubmit} className="space-y-4">
        {erro && (
          <Alert ref={avisoRef} tabIndex={-1} variant="error" icon={AlertCircle} className="text-xs">
            <span className="font-medium leading-relaxed">{erro}</span>
          </Alert>
        )}

        <div className="space-y-1.5">
          <label
            htmlFor="reset-email"
            className="text-xs font-semibold uppercase tracking-wide text-muted-foreground"
          >
            E-mail
          </label>
          <Input
            id="reset-email"
            type="email"
            autoComplete="email"
            placeholder="seu@email.com"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="rounded-xl"
            disabled={carregando}
            aria-invalid={!!erroCampo}
            aria-describedby={erroCampo ? 'erro-reset-email' : undefined}
          />
          {erroCampo && (
            <p id="erro-reset-email" className="text-xs text-red-700 dark:text-red-400">
              {erroCampo}
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
              <span>Enviando...</span>
            </>
          ) : (
            <span>Enviar link de redefinição</span>
          )}
        </Button>
      </form>
    </AuthPageShell>
  );
}
