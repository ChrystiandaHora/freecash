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
import { useState, useEffect } from 'react';
import { Outlet, Link, useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthProvider';
import {
  LayoutDashboard,
  LogOut,
  Menu, 
  X, 
  Sun, 
  Moon, 
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
import { helpContent } from '../config/helpContent';

export default function DashboardLayout() {
  const { logout, user } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();
  const [collapsed, setCollapsed] = useState(() => localStorage.getItem('sidebar-collapsed') === 'true');
  const [mobileOpen, setMobileOpen] = useState(false);
  const [openGroup, setOpenGroup] = useState('geral');
  const [currentTime, setCurrentTime] = useState(new Date());
  const [helpOpen, setHelpOpen] = useState(false);
  
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
  
  // Theme Management
  const [theme, setTheme] = useState(() => {
    const saved = localStorage.getItem('theme');
    if (saved) return saved;
    return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
  });
  
  useEffect(() => {
    localStorage.setItem('sidebar-collapsed', collapsed);
  }, [collapsed]);

  useEffect(() => {
    const root = window.document.documentElement;
    if (theme === 'dark') {
      root.classList.add('dark');
    } else {
      root.classList.remove('dark');
    }
  }, [theme]);

  // Listen to OS theme changes if the user hasn't set an explicit preference
  useEffect(() => {
    if (localStorage.getItem('theme')) return;
    const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)');
    const handleChange = (e) => {
      setTheme(e.matches ? 'dark' : 'light');
    };
    mediaQuery.addEventListener('change', handleChange);
    return () => mediaQuery.removeEventListener('change', handleChange);
  }, []);

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

  const toggleTheme = () => {
    const nextTheme = theme === 'dark' ? 'light' : 'dark';
    setTheme(nextTheme);
    localStorage.setItem('theme', nextTheme);
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
      
      {/* Mobile Sidebar Overlay */}
      {mobileOpen && (
        <div 
          className="fixed inset-0 z-40 bg-black/40 backdrop-blur-sm lg:hidden transition-opacity"
          onClick={() => setMobileOpen(false)}
        />
      )}

      {/* Sidebar Component */}
      <aside 
        className={`fixed inset-y-0 left-0 z-50 flex flex-col bg-card/80 backdrop-blur-md border-r border-border/50 transition-all duration-300 ease-in-out
          ${collapsed ? 'w-20' : 'w-72'} 
          ${mobileOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0'}
        `}
      >
        {/* Brand Logo / Title */}
        <div className="h-16 shrink-0 flex items-center justify-between px-6 border-b border-border/50">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-primary flex items-center justify-center shadow-lg shadow-primary/20">
              <Wallet className="h-5 w-5 text-primary-foreground" />
            </div>
            {!collapsed && (
              <span className="font-bold text-xl tracking-tight text-primary">
                FreeCash
              </span>
            )}
          </div>
          <button 
            onClick={() => setMobileOpen(false)} 
            className="lg:hidden p-1.5 rounded-lg text-muted-foreground hover:bg-muted/80"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Navigation Items (Scrollable) */}
        <nav className="flex-1 overflow-y-auto px-3 py-4 space-y-4 custom-scrollbar">
          {navGroups.map((group) => {
            const isOpen = openGroup === group.id || collapsed;
            return (
              <div key={group.id} className="space-y-1">
                {!collapsed && (
                  <button 
                    onClick={() => toggleGroup(group.id)}
                    className="w-full flex items-center justify-between px-3 py-2 text-[10px] uppercase tracking-widest text-muted-foreground font-bold hover:text-foreground transition-colors"
                  >
                    <span>{group.label}</span>
                    <ChevronDown className={`h-3.5 w-3.5 transition-transform duration-300 ${isOpen ? 'rotate-0' : '-rotate-90'}`} />
                  </button>
                )}
                
                {/* Items Container */}
                <div 
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
                        className={`flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-all duration-200
                          ${isHighlighted 
                            ? 'bg-primary/10 text-primary dark:bg-primary/20' 
                            : 'text-muted-foreground hover:bg-muted/50 hover:text-foreground'
                          }
                          ${collapsed ? 'justify-center' : ''}
                        `}
                        onClick={() => setMobileOpen(false)}
                        title={collapsed ? item.name : undefined}
                      >
                        <Icon className={`h-[18px] w-[18px] shrink-0 ${isHighlighted ? 'text-primary' : 'text-muted-foreground'}`} />
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
                {user.username ? user.username.charAt(0).toUpperCase() : <User className="h-4 w-4" />}
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
          >
            <LogOut className="h-5 w-5 shrink-0 text-red-500" />
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
            >
              <Menu className="h-5 w-5" />
            </button>
            {/* Mobile menu trigger */}
            <button
              onClick={() => setMobileOpen(true)}
              className="lg:hidden p-2 rounded-lg text-muted-foreground hover:bg-muted/50"
            >
              <Menu className="h-5 w-5" />
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
            >
              <HelpCircle className="h-[1.1rem] w-[1.1rem]" />
            </Button>

            {/* Theme Toggle */}
            <Button
              variant="ghost"
              size="icon"
              onClick={toggleTheme}
              className="rounded-xl hover:bg-muted/50 text-muted-foreground h-9 w-9"
            >
              {theme === 'dark' ? (
                <Sun className="h-[1.1rem] w-[1.1rem]" />
              ) : (
                <Moon className="h-[1.1rem] w-[1.1rem]" />
              )}
            </Button>

            <div className="h-5 w-[1px] bg-border mx-1" />

            {/* Real-time dynamic clock */}
            <div className="hidden md:flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-muted border border-border/50 text-xs font-semibold text-muted-foreground shadow-sm">
              <Clock className="w-3.5 h-3.5 text-primary shrink-0 animate-pulse" />
              <span>{formattedDateTime}</span>
            </div>
          </div>
        </header>

        {/* Content Viewport */}
        <main className="flex-grow p-4 sm:p-6 lg:p-8 overflow-y-auto overflow-x-hidden min-w-0">
          <div className="w-full space-y-8 min-w-0">
            <Outlet />
          </div>
        </main>

        {/* Minimal Footer */}
        <footer className="py-4 border-t border-border/30 text-center text-xs text-muted-foreground">
          &copy; {new Date().getFullYear()} FreeCash. Todos os direitos reservados.
        </footer>
      </div>

      {/* Help Modal */}
      {helpOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 animate-fade-in">
          {/* Backdrop Blur Overlay */}
          <div 
            className="absolute inset-0 bg-slate-900/40 dark:bg-black/60 backdrop-blur-sm transition-opacity"
            onClick={() => setHelpOpen(false)}
          />

          {/* Modal Content Card */}
          <div className="relative bg-card border border-border/60 shadow-2xl rounded-2xl max-w-2xl w-full max-h-[85vh] flex flex-col overflow-hidden animate-scale-up z-10 transition-all duration-300">
            {/* Header */}
            <div className="flex items-center justify-between p-5 border-b border-border/50 bg-muted/20 shrink-0">
              <div className="flex items-center gap-2.5">
                <div className="w-8 h-8 rounded-lg bg-primary/10 border border-primary/20 flex items-center justify-center text-primary">
                  <HelpCircle className="h-4 w-4" />
                </div>
                <h3 className="font-bold text-base text-foreground leading-tight">
                  Ajuda: {currentHelp.title}
                </h3>
              </div>
              <button 
                onClick={() => setHelpOpen(false)}
                className="p-1.5 rounded-lg text-muted-foreground hover:bg-muted/80 hover:text-foreground transition-colors"
                title="Fechar"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            {/* Body (Scrollable) */}
            <div className="flex-1 overflow-y-auto p-6 space-y-6 custom-scrollbar">
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
                  <div className="overflow-hidden rounded-xl border border-border/40 bg-muted/10">
                    <table className="w-full text-xs text-left border-collapse">
                      <thead>
                        <tr className="border-b border-border/40 text-muted-foreground font-semibold bg-muted/20">
                          <th className="py-2.5 px-4 font-bold uppercase tracking-wider">Elemento / Ação</th>
                          <th className="py-2.5 px-4 font-bold uppercase tracking-wider">O que faz</th>
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
            <div className="p-4 border-t border-border/50 bg-muted/10 flex justify-end shrink-0">
              <Button 
                onClick={() => setHelpOpen(false)}
                className="rounded-xl px-5 font-semibold text-xs py-2 shadow-sm"
              >
                Entendi
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
