/**
 * O tour em si: escurece a tela, recorta o elemento do passo e abre um balão ao lado.
 *
 * Acessibilidade: o balão é um diálogo modal (`aria-modal`), recebe o foco a cada passo
 * para o leitor de tela anunciar título e texto, prende o Tab nos seus botões, fecha
 * com Escape e navega com ← e →. Ao fechar, o foco volta a quem abriu o tour. Com
 * movimento reduzido, a rolagem até o alvo é instantânea e o destaque não anima.
 *
 * Camada `z-[45]`: acima do header (`z-40`), que também escurece, e abaixo dos modais
 * (`z-50`) — o aviso de inatividade precisa continuar aparecendo por cima de um tour.
 * Renderizado por portal pelo mesmo motivo do `ui/Modal` (ver A11Y-DECISIONS.md).
 *
 * No mobile o balão fica preso embaixo da tela e o alvo rola para o topo: não há
 * largura para pô-lo ao lado de nada.
 *
 * @param {object} props
 * @param {Array<{alvo?: string, titulo: string, texto: string}>} props.passos Passos já filtrados.
 * @param {() => void} props.onFechar Encerra o tour.
 * @returns {JSX.Element} Camada do tour, por portal no `document.body`.
 */
import { useCallback, useEffect, useId, useLayoutEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { Button } from '../ui/Button';
import { useMediaQuery } from '../../hooks/useMediaQuery';
import { posicionarBalao } from '../../lib/tour';
import { elementoDoAlvo } from './alvos';

const MOBILE_QUERY = '(max-width: 639px)';
const MOVIMENTO_REDUZIDO_QUERY = '(prefers-reduced-motion: reduce)';
// 64px do header fixo (`--header-h`) + folga
const TOPO_LIVRE = 76;
const FOLGA_DO_RECORTE = 6;
const BOTOES = 'button:not([disabled])';

function medir(elemento) {
  if (!elemento) return null;
  const r = elemento.getBoundingClientRect();
  return {
    top: r.top - FOLGA_DO_RECORTE,
    left: r.left - FOLGA_DO_RECORTE,
    width: r.width + FOLGA_DO_RECORTE * 2,
    height: r.height + FOLGA_DO_RECORTE * 2,
    bottom: r.bottom + FOLGA_DO_RECORTE,
    right: r.right + FOLGA_DO_RECORTE,
  };
}

export function TourGuiado({ passos, onFechar }) {
  const [indice, setIndice] = useState(0);
  const [recorte, setRecorte] = useState(null);
  const [posicao, setPosicao] = useState(null);
  const balaoRef = useRef(null);
  const quemAbriuRef = useRef(document.activeElement);
  const idTitulo = useId();
  const idTexto = useId();
  const mascaraId = useId();
  const mobile = useMediaQuery(MOBILE_QUERY);
  const movimentoReduzido = useMediaQuery(MOVIMENTO_REDUZIDO_QUERY);

  const passo = passos[indice];
  const ultimo = indice === passos.length - 1;

  const avancar = useCallback(() => {
    if (ultimo) onFechar();
    else setIndice((i) => i + 1);
  }, [ultimo, onFechar]);
  const voltar = useCallback(() => setIndice((i) => Math.max(i - 1, 0)), []);

  // Leva o alvo para a tela e acompanha rolagem e redimensionamento
  useEffect(() => {
    const elemento = elementoDoAlvo(passo.alvo);
    if (passo.alvo && !elemento) {
      // O alvo sumiu desde o início do tour (dados recarregados): segue adiante
      const pular = setTimeout(avancar, 0);
      return () => clearTimeout(pular);
    }
    elemento?.scrollIntoView({
      block: mobile ? 'start' : 'center',
      behavior: movimentoReduzido ? 'auto' : 'smooth',
    });
    const atualizar = () => setRecorte(medir(elementoDoAlvo(passo.alvo)));
    atualizar();
    window.addEventListener('scroll', atualizar, { passive: true });
    window.addEventListener('resize', atualizar);
    return () => {
      window.removeEventListener('scroll', atualizar);
      window.removeEventListener('resize', atualizar);
    };
    // `avancar` muda a cada passo; o efeito só deve rodar quando o passo muda
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [passo, mobile, movimentoReduzido]);

  // Posição do balão depende do tamanho que ele acabou de ter na tela
  useLayoutEffect(() => {
    if (mobile || !balaoRef.current) {
      setPosicao(null);
      return;
    }
    const { offsetWidth, offsetHeight } = balaoRef.current;
    setPosicao(
      posicionarBalao({
        alvo: recorte,
        balao: { largura: offsetWidth, altura: offsetHeight },
        janela: { largura: window.innerWidth, altura: window.innerHeight },
        topoLivre: TOPO_LIVRE,
        margem: 16,
        espaco: 12,
      }),
    );
  }, [recorte, mobile, indice]);

  // Foco no balão a cada passo, para o leitor de tela anunciar o novo conteúdo
  useEffect(() => {
    balaoRef.current?.focus({ preventScroll: true });
  }, [indice]);

  // Devolve o foco a quem abriu o tour
  useEffect(() => {
    const quemAbriu = quemAbriuRef.current;
    return () => {
      if (quemAbriu?.isConnected) quemAbriu.focus({ preventScroll: true });
      else document.getElementById('conteudo-principal')?.focus({ preventScroll: true });
    };
  }, []);

  useEffect(() => {
    const aoTeclar = (e) => {
      if (e.key === 'Escape') {
        e.preventDefault();
        onFechar();
      } else if (e.key === 'ArrowRight') {
        e.preventDefault();
        avancar();
      } else if (e.key === 'ArrowLeft') {
        e.preventDefault();
        voltar();
      } else if (e.key === 'Tab') {
        const botoes = Array.from(balaoRef.current?.querySelectorAll(BOTOES) ?? []);
        if (botoes.length === 0) return;
        const primeiro = botoes[0];
        const derradeiro = botoes[botoes.length - 1];
        const ativo = document.activeElement;
        const dentro = balaoRef.current?.contains(ativo);
        if (!dentro || (e.shiftKey && ativo === primeiro) || (!e.shiftKey && ativo === derradeiro)) {
          e.preventDefault();
          (e.shiftKey ? derradeiro : primeiro).focus();
        } else if (e.shiftKey && ativo === balaoRef.current) {
          e.preventDefault();
          derradeiro.focus();
        }
      }
    };
    document.addEventListener('keydown', aoTeclar);
    return () => document.removeEventListener('keydown', aoTeclar);
  }, [avancar, voltar, onFechar]);

  const transicao = movimentoReduzido ? '' : 'transition-all duration-300 ease-out';
  const estiloDoBalao = mobile
    ? undefined
    : posicao
      ? { top: posicao.top, left: posicao.left }
      : { top: '50%', left: '50%', transform: 'translate(-50%, -50%)' };

  return createPortal(
    <div className="fixed inset-0 z-[45]">
      {/* Escurecimento com recorte do alvo; só visual, e bloqueia cliques na página */}
      <svg className="absolute inset-0 h-full w-full" aria-hidden="true">
        <defs>
          <mask id={mascaraId}>
            <rect width="100%" height="100%" fill="white" />
            {recorte && (
              <rect
                x={recorte.left}
                y={recorte.top}
                width={recorte.width}
                height={recorte.height}
                rx="12"
                fill="black"
              />
            )}
          </mask>
        </defs>
        <rect width="100%" height="100%" fill="rgba(0,0,0,0.55)" mask={`url(#${mascaraId})`} />
      </svg>

      {recorte && (
        <div
          aria-hidden="true"
          // Sem transição: a posição acompanha a rolagem quadro a quadro, junto com o recorte
          className="pointer-events-none absolute rounded-xl ring-2 ring-primary"
          style={{ top: recorte.top, left: recorte.left, width: recorte.width, height: recorte.height }}
        />
      )}

      <div
        ref={balaoRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={idTitulo}
        aria-describedby={idTexto}
        tabIndex={-1}
        style={estiloDoBalao}
        className={`absolute rounded-2xl border border-border bg-card p-5 text-card-foreground shadow-2xl focus:outline-none ${
          mobile ? 'inset-x-4 bottom-4' : 'w-[22rem]'
        }`}
      >
        <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
          Passo {indice + 1} de {passos.length}
        </p>
        <h2 id={idTitulo} className="mt-1 text-base font-bold tracking-tight text-foreground">
          {passo.titulo}
        </h2>
        <p id={idTexto} className="mt-2 text-sm leading-relaxed text-muted-foreground">
          {passo.texto}
        </p>

        <div className="mt-4 flex gap-1" aria-hidden="true">
          {passos.map((p, i) => (
            <span
              key={`${p.titulo}-${i}`}
              className={`h-1.5 rounded-full ${transicao} ${i === indice ? 'w-5 bg-primary' : 'w-1.5 bg-border'}`}
            />
          ))}
        </div>

        <div className="mt-4 flex items-center justify-between gap-2">
          {ultimo ? (
            <span />
          ) : (
            <Button variant="ghost" onClick={onFechar} className="px-3 text-muted-foreground">
              Pular tour
            </Button>
          )}
          <div className="flex gap-2">
            {indice > 0 && (
              <Button variant="outline" onClick={voltar}>
                Anterior
              </Button>
            )}
            <Button onClick={avancar}>{ultimo ? 'Concluir' : 'Próximo'}</Button>
          </div>
        </div>
      </div>
    </div>,
    document.body,
  );
}
