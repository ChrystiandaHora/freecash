/**
 * Teste tabelado do matcher de navegação.
 *
 * Um caso por rota real declarada em `src/App.jsx`. É o seguro contra "perdi uma
 * tela": se um caminho deixar de resolver para o grupo/título certo, isto falha.
 *
 * Não precisa de jsdom nem de @testing-library — `lib/navigation.js` é puro.
 */
import { describe, expect, it } from 'vitest';
import { directNavLinks, filtrarGruposVisiveis, navGroups, navIndex } from '../config/navigation';
import { findActiveNav, getRouteTitle } from './navigation';
import { helpContent } from '../config/helpContent';

/** [rota, grupo esperado, caminho de menu esperado, título esperado] */
const ROUTES = [
  // Itens que existem no menu ou como link direto.
  ['/', 'dashboard', '/dashboard', 'Dashboard'],
  ['/dashboard', 'dashboard', '/dashboard', 'Dashboard'],
  ['/relatorios', 'ferramentas', '/relatorios', 'Relatórios'],
  ['/contas-pagar', 'financeiro', '/contas-pagar', 'Contas a Pagar'],
  ['/contas-kanban', 'financeiro', '/contas-kanban', 'Kanban de Contas'],
  ['/cartoes', 'financeiro', '/cartoes', 'Meus Cartões'],
  ['/receitas', 'financeiro', '/receitas', 'Receitas'],
  ['/transacoes', 'financeiro', '/transacoes', 'Transações'],
  ['/simulador', 'financeiro', '/simulador', 'Simulador de Gastos'],
  ['/metas', 'financeiro', '/metas', 'Metas'],
  ['/investimentos', 'investimentos', '/investimentos', 'Investimentos'],
  ['/investimentos/ativos', 'investimentos', '/investimentos/ativos', 'Meus Ativos'],
  ['/investimentos/balanceamento', 'investimentos', '/investimentos/balanceamento', 'Balanceamento'],
  ['/investimentos/historico', 'investimentos', '/investimentos/historico', 'Histórico de Ordens'],
  ['/investimentos/classes', 'investimentos', '/investimentos/classes', 'Classes de Ativos'],
  ['/importar', 'ferramentas', '/importar', 'Importar'],
  ['/compras-cartao', 'ferramentas', '/compras-cartao', 'Compras no Cartão'],
  ['/backup', 'ferramentas', '/backup', 'Backup'],
  ['/pagamentos', 'financeiro', '/pagamentos', 'Formas de Pagamento'],

  // Sub-rotas de formulário que NÃO estão no menu: devem acender o item pai.
  ['/contas-pagar/lote', 'financeiro', '/contas-pagar', 'Contas a Pagar'],
  ['/contas-pagar/novo', 'financeiro', '/contas-pagar', 'Contas a Pagar'],
  ['/contas-pagar/editar/42', 'financeiro', '/contas-pagar', 'Contas a Pagar'],
  ['/receitas/novo', 'financeiro', '/receitas', 'Receitas'],
  ['/receitas/editar/42', 'financeiro', '/receitas', 'Receitas'],
  ['/compras-cartao/novo', 'ferramentas', '/compras-cartao', 'Compras no Cartão'],
  ['/compras-cartao/editar/42', 'ferramentas', '/compras-cartao', 'Compras no Cartão'],
  ['/pagamentos/novo', 'financeiro', '/pagamentos', 'Formas de Pagamento'],
  ['/pagamentos/editar/42', 'financeiro', '/pagamentos', 'Formas de Pagamento'],
  ['/investimentos/ativos/42', 'investimentos', '/investimentos/ativos', 'Meus Ativos'],
  ['/investimentos/ativos/novo', 'investimentos', '/investimentos/ativos', 'Meus Ativos'],
  ['/investimentos/ativos/editar/42', 'investimentos', '/investimentos/ativos', 'Meus Ativos'],
  ['/investimentos/classes/formulario', 'investimentos', '/investimentos/classes', 'Classes de Ativos'],
  ['/investimentos/historico/novo', 'investimentos', '/investimentos/historico', 'Histórico de Ordens'],
  ['/investimentos/historico/editar/42', 'investimentos', '/investimentos/historico', 'Histórico de Ordens'],
];

describe('findActiveNav', () => {
  it.each(ROUTES)('%s → grupo %s, item %s', (pathname, groupId, activePath) => {
    const hit = findActiveNav(pathname, navIndex);
    expect(hit, `nenhum item de menu casou ${pathname}`).not.toBeNull();
    expect(hit.groupId).toBe(groupId);
    expect(hit.item.path).toBe(activePath);
  });

  it('não casa caminho que só compartilha prefixo textual (fronteira de segmento)', () => {
    // O matcher antigo, com startsWith(item.path) sem barra, casava estes.
    expect(findActiveNav('/contas-pagarolho', navIndex)).toBeNull();
    expect(findActiveNav('/metasx', navIndex)).toBeNull();
    expect(findActiveNav('/investimentos/ativos-antigos', navIndex)?.item.path).not.toBe(
      '/investimentos/ativos'
    );
  });

  it('/investimentos é exato: não rouba o realce das suas subtelas', () => {
    const entry = navIndex.find((e) => e.item.path === '/investimentos');
    expect(entry.exact).toBe(true);
    expect(findActiveNav('/investimentos/ativos', navIndex).item.path).toBe('/investimentos/ativos');
  });

  it('rota desconhecida não casa nada', () => {
    expect(findActiveNav('/rota-inexistente', navIndex)).toBeNull();
  });
});

describe('getRouteTitle', () => {
  it.each(ROUTES)('%s → "%s"', (pathname, _groupId, _activePath, title) => {
    expect(getRouteTitle(pathname, navIndex)).toBe(title);
  });

  it('cai em FreeCash quando a rota é desconhecida', () => {
    expect(getRouteTitle('/rota-inexistente', navIndex)).toBe('FreeCash');
  });
});

describe('integridade da config', () => {
  const items = navGroups.flatMap((g) => g.items);

  it('tem os 4 grupos e os 22 itens esperados em navGroups, mais 3 directNavLinks', () => {
    // O quarto grupo é Administração, marcado com `adminOnly`.
    // 22 itens desde que Investimentos ganhou "Carteiras" — o grupo foi a 6 itens,
    // dentro do teto de 7 por painel registrado no A11Y-DECISIONS.
    expect(navGroups).toHaveLength(4);
    expect(items).toHaveLength(22);
    expect(directNavLinks).toHaveLength(3);
  });

  it('esconde o grupo administrativo de quem não é administrador', () => {
    expect(filtrarGruposVisiveis(true)).toHaveLength(4);

    const semAdmin = filtrarGruposVisiveis(false);
    expect(semAdmin).toHaveLength(3);
    expect(semAdmin.some((g) => g.adminOnly)).toBe(false);
  });

  it('não repete caminhos dentro de navGroups', () => {
    const paths = items.map((i) => i.path);
    expect(new Set(paths).size).toBe(paths.length);
  });

  it('todo item tem entrada de ajuda contextual em helpContent', () => {
    const allItems = [...items, ...directNavLinks];
    const missing = allItems.filter((i) => !(i.path in helpContent)).map((i) => i.path);
    expect(missing).toEqual([]);
  });
});
