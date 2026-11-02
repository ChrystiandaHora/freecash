/**
 * Telão de investimentos: a carteira em tela cheia, atualizada sozinha.
 *
 * Abre pelo botão "Telão" do painel de investimentos. A cada ciclo pede sincronização ao
 * servidor, que decide se vai à fonte de cotações (no máximo uma consulta a cada 15
 * minutos, só em dia e hora de pregão, recuando se a fonte limitar — ver
 * docs/cotacoes-e-preco-medio.md). Os dados anteriores ficam na tela enquanto os novos
 * chegam.
 *
 * Em telas a partir de `lg` o telão ocupa exatamente o viewport, sem rolagem: a
 * fonte-base acompanha a altura e a largura da tela, todos os tamanhos internos são em
 * `em`, e as listas mostram só o que cabe (ver hooks/useQuantosCabem.js). Abaixo disso
 * (celular) a página rola normalmente.
 *
 * O layout (components/telao/TelaoLayout.jsx) pausa o logout por inatividade enquanto a
 * tela está cheia.
 */
import { useNavigate } from 'react-router-dom';
import { AlertCircle, RefreshCw } from 'lucide-react';
import { useCarteira } from '../context/CarteiraProvider';
import { useTelao } from '../hooks/useTelao';
import { useTelaCheia } from '../hooks/useTelaCheia';
import { formatarAtualizacao } from '../lib/telao';
import { FaixaTopo } from '../components/telao/FaixaTopo';
import { KpisTelao } from '../components/telao/KpisTelao';
import { TabelaAtivosTelao } from '../components/telao/TabelaAtivosTelao';
import { DonutAlocacao } from '../components/telao/DonutAlocacao';
import { SinaisTelao } from '../components/telao/SinaisTelao';

// Fonte-base: fixa no celular; no desktop/TV segue o menor entre altura e largura
const ESCALA = 'text-[15px] lg:text-[length:clamp(12px,min(1.7vh,1.05vw),28px)]';

export default function Telao() {
  const navigate = useNavigate();
  const { carteiraId, carteiraSelecionada } = useCarteira();
  const { emTelaCheia, suportado, entrar, sair } = useTelaCheia();
  const { telao, dashboard, sinais, sincronizacao } = useTelao(carteiraId);

  const escopo = carteiraSelecionada ? `Carteira ${carteiraSelecionada.nome}` : 'Consolidado de todas as carteiras';
  const atualizadoEm = telao.data?.cotacoes_atualizadas_em ?? null;
  const momentoAtualizacao = formatarAtualizacao(atualizadoEm);
  const listaSinais = sinais.data?.sinais ?? [];
  // Com uma carteira só, o donut por carteira diria apenas "100%"
  const variasCarteiras = (dashboard.data?.alocacao_carteiras?.labels ?? []).length > 1;

  const sairDoTelao = async () => {
    await sair();
    navigate('/investimentos');
  };

  if (dashboard.isLoading || telao.isLoading) {
    return (
      <div role="status" className="flex min-h-dvh flex-col items-center justify-center gap-4">
        <RefreshCw className="h-10 w-10 text-primary motion-safe:animate-spin" aria-hidden="true" />
        <p className="text-lg font-semibold text-muted-foreground">Montando o telão…</p>
      </div>
    );
  }

  // Erro só derruba a tela se não houver nada para mostrar; com dados, a faixa avisa
  if (!dashboard.data || !telao.data) {
    return (
      <div role="alert" className="mx-auto flex min-h-dvh max-w-md flex-col items-center justify-center gap-4 text-center">
        <AlertCircle className="h-12 w-12 text-rose-600" aria-hidden="true" />
        <h1 className="text-2xl font-bold text-foreground">Não foi possível montar o telão</h1>
        <p className="text-muted-foreground">Os dados de investimentos não carregaram. Uma nova tentativa acontece no próximo ciclo.</p>
        <button type="button" onClick={sairDoTelao} className="min-h-11 rounded-xl px-4 font-semibold text-primary underline">
          Voltar ao painel de investimentos
        </button>
      </div>
    );
  }

  return (
    <div
      className={`flex min-h-dvh flex-col gap-[1em] p-[1em] lg:h-dvh lg:overflow-hidden lg:px-[1.75em] lg:py-[1.25em] ${ESCALA}`}
    >
      <FaixaTopo
        escopo={escopo}
        atualizadoEm={atualizadoEm}
        sincronizacao={sincronizacao}
        emTelaCheia={emTelaCheia}
        suportaTelaCheia={suportado}
        onEntrarTelaCheia={entrar}
        onSair={sairDoTelao}
      />

      {/* Só o momento é anunciado; a contagem e os números mudariam a cada ciclo */}
      <p className="sr-only" aria-live="polite">
        {momentoAtualizacao ? `Cotações atualizadas: ${momentoAtualizacao}.` : ''}
      </p>

      {!suportado && (
        <p className="shrink-0 rounded-xl border border-amber-500/40 bg-amber-500/10 px-[1em] py-[0.5em] text-[0.85em] text-foreground">
          Este navegador não oferece tela cheia. O telão continua se atualizando, mas a sessão
          expira após 15 minutos sem interação.
        </p>
      )}

      <KpisTelao dados={dashboard.data} />

      <div className="grid grid-cols-[minmax(0,1fr)] gap-[1em] lg:min-h-0 lg:flex-1 lg:grid-cols-[minmax(0,1.85fr)_minmax(0,1fr)]">
        <TabelaAtivosTelao ativos={telao.data.ativos} className="min-h-[20em] lg:min-h-0" />

        <div className="flex flex-col gap-[1em] lg:min-h-0">
          <DonutAlocacao
            id="telao-categorias"
            titulo="Por categoria"
            alocacao={dashboard.data.alocacao_categorias}
            className="lg:max-h-[16em] lg:flex-[0_1_auto]"
          />
          {variasCarteiras && (
            <DonutAlocacao
              id="telao-carteiras"
              titulo="Por carteira"
              alocacao={dashboard.data.alocacao_carteiras}
              className="lg:max-h-[13em] lg:flex-[0_1_auto]"
            />
          )}
          {listaSinais.length > 0 && <SinaisTelao sinais={listaSinais} className="lg:flex-1" />}
        </div>
      </div>
    </div>
  );
}
