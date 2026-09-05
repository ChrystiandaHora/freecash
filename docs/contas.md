# Contas a pagar, receitas e recorrência

Referência para quem for mexer em lançamento financeiro, liquidação ou regra de
recorrência. Para o caso específico de cartão, ver
[fatura-cartao.md](fatura-cartao.md).

---

## Um modelo só: `Conta`

Receita, despesa e fatura de cartão são a mesma tabela, separadas por `tipo` (`R`, `D`,
`I`) e por flags. As telas de Contas a Pagar, Receitas, Kanban, Calendário, Extrato e
Horizonte de Saldos são todas recortes de `Conta`.

O nome engana: **`Conta` é um lançamento, não uma conta bancária**. Conta bancária não
existe como domínio — `ContasBancariasViewSet` é um alias que faz CRUD de
`CartaoCredito`, e o saldo é derivado dos lançamentos, não guardado.

Um modelo só evita a duplicação que apareceria em três: a mesma lógica de liquidação, de
recorrência e de projeção valeria para receita e para despesa, e divergiria com o tempo.

---

## Previsto e realizado são campos diferentes

| Campo | O que significa |
|---|---|
| `data_prevista` | Quando **deveria** entrar ou sair. Sempre preenchido |
| `transacao_realizada` | Se já entrou ou saiu |
| `data_realizacao` | Quando de fato aconteceu. Só existe se realizada |

Os três estão indexados, porque toda consulta de saldo, projeção e calendário passa por
eles.

A distinção é o que permite projetar. Um lançamento previsto para daqui a dois meses é
compromisso conhecido; o mesmo lançamento liquidado é dinheiro que já se moveu. O
Horizonte de Saldos trata os dois de modo oposto: o realizado entra na âncora do saldo, o
previsto entra no fluxo futuro.

**Pendência vencida é o terceiro caso.** Um lançamento com `data_prevista` no passado e
nunca liquidado é dinheiro que ainda vai sair; ele entra no **primeiro dia** da projeção,
não distribuído adiante — espalhá-lo esconderia que já venceu.

O status que a interface mostra — Atrasado, Pendente, Vence Hoje, Pago — é derivado desses
três campos, e não persistido. Não há coluna de estado a manter em sincronia.

---

## A recorrência tem um motor só

`LancamentoRecorrente` cobre **receita e despesa**, com um campo `tipo`. Antes ele se
chamava `ReceitaRecorrente` e só cobria entradas — e enquanto foi assim, qualquer projeção
de longo prazo era sistematicamente otimista: salário fixo era materializado doze meses à
frente, aluguel e assinaturas só existiam nos meses lançados à mão. Com salário de 8 mil e
aluguel de 3 mil, a curva subia 8 mil por mês em vez de 5 mil.

Generalizar a regra existente, em vez de criar um `DespesaRecorrente` paralelo, manteve
**um único motor de geração** — e um único lugar para corrigir cada defeito de geração de
ocorrência.

> A renomeação quebrou o formato de backup. Ver os mapas de compatibilidade em
> [backup.md](backup.md): `ReceitaRecorrente` → `LancamentoRecorrente` e
> `Conta.receita_recorrente` → `Conta.recorrencia`.

Frequências: mensal, quinzenal, semanal e anual. `data_fim` é opcional — sem ela a regra
não tem prazo.

---

## As ocorrências são materializadas, não calculadas

`gerar_ocorrencias` cria `Conta` de verdade para cada repetição. Não há "lançamento
virtual" que exista só na projeção.

Isso é o que permite tratar cada ocorrência como um lançamento normal: liquidar uma sem
liquidar as outras, mudar o valor de um mês só, apagar a de dezembro. Uma série calculada
na hora não teria onde guardar essas exceções.

O preço é que a projeção só enxerga o que já foi materializado — por isso
`horizonte_saldos` chama `garantir_horizonte` antes de ler.

**A geração é idempotente e barata em repetição.** Ela parte da última ocorrência
existente (`Max("data_prevista")`) e usa `get_or_create`, então uma janela já coberta custa
um agregado por regra e nenhuma escrita.

---

## Editar a regra não reescreve o passado

`propagar_edicao` atualiza a regra e propaga **apenas** para ocorrências que sejam ao mesmo
tempo:

- `transacao_realizada=False` — e
- `data_prevista >= hoje`

Mudar o valor do aluguel a partir de agora não pode reescrever o que já foi pago: os meses
passados registram o que de fato saiu, e alterá-los faria o saldo histórico deixar de bater
com o extrato do banco.

`pausar_regra` interrompe a geração sem apagar as ocorrências já criadas.

---

## Liquidar tem endpoint próprio

`/api/planejamento/lancamentos/<id>/liquidar/` existe separado da ação `pagar` do
`ContasPagarViewSet` porque aquela tela lista só despesas. Calendário e Extrato mostram os
dois tipos, e precisam de um caminho que sirva a ambos.

É também por isso que o rótulo do botão muda com o tipo: **"Marcar como pago"** para
despesa, **"Marcar como recebido"** para receita. Um verbo único não descreveria os dois
casos.

Desfazer a liquidação existe (`desfazerLiquidacao`) e tem um efeito colateral que a
interface precisa explicar: o Extrato lista receitas e **apenas despesas já pagas**, então
desfazer uma despesa faz a linha sair da tela. Sem dizer isso, o usuário vê o registro
sumir e conclui que apagou algo.

---

## O que ficou de fora, e por quê

**Orçamento não existe.** Não há modelo, endpoint nem tela. O sistema registra o que
aconteceu e projeta o que está lançado; ele não sabe quanto você *pretendia* gastar com
alimentação, e portanto não avisa que passou. Um card de orçamento com número inventado
chegou a existir no frontend e foi removido — mostrar um limite fabricado como se o usuário
o tivesse definido é pior que não ter o recurso.

**Dívida com juros não é projetada.** Um financiamento aparece só pelas parcelas lançadas
como `Conta`. Não há saldo devedor que evolua, nem amortização.

**Gasto variável futuro não é estimado.** A projeção não extrapola média de gastos passados.
É deliberado: a extrapolação teria a mesma aparência de um compromisso real, e o usuário não
teria como distinguir o que assumiu do que o sistema supôs. O caminho para cobrir gasto
variável é cadastrá-lo como despesa fixa quando ele de fato for recorrente.

**Não há limite por categoria.** Mesma razão do orçamento: exigiria um domínio próprio, com
modelo, CRUD e tela.
