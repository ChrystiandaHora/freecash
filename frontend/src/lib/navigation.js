/**
 * Matchers puros de navegação (sem dependências de DOM ou React).
 * Regra: prefixo mais longo vence, respeitando fronteiras de segmento.
 */

/**
 * Achata grupos e links diretos num índice ordenado por especificidade.
 * @param {Array<{id: string, label: string, items: Array<Object>}>} groups
 * @param {Array<Object>} [directLinks=[]]
 * @returns {Array<Object>} Índice ordenado para busca rápida.
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
      // Se houver sub-rotas filhas, casa exato por padrão para não sobrepor telas
      exact:
        entry.item.exact ??
        allPaths.some((p) => p !== entry.item.path && p.startsWith(entry.item.path + '/')),
    }))
    .sort((a, b) => b.item.path.length - a.item.path.length);
}

/**
 * Resolve o pathname para a entrada de navegação correspondente.
 * @param {string} pathname
 * @param {Array<Object>} index
 * @returns {Object | null}
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
 * Retorna o título legível da rota para o cabeçalho/document.title.
 * @param {string} pathname
 * @param {Array<Object>} index
 * @returns {string}
 */
export function getRouteTitle(pathname, index) {
  const hit = findActiveNav(pathname, index);
  return hit ? (hit.item.docTitle ?? hit.item.name) : 'FreeCash';
}

