# Tour guiado

O tour apresenta uma tela a quem nunca a viu: escurece a página, recorta um elemento de
cada vez e explica em uma ou duas frases para que ele serve. Começa pelo botão de ajuda
(`?` → "Fazer o tour") e abre sozinho na primeira visita a cada tela.

---

## Como dar tour a uma tela

1. Marque na página os elementos que o tour vai destacar com `data-tour="<tela>-<coisa>"`.
   Componentes de `ui/` (`Card`, `Button`, `Input`, `Select`) repassam o atributo.
2. Escreva os passos no arquivo do grupo em
   [`frontend/src/config/tour/`](../frontend/src/config/tour/), na chave do padrão da
   rota — o mesmo do `helpContent.js` (`/eventos/:id`, não `/eventos/42`).
3. Rode `npx vitest run src/config/tour`.

```js
'/backup': [
  { titulo: 'Exportação & Backup', texto: 'Aqui você leva todos os seus dados…' },
  { alvo: 'backup-status', titulo: 'Quando foi o último backup', texto: 'O selo fica amarelo…' },
]
```

O teste [`tours.test.js`](../frontend/src/config/tour/tours.test.js) garante que a rota
existe no `App.jsx`, que o primeiro passo não tem alvo, que cada tour tem de 3 a 8
passos, que cada `alvo` existe como `data-tour` em algum lugar do código e que título
(40) e texto (200) são curtos.

---

## Alvo ausente é pulado — e por que o teste existe

Antes de abrir, o tour descarta os passos cujo alvo não está na tela: lista vazia,
seção que só aparece com dados, campo condicional escondido. É o comportamento certo
para uma conta nova, e por isso **nenhum passo pode depender do anterior** para fazer
sentido.

O mesmo mecanismo esconderia um erro de digitação: um `alvo` que não bate com o
`data-tour` da página seria pulado em silêncio, para sempre. O teste separa os dois
casos — o alvo precisa existir no código, mesmo que nem sempre esteja na tela.

O elemento marcado precisa ter caixa: `display: none` e `display: contents` contam como
ausentes (`getClientRects()` vazio).

---

## Abertura automática

[`TourProvider`](../frontend/src/components/tour/TourProvider.jsx) tenta abrir 700 ms
depois da navegação e repete a cada 250 ms por até 6 s, esperando duas coisas:

- **algum alvo na tela** — o primeiro costuma depender de dados ainda carregando;
- **nenhum outro diálogo aberto** (`[aria-modal="true"]`) — ajuda, aviso de inatividade.

Se o prazo vence sem alvo, desiste **sem** marcar a tela como vista: tenta de novo na
próxima visita. Quando abre, marca na hora (`freecash_tours_vistos`, no
`localStorage`): quem fechou no meio não quer vê-lo outra vez sozinho. É por navegador,
não por conta — limpar os dados do site faz os tours voltarem.

---

## Posição do balão

[`posicionarBalao`](../frontend/src/lib/tour.js) tenta abaixo do alvo, depois acima,
à direita, à esquerda e, sem espaço, por cima da parte de baixo da tela. O topo útil
começa em 76 px: o header fixo cobre os primeiros 64, e um balão "acima" calculado sem
isso ficaria atrás da barra. No mobile (< 640 px) o balão fica preso embaixo e o alvo
rola para o topo.

Acessibilidade (diálogo modal, foco, teclado, camada `z-[45]`) está registrada em
[A11Y-DECISIONS.md](../A11Y-DECISIONS.md).
