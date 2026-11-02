/**
 * Mede quantos itens de uma lista cabem inteiros na altura do contêiner.
 *
 * Todos os itens continuam renderizados; quem chama esconde (`invisible`) os que passam
 * de `quantos`. Assim esconder não muda o layout e a medição não entra em laço. Os itens
 * medidos são os descendentes com `data-cabe`.
 *
 * Fora de um contêiner com altura limitada (telas pequenas, onde a página rola), tudo
 * cabe e `quantos` é o total.
 */
import { useEffect, useRef, useState } from 'react';
import { contarQueCabem } from '../lib/telao';

/**
 * @param {number} total - Quantidade de itens; remede quando muda.
 * @returns {[React.RefObject<HTMLElement>, number]} Ref do contêiner e quantos cabem.
 */
export function useQuantosCabem(total) {
  const containerRef = useRef(null);
  const [quantos, setQuantos] = useState(total);

  useEffect(() => {
    const container = containerRef.current;
    if (!container || typeof ResizeObserver === 'undefined') return undefined;

    // O ResizeObserver dispara uma vez ao começar a observar, o que faz a primeira medição
    const observer = new ResizeObserver(() => {
      const limite = container.getBoundingClientRect().bottom;
      const fundos = Array.from(container.querySelectorAll('[data-cabe]'), (item) => item.getBoundingClientRect().bottom);
      setQuantos(contarQueCabem(fundos, limite));
    });
    observer.observe(container);
    return () => observer.disconnect();
  }, [total]);

  return [containerRef, Math.min(quantos, total)];
}
