/**
 * Tours guiados por rota — o "Fazer o tour desta tela" do botão de ajuda.
 *
 * Contrato de cada tour: `'/rota/:param': [passo, ...]`, com o padrão igual ao do
 * `helpContent.js`. Cada passo é `{ titulo, texto, alvo? }`:
 * - `alvo` é o valor de um `data-tour="..."` na página. Sem alvo, o balão aparece no
 *   centro — use assim só no primeiro passo, para apresentar a tela.
 * - O passo cujo alvo não está na tela (lista vazia, seção que só aparece com dados)
 *   é pulado em silêncio. Por isso o tour não pode depender de um passo para fazer
 *   sentido no seguinte.
 * - Rápido e claro: de 4 a 7 passos, título curto, texto de uma ou duas frases que diz
 *   para que serve o elemento — não descreve o que já está escrito nele.
 *
 * Os grupos ficam em arquivos separados por área da navegação. Rotas fixas vêm antes
 * das paramétricas na ordenação abaixo, senão `/investimentos/ativos/:id` engoliria
 * `/investimentos/ativos/novo`.
 */
import { toursDeFerramentas } from './ferramentas';
import { toursDeFinanceiro } from './financeiro';
import { toursDeFormulariosDeInvestimento } from './formulariosInvestimento';
import { toursDeFormulariosFinanceiros } from './formulariosFinanceiro';
import { toursDeInvestimentos } from './investimentos';
import { toursDePlanejamento } from './planejamento';

const todos = {
  ...toursDeFinanceiro,
  ...toursDePlanejamento,
  ...toursDeInvestimentos,
  ...toursDeFerramentas,
  ...toursDeFormulariosFinanceiros,
  ...toursDeFormulariosDeInvestimento,
};

export const tours = Object.fromEntries(
  Object.entries(todos).sort(([a], [b]) => Number(a.includes(':')) - Number(b.includes(':'))),
);
