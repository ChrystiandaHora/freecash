/**
 * Manifesto do backup: o conteúdo do ZIP desenhado como árvore de arquivos.
 *
 * É o que torna concreto o "formato comum" — antes de baixar, a pessoa vê que vai
 * receber planilhas e um JSON, não um arquivo que só o freecash abre. A lista de
 * planilhas é ilustrativa: o ZIP traz uma por tipo de dado que a conta tiver.
 *
 * @returns {JSX.Element} Árvore do conteúdo e a orientação de como abrir o arquivo.
 */
import { Braces, FileArchive, FileText, FolderOpen, Lock, Sheet } from 'lucide-react';

const PLANILHAS_DE_EXEMPLO = [
  'lancamentos.csv',
  'cartoes-de-credito.csv',
  'metas-financeiras.csv',
  'ativos.csv',
];

// Traço horizontal que liga cada item à linha vertical da árvore
const RAMO =
  "relative before:absolute before:-left-4 before:top-[0.65rem] before:h-px before:w-3 before:bg-border before:content-['']";

function Item({ icon: Icon, nome, children }) {
  return (
    <li className={RAMO}>
      <span className="flex items-center gap-2 font-mono text-[13px] text-foreground">
        <Icon className="h-4 w-4 shrink-0 text-primary" aria-hidden="true" />
        {nome}
      </span>
      {children}
    </li>
  );
}

export function ConteudoDoArquivo() {
  return (
    <div className="space-y-6">
      <div>
        <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
          O que vem no arquivo
        </h3>

        <div className="mt-4">
          <p className="flex flex-wrap items-center gap-x-2 gap-y-1 font-mono text-[13px] font-semibold text-foreground">
            <FileArchive className="h-4 w-4 shrink-0 text-primary" aria-hidden="true" />
            freecash_meus-dados.zip
            <span className="inline-flex items-center gap-1 rounded-full border border-border bg-card px-2 py-0.5 font-sans text-[11px] font-semibold text-foreground">
              <Lock className="h-3 w-3" aria-hidden="true" />
              AES-256
            </span>
          </p>

          <ul className="ml-[7px] mt-3 space-y-3 border-l border-border pl-4" aria-label="Conteúdo do ZIP">
            <Item icon={FileText} nome="LEIA-ME.txt">
              <p className="mt-0.5 text-xs text-muted-foreground">Como abrir e o que é cada coluna.</p>
            </Item>
            <Item icon={Braces} nome="dados.json">
              <p className="mt-0.5 text-xs text-muted-foreground">
                Tudo num arquivo só. É o que o freecash lê para importar de volta.
              </p>
            </Item>
            <Item icon={FolderOpen} nome="planilhas/">
              <p className="mt-0.5 text-xs text-muted-foreground">
                Uma por tipo de dado, para Excel, Numbers ou LibreOffice.
              </p>
              <ul className="ml-[7px] mt-2 space-y-1.5 border-l border-border pl-4" aria-label="Exemplos de planilhas">
                {PLANILHAS_DE_EXEMPLO.map((nome) => (
                  <Item key={nome} icon={Sheet} nome={nome} />
                ))}
                <li className={`${RAMO} text-xs italic text-muted-foreground`}>e as demais que a conta tiver</li>
              </ul>
            </Item>
          </ul>
        </div>
      </div>

      <div className="border-t border-border/60 pt-5">
        <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
          Para abrir
        </h3>
        <p className="mt-2 text-xs leading-relaxed text-muted-foreground">
          Use o <strong className="font-semibold text-foreground">7-Zip</strong> ou o{' '}
          <strong className="font-semibold text-foreground">WinRAR</strong> no Windows, o{' '}
          <strong className="font-semibold text-foreground">Keka</strong> ou o{' '}
          <strong className="font-semibold text-foreground">The Unarchiver</strong> no macOS, ou o app
          Arquivos no Android. O descompactador que já vem no sistema não abre ZIP com AES-256.
        </p>
      </div>
    </div>
  );
}
