/**
 * Faixa do topo do telão: escopo, relógio, frescor das cotações e controles.
 *
 * Tem o próprio tique de um segundo, para que a contagem regressiva não redesenhe a
 * tela inteira. A contagem fica fora de região viva: anunciá-la a cada segundo seria
 * ruído; quem anuncia a atualização é a página (ver pages/Telao.jsx).
 *
 * Os tamanhos são em `em`, relativos à fonte-base do telão, que acompanha o viewport.
 */
import { useEffect, useState } from 'react';
import { LogOut, Maximize, RefreshCw } from 'lucide-react';
import { Button } from '../ui/Button';
import { formatarAtualizacao, formatarContagem, rotuloStatus, STATUS_SINCRONIZACAO } from '../../lib/telao';

const RELOGIO = new Intl.DateTimeFormat('pt-BR', { hour: '2-digit', minute: '2-digit' });

const TOM_STATUS = {
  [STATUS_SINCRONIZACAO.ATUALIZADO]: 'bg-emerald-500',
  [STATUS_SINCRONIZACAO.EM_CACHE]: 'bg-emerald-500',
  [STATUS_SINCRONIZACAO.FORA_DO_PREGAO]: 'bg-slate-400',
  [STATUS_SINCRONIZACAO.LIMITADO]: 'bg-amber-500',
  [STATUS_SINCRONIZACAO.FALHOU]: 'bg-amber-500',
};

const BOTAO = 'h-auto min-h-[2.75em] gap-[0.5em] rounded-xl px-[0.9em] text-[0.85em]';

function useAgora(intervaloMs) {
  const [agora, setAgora] = useState(() => Date.now());
  useEffect(() => {
    const id = setInterval(() => setAgora(Date.now()), intervaloMs);
    return () => clearInterval(id);
  }, [intervaloMs]);
  return agora;
}

/**
 * @param {Object} props
 * @param {string} props.escopo - "Consolidado" ou o nome da carteira.
 * @param {string|null} props.atualizadoEm - ISO da última cotação gravada.
 * @param {{resultado?: Object, emAndamento: boolean, falhou: boolean, agendadoPara: number|null}} props.sincronizacao
 * @param {boolean} props.emTelaCheia
 * @param {boolean} props.suportaTelaCheia
 * @param {() => void} props.onEntrarTelaCheia
 * @param {() => void} props.onSair
 */
export function FaixaTopo({
  escopo,
  atualizadoEm,
  sincronizacao,
  emTelaCheia,
  suportaTelaCheia,
  onEntrarTelaCheia,
  onSair,
}) {
  const agora = useAgora(1000);
  const status = sincronizacao.resultado?.status;
  const motivo = sincronizacao.resultado?.motivo;
  const rotulo = rotuloStatus(status);
  const momentoAtualizacao = formatarAtualizacao(atualizadoEm, agora);

  let proxima = null;
  if (sincronizacao.emAndamento) proxima = 'Atualizando…';
  else if (sincronizacao.agendadoPara) proxima = `próxima em ${formatarContagem(sincronizacao.agendadoPara - agora)}`;

  return (
    <header className="flex shrink-0 flex-wrap items-center justify-between gap-x-[2em] gap-y-[0.75em] border-b border-border/60 pb-[0.75em]">
      <div className="min-w-0">
        <p className="text-[0.7em] font-bold uppercase tracking-[0.2em] text-muted-foreground">Telão de investimentos</p>
        <h1 className="truncate text-[1.75em] font-extrabold leading-tight tracking-tight text-foreground">{escopo}</h1>
      </div>

      <div className="flex flex-wrap items-center gap-x-[1.5em] gap-y-[0.5em]">
        {rotulo && (
          <span className="inline-flex items-center gap-[0.5em] font-semibold text-foreground">
            <span aria-hidden="true" className={`h-[0.6em] w-[0.6em] rounded-full ${TOM_STATUS[status]}`} />
            {rotulo}
            {motivo && <span className="font-normal text-muted-foreground">· {motivo}</span>}
          </span>
        )}

        <span className="inline-flex items-center gap-[0.5em] text-muted-foreground tabular-nums">
          <RefreshCw
            aria-hidden="true"
            className={`h-[1em] w-[1em] ${sincronizacao.emAndamento ? 'motion-safe:animate-spin' : ''}`}
          />
          {momentoAtualizacao ? `Cotações de ${momentoAtualizacao}` : 'Sem cotações gravadas'}
          {proxima && <span aria-hidden="true">·</span>}
          {proxima}
        </span>

        {sincronizacao.falhou && !sincronizacao.emAndamento && (
          <span className="font-semibold text-amber-700 dark:text-amber-400">
            A última tentativa falhou; os valores mostrados são os anteriores.
          </span>
        )}

        <time
          dateTime={new Date(agora).toISOString()}
          className="text-[2.6em] font-black leading-none tabular-nums tracking-tight text-foreground"
        >
          {RELOGIO.format(agora)}
        </time>

        <div className="flex items-center gap-[0.5em]">
          {suportaTelaCheia && !emTelaCheia && (
            <Button variant="outline" onClick={onEntrarTelaCheia} className={BOTAO}>
              <Maximize className="h-[1.1em] w-[1.1em]" aria-hidden="true" />
              Voltar à tela cheia
            </Button>
          )}
          <Button variant="ghost" onClick={onSair} className={BOTAO}>
            <LogOut className="h-[1.1em] w-[1.1em]" aria-hidden="true" />
            Sair do telão
          </Button>
        </div>
      </div>
    </header>
  );
}
