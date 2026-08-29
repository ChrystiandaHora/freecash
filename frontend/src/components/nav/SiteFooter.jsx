/**
 * Rodapé da aplicação autenticada: mapa do site + copyright.
 *
 * Substituiu a tira de copyright que vivia inline no DashboardLayout. Expõe as
 * mesmas 18 telas da navbar em cinco colunas — uma por grupo — lendo o MESMO
 * `config/navigation.js` que alimenta o topo, para que rodapé e mega-menu não
 * possam divergir. Nada aqui é uma segunda fonte de verdade.
 *
 * Fica só nas telas autenticadas: o Login não tem rodapé, porque links para
 * rotas protegidas ali só levariam a um redirect.
 *
 * @component
 * @returns {React.JSX.Element} O rodapé com o mapa do site e o aviso de copyright.
 */
import { useLocation } from 'react-router-dom';
import { NavLinkList } from './NavLinkList';
import { filtrarGruposVisiveis, navIndex } from '../../config/navigation';
import { useAuth } from '../../context/AuthProvider';
import { findActiveNav } from '../../lib/navigation';
import { cn } from '../../lib/utils';

export default function SiteFooter() {
  const location = useLocation();
  // Mesmo matcher do TopNav: em `/contas-pagar/novo` o item "Contas a Pagar"
  // continua ativo (prefixo com fronteira de segmento).
  const activePath = findActiveNav(location.pathname, navIndex)?.item.path ?? null;

  const { perfil } = useAuth();
  // Mesmo critério do TopNav: o mapa do site não anuncia uma área que a pessoa
  // não pode abrir.
  const gruposVisiveis = filtrarGruposVisiveis(Boolean(perfil?.is_staff));

  return (
    // Único `contentinfo` da página, então NÃO leva `aria-label`: o rótulo só
    // seria necessário para desambiguar landmarks irmãos do mesmo tipo.
    <footer className="mt-8 border-t border-border/30 bg-background">
      <div className="mx-auto max-w-[1600px] px-4 py-10 sm:px-6 xl:px-8">
        {/* Segundo landmark de navegação da página. O do topo é "Principal";
            sem um rótulo distinto aqui os dois ficariam indistinguíveis na
            lista de landmarks de um leitor de tela (WCAG 1.3.1 / 2.4.1). */}
        <nav aria-label="Mapa do site">
          {/* O número de colunas acompanha o número de grupos: são 5 para o
              usuário comum e 6 quando o grupo Administração aparece. Fixar em 5
              jogaria o sexto grupo para uma segunda linha solitária. */}
          <div
            className={cn(
              'grid grid-cols-2 items-start gap-x-6 gap-y-8 sm:grid-cols-3',
              gruposVisiveis.length > 5 ? 'lg:grid-cols-6' : 'lg:grid-cols-5'
            )}
          >
            {gruposVisiveis.map((group) => (
              <NavLinkList
                key={group.id}
                labelId={`footer-${group.id}-label`}
                label={group.label}
                items={group.items}
                activePath={activePath}
                size="md"
                // Aqui os rótulos SÃO headings, ao contrário dos painéis da
                // navbar. Lá o motivo de não serem é que cinco painéis
                // transientes injetariam entradas homônimas no rotor; o rodapé
                // é estrutura permanente e única do documento, então as cinco
                // seções ajudam a navegar em vez de poluir.
                labelAs="h2"
                // Os links ficam sobre `--background`, não sobre o `--card` dos
                // painéis: o offset do anel de foco tem que acompanhar.
                surface="page"
              />
            ))}
          </div>
        </nav>

        <p className="mt-10 border-t border-border/30 pt-6 text-center text-xs text-muted-foreground">
          &copy; {new Date().getFullYear()} FreeCash. Todos os direitos reservados.
        </p>
      </div>
    </footer>
  );
}
