/**
 * Componente de Layout Master da Aplicação Autenticada.
 * 
 * Estrutura o esqueleto visual do painel administrativo, contendo a navegação lateral
 * com transições dinâmicas de colapso, o cabeçalho superior com controle de sessão
 * e o container principal que injeta as páginas filhas.
 *
 * @component
 * @returns {React.JSX.Element} O layout mestre encapsulado com suporte a temas responsivos.
 */
import { useState, useEffect, useRef } from 'react';
import { Outlet, Link, useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthProvider';
import {
  LayoutDashboard,
  LogOut,
  Menu, 
  X, 
  Sun, 
  Moon, 
  SunMoon,
  User,
  CreditCard,
  Wallet,
  FileText,
  FileSpreadsheet,
  KanbanSquare,
  Coins,
  List,
  Activity,
  Gem,
  Scale,
  History,
  Layers,
  UploadCloud,
  CheckSquare,
  DownloadCloud,
  Settings,
  ChevronDown,
  Clock,
  HelpCircle
} from 'lucide-react';
import { Button } from './ui/Button';
import { Modal } from './ui/Modal';
import { helpContent } from '../config/helpContent';

/** Título legível de cada rota, usado para atualizar `document.title` na navegação (WCAG 2.4.2). */
const routeTitles = [
  { match: (p) => p === '/dashboard' || p === '/', title: 'Dashboard' },
  { match: (p) => p === '/investimentos', title: 'Investimentos' },
  { match: (p) => p.startsWith('/investimentos/ativos'), title: 'Meus Ativos' },
  { match: (p) => p.startsWith('/investimentos/balanceamento'), title: 'Balanceamento' },
  { match: (p) => p.startsWith('/investimentos/historico'), title: 'Histórico de Ordens' },
  { match: (p) => p.startsWith('/investimentos/classes'), title: 'Classes de Ativos' },
  { match: (p) => p.startsWith('/contas-pagar'), title: 'Contas a Pagar' },
  { match: (p) => p.startsWith('/contas-kanban'), title: 'Kanban de Contas' },
  { match: (p) => p.startsWith('/cartoes'), title: 'Meus Cartões' },
  { match: (p) => p.startsWith('/receitas'), title: 'Receitas' },
  { match: (p) => p.startsWith('/transacoes'), title: 'Transações' },
  { match: (p) => p.startsWith('/simulador'), title: 'Simulador de Gastos' },
  { match: (p) => p.startsWith('/relatorios'), title: 'Relatórios' },
  { match: (p) => p.startsWith('/importar'), title: 'Importar' },
  { match: (p) => p.startsWith('/compras-cartao'), title: 'Compras no Cartão' },
  { match: (p) => p.startsWith('/backup'), title: 'Backup' },
  { match: (p) => p.startsWith('/pagamentos'), title: 'Formas de Pagamento' },
];

const getRouteTitle = (path) =>
  routeTitles.find((r) => r.match(path))?.title ?? 'FreeCash';

export default function DashboardLayout() {
  const { logout, user } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();
  const [collapsed, setCollapsed] = useState(() => localStorage.getItem('sidebar-collapsed') === 'true');
  const [mobileOpen, setMobileOpen] = useState(false);
  const [openGroup, setOpenGroup] = useState('geral');
  const [currentTime, setCurrentTime] = useState(new Date());
  const [helpOpen, setHelpOpen] = useState(false);
  const mainRef = useRef(null);
  // Evita roubar o foco na primeira renderização — só realoca a partir da 1ª navegação.
  const isFirstRenderRef = useRef(true);
  // `lg` do Tailwind = 1024px. Precisamos disso em JS (não só como classe) porque
  // `inert` é atributo do DOM e não pode ser condicionado por breakpoint no CSS.
  const [isDesktop, setIsDesktop] = useState(
    () => typeof window !== 'undefined' && window.matchMedia('(min-width: 1024px)').matches
  );
  const sidebarRef = useRef(null);
  const mobileTriggerRef = useRef(null);

  // Helper para casar a rota atual com o dicionário de ajuda usando Expressões Regulares
  const getHelpForPath = (path) => {
    for (const pattern in helpContent) {
      // Converte parâmetros como :id em expressão regular que aceita qualquer valor sem barra
      const escaped = pattern.replace(/([.+*?=^!:${}()[\]|/\\])/g, '\\$1');
      const regexStr = '^' + escaped.replace(/\\:[a-zA-Z0-9_]+/g, '[^/]+') + '$';
      const regex = new RegExp(regexStr);
      
      if (regex.test(path)) {
        return helpContent[pattern];
      }
    }
    return null;
  };

  // Fallback padrão se não encontrar ajuda cadastrada
  const fallbackHelp = {
    title: "Central de Ajuda FreeCash",
    overview: "Você está navegando pelo painel consolidado do FreeCash. Explore o menu lateral esquerdo para gerenciar suas contas, cartões de crédito e carteiras de investimento.",
    features: [
      "Acompanhe o painel de controle geral (Dashboard) para ver resumos de receitas e despesas.",
      "Cadastre ativos e gerencie sua carteira na seção de Investimentos.",
      "Importe planilhas, concilie compras de cartões de crédito e realize backups de seus dados."
    ],
    actions: {
      "Navegação": "Utilize o menu lateral esquerdo para alternar entre as telas do sistema.",
      "Tema Claro/Escuro": "Clique no ícone de sol/lua no cabeçalho superior para mudar as cores do painel.",
      "Ajuda Contextual": "Clique no botão (?) em qualquer tela para abrir este guia novamente."
    }
  };

  const currentHelp = getHelpForPath(location.pathname) || fallbackHelp;
  
  // Theme Management (Supports 'light', 'dark', 'auto')
  const [themeMode, setThemeMode] = useState(() => {
    const saved = localStorage.getItem('theme');
    if (saved === 'light' || saved === 'dark' || saved === 'auto') {
      return saved;
    }
    return 'auto';
  });

  // Calculate theme based on local machine time (06:00 to 17:59 -> light, 18:00 to 05:59 -> dark)
  const getAutoTheme = () => {
    const hours = new Date().getHours();
    return (hours >= 6 && hours < 18) ? 'light' : 'dark';
  };

  const activeTheme = themeMode === 'auto' ? getAutoTheme() : themeMode;

  useEffect(() => {
    localStorage.setItem('sidebar-collapsed', collapsed);
  }, [collapsed]);

  useEffect(() => {
    const root = window.document.documentElement;
    if (activeTheme === 'dark') {
      root.classList.add('dark');
    } else {
      root.classList.remove('dark');
    }
  }, [activeTheme]);

  // Periodic check for auto mode to handle hour changes in real-time
  useEffect(() => {
    if (themeMode !== 'auto') return;

    const interval = setInterval(() => {
      const currentResolved = getAutoTheme();
      const root = window.document.documentElement;
      if (currentResolved === 'dark') {
        root.classList.add('dark');
      } else {
        root.classList.remove('dark');
      }
    }, 60000);

    return () => clearInterval(interval);
  }, [themeMode]);

  // Real-time dynamic clock timer
  useEffect(() => {
    const timer = setInterval(() => {
      setCurrentTime(new Date());
    }, 1000);
    return () => clearInterval(timer);
  }, []);

  // Open appropriate group based on current route
  useEffect(() => {
    const path = location.pathname;
    if (path.includes('investimentos')) setOpenGroup('investimentos');
    else if (path.includes('contas') || path.includes('cartoes') || path.includes('receitas') || path.includes('transacoes') || path.includes('simulador')) setOpenGroup('financeiro');
    else if (path.includes('importar') || path.includes('compras-cartao') || path.includes('backup')) setOpenGroup('ferramentas');
    else if (path.includes('pagamentos')) setOpenGroup('ajustes');
    else setOpenGroup('geral');
  }, [location.pathname]);

  // Ao navegar (SPA): atualiza o título da aba e devolve o foco ao conteúdo principal,
  // para que usuários de teclado/leitor de tela percebam a mudança de página (WCAG 2.4.2 / 2.4.3).
  useEffect(() => {
    document.title = `${getRouteTitle(location.pathname)} · FreeCash`;

    if (isFirstRenderRef.current) {
      isFirstRenderRef.current = false;
      return;
    }
    mainRef.current?.focus();
  }, [location.pathname]);

  // Escape fecha a sidebar mobile, equivalente ao clique no backdrop.
  // Espelha `closeMobileSidebar` (declarada abaixo) em vez de chamá-la, para não
  // precisar dela nas dependências deste efeito — mantenha as duas em sincronia.
  useEffect(() => {
    if (!mobileOpen) return;
    const handleKey = (e) => {
      if (e.key !== 'Escape') return;
      setMobileOpen(false);
      mobileTriggerRef.current?.focus();
    };
    document.addEventListener('keydown', handleKey);
    return () => document.removeEventListener('keydown', handleKey);
  }, [mobileOpen]);

  // Acompanha o breakpoint para saber se a sidebar está fora da tela (mobile fechado)
  // ou fixa e visível (desktop).
  useEffect(() => {
    const mql = window.matchMedia('(min-width: 1024px)');
    const onChange = (e) => {
      setIsDesktop(e.matches);
      // Ao entrar em desktop, zera o estado do menu mobile. Sem isso ele ficaria
      // `true` de forma invisível e, ao voltar para mobile, o efeito de abertura
      // roubaria o foco para o botão de fechar durante um simples resize.
      if (e.matches) setMobileOpen(false);
    };
    mql.addEventListener('change', onChange);
    return () => mql.removeEventListener('change', onChange);
  }, []);

  // Ao ABRIR no mobile, leva o foco para dentro da sidebar.
  // O caminho de fechamento NÃO fica aqui de propósito: um efeito não distingue
  // "usuário fechou o menu" de "efeito re-executou" (troca de breakpoint) nem de
  // "fechou porque navegou". Devolver o foco é responsabilidade de quem fecha —
  // ver `closeMobileSidebar` abaixo. Antes, este efeito roubava o foco no resize
  // desktop→mobile e anulava o foco de troca de rota no mobile.
  useEffect(() => {
    if (isDesktop || !mobileOpen) return;
    sidebarRef.current?.querySelector('a, button')?.focus();
  }, [mobileOpen, isDesktop]);

  /**
   * Fecha a sidebar mobile por ação explícita do usuário (X, Escape ou backdrop)
   * e devolve o foco ao gatilho. Não usar ao fechar por navegação: nesse caso o
   * efeito de troca de rota é que posiciona o foco no conteúdo principal.
   */
  const closeMobileSidebar = () => {
    setMobileOpen(false);
    mobileTriggerRef.current?.focus();
  };

  /**
   * Fecha a sidebar ao clicar num item de navegação. Normalmente o foco é
   * posicionado pelo efeito de troca de rota — mas se o item clicado JÁ é a rota
   * atual, `location.pathname` não muda, aquele efeito não dispara e o foco
   * cairia no <body> quando a sidebar fica inert. Nesse caso posicionamos aqui.
   */
  const handleNavItemClick = (path) => {
    setMobileOpen(false);
    if (path === location.pathname) {
      mainRef.current?.focus();
    }
  };

  const cycleThemeMode = () => {
    const nextMode = themeMode === 'light' ? 'dark' : themeMode === 'dark' ? 'auto' : 'light';
    setThemeMode(nextMode);
    localStorage.setItem('theme', nextMode);
  };

  const handleLogout = async () => {
    await logout();
    navigate('/login');
  };

  const navGroups = [
    {
      id: 'geral',
      label: 'Geral',
      items: [
        { name: 'Dashboard', path: '/dashboard', icon: LayoutDashboard },
        { name: 'Relatórios', path: '/relatorios', icon: FileText },
      ]
    },
    {
      id: 'financeiro',
      label: 'Financeiro',
      items: [
        { name: 'Contas a Pagar', path: '/contas-pagar', icon: FileSpreadsheet },
        { name: 'Kanban', path: '/contas-kanban', icon: KanbanSquare },
        { name: 'Meus Cartões', path: '/cartoes', icon: CreditCard },
        { name: 'Receitas', path: '/receitas', icon: Coins },
        { name: 'Transações', path: '/transacoes', icon: List },
        { name: 'Simulador de Gastos', path: '/simulador', icon: Clock },
      ]
    },
    {
      id: 'investimentos',
      label: 'Investimentos',
      items: [
        { name: 'Dashboard', path: '/investimentos', icon: Activity },
        { name: 'Meus Ativos', path: '/investimentos/ativos', icon: Gem },
        { name: 'Balanceamento', path: '/investimentos/balanceamento', icon: Scale },
        { name: 'Histórico', path: '/investimentos/historico', icon: History },
        { name: 'Classes', path: '/investimentos/classes', icon: Layers },
      ]
    },
    {
      id: 'ferramentas',
      label: 'Ferramentas',
      items: [
        { name: 'Importar', path: '/importar', icon: UploadCloud },
        { name: 'Compras Cartão', path: '/compras-cartao', icon: CheckSquare },
        { name: 'Backup', path: '/backup', icon: DownloadCloud },
      ]
    },
    {
      id: 'ajustes',
      label: 'Ajustes',
      items: [
        { name: 'Pagamentos', path: '/pagamentos', icon: Settings },
      ]
    }
  ];

  const toggleGroup = (id) => {
    setOpenGroup(openGroup === id ? null : id);
  };

  const formattedDateTime = currentTime.toLocaleDateString('pt-BR', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
  }) + ' ' + currentTime.toLocaleTimeString('pt-BR', {
    hour: '2-digit',
    minute: '2-digit'
  });

  return (
    <div className="min-h-screen flex bg-background text-foreground transition-colors duration-300 font-sans">

      {/* Skip link: primeiro elemento focável da página, permite pular a navegação repetida (WCAG 2.4.1) */}
      <a
        href="#conteudo-principal"
        className="sr-only focus:not-sr-only focus:fixed focus:top-3 focus:left-3 focus:z-[60] focus:rounded-lg focus:bg-primary focus:px-4 focus:py-2 focus:text-sm focus:font-semibold focus:text-primary-foreground focus:shadow-lg focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2"
      >
        Pular para o conteúdo principal
      </a>

      {/* Mobile Sidebar Overlay (fechamento também disponível via Escape e botão X) */}
      {mobileOpen && (
        <div
          aria-hidden="true"
          className="fixed inset-0 z-40 bg-black/40 backdrop-blur-sm lg:hidden transition-opacity"
          onClick={closeMobileSidebar}
        />
      )}

      {/* Sidebar Component.
          `inert` quando está fora da tela (mobile fechado): sem isso o usuário de
          teclado tabulava por todos os links de um painel invisível (WCAG 2.4.3).
          Em desktop a sidebar é sempre visível, então nunca fica inert. */}
      <aside
        ref={sidebarRef}
        inert={!isDesktop && !mobileOpen}
        className={`fixed inset-y-0 left-0 z-50 flex flex-col bg-card/80 backdrop-blur-md border-r border-border/50 transition-all duration-300 ease-in-out
          ${collapsed ? 'w-20' : 'w-72'}
          ${mobileOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0'}
        `}
      >
        {/* Brand Logo / Title */}
        <div className="h-16 shrink-0 flex items-center justify-between px-6 border-b border-border/50">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-primary flex items-center justify-center shadow-lg shadow-primary/20">
              <Wallet className="h-5 w-5 text-primary-foreground" aria-hidden="true" />
            </div>
            {!collapsed && (
              <span className="font-bold text-xl tracking-tight text-primary">
                FreeCash
              </span>
            )}
          </div>
          <button
            onClick={closeMobileSidebar}
            className="lg:hidden p-1.5 rounded-lg text-muted-foreground hover:bg-muted/80"
            aria-label="Fechar menu"
          >
            <X className="h-5 w-5" aria-hidden="true" />
          </button>
        </div>

        {/* Navigation Items (Scrollable) */}
        <nav className="flex-1 overflow-y-auto px-3 py-4 space-y-4 custom-scrollbar" aria-label="Navegação principal">
          {navGroups.map((group) => {
            const isOpen = openGroup === group.id || collapsed;
            return (
              <div key={group.id} className="space-y-1">
                {!collapsed && (
                  <button
                    onClick={() => toggleGroup(group.id)}
                    aria-expanded={isOpen}
                    aria-controls={`nav-group-${group.id}`}
                    className="w-full flex items-center justify-between px-3 py-2 text-xs uppercase tracking-widest text-muted-foreground font-bold hover:text-foreground transition-colors"
                  >
                    <span>{group.label}</span>
                    <ChevronDown className={`h-3.5 w-3.5 transition-transform duration-300 ${isOpen ? 'rotate-0' : '-rotate-90'}`} aria-hidden="true" />
                  </button>
                )}

                {/* Items Container */}
                <div
                  id={`nav-group-${group.id}`}
                  inert={!isOpen}
                  className={`space-y-1 overflow-hidden transition-all duration-300 ease-in-out ${isOpen ? 'max-h-[500px] opacity-100' : 'max-h-0 opacity-0'}`}
                >
                  {group.items.map((item) => {
                    const Icon = item.icon;
                    const isActive = location.pathname === item.path || (item.path !== '/' && item.path !== '/dashboard' && item.path !== '/investimentos' && location.pathname.startsWith(item.path));
                    // Exact match for dashboard/investimentos to avoid matching subroutes
                    const isExactMatch = location.pathname === item.path;
                    const isHighlighted = (item.path === '/dashboard' || item.path === '/investimentos') ? isExactMatch : isActive;

                    return (
                      <Link
                        key={item.path}
                        to={item.path}
                        // Item ativo é sinalizado por peso da fonte + barra lateral além da cor,
                        // para não depender de cor isolada (WCAG 1.4.1), e por aria-current (4.1.2).
                        aria-current={isHighlighted ? 'page' : undefined}
                        className={`flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm transition-all duration-200 border-l-2
                          ${isHighlighted
                            ? 'bg-primary/10 text-primary dark:bg-primary/20 font-bold border-l-primary'
                            : 'text-muted-foreground hover:bg-muted/50 hover:text-foreground font-medium border-l-transparent'
                          }
                          ${collapsed ? 'justify-center' : ''}
                        `}
                        onClick={() => handleNavItemClick(item.path)}
                        title={collapsed ? item.name : undefined}
                        aria-label={collapsed ? item.name : undefined}
                      >
                        <Icon className={`h-[18px] w-[18px] shrink-0 ${isHighlighted ? 'text-primary' : 'text-muted-foreground'}`} aria-hidden="true" />
                        {!collapsed && <span>{item.name}</span>}
                      </Link>
                    );
                  })}
                </div>
              </div>
            );
          })}
        </nav>

        {/* Sidebar Footer (User Info & Logout) */}
        <div className="shrink-0 p-4 border-t border-border/50 space-y-3 bg-muted/20">
          {user && (
            <div className={`flex items-center gap-3 ${collapsed ? 'justify-center px-0 py-1' : 'px-2 py-1'}`}>
              <div 
                className="w-9 h-9 rounded-xl bg-primary/10 dark:bg-primary/20 border border-primary/20 flex items-center justify-center text-primary font-bold text-sm shadow-sm transition-all hover:scale-105 duration-200"
                title={collapsed ? (user.username || 'Usuário') : undefined}
              >
                {user.username ? user.username.charAt(0).toUpperCase() : <User className="h-4 w-4" aria-hidden="true" />}
              </div>
              {!collapsed && (
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-semibold truncate text-foreground" title={user.username || 'Usuário'}>
                    {user.username || 'Usuário'}
                  </p>
                </div>
              )}
            </div>
          )}

          <Button
            variant="ghost"
            onClick={handleLogout}
            className={`w-full flex items-center gap-3 hover:bg-red-500/10 hover:text-red-500 dark:hover:bg-red-500/20 ${collapsed ? 'justify-center px-0' : 'justify-start px-4'} py-2.5 rounded-xl text-muted-foreground`}
            title={collapsed ? 'Sair' : undefined}
            aria-label={collapsed ? 'Sair' : undefined}
          >
            <LogOut className="h-5 w-5 shrink-0 text-red-500" aria-hidden="true" />
            {!collapsed && <span className="font-semibold text-sm">Sair</span>}
          </Button>
        </div>
      </aside>

      {/* Main Workspace Shell */}
      <div
        className={`flex-1 flex flex-col min-h-screen min-w-0 transition-all duration-300
          ${collapsed ? 'lg:pl-20' : 'lg:pl-72'}
        `}
      >
        
        {/* Top Header */}
        <header className="h-16 flex items-center justify-between px-4 sm:px-6 lg:px-8 border-b border-border/50 bg-card/60 backdrop-blur-md sticky top-0 z-30">
          <div className="flex items-center gap-4">
            {/* Sidebar toggle for desktop */}
            <button
              onClick={() => setCollapsed(!collapsed)}
              className="hidden lg:flex p-2 rounded-lg text-muted-foreground hover:bg-muted/50"
              aria-label={collapsed ? 'Expandir menu lateral' : 'Recolher menu lateral'}
              aria-expanded={!collapsed}
            >
              <Menu className="h-5 w-5" aria-hidden="true" />
            </button>
            {/* Mobile menu trigger */}
            <button
              ref={mobileTriggerRef}
              onClick={() => setMobileOpen(true)}
              className="lg:hidden p-2 rounded-lg text-muted-foreground hover:bg-muted/50"
              aria-label="Abrir menu"
              aria-expanded={mobileOpen}
            >
              <Menu className="h-5 w-5" aria-hidden="true" />
            </button>

            <h2 className="text-sm font-semibold text-muted-foreground uppercase tracking-wider hidden sm:block">
              {location.pathname.includes('investimentos') ? 'Gerenciador de Ativos' : 'Visão Geral Financeira'}
            </h2>
          </div>

          <div className="flex items-center gap-3">
            {/* Help Button */}
            <Button
              variant="ghost"
              size="icon"
              onClick={() => setHelpOpen(true)}
              className="rounded-xl hover:bg-muted/50 text-muted-foreground h-9 w-9"
              title="Ajuda desta tela"
              aria-label="Ajuda desta tela"
            >
              <HelpCircle className="h-[1.1rem] w-[1.1rem]" aria-hidden="true" />
            </Button>

            {/* Theme Toggle */}
            <Button
              variant="ghost"
              size="icon"
              onClick={cycleThemeMode}
              className="rounded-xl hover:bg-muted/50 text-muted-foreground h-9 w-9 relative"
              title={
                themeMode === 'light'
                  ? 'Tema: Claro (clique para alternar)'
                  : themeMode === 'dark'
                  ? 'Tema: Escuro (clique para alternar)'
                  : `Tema: Automático (${activeTheme === 'dark' ? 'Modo Noturno' : 'Modo Diurno'} por horário)`
              }
              aria-label={
                themeMode === 'light'
                  ? 'Tema: Claro. Clique para alternar'
                  : themeMode === 'dark'
                  ? 'Tema: Escuro. Clique para alternar'
                  : `Tema: Automático, ${activeTheme === 'dark' ? 'modo noturno' : 'modo diurno'} por horário. Clique para alternar`
              }
            >
              {themeMode === 'light' && <Sun className="h-[1.1rem] w-[1.1rem]" aria-hidden="true" />}
              {themeMode === 'dark' && <Moon className="h-[1.1rem] w-[1.1rem]" aria-hidden="true" />}
              {themeMode === 'auto' && <SunMoon className="h-[1.1rem] w-[1.1rem] text-primary" aria-hidden="true" />}
            </Button>

            <div className="h-5 w-[1px] bg-border mx-1" aria-hidden="true" />

            {/* Real-time dynamic clock */}
            <div className="hidden md:flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-muted border border-border/50 text-xs font-semibold text-muted-foreground shadow-sm">
              <Clock className="w-3.5 h-3.5 text-primary shrink-0 animate-pulse" aria-hidden="true" />
              <span>{formattedDateTime}</span>
            </div>
          </div>
        </header>

        {/* Content Viewport — alvo do skip link e do foco realocado na troca de rota */}
        <main
          id="conteudo-principal"
          ref={mainRef}
          tabIndex={-1}
          className="flex-grow p-4 sm:p-6 lg:p-8 overflow-y-auto overflow-x-hidden min-w-0 focus:outline-none"
        >
          <div className="w-full space-y-8 min-w-0">
            <Outlet />
          </div>
        </main>

        {/* Minimal Footer */}
        <footer className="py-4 border-t border-border/30 text-center text-xs text-muted-foreground">
          &copy; {new Date().getFullYear()} FreeCash. Todos os direitos reservados.
        </footer>
      </div>

      {/* Help Modal — usa o Modal compartilhado (role="dialog", foco inicial, trap de Tab, Escape) */}
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
    </div>
  );
}
