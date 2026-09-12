/**
 * Atrasa a propagação de um valor até ele parar de mudar.
 *
 * Existe para campos que alimentam `queryKey`: sem o atraso, cada tecla monta
 * uma chave nova, dispara uma requisição e — pior — deixa o React Query sem
 * dado em cache para aquela chave, o que acende o estado de carregamento
 * inicial e desmonta a tela debaixo de quem está digitando.
 */
import { useEffect, useState } from 'react';

/**
 * @param {*} valor - Valor que muda a cada tecla.
 * @param {number} [atrasoMs=400] - Silêncio necessário antes de propagar.
 * @returns {*} O último valor estável.
 */
export function useDebounce(valor, atrasoMs = 400) {
  const [estavel, setEstavel] = useState(valor);

  useEffect(() => {
    const id = setTimeout(() => setEstavel(valor), atrasoMs);
    return () => clearTimeout(id);
  }, [valor, atrasoMs]);

  return estavel;
}
