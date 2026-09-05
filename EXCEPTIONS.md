# Exceções de acessibilidade

Cada entrada registra uma regra automatizada que **não** é seguida, com o motivo e o
que a substitui. A regra 5 do `A11Y-DECISIONS.md` proíbe divergir em silêncio: se o
lint acusa e o código não muda, o porquê fica aqui.

Aberto em 2026-09-04, junto com a instalação do `eslint-plugin-jsx-a11y`.

---

## `jsx-a11y/heading-has-content` — `components/ui/Card.jsx:45`

**Falso positivo.** `CardTitle` é `<h3 {...props} />`: o conteúdo chega por `children`
no spread, e a regra não enxerga através do componente. Todos os usos passam texto.

Substituir por um `<h3>{children}</h3>` explícito só para calar o lint mudaria a API do
componente sem ganho de acessibilidade.

---

## `jsx-a11y/click-events-have-key-events` e `no-noninteractive-element-interactions` — `components/ui/DataTable.jsx:183`

**Falso positivo.** O `onClick` do painel de filtro é `(e) => e.stopPropagation()` — ele
existe para o clique dentro do popover não borbulhar até o fechamento, não para oferecer
uma ação. Acrescentar `onKeyDown` equivalente não daria nada a quem usa teclado: não há
ação a acionar ali.

O popover em si é `role="dialog"` com `aria-label`, e os controles dentro dele são
elementos nativos, todos alcançáveis por Tab.

---

## `jsx-a11y/no-autofocus` — `components/ui/DataTable.jsx:209,229,243,275`

**Divergência deliberada.** A regra existe contra `autoFocus` em carregamento de página,
onde ele rouba o foco de quem não pediu nada. Aqui os quatro casos estão dentro do
popover de filtro de coluna, que **só existe depois de o usuário clicá-lo** — mover o
foco para o primeiro campo é o comportamento esperado de um diálogo, e é o mesmo que
`components/ui/Modal.jsx:93-116` faz de propósito.

Sem o `autoFocus`, quem abre o filtro por teclado precisaria tabular de volta para
dentro do popover que acabou de pedir.

---

## Pendências reais, adiadas para o plano de auditoria das demais telas

Não são exceções — são defeitos que ainda não foram corrigidos porque estão em telas
fora do escopo da entrega atual. Devem sair quando aquelas telas forem auditadas.

- [ ] `components/CalendarHeatmap.jsx:220` — `no-static-element-interactions`: elemento
      não nativo com interação. Precisa de `role`, `tabIndex` e tratamento de teclado,
      ou virar `<button>`.
- [ ] `pages/FerramentasImportar.jsx:178` — `click-events-have-key-events` e
      `no-static-element-interactions`: a área de soltar arquivo só responde a mouse.
      Precisa de alternativa por teclado — o `<input type="file">` costuma resolver.
- [ ] `pages/FerramentasImportar.jsx:126` — `no-autofocus` fora de diálogo, diferente
      do caso do `DataTable` acima; aqui vale remover.
