/**
 * Provedor da carteira em foco nas telas de investimento.
 *
 * A seleção vive num contexto, e não no estado de cada página, porque ela precisa
 * sobreviver à navegação entre as seis telas de `/investimentos` — dashboard, meus
 * ativos, detalhe, balanceamento, histórico e carteiras. Guardar em `useState`
 * local faria o filtro voltar para "todas" a cada clique no menu; propagar por
 * querystring exigiria tocar em todos os `<Link>` do módulo.
 *
 * O valor é persistido em `localStorage`, no mesmo padrão do ThemeProvider, para
 * atravessar o F5. É preferência de exibição de um dispositivo — nada que precise
 * ir para o servidor.
 *
 * `carteiraId` nulo significa **consolidado** (todas as carteiras), que é o estado
 * inicial e o comportamento que o sistema sempre teve. Quem precisa separar "o usuário
 * pediu o consolidado" de "ainda não escolheu" lê `consolidadoExplicito`: o
 * balanceamento abre numa carteira concreta, porque metas por ativo somam 100% dentro
 * de uma só, e não teria o que mostrar no consolidado (ver docs/carteiras.md).
 */
import { createContext, useCallback, useContext, useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';

import { fetchCarteiras } from '../services/investimentos';
import { useAuth } from './AuthProvider';

const CarteiraContext = createContext(null);

const CHAVE_STORAGE = 'freecash-carteira-selecionada';

// Gravado quando o usuário pede o consolidado de propósito. Sem esta sentinela,
// "escolheu todas as carteiras" e "ainda não escolheu nada" viram o mesmo `null`,
// e uma tela que precisa abrir numa carteira concreta não sabe qual dos dois é.
const VALOR_CONSOLIDADO = 'consolidado';

const lerSelecaoSalva = () => {
  try {
    const salvo = localStorage.getItem(CHAVE_STORAGE);
    if (!salvo) return null;
    if (salvo === VALOR_CONSOLIDADO) return VALOR_CONSOLIDADO;
    const id = Number(salvo);
    return Number.isFinite(id) && id > 0 ? id : null;
  } catch {
    return null;
  }
};

/**
 * @param {{children: React.ReactNode}} props
 */
export function CarteiraProvider({ children }) {
  const { user } = useAuth();
  const [carteiraSalva, setCarteiraIdState] = useState(lerSelecaoSalva);

  const { data: carteiras = [], isLoading } = useQuery({
    queryKey: ['carteiras'],
    queryFn: fetchCarteiras,
    enabled: !!user,
    staleTime: 5 * 60 * 1000,
  });

  // Seleção derivada: carteira arquivada volta ao consolidado sem gastar um render num efeito
  const carteiraId = useMemo(() => {
    if (carteiraSalva === VALOR_CONSOLIDADO) return null;
    if (carteiraSalva === null || isLoading) return carteiraSalva;
    return carteiras.some((c) => c.id === carteiraSalva && c.ativa) ? carteiraSalva : null;
  }, [carteiraSalva, carteiras, isLoading]);

  // Distingue-se de `carteiraId === null`, que também cobre "nunca escolheu" e
  // "a carteira salva foi arquivada" — casos em que abrir no consolidado é palpite
  const consolidadoExplicito = carteiraSalva === VALOR_CONSOLIDADO;

  const setCarteiraId = useCallback((proximo) => {
    const valor = proximo ? Number(proximo) : VALOR_CONSOLIDADO;
    setCarteiraIdState(valor);
    try {
      localStorage.setItem(CHAVE_STORAGE, String(valor));
    } catch {
      // Janela privada ou storage bloqueado: o filtro ainda funciona nesta sessão.
    }
  }, []);

  const carteirasAtivas = useMemo(() => carteiras.filter((c) => c.ativa), [carteiras]);

  const carteiraSelecionada = useMemo(
    () => carteiras.find((c) => c.id === carteiraId) ?? null,
    [carteiras, carteiraId]
  );

  const value = useMemo(
    () => ({
      carteiraId,
      setCarteiraId,
      carteiras,
      carteirasAtivas,
      carteiraSelecionada,
      consolidadoExplicito,
      carregandoCarteiras: isLoading,
    }),
    [
      carteiraId,
      setCarteiraId,
      carteiras,
      carteirasAtivas,
      carteiraSelecionada,
      consolidadoExplicito,
      isLoading,
    ]
  );

  return <CarteiraContext.Provider value={value}>{children}</CarteiraContext.Provider>;
}

/**
 * @returns {{carteiraId: number|null, setCarteiraId: Function, carteiras: Array,
 *   carteirasAtivas: Array, carteiraSelecionada: object|null,
 *   consolidadoExplicito: boolean, carregandoCarteiras: boolean}}
 */
export function useCarteira() {
  const ctx = useContext(CarteiraContext);
  if (!ctx) throw new Error('useCarteira deve ser usado dentro de <CarteiraProvider>');
  return ctx;
}
