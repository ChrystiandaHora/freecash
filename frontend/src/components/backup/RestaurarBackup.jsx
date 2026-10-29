/**
 * Atalho da tela de Exportação & Backup para a restauração, que vive em Importar.
 *
 * Fica ao lado dos relatórios, não dentro do painel do backup: restaurar substitui a
 * conta inteira, e um botão disso perto do "Baixar meus dados" convida ao clique errado.
 *
 * @returns {JSX.Element} Seção curta com o aviso e o link para Importar.
 */
import { Link } from 'react-router-dom';
import { ArrowRight, History } from 'lucide-react';

export function RestaurarBackup() {
  return (
    <section
      data-tour="backup-restaurar"
      aria-labelledby="restaurar-titulo"
      className="flex flex-col rounded-2xl border border-border/60 bg-card p-6 shadow-sm sm:p-8 lg:self-start"
    >
      <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-muted" aria-hidden="true">
        <History className="h-5 w-5 text-primary" />
      </span>
      <h2 id="restaurar-titulo" className="mt-4 text-lg font-bold tracking-tight text-foreground">
        Restaurar um backup
      </h2>
      <p className="mt-1 text-sm leading-relaxed text-muted-foreground">
        Envie o <strong className="font-semibold text-foreground">.zip</strong> em Importar, com a
        senha que você definiu ao baixar.
      </p>
      <p className="mt-3 text-sm leading-relaxed text-muted-foreground">
        Os dados atuais da conta são trocados pelos do arquivo — inclusive o que você registrou
        depois de gerá-lo.
      </p>

      <Link
        to="/importar"
        className="mt-6 inline-flex h-11 items-center justify-center gap-2 self-start rounded-md border border-input bg-background px-4 text-sm font-medium text-foreground transition-colors hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
      >
        Ir para Importar
        <ArrowRight className="h-4 w-4" aria-hidden="true" />
      </Link>
    </section>
  );
}
