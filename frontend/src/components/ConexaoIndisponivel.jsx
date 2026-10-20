/**
 * Tela de conexão indisponível.
 *
 * Cobre o aplicativo inteiro quando a API não responde — seja porque a internet do
 * usuário caiu, seja porque o servidor está fora do ar. Sem ela, cada tela mostrava o
 * seu próprio erro genérico, e o usuário não tinha como distinguir "quebrou" de "caiu"
 * nem saber se devia fazer algo.
 *
 * Não depende de ação do usuário para sair: reconsulta `/api/health/` em intervalos
 * crescentes e some sozinha quando a API volta, recarregando as consultas ativas do
 * React Query para que a tela por baixo não fique com dados de erro.
 *
 * Quem detecta a queda é o interceptor do axios (`services/api.js`); este componente
 * só lê o estado de `lib/statusConexao` e cuida da reconexão.
 *
 * Arquitetura: renderizada por portal no `document.body`, pelo mesmo motivo do
 * `ui/Modal` — escapar de qualquer containing block de ancestral. Enquanto aberta, o
 * `#root` recebe `inert`, então nem o teclado nem o leitor de tela alcançam a página
 * que ficou por baixo e que não funciona sem a API.
 */
import { useCallback, useEffect, useRef, useState, useSyncExternalStore } from 'react';
import { createPortal } from 'react-dom';
import { useQueryClient } from '@tanstack/react-query';
import { Loader2, RefreshCw, ServerOff, ShieldCheck, Wallet, WifiOff } from 'lucide-react';
import { Button } from './ui/Button';
import { ThemeToggle } from './nav/ThemeToggle';
import { verificarSaudeApi } from '../services/api';
import {
  STATUS_CONEXAO,
  assinarStatusConexao,
  classificarFalha,
  definirStatusConexao,
  intervaloDeTentativa,
  lerStatusConexao,
} from '../lib/statusConexao';

/** Texto e ícone de cada causa: a orientação muda conforme o usuário pode agir ou não. */
const CONTEUDO = {
  [STATUS_CONEXAO.SEM_INTERNET]: {
    Icone: WifiOff,
    titulo: 'Você está sem internet',
    descricao:
      'Não conseguimos alcançar a rede. Verifique o Wi-Fi ou os dados móveis — assim que a conexão voltar, o FreeCash retoma sozinho.',
  },
  [STATUS_CONEXAO.API_INDISPONIVEL]: {
    Icone: ServerOff,
    titulo: 'Servidor indisponível no momento',
    descricao:
      'O FreeCash está temporariamente fora do ar ou em manutenção. Não é preciso fazer nada: quando ele voltar, você continua exatamente de onde parou.',
  },
};

export function ConexaoIndisponivel() {
  const status = useSyncExternalStore(assinarStatusConexao, lerStatusConexao);
  const indisponivel = status !== STATUS_CONEXAO.ONLINE;

  // Os eventos do navegador valem mesmo com a tela fechada: cair o Wi-Fi já é motivo
  // para avisar, sem esperar a próxima requisição falhar.
  useEffect(() => {
    const aoFicarOffline = () => definirStatusConexao(STATUS_CONEXAO.SEM_INTERNET);
    window.addEventListener('offline', aoFicarOffline);
    return () => window.removeEventListener('offline', aoFicarOffline);
  }, []);

  if (!indisponivel) {
    return null;
  }

  return createPortal(<PainelReconexao status={status} />, document.body);
}

/**
 * Conteúdo da tela, montado só enquanto a conexão está indisponível — assim o
 * contador de tentativas recomeça do zero a cada nova queda.
 *
 * @param {{status: string}} props
 */
