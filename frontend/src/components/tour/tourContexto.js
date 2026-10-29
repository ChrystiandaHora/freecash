/** Contexto do tour guiado, separado do provider para o fast refresh do Vite. */
import { createContext, useContext } from 'react';

export const TourContexto = createContext({ tourDisponivel: false, iniciarTour: () => {} });

/**
 * @returns {{tourDisponivel: boolean, iniciarTour: () => void}} Se a rota atual tem
 *   tour e a função que o inicia.
 */
export function useTour() {
  return useContext(TourContexto);
}
