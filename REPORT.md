# Relatório de acessibilidade — telas de investimento

Cobre a entrega que removeu o redesign fintech e alinhou backend↔frontend no módulo de
investimentos. Escrito conforme a regra 6 do `A11Y-DECISIONS.md`: parcial, com `[ ]` no
que exige ferramenta ou pessoa que eu não tenho aqui.

**Perfil:** Standard (WCAG 2.2 AA). **Data:** 2026-09-04.

---

## Telas no escopo

Painel de Investimentos, Meus Ativos, Carteiras, Balanceamento, Histórico de Ordens,
Detalhe do Ativo, os formulários de Ativo e de Ordem, Transações e Dashboard.

Ficaram **fora**: Contas a Pagar, Kanban, Cartões, Metas, Relatórios, Calendário,
Simulador, Importar, Backup, Minha Conta e as duas de admin. Elas têm plano próprio.

---

## Verificado

- [x] **Lint de acessibilidade existe.** `eslint-plugin-jsx-a11y` instalado e ligado
      nesta entrega — até então nenhuma das decisões deste projeto tinha checagem
      automática. Achou 12 problemas, **nenhum no código de carteiras**.
- [x] **`aria-selected` inerte corrigido.** `DateRangeCalendar` usava um atributo que
      `role="button"` não suporta; o dia selecionado não era anunciado. Virou `aria-pressed`.
- [x] **Gráficos fora da árvore de acessibilidade.** Os 4 contêineres de ApexCharts em
      `Investimentos.jsx` ganharam `aria-hidden="true"`, cumprindo a decisão de
      `A11Y-DECISIONS.md` que já estava registrada e não implementada. A legenda em
      `<ul>` ao lado entrega os mesmos dados em texto.
- [x] **Zero erro de JS.** 12 capturas (6 telas × 1440px e 420px) sem exceção no console.
      Os dois erros que existiam a 420px vinham de animação do ApexCharts em contêiner
      estreito e sumiram com `animations: { enabled: false }`.
- [x] **Sem estouro horizontal a 420px** em nenhuma das 6 telas.
- [x] **Estado nunca só por cor.** A coluna Situação de Transações usa ícone de forma
      distinta (círculo vazio × check) mais a palavra; "Falta Aportar" traz o verbo
      ("aportar" / "acima em"), não só a cor do número.
- [x] **Número fora de escopo é declarado.** O card de custódia e o Detalhe do Ativo
      avisam, em `aria-live="polite"`, quando mostram consolidado sob filtro ativo.
- [x] **Formulários** com `label`/`htmlFor`, `aria-invalid`, `aria-describedby` e erro
      em `role="alert"` nos modais de carteira e de transferência.
- [x] **Diálogos** herdam o focus trap, a tecla Escape e a devolução de foco de
      `ui/Modal.jsx`. A confirmação de exclusão de Transações usa esse Modal, e não o
      `window.confirm` que o código removido usava.
- [x] **Ajuda em contexto (SC 3.2.6):** `/investimentos/carteiras` tem entrada em
      `config/helpContent.js`.

---

## Não verificado — precisa de pessoa ou ferramenta

- [ ] **Leitor de tela real** (NVDA / VoiceOver). Em especial: o que é anunciado ao
      trocar a carteira no filtro, e se a região viva do subtítulo chega antes de os
      números trocarem. Com `keepPreviousData`, os valores antigos ficam à vista por um
      instante depois do anúncio do novo escopo.
- [ ] **Contraste medido** de `text-muted-foreground` em `text-xs` (12px) na legenda do
      donut, nos dois temas. 12px em peso semibold exige 4,5:1 e essa combinação nunca
      foi medida.
- [ ] **Simulação de daltonismo** no donut de custódia. A paleta fixa foi validada por
      script para separação CVD, mas nunca vista com filtro de simulação.
- [ ] **Zoom 200% e refluxo a 320px** na linha donut + legenda, que usa gráfico de
      largura fixa (180px) ao lado de uma lista flexível.
- [ ] **Ordem de tabulação real** no modal de transferência, agora que o campo dependente
      deixou de ser `disabled`.

---

## Exceções

Três regras do `jsx-a11y` não são seguidas, com justificativa em
[EXCEPTIONS.md](EXCEPTIONS.md): `heading-has-content` e as interações do `DataTable`
são falsos positivos; o `no-autofocus` do popover de filtro é divergência deliberada.

Três defeitos reais ficaram registrados lá como pendência, por estarem em telas fora
deste escopo: `CalendarHeatmap` e duas ocorrências em `FerramentasImportar`.

---

## Defeito conhecido, sem correção nesta entrega

`pages/AtivosClasses.jsx` guarda seis mutations mortas de um refactor anterior, e o
estado `mutError` recebe mensagem de erro que **nunca é renderizada** — falha de
gravação naquela tela não aparece para o usuário (SC 3.3.1). Apagar as variáveis
calaria o lint e esconderia o defeito; corrigi-lo exige entender o fluxo da tela, que
não foi auditada. Fica para o plano das telas restantes.