function PainelReconexao({ status }) {
  const queryClient = useQueryClient();
  const [tentativa, setTentativa] = useState(0);
  const [segundosRestantes, setSegundosRestantes] = useState(() => intervaloDeTentativa(0));
  const [verificando, setVerificando] = useState(false);
  const [aviso, setAviso] = useState('');
  const tituloRef = useRef(null);

  const { Icone, titulo, descricao } = CONTEUDO[status];
  const intervaloAtual = intervaloDeTentativa(tentativa);

  const verificar = useCallback(async () => {
    setVerificando(true);
    setAviso('Verificando a conexão...');
    const voltou = await verificarSaudeApi();
    setVerificando(false);

    if (voltou) {
      // `invalidateQueries` refaz só as consultas com observador ativo; as demais
      // ficam marcadas como velhas e recarregam quando alguém voltar a usá-las.
      definirStatusConexao(STATUS_CONEXAO.ONLINE);
      queryClient.invalidateQueries();
      return;
    }

    definirStatusConexao(classificarFalha(navigator.onLine));
    setAviso('Ainda sem resposta. Vamos tentar de novo em instantes.');
    const proxima = tentativa + 1;
    setTentativa(proxima);
    setSegundosRestantes(intervaloDeTentativa(proxima));
  }, [queryClient, tentativa]);

  // Contagem regressiva até a próxima tentativa automática; no último segundo, em vez
  // de chegar a zero, dispara a verificação.
  useEffect(() => {
    if (verificando) return undefined;
    const timer = setTimeout(() => {
      if (segundosRestantes <= 1) {
        verificar();
      } else {
        setSegundosRestantes((s) => s - 1);
      }
    }, 1000);
    return () => clearTimeout(timer);
  }, [segundosRestantes, verificando, verificar]);

  // A volta da rede é a melhor hora para tentar: não faz sentido esperar o contador.
  useEffect(() => {
    const aoFicarOnline = () => verificar();
    window.addEventListener('online', aoFicarOnline);
    return () => window.removeEventListener('online', aoFicarOnline);
  }, [verificar]);

  // Isola a página de baixo e trava a rolagem enquanto a tela está aberta. O foco vai
  // para o título, que anuncia o motivo antes das ações (WCAG 2.4.3).
  useEffect(() => {
    const raiz = document.getElementById('root');
    const overflowAnterior = document.body.style.overflow;
    raiz?.setAttribute('inert', '');
    document.body.style.overflow = 'hidden';
    tituloRef.current?.focus();

    return () => {
      raiz?.removeAttribute('inert');
      document.body.style.overflow = overflowAnterior;
    };
  }, []);

  const progresso = verificando ? 0 : (segundosRestantes / intervaloAtual) * 100;

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="conexao-titulo"
      aria-describedby="conexao-descricao"
      className="fixed inset-0 z-[100] overflow-y-auto bg-background text-foreground font-sans animate-fade-in"
    >
      <div className="fixed right-5 top-5 z-10 sm:right-6 sm:top-6">
        <ThemeToggle />
      </div>

      <div className="flex min-h-full items-center justify-center px-6 py-12">
        <div className="w-full max-w-md">
          <div className="mb-8 flex flex-col items-center text-center">
            <div className="mb-3 flex h-12 w-12 items-center justify-center rounded-2xl bg-primary shadow-lg shadow-primary/20">
              <Wallet className="h-6 w-6 text-primary-foreground" aria-hidden="true" />
            </div>
            <p className="text-2xl font-bold tracking-tight text-primary">FreeCash</p>
          </div>

          <div className="flex flex-col items-center space-y-5 rounded-2xl border border-border/40 bg-card p-6 text-center text-card-foreground shadow-lg sm:p-8">
            <div className="relative flex h-16 w-16 items-center justify-center rounded-2xl bg-amber-500/10">
              <Icone className="h-8 w-8 text-amber-700 dark:text-amber-400" aria-hidden="true" />
              <span className="absolute -right-1 -top-1 flex h-3.5 w-3.5" aria-hidden="true">
                <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-amber-500 opacity-60" />
                <span className="relative inline-flex h-3.5 w-3.5 rounded-full bg-amber-500" />
              </span>
            </div>

            <div className="space-y-1.5">
              <h1
                id="conexao-titulo"
                ref={tituloRef}
                tabIndex={-1}
                className="text-xl font-bold tracking-tight text-foreground focus:outline-none"
              >
                {titulo}
              </h1>
              <p id="conexao-descricao" className="text-sm leading-relaxed text-muted-foreground">
                {descricao}
              </p>
            </div>

            <div className="w-full space-y-2">
              <div className="h-1.5 w-full overflow-hidden rounded-full bg-muted" aria-hidden="true">
                <div
                  className="h-full rounded-full bg-primary transition-[width] duration-1000 ease-linear"
                  style={{ width: `${progresso}%` }}
                />
              </div>
              {/* Contagem fora da região viva: anunciar um número por segundo seria
                  ruído. O leitor de tela recebe só as mudanças de estado, abaixo. */}
              <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                {verificando
                  ? 'Verificando...'
                  : `Nova tentativa em ${segundosRestantes}s`}
              </p>
              <p role="status" aria-live="polite" className="sr-only">
                {aviso}
              </p>
            </div>

            <Button
              type="button"
              onClick={verificar}
              disabled={verificando}
              className="min-h-11 w-full gap-2 rounded-xl font-semibold"
            >
              {verificando ? (
                <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
              ) : (
                <RefreshCw className="h-4 w-4" aria-hidden="true" />
              )}
              {verificando ? 'Verificando conexão' : 'Tentar agora'}
            </Button>

            <div className="flex items-start gap-1.5 text-left text-xs text-muted-foreground">
              <ShieldCheck className="mt-px h-4 w-4 shrink-0 text-emerald-500" aria-hidden="true" />
              <span>Seus dados estão seguros: nada do que já foi salvo se perdeu.</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
