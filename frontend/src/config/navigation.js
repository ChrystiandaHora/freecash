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
  Scale,
  History,
  Layers,
  UploadCloud,
  CheckSquare,
  DownloadCloud,
  Settings,
  Users,
  BarChart3,
  CalendarClock,
  TrendingUp,
} from 'lucide-react';
import { buildNavIndex } from '../lib/navigation';

/**
 * Grupos de navegação. Cada grupo é um item de topo da navbar, e seus `items`
 * são os links do painel que ele abre.
 *
 * - `docTitle`: sobrescreve `name` no `document.title` (WCAG 2.4.2).
 * - `aliases`: caminhos extras que ativam o item (ex.: `/` → Dashboard).
 * - `exact`: escape hatch; por padrão é derivado em `buildNavIndex`.
 * - `adminOnly`: o grupo só é renderizado para quem tem `is_staff`. Ele permanece
 *   na tabela mesmo para os demais usuários porque `navIndex` também resolve o
 *   `document.title` e o estado ativo; retirá-lo daqui deixaria essas rotas sem
 *   título para o próprio administrador. Filtrar é responsabilidade de quem
 *   renderiza — ver `filtrarGruposVisiveis`.
 */
export const navGroups = [
  {
    id: 'geral',
    label: 'Geral',
    items: [
      { name: 'Dashboard', path: '/dashboard', icon: LayoutDashboard, aliases: ['/'] },
      { name: 'Relatórios', path: '/relatorios', icon: FileText },
    ],
  },
  {
    id: 'financeiro',
    label: 'Financeiro',
    items: [
      { name: 'Contas a Pagar', path: '/contas-pagar', icon: FileSpreadsheet },
      { name: 'Kanban', path: '/contas-kanban', icon: KanbanSquare, docTitle: 'Kanban de Contas' },
      { name: 'Meus Cartões', path: '/cartoes', icon: CreditCard },
      { name: 'Receitas', path: '/receitas', icon: Coins },
      { name: 'Transações', path: '/transacoes', icon: List },
      { name: 'Simulador de Gastos', path: '/simulador', icon: ClockIcon },
      { name: 'Metas', path: '/metas', icon: Target },
      { name: 'Horizonte de Saldos', path: '/horizonte-saldos', icon: TrendingUp },
      { name: 'Calendário', path: '/calendario', icon: CalendarClock, docTitle: 'Calendário de Pagamentos' },
    ],
  },
  {
    id: 'investimentos',
    label: 'Investimentos',
    items: [
      { name: 'Dashboard', path: '/investimentos', icon: Activity, docTitle: 'Investimentos' },
      { name: 'Meus Ativos', path: '/investimentos/ativos', icon: Gem },
      { name: 'Balanceamento', path: '/investimentos/balanceamento', icon: Scale },
      { name: 'Histórico', path: '/investimentos/historico', icon: History, docTitle: 'Histórico de Ordens' },
      { name: 'Classes', path: '/investimentos/classes', icon: Layers, docTitle: 'Classes de Ativos' },
    ],
  },
  {
    id: 'ferramentas',
    label: 'Ferramentas',
    items: [
      { name: 'Importar', path: '/importar', icon: UploadCloud },
      { name: 'Compras Cartão', path: '/compras-cartao', icon: CheckSquare, docTitle: 'Compras no Cartão' },
      { name: 'Backup', path: '/backup', icon: DownloadCloud },
    ],
  },
  {
    id: 'ajustes',
    label: 'Ajustes',
    items: [
      { name: 'Pagamentos', path: '/pagamentos', icon: Settings, docTitle: 'Formas de Pagamento' },
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
 * Esconder o grupo é conveniência de interface, não controle de acesso: as rotas
 * são guardadas por `AdminRoute` no cliente e pela permission class
 * `IsAdminPlataforma` no servidor.
 *
 * @param {boolean} isAdmin - Se quem navega tem papel administrativo.
 * @returns {Array} Grupos que devem ser renderizados.
 */
export function filtrarGruposVisiveis(isAdmin) {
  return isAdmin ? navGroups : navGroups.filter((grupo) => !grupo.adminOnly);
}
