/**
 * Provider do tour guiado: diz se a rota atual tem tour, inicia-o a pedido (botão de
 * ajuda) e o abre sozinho na primeira visita a cada tela.
 *
 * A abertura automática espera a página ter o que mostrar — o primeiro alvo costuma
 * depender de dados ainda carregando — e não abre por cima de outro diálogo (ajuda,
 * aviso de inatividade). Se em `ESPERA_MAXIMA_MS` nenhum alvo aparecer, desiste sem
 * marcar a tela como vista, para tentar na próxima visita. Fica marcada no momento em
 * que abre: quem fecha no meio não quer vê-lo de novo sozinho, e o botão de ajuda
 * continua disponível.
 *
 * @param {{children: React.ReactNode}} props
 * @returns {JSX.Element} Os filhos, com o tour por cima quando ativo.
 */
import { useCallback, useEffect, useMemo, useState } from 'react';
import { useLocation } from 'react-router-dom';
import { tours } from '../../config/tour';
import { casarRota, marcarTourVisto, passosDisponiveis, tourJaVisto } from '../../lib/tour';
import { elementoDoAlvo } from './alvos';
import { TourGuiado } from './TourGuiado';
import { TourContexto } from './tourContexto';

const ATRASO_INICIAL_MS = 700;
const INTERVALO_MS = 250;
const ESPERA_MAXIMA_MS = 6000;

const alvoVisivel = (alvo) => Boolean(elementoDoAlvo(alvo));
const haDialogoAberto = () => Boolean(document.querySelector('[aria-modal="true"]'));

export function TourProvider({ children }) {
  const { pathname } = useLocation();
  const encontrado = useMemo(() => casarRota(tours, pathname), [pathname]);
  const [ativo, setAtivo] = useState(null);

  const iniciarTour = useCallback(() => {
    if (!encontrado) return;
    const passos = passosDisponiveis(encontrado.valor, alvoVisivel);
    if (passos.length > 0) setAtivo({ passos, pathname });
  }, [encontrado, pathname]);

  useEffect(() => {
    if (!encontrado || tourJaVisto(encontrado.padrao)) return undefined;

    const inicio = Date.now();
    let temporizador;
    const tentar = () => {
      const passos = passosDisponiveis(encontrado.valor, alvoVisivel);
      if (passos.some((p) => p.alvo) && !haDialogoAberto()) {
        marcarTourVisto(encontrado.padrao);
        setAtivo({ passos, pathname });
      } else if (Date.now() - inicio < ESPERA_MAXIMA_MS) {
        temporizador = setTimeout(tentar, INTERVALO_MS);
      }
    };
    temporizador = setTimeout(tentar, ATRASO_INICIAL_MS);
    return () => clearTimeout(temporizador);
  }, [encontrado, pathname]);

  const fechar = useCallback(() => setAtivo(null), []);
  const valor = useMemo(() => ({ tourDisponivel: Boolean(encontrado), iniciarTour }), [encontrado, iniciarTour]);

  return (
    <TourContexto.Provider value={valor}>
      {children}
      {/* O tour pertence à rota em que nasceu: trocar de tela o encerra */}
      {ativo?.pathname === pathname && <TourGuiado passos={ativo.passos} onFechar={fechar} />}
    </TourContexto.Provider>
  );
}
