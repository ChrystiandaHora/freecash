/**
 * Fonte única de verdade da navegação autenticada.
 *
 * Absorveu a tabela `routeTitles` que antes vivia duplicada no DashboardLayout:
 * as duas cobriam exatamente os mesmos 18 caminhos, e o matcher que o título da
 * aba precisa é o mesmo que o estado ativo precisa. Só 6 itens divergiam do
 * rótulo do menu, e esses carregam `docTitle`.
 *
 * O campo `icon` é mantido mesmo o mega-menu desktop sendo puramente
 * tipográfico: o acordeão mobile pode usá-lo, e removê-lo obrigaria a
 * re-derivar o mapa ícone↔rota depois.
 */
import {
  LayoutDashboard,
  FileText,
  FileSpreadsheet,
  KanbanSquare,
  CreditCard,
  Coins,
  List,
  Clock as ClockIcon,
  Target,
  Activity,
  Gem,
  Wallet,
  Scale,
  History,
  Layers,
  UploadCloud,
  Inbox,
  CheckSquare,
  DownloadCloud,
  Settings,
  Users,
  BarChart3,
  CalendarClock,
  TrendingUp,
  Rows3,
  Sparkles,
} from 'lucide-react';
import { buildNavIndex } from '../lib/navigation';

/**
 * Grupos de navegação com menus colapsáveis (disclosure).
 * Cada grupo é um item de topo da navbar (ou acordeão no mobile), e seus `items`
 * são os links do painel que ele abre.
 *
 * - `docTitle`: sobrescreve `name` no `document.title` (WCAG 2.4.2).
 * - `aliases`: caminhos extras que ativam o item.
 * - `exact`: escape hatch; por padrão é derivado em `buildNavIndex`.
 * - `adminOnly`: o grupo só é renderizado para quem tem `is_staff`.
 *
 * Os itens de cada grupo ficam em ordem alfabética (pt-BR, acento ignorado) — é a
 * ordem em que o painel os desenha, e `navigation.test.js` a trava. A ordem daqui
 * não influencia o casamento de rota: `buildNavIndex` reordena por especificidade.
 */
export const navGroups = [
  {
    id: 'financeiro',
    label: 'Financeiro',
    items: [
      { name: 'Calendário', path: '/calendario', icon: CalendarClock, docTitle: 'Calendário de Pagamentos' },
      // `exact: false` explícito: com a rota de lote no índice, a derivação
      // automática marcaria este item como exato e os formulários filhos
      // (`/novo`, `/editar/:id`) ficariam sem título e sem estado ativo.
      { name: 'Contas a Pagar', path: '/contas-pagar', icon: FileSpreadsheet, exact: false },
      { name: 'Dashboard', path: '/dashboard', icon: LayoutDashboard, aliases: ['/'] },
      { name: 'Eventos', path: '/eventos', icon: Sparkles, exact: false },
      { name: 'Horizonte de Saldos', path: '/horizonte-saldos', icon: TrendingUp },
      { name: 'Kanban', path: '/contas-kanban', icon: KanbanSquare, docTitle: 'Kanban de Contas' },
      { name: 'Lançamento em Lote', path: '/contas-pagar/lote', icon: Rows3 },
      { name: 'Metas', path: '/metas', icon: Target },
      { name: 'Meus Cartões', path: '/cartoes', icon: CreditCard },
      { name: 'Pagamentos', path: '/pagamentos', icon: Settings, docTitle: 'Formas de Pagamento' },
      { name: 'Receitas', path: '/receitas', icon: Coins },
      { name: 'Simulador de Gastos', path: '/simulador', icon: ClockIcon },
      { name: 'Transações', path: '/transacoes', icon: List },
    ],
  },
  {
    id: 'investimentos',
    label: 'Investimentos',
    items: [
      { name: 'Balanceamento', path: '/investimentos/balanceamento', icon: Scale },
      { name: 'Carteiras', path: '/investimentos/carteiras', icon: Wallet },
      { name: 'Classes', path: '/investimentos/classes', icon: Layers, docTitle: 'Classes de Ativos' },
      { name: 'Dashboard', path: '/investimentos', icon: Activity, docTitle: 'Investimentos' },
      { name: 'Histórico', path: '/investimentos/historico', icon: History, docTitle: 'Histórico de Ordens' },
      { name: 'Meus Ativos', path: '/investimentos/ativos', icon: Gem },
    ],
  },
  {
    id: 'ferramentas',
    label: 'Ferramentas',
    items: [
      { name: 'Backup', path: '/backup', icon: DownloadCloud },
      { name: 'Compras Cartão', path: '/compras-cartao', icon: CheckSquare, docTitle: 'Compras no Cartão' },
      { name: 'Conciliação', path: '/conciliacao', icon: Inbox, docTitle: 'Conciliação de Extratos' },
      { name: 'Importar', path: '/importar', icon: UploadCloud },
      { name: 'Relatórios', path: '/relatorios', icon: FileText },
    ],
  },
  {
    id: 'administracao',
    label: 'Administração',
    adminOnly: true,
    items: [
      { name: 'Contas de Usuário', path: '/admin/usuarios', icon: Users },
      { name: 'Métricas', path: '/admin/metricas', icon: BarChart3, docTitle: 'Métricas da Plataforma' },
    ],
  },
];

/** Índice pré-computado (singleton de módulo) consumido por `findActiveNav`. */
export const navIndex = buildNavIndex(navGroups);

/**
 * Filtra os grupos de navegação conforme o papel de quem está navegando.
 *
 * @param {boolean} isAdmin - Se quem navega tem papel administrativo.
 * @returns {Array} Grupos que devem ser renderizados.
 */
export function filtrarGruposVisiveis(isAdmin) {
  return isAdmin ? navGroups : navGroups.filter((grupo) => !grupo.adminOnly);
}
