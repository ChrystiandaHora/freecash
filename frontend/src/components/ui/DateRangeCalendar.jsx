/**
 * Calendário de seleção de intervalo, usado no filtro de data das tabelas.
 *
 * Substitui os dois campos `De` / `Até` soltos, que abriam o calendário nativo do
 * navegador um por vez: escolher um intervalo exigia dois pickers separados, sem
 * ver o período selecionado e sem atalho para pular de mês.
 *
 * Os campos nativos **continuam presentes**, abaixo da grade. Eles são o caminho
 * digitável e colável, funcionam com qualquer tecnologia assistiva sem depender
 * deste widget, e removê-los trocaria uma coisa que funciona por uma mais bonita.
 * A grade é uma camada visual acrescentada, não uma substituição.
 *
 * ## Padrão de acessibilidade
 *
 * Segue o padrão **grid** do WAI-ARIA para calendários: `role="grid"` com
 * `gridcell`, e **roving tabindex** — só o dia focado é tabulável, e as setas
 * movem entre os dias.
 *
 * Isso é uma escolha entre duas alternativas conformes, e vale registrar por quê:
 * a alternativa seria 31 botões todos tabuláveis, o que também passa nos critérios
 * mas custa 31 paradas de Tab para atravessar um mês. O roving aqui **não**
 * contradiz a decisão registrada em `A11Y-DECISIONS.md` que o proíbe na navegação
 * por disclosure: lá o widget nunca anunciou contrato de teclado, aqui `role="grid"`
 * anuncia exatamente esse contrato, e é o que a tecnologia assistiva espera. Mesmo
 * raciocínio das abas de `AtivoDetalhes`.
 *
 * Teclado: setas movem por dia, PageUp/PageDown por mês, Home/End para o começo e
 * o fim da semana, Enter/Espaço seleciona.
 *
 * @module components/ui/DateRangeCalendar
 */
import { useEffect, useMemo, useRef, useState } from 'react';
import { ChevronLeft, ChevronRight } from 'lucide-react';

import { cn } from '../../lib/utils';
import {
  ATALHOS_DE_PERIODO,
  DIAS_DA_SEMANA,
  NOMES_DOS_MESES,
  compararISO,
  deISO,
  deslocarMes,
  formatarData,
  montarGradeDoMes,
  paraISO,
} from '../../lib/datas';

/**
 * Decide qual mês abrir quando o calendário aparece.
 *
 * Prioriza o início do intervalo já filtrado — se o usuário volta ao filtro, ele
 * espera ver o período que escolheu, não o mês corrente.
 *
 * @param {{from?: string, to?: string}} valor - Intervalo atual do filtro.
 * @returns {{ano: number, mes: number}} Mês a exibir.
 */
function mesInicial(valor) {
  const referencia = deISO(valor?.from) || deISO(valor?.to) || new Date();
  return { ano: referencia.getFullYear(), mes: referencia.getMonth() + 1 };
}

