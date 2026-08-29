/**
 * Botão de ajuda contextual do header e seu modal.
 *
 * Movido do DashboardLayout praticamente verbatim — o corpo do modal, o matcher de
 * rota por expressão regular e o texto de fallback são os mesmos. Duas mudanças:
 * as duas strings do fallback que mandavam usar o "menu lateral esquerdo" (que não
 * existe mais), e a remoção do `title` (falha a SC 1.4.13 e duplicava o
 * `aria-label`).
 *
 * SC 3.2.6 Consistent Help: este é um mecanismo de ajuda automatizada, então ele
 * precisa viver no layout compartilhado — nunca posicionado tela por tela — e sua
 * ORDEM relativa ao tema e ao relógio não pode mudar entre breakpoints.
 */
import { useState } from 'react';
import { useLocation } from 'react-router-dom';
import { HelpCircle } from 'lucide-react';
import { Button } from '../ui/Button';
import { Modal } from '../ui/Modal';
import { helpContent } from '../../config/helpContent';

/** Casa a rota atual com o dicionário de ajuda, aceitando parâmetros como `:id`. */
const getHelpForPath = (path) => {
  for (const pattern in helpContent) {
    const escaped = pattern.replace(/([.+*?=^!:${}()[\]|/\\])/g, '\\$1');
    const regexStr = '^' + escaped.replace(/\\:[a-zA-Z0-9_]+/g, '[^/]+') + '$';
    if (new RegExp(regexStr).test(path)) return helpContent[pattern];
  }
  return null;
};

const fallbackHelp = {
  title: 'Central de Ajuda FreeCash',
  overview:
    'Você está navegando pelo painel consolidado do FreeCash. Use a barra de navegação no topo para gerenciar suas contas, cartões de crédito e carteiras de investimento.',
  features: [
    'Acompanhe o painel de controle geral (Dashboard) para ver resumos de receitas e despesas.',
    'Cadastre ativos e gerencie sua carteira na seção de Investimentos.',
    'Importe planilhas, concilie compras de cartões de crédito e realize backups de seus dados.',
  ],
  actions: {
    Navegação:
      'Use a barra no topo para alternar entre as telas: cada grupo abre um painel com os seus destinos.',
    'Tema Claro/Escuro':
      'Clique no ícone de sol/lua no cabeçalho superior para mudar as cores do painel.',
    'Ajuda Contextual': 'Clique no botão (?) em qualquer tela para abrir este guia novamente.',
  },
};

/**
 */
export function HelpButton() {
  const [helpOpen, setHelpOpen] = useState(false);
  const location = useLocation();
  const currentHelp = getHelpForPath(location.pathname) || fallbackHelp;

  return (
    <>
      <Button
        variant="ghost"
        size="icon"
        onClick={() => setHelpOpen(true)}
        className="rounded-xl text-muted-foreground hover:bg-muted/50"
        aria-label="Ajuda desta tela"
      >
        <HelpCircle className="h-[1.1rem] w-[1.1rem]" aria-hidden="true" />
      </Button>

      {helpOpen && (
        <Modal
          isOpen
          onClose={() => setHelpOpen(false)}
          size="lg"
          title={
            <span className="flex items-center gap-2.5">
              <span className="w-8 h-8 rounded-lg bg-primary/10 border border-primary/20 flex items-center justify-center text-primary shrink-0">
                <HelpCircle className="h-4 w-4" aria-hidden="true" />
              </span>
              Ajuda: {currentHelp.title}
            </span>
          }
        >
          <div className="space-y-6">
            {/* Body (Scrollable) */}
            <div className="max-h-[60vh] overflow-y-auto space-y-6 custom-scrollbar pr-1">
              {/* Visão Geral */}
              <div className="space-y-2">
                <h4 className="text-xs font-bold text-muted-foreground uppercase tracking-wider">Visão Geral</h4>
                <p className="text-sm text-foreground/90 leading-relaxed font-medium">
                  {currentHelp.overview}
                </p>
              </div>

              {/* Como Usar */}
              {currentHelp.features && currentHelp.features.length > 0 && (
                <div className="space-y-3">
                  <h4 className="text-xs font-bold text-muted-foreground uppercase tracking-wider">Como Usar / Recursos</h4>
                  <ul className="space-y-2 text-sm text-foreground/80 font-medium">
                    {currentHelp.features.map((feature, i) => (
                      <li key={i} className="flex items-start gap-2.5">
                        <span className="w-1.5 h-1.5 rounded-full bg-primary mt-1.5 shrink-0" />
                        <span>{feature}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Conceitos Importantes */}
              {currentHelp.concepts && Object.keys(currentHelp.concepts).length > 0 && (
                <div className="space-y-3">
                  <h4 className="text-xs font-bold text-muted-foreground uppercase tracking-wider">Conceitos Importantes</h4>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    {Object.entries(currentHelp.concepts).map(([concept, desc]) => (
                      <div key={concept} className="p-3.5 rounded-xl border border-border/40 bg-muted/20 space-y-1.5">
                        <span className="text-xs font-bold text-primary uppercase tracking-wider">{concept}</span>
                        <p className="text-xs text-foreground/80 leading-relaxed font-medium">{desc}</p>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Dicionário de Ações */}
              {currentHelp.actions && Object.keys(currentHelp.actions).length > 0 && (
                <div className="space-y-3">
                  <h4 className="text-xs font-bold text-muted-foreground uppercase tracking-wider">Guia de Ações e Botões</h4>
                  <div className="overflow-x-auto rounded-xl border border-border/40 bg-muted/10">
                    <table className="w-full text-xs text-left border-collapse">
                      <thead>
                        <tr className="border-b border-border/40 text-muted-foreground font-semibold bg-muted/20">
                          <th scope="col" className="py-2.5 px-4 font-bold uppercase tracking-wider">Elemento / Ação</th>
                          <th scope="col" className="py-2.5 px-4 font-bold uppercase tracking-wider">O que faz</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-border/20 text-foreground/90 font-medium">
                        {Object.entries(currentHelp.actions).map(([name, desc]) => (
                          <tr key={name} className="hover:bg-muted/10 transition-colors">
                            <td className="py-3 px-4 font-bold text-primary">{name}</td>
                            <td className="py-3 px-4 leading-relaxed">{desc}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
            </div>

            {/* Footer */}
            <div className="pt-4 border-t border-border/50 flex justify-end shrink-0">
              <Button
                onClick={() => setHelpOpen(false)}
                className="rounded-xl px-5 font-semibold text-xs py-2 shadow-sm"
              >
                Entendi
              </Button>
            </div>
          </div>
        </Modal>
      )}
    </>
  );
}
