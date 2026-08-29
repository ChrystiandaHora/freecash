/**
 * Moldura compartilhada das telas públicas de identidade.
 *
 * Confirmação de e-mail, "esqueci minha senha" e redefinição de senha são telas
 * curtas, de passagem, que precisam parecer parte do mesmo produto que a tela de
 * login sem replicar o painel de marca dela. Concentrar a moldura aqui evita que
 * as três divirjam em espaçamento, tipografia ou posição do controle de tema.
 *
 * O `<h1>` vive nesta moldura, dentro do `<main>`: cada uma dessas rotas é uma
 * página inteira, e não um fragmento, então precisa do seu próprio título de
 * primeiro nível.
 *
 * @component
 * @param {Object} props - Propriedades do componente.
 * @param {string} props.titulo - Título da página, renderizado como `<h1>`.
 * @param {string} [props.descricao] - Linha de apoio abaixo do título.
 * @param {React.ReactNode} props.children - Conteúdo do cartão.
 * @param {React.ReactNode} [props.rodape] - Ações secundárias abaixo do conteúdo.
 * @returns {React.JSX.Element} Moldura renderizada.
 */
import { Wallet } from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader } from '../ui/Card';
import { ThemeToggle } from '../nav/ThemeToggle';

export function AuthPageShell({ titulo, descricao, children, rodape }) {
  return (
    <div className="min-h-screen w-full bg-background text-foreground font-sans">
      <div className="fixed right-5 top-5 z-40 sm:right-6 sm:top-6">
        <ThemeToggle />
      </div>

      <main className="flex min-h-screen items-center justify-center px-6 py-12">
        <div className="w-full max-w-md">
          <div className="mb-8 flex flex-col items-center text-center">
            <div className="mb-3 flex h-12 w-12 items-center justify-center rounded-2xl bg-primary shadow-lg shadow-primary/20">
              <Wallet className="h-6 w-6 text-primary-foreground" aria-hidden="true" />
            </div>
            <p className="text-2xl font-bold tracking-tight text-primary">FreeCash</p>
          </div>

          <Card className="overflow-hidden rounded-2xl border-border/40 bg-card text-card-foreground shadow-lg">
            <CardHeader className="space-y-1.5 pb-4">
              {/* `<h1>` direto, e não `ui/CardTitle`: aquele componente renderiza
                  um `<h3>` fixo, e estas rotas são páginas inteiras — precisam do
                  seu próprio título de primeiro nível, não de um terceiro. */}
              <h1 className="text-center text-xl font-bold leading-none tracking-tight text-foreground">
                {titulo}
              </h1>
              {descricao && (
                <CardDescription className="text-center text-xs text-muted-foreground">
                  {descricao}
                </CardDescription>
              )}
            </CardHeader>

            <CardContent className="space-y-4 pb-6">{children}</CardContent>
          </Card>

          {rodape && <div className="mt-6 text-center">{rodape}</div>}
        </div>
      </main>
    </div>
  );
}
