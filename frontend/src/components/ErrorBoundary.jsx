/**
 * Fronteira de erro do aplicativo.
 *
 * Existe por um caso real: `AjustePagamentoForm` chamava `React.createElement` sem
 * importar `React`, e o `ReferenceError` em render **apagava a aplicação inteira** — nem
 * a navegação sobrava, porque não havia fronteira alguma. Uma tela branca não diz o que
 * aconteceu, não permite voltar e não distingue "o app quebrou" de "a internet caiu".
 *
 * É componente de classe porque `componentDidCatch` e `getDerivedStateFromError` só
 * existem nessa forma; o React não oferece equivalente em hook.
 *
 * Captura erros de **render** dos descendentes. Erro em manipulador de evento,
 * `setTimeout` ou promessa rejeitada não passa por aqui — nas chamadas de API, quem
 * trata é o React Query em cada tela.
 */
import { Component } from 'react';
import { AlertTriangle, RefreshCw } from 'lucide-react';

export class ErrorBoundary extends Component {
  /**
   * @param {{children: React.ReactNode, onReset?: () => void}} props - Props do componente.
   */
  constructor(props) {
    super(props);
    this.state = { erro: null };
  }

  /**
   * Converte a exceção em estado, para que o render seguinte mostre a falha.
   *
   * @param {Error} erro - Exceção lançada por um descendente durante o render.
   * @returns {{erro: Error}} Novo estado.
   */
  static getDerivedStateFromError(erro) {
    return { erro };
  }

  /**
   * Registra a falha no console, com o rastro de componentes.
   *
   * O `componentStack` é o que diz *qual* componente quebrou — sem ele, a mensagem
   * do erro raramente basta para localizar a origem.
   *
   * @param {Error} erro - Exceção capturada.
   * @param {{componentStack: string}} info - Rastro de componentes do React.
   */
  componentDidCatch(erro, info) {
    console.error('Erro de render capturado pela fronteira:', erro, info?.componentStack);
  }

  /**
   * Limpa o erro para tentar renderizar novamente.
   */
  tentarNovamente = () => {
    this.setState({ erro: null });
    this.props.onReset?.();
  };

  render() {
    if (!this.state.erro) {
      return this.props.children;
    }

    return (
      // `role="alert"` porque a falha é assertiva e substitui o conteúdo esperado.
      <div role="alert" className="flex flex-col items-center justify-center px-6 py-20 text-center">
        <div className="mb-4 flex h-16 w-16 items-center justify-center rounded-2xl bg-red-500/10">
          <AlertTriangle className="h-8 w-8 text-red-700 dark:text-red-400" aria-hidden="true" />
        </div>

        <h2 className="mb-1 text-lg font-semibold text-foreground">
          Algo quebrou nesta tela
        </h2>
        <p className="mb-1 max-w-md text-sm text-muted-foreground">
          O erro ficou contido aqui — o restante do aplicativo continua funcionando, e
          nenhum dado seu foi perdido.
        </p>
        <p className="mb-6 max-w-md text-xs text-muted-foreground">
          Se acontecer de novo, os detalhes técnicos estão no console do navegador.
        </p>

        <div className="flex flex-wrap items-center justify-center gap-2">
          <button
            type="button"
            onClick={this.tentarNovamente}
            className="inline-flex min-h-11 items-center gap-2 rounded-xl bg-primary px-4 text-sm font-semibold text-primary-foreground transition-colors hover:bg-primary/90"
          >
            <RefreshCw className="h-4 w-4" aria-hidden="true" />
            Tentar novamente
          </button>
          <a
            href="/dashboard"
            className="inline-flex min-h-11 items-center rounded-xl border border-border px-4 text-sm font-semibold text-foreground transition-colors hover:bg-muted"
          >
            Ir para o início
          </a>
        </div>

        {/* Mensagem crua por último e discreta: ajuda quem sabe ler, sem assustar
            quem não sabe. */}
        <p className="mt-6 max-w-md break-words font-mono text-xs text-muted-foreground/70">
          {this.state.erro?.message}
        </p>
      </div>
    );
  }
}
