/**
 * Componente de Layout Master da Aplicação Autenticada.
 *
 * Estrutura o esqueleto visual do painel: a barra de navegação superior com
 * mega-menu, o container que injeta as páginas filhas e o rodapé.
 *
 * Antes da migração para navbar este arquivo tinha 685 linhas e acumulava oito
 * responsabilidades. Cada uma foi para o seu lugar: os dados de navegação em
 * `config/navigation.js`, os matchers em `lib/navigation.js`, o motor de tema em
 * `context/ThemeProvider.jsx`, e a barra, o relógio e a ajuda contextual em
 * `components/nav/`.
 *
 * @component
 * @returns {React.JSX.Element} O layout mestre com a navbar e o conteúdo da rota.
 */
import { useEffect, useRef } from 'react';
import { Outlet, useLocation } from 'react-router-dom';
import TopNav from './nav/TopNav';
import { navIndex } from '../config/navigation';
import { getRouteTitle } from '../lib/navigation';

export default function DashboardLayout() {
  const location = useLocation();
  const mainRef = useRef(null);
  // Evita roubar o foco na primeira renderização — só realoca a partir da 1ª navegação.
  const isFirstRenderRef = useRef(true);

  // Ao navegar (SPA): atualiza o título da aba e devolve o foco ao conteúdo
  // principal, para que usuários de teclado/leitor de tela percebam a mudança de
  // página (WCAG 2.4.2 / 2.4.3).
  useEffect(() => {
    document.title = `${getRouteTitle(location.pathname, navIndex)} · FreeCash`;

    if (isFirstRenderRef.current) {
      isFirstRenderRef.current = false;
      return;
    }
    mainRef.current?.focus();
  }, [location.pathname]);

  return (
    <div className="flex min-h-screen flex-col bg-background font-sans text-foreground transition-colors duration-300">
      {/* Skip link: primeiro elemento focável da página, permite pular a
          navegação repetida (WCAG 2.4.1). `min-h-11` atende a SC 2.5.8. */}
      <a
        href="#conteudo-principal"
        className="sr-only focus:not-sr-only focus:fixed focus:left-3 focus:top-3 focus:z-[60] focus:inline-flex focus:min-h-11 focus:items-center focus:rounded-lg focus:bg-primary focus:px-4 focus:text-sm focus:font-semibold focus:text-primary-foreground focus:shadow-lg focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2"
      >
        Pular para o conteúdo principal
      </a>

      <TopNav mainRef={mainRef} />

      {/* Content Viewport — alvo do skip link e do foco realocado na troca de rota.
          O `id` é LOAD-BEARING: ui/Modal.jsx recorre a ele para devolver o foco
          quando o elemento que abriu a modal já saiu do DOM.

          Sem utilidades de `overflow` aqui, de propósito. Além de serem inertes
          (o pai é `min-h-screen`, não `h-screen`, então é o documento que rola),
          `overflow-x: hidden` com `overflow-y: visible` faz o browser computar
          `overflow-y: auto` — e qualquer overflow diferente de `visible` num
          ancestral faz `position: sticky` grudar naquela caixa em vez da
          viewport, o que seria uma armadilha para qualquer sticky de página. */}
      <main
        id="conteudo-principal"
        ref={mainRef}
        tabIndex={-1}
        className="min-w-0 flex-1 p-4 focus:outline-none sm:p-6 lg:p-8"
      >
        <div className="w-full min-w-0 space-y-8">
          <Outlet />
        </div>
      </main>

      <footer className="border-t border-border/30 py-4 text-center text-xs text-muted-foreground">
        &copy; {new Date().getFullYear()} FreeCash. Todos os direitos reservados.
      </footer>
    </div>
  );
}
