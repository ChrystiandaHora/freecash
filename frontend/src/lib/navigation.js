/**
 * Matchers puros de navegação.
 *
 * Módulo deliberadamente SEM imports: nada de React, react-router ou lucide.
 * É o que permite testar a resolução de rota → { grupo, item, título } sem DOM
 * e sem carregar 18 componentes de ícone.
 *
 * Regra única: **prefixo mais longo vence, com fronteira de segmento**.
 * Substitui a lista chumbada de casos especiais que vivia no DashboardLayout
 * (`path !== '/dashboard' && path !== '/investimentos'`).
 */

/**
 * Achata os grupos e links diretos num índice ordenado por especificidade (caminho mais longo primeiro).
 *
 * A ordenação é o que resolve ambiguidade de forma determinística: para
 * `/investimentos/ativos/42`, o prefixo `/investimentos/ativos` é considerado
 * antes de `/investimentos`.
 *
 * @param {Array<{id: string, label: string, items: Array<Object>}>} groups - Grupos de navegação.
 * @param {Array<Object>} [directLinks=[]] - Links diretos promovidos à barra.
 * @returns {Array<Object>} Índice achatado e ordenado, pronto para `findActiveNav`.
 */
export function buildNavIndex(groups, directLinks = []) {
  const directFlat = directLinks.map((item) => ({
    groupId: item.groupId ?? 'dashboard',
    groupLabel: item.groupLabel ?? item.name,
    item,
    paths: [item.path, ...(item.aliases ?? [])],
  }));

  const groupsFlat = groups.flatMap((group) =>
    group.items.map((item) => ({
      groupId: group.id,
      groupLabel: group.label,
      item,
      paths: [item.path, ...(item.aliases ?? [])],
    }))
  );

  const seenPaths = new Set();
  const flat = [];
  for (const entry of [...directFlat, ...groupsFlat]) {
    if (!seenPaths.has(entry.item.path)) {
      seenPaths.add(entry.item.path);
      flat.push(entry);
    }
  }

  const allPaths = flat.flatMap((entry) => entry.paths);

  return flat
    .map((entry) => ({
      ...entry,
      // `exact` é DERIVADO: um item casa exatamente quando outro item vive
      // abaixo dele. Ex.: `/investimentos` tem 4 filhos no menu, então casar por
      // prefixo faria o item "Dashboard" de investimentos acender em todas as
      // subtelas. Auto-mantido quando rotas novas entram na config; a flag
      // explícita `exact` na config fica como escape hatch.
      exact:
        entry.item.exact ??
        allPaths.some((p) => p !== entry.item.path && p.startsWith(entry.item.path + '/')),
    }))
    .sort((a, b) => b.item.path.length - a.item.path.length);
}

/**
 * Resolve o caminho atual para a entrada de navegação correspondente.
 *
 * A fronteira de segmento (`p + '/'`) é o que impede `/contas-pagar` de casar
 * `/contas-pagarolho` — bug que a versão anterior com `startsWith(item.path)` tinha.
 *
 * @param {string} pathname - `location.pathname` atual.
 * @param {Array<Object>} index - Índice devolvido por `buildNavIndex`.
 * @returns {Object | null} Entrada ativa, ou `null` se nenhuma casar.
 */
export function findActiveNav(pathname, index) {
  return (
    index.find((entry) =>
      entry.paths.some((p) =>
        entry.exact ? pathname === p : pathname === p || pathname.startsWith(p + '/')
      )
    ) ?? null
  );
}

/**
 * Título legível da rota, para `document.title` (WCAG 2.4.2).
 *
 * @param {string} pathname - `location.pathname` atual.
 * @param {Array<Object>} index - Índice devolvido por `buildNavIndex`.
 * @returns {string} Título da rota, ou 'FreeCash' se desconhecida.
 */
export function getRouteTitle(pathname, index) {
  const hit = findActiveNav(pathname, index);
  return hit ? (hit.item.docTitle ?? hit.item.name) : 'FreeCash';
}