export function DateRangeCalendar({ value, onChange, inputClass }) {
  const [{ ano, mes }, setMesVisivel] = useState(() => mesInicial(value));

  // Dia que carrega o `tabindex=0` da grade. Começa no início do intervalo, ou hoje.
  const [diaFocado, setDiaFocado] = useState(
    () => value?.from || paraISO(new Date())
  );

  const gradeRef = useRef(null);
  const precisaFocar = useRef(false);

  const semanas = useMemo(() => montarGradeDoMes(ano, mes), [ano, mes]);
  const hoje = useMemo(() => paraISO(new Date()), []);

  const from = value?.from || '';
  const to = value?.to || '';

  // Move o foco do DOM só quando a navegação partiu do teclado. Focar a cada
  // render roubaria o foco de quem está digitando nos campos abaixo da grade.
  useEffect(() => {
    if (!precisaFocar.current) return;
    precisaFocar.current = false;
    gradeRef.current
      ?.querySelector(`[data-dia="${diaFocado}"]`)
      ?.focus();
  }, [diaFocado, ano, mes]);

  /**
   * Aplica o clique num dia, montando ou reiniciando o intervalo.
   *
   * @param {string} iso - Dia clicado.
   */
  const selecionarDia = (iso) => {
    // Sem início, ou intervalo já fechado: o clique recomeça a seleção. É o que
    // permite ao terceiro clique iniciar um período novo sem precisar limpar antes.
    if (!from || (from && to)) {
      onChange({ from: iso, to: '' });
      return;
    }

    // Há início e falta o fim: fecha o intervalo, invertendo se o clique vier antes
    // do início — quem seleciona de trás para frente quer o mesmo período.
    if (compararISO(iso, from) < 0) {
      onChange({ from: iso, to: from });
    } else {
      onChange({ from, to: iso });
    }
  };

  /**
   * Navega a grade pelo teclado, no contrato que `role="grid"` anuncia.
   *
   * @param {React.KeyboardEvent} evento - Evento de tecla.
   */
  const aoTeclar = (evento) => {
    const atual = deISO(diaFocado);
    if (!atual) return;

    const deslocamentos = {
      ArrowRight: 1,
      ArrowLeft: -1,
      ArrowDown: 7,
      ArrowUp: -7,
    };

    // Sem valor inicial: todo caminho abaixo ou atribui um destino, ou retorna
    // antes de usá-lo.
    let destino;

    if (evento.key in deslocamentos) {
      destino = new Date(
        atual.getFullYear(), atual.getMonth(), atual.getDate() + deslocamentos[evento.key]
      );
    } else if (evento.key === 'PageUp' || evento.key === 'PageDown') {
      const passo = evento.key === 'PageDown' ? 1 : -1;
      destino = new Date(atual.getFullYear(), atual.getMonth() + passo, atual.getDate());
    } else if (evento.key === 'Home') {
      destino = new Date(
        atual.getFullYear(), atual.getMonth(), atual.getDate() - atual.getDay()
      );
    } else if (evento.key === 'End') {
      destino = new Date(
        atual.getFullYear(), atual.getMonth(), atual.getDate() + (6 - atual.getDay())
      );
    } else if (evento.key === 'Enter' || evento.key === ' ') {
      evento.preventDefault();
      selecionarDia(diaFocado);
      return;
    } else {
      return;
    }

    evento.preventDefault();
    precisaFocar.current = true;
    setDiaFocado(paraISO(destino));
    // Acompanha a virada de mês, senão o dia focado sairia da grade visível.
    setMesVisivel({ ano: destino.getFullYear(), mes: destino.getMonth() + 1 });
  };

  const irParaMes = (delta) => setMesVisivel(deslocarMes(ano, mes, delta));

  /**
   * Classifica um dia para o tratamento visual do intervalo.
   *
   * @param {string} iso - Dia a classificar.
   * @returns {{inicio: boolean, fim: boolean, dentro: boolean}} Posição no intervalo.
   */
  const posicaoNoIntervalo = (iso) => {
    const inicio = Boolean(from) && iso === from;
    const fim = Boolean(to) && iso === to;
    const dentro =
      Boolean(from) && Boolean(to) &&
      compararISO(iso, from) > 0 && compararISO(iso, to) < 0;
    return { inicio, fim, dentro };
  };

  const rotuloDoMes = `${NOMES_DOS_MESES[mes - 1]} de ${ano}`;

  return (
    <div className="flex flex-col gap-3">
      {/* Atalhos: resolvem o caso mais comum sem obrigar a clicar dois dias. */}
      <div role="group" aria-label="Períodos rápidos" className="flex flex-wrap gap-1">
        {ATALHOS_DE_PERIODO.map((atalho) => (
          <button
            key={atalho.id}
            type="button"
            onClick={() => {
              const intervalo = atalho.calcular();
              onChange(intervalo);
              setMesVisivel(mesInicial(intervalo));
            }}
            className="rounded-md border border-border px-2 py-1 text-[0.7rem] font-medium text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
          >
            {atalho.rotulo}
          </button>
        ))}
      </div>

      {/* Navegação de mês */}
      <div className="flex items-center justify-between gap-1">
        <button
          type="button"
          onClick={() => irParaMes(-1)}
          aria-label="Mês anterior"
          className="flex h-7 w-7 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
        >
          <ChevronLeft className="h-4 w-4" aria-hidden="true" />
        </button>

        {/* `aria-live` porque o mês muda sem que o rótulo do botão de seta mude:
            sem isto, quem usa leitor de tela navega às cegas entre os meses. */}
        <span
          aria-live="polite"
          className="flex-1 text-center text-xs font-semibold capitalize text-foreground"
        >
          {rotuloDoMes}
        </span>

        <button
          type="button"
          onClick={() => irParaMes(1)}
          aria-label="Próximo mês"
          className="flex h-7 w-7 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
        >
          <ChevronRight className="h-4 w-4" aria-hidden="true" />
        </button>
      </div>

      {/* Grade do mês */}
      <table
        ref={gradeRef}
        role="grid"
        aria-label={`Dias de ${rotuloDoMes}`}
        className="w-full border-collapse"
        onKeyDown={aoTeclar}
      >
        <thead>
          <tr>
            {DIAS_DA_SEMANA.map((dia, i) => (
              <th
                key={i}
                scope="col"
                className="pb-1 text-center text-[0.65rem] font-semibold uppercase text-muted-foreground"
              >
                <span aria-hidden="true">{dia.curto}</span>
                <span className="sr-only">{dia.longo}</span>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {semanas.map((semana, iSemana) => (
            <tr key={iSemana}>
              {semana.map((celula, iDia) => {
                if (!celula) {
                  return <td key={iDia} className="p-0.5" />;
                }

                const { inicio, fim, dentro } = posicaoNoIntervalo(celula.iso);
                const extremo = inicio || fim;
                const ehHoje = celula.iso === hoje;

                return (
                  <td key={iDia} className="p-0.5">
                    <button
                      type="button"
                      data-dia={celula.iso}
                      // Roving tabindex: só o dia focado entra na ordem de tabulação.
                      tabIndex={celula.iso === diaFocado ? 0 : -1}
                      aria-selected={extremo || dentro}
                      aria-current={ehHoje ? 'date' : undefined}
                      onClick={() => {
                        setDiaFocado(celula.iso);
                        selecionarDia(celula.iso);
                      }}
                      className={cn(
                        'flex h-7 w-full items-center justify-center rounded-md text-xs tabular-nums transition-colors',
                        'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/50',
                        extremo && 'bg-primary font-bold text-primary-foreground',
                        dentro && 'bg-primary/15 text-foreground',
                        !extremo && !dentro && 'text-foreground hover:bg-muted',
                        // Hoje ganha contorno, não cor de fundo: sem isso ele
                        // competiria com o destaque do intervalo (SC 1.4.1 —
                        // o estado não pode depender só de cor).
                        ehHoje && !extremo && 'ring-1 ring-inset ring-primary/60'
                      )}
                    >
                      {celula.dia}
                      <span className="sr-only">
                        {' '}{formatarData(celula.iso)}
                        {inicio && ', início do período'}
                        {fim && ', fim do período'}
                        {ehHoje && ', hoje'}
                      </span>
                    </button>
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>

      {/* Campos digitáveis: caminho alternativo, preservado de propósito. */}
      <div className="flex items-end gap-2 border-t border-border/60 pt-2">
        <label className="flex flex-1 flex-col gap-1 text-[0.7rem] font-medium text-muted-foreground">
          De
          <input
            type="date"
            className={inputClass}
            value={from}
            onChange={(e) => {
              onChange({ ...value, from: e.target.value });
              if (e.target.value) setMesVisivel(mesInicial({ from: e.target.value }));
            }}
          />
        </label>
        <label className="flex flex-1 flex-col gap-1 text-[0.7rem] font-medium text-muted-foreground">
          Até
          <input
            type="date"
            className={inputClass}
            value={to}
            onChange={(e) => onChange({ ...value, to: e.target.value })}
          />
        </label>
      </div>

      {/* Resumo do que está selecionado, em texto. O destaque na grade responde a
          quem olha; esta linha responde a quem ouve, e confirma o intervalo antes
          de fechar o popover. */}
      <p role="status" className="text-[0.7rem] text-muted-foreground">
        {from && to
          ? `Período: ${formatarData(from)} a ${formatarData(to)}`
          : from
            ? `Início em ${formatarData(from)} — escolha a data final`
            : 'Nenhum período selecionado'}
      </p>
    </div>
  );
}
