# Horizonte de Saldos e Calendário de Pagamentos

Referência para quem for mexer na projeção de saldo, no calendário ou na
recorrência. Descreve o que o sistema faz, **por que** faz assim e o que
deliberadamente ficou de fora.

---

## O que mudou na recorrência

`ReceitaRecorrente` virou `LancamentoRecorrente`, com um campo `tipo` (receita ou
despesa). O motivo não é organização: enquanto a recorrência só cobria entradas,
qualquer projeção de longo prazo era **sistematicamente otimista**. A receita fixa
era materializada doze meses à frente por `recorrencia_service`, enquanto aluguel,
assinaturas e contas de consumo só existiam nos meses lançados à mão. Com salário
de 8 mil e aluguel de 3 mil, a curva subia 8 mil por mês em vez de 5 mil.

Generalizar a regra existente, em vez de criar um `DespesaRecorrente` paralelo,
mantém **um único motor de geração** — e um único lugar para corrigir cada defeito
de geração de ocorrência.

### Compatibilidade de backup — leia antes de renomear qualquer modelo

As chaves do arquivo `.fcbk` são **nomes de classe** (`data[app][NomeDoModelo]`) e
**nomes de campo** (chaves estrangeiras viram `<campo>_uuid`). Qualquer renomeação
no código é, portanto, uma quebra de formato de arquivo: um backup gerado antes da
mudança continua trazendo os nomes antigos.

O modo de falha é o pior possível num backup — a restauração **não dá erro**,
apenas não encontra os registros e devolve a base sem eles.

Por isso `import_service.py` mantém dois mapas:

- `NOMES_LEGADOS_DE_MODELO` — nomes de classe antigos, por modelo atual;
- `CAMPOS_RENOMEADOS_POR_MODELO` — chaves de campo antigas, por modelo atual.

Ambos são cobertos por `test_backup_compatibilidade.py`. **A próxima renomeação de
modelo ou de campo precisa incluir a entrada correspondente**, ou os usuários
perdem dados em silêncio ao restaurar um backup anterior.

---

## Como a projeção é construída

O saldo projetado de um dia soma três partes:

1. **A âncora** — o dinheiro que já está em caixa hoje, de
   `dashboard_helper.saldo_liquidez_ate`. Sem ela a curva partiria de zero e
   mediria apenas o fluxo líquido futuro, não o saldo da conta.
2. **A pendência acumulada** — lançamentos com `data_prevista` no passado nunca
   liquidados. São dinheiro que ainda vai sair, e entram no **primeiro dia** da
   projeção: distribuí-los adiante esconderia que já venceram.
3. **O fluxo futuro** — os lançamentos previstos, dia a dia, acumulados.

A âncora vai até **ontem**, e o que está previsto para hoje entra como movimento do
dia. Se a âncora incluísse hoje e o dia também somasse o previsto, um lançamento
de hoje apareceria dobrado.

### Duas invariantes

**O filtro de cartão.** Toda consulta de valor usa
`Q(cartao__isnull=True) | Q(eh_fatura_cartao=True)`. A compra individual e a fatura
consolidada são o mesmo dinheiro em dois níveis de registro. O mesmo filtro está em
`saldo_liquidez_ate`, e as duas metades **precisam concordar**: se divergirem, a
âncora e o fluxo passam a medir universos diferentes e o resultado não significa
nada.

Note que não é possível ter uma compra de cartão isolada no banco — o signal
`monitorar_salvamento_conta` consolida a fatura do período assim que a compra é
salva. O que os testes garantem, portanto, não é que a compra seja ignorada, e sim
que compra e fatura juntas produzam **um único desembolso**.

**A recorrência precisa estar materializada.** As ocorrências futuras só existem
como `Conta` depois de geradas, por isso `horizonte_saldos` chama
`garantir_horizonte` antes de ler. A geração é idempotente e barata em chamadas
repetidas: `gerar_ocorrencias` parte da última ocorrência existente, então uma
janela já coberta custa um agregado por regra, e nenhuma escrita.

---

## O cenário de metas

Metas têm valor-alvo, acumulado e prazo, mas **nenhum cronograma de aporte**. O
aporte mensal é derivado — (alvo − acumulado) ÷ meses até o prazo — e devolvido
como **série separada** (`saldo_com_metas`), nunca somado à principal.

A distinção é de significado, não de apresentação: uma despesa lançada é
compromisso assumido; um aporte para meta é intenção de poupar. Misturar as duas
numa curva faria o usuário ler como dívida algo que ele decidiu e pode desfazer.

Regras de borda:

- **Meta sem prazo é ignorada.** Sem prazo não há cronograma dedutível, e
  distribuir o valor faltante numa janela arbitrária inventaria um compromisso.
- **Meta com prazo vencido** é cobrada integralmente no primeiro mês — represar o
  valor num prazo que já passou apenas esconderia que a meta está atrasada.
- **Meta já atingida** não gera aporte.

---

## Sinalização na interface

`_situacao` classifica cada dia em `negativo`, `atencao` ou `confortavel`, e o
servidor devolve a classificação dos **dois** cenários. A regra de limite fica num
lugar só: se o cliente a recalculasse, poderia divergir do servidor.

Na tela, a situação nunca é comunicada só por cor — a SC 1.4.1 não admite isso, e
numa grade de ~370 células é fácil esquecer. Cada célula carrega três sinais
redundantes: cor de fundo, **borda esquerda com espessura e estilo próprios**
(sólida no negativo, tracejada na atenção, ausente no confortável) e um texto
`sr-only` com a palavra da situação. A borda é o sinal que sobrevive à escala de
cinza, ao daltonismo e ao modo de cores forçadas.

---

## O calendário

`calendario_mes` **não** aplica o filtro de cartão na listagem: quem abre um
calendário de pagamentos quer reconhecer a compra que fez, não apenas a fatura. O
filtro entra nos **totais** do dia, que representam desembolso real.

O detalhe do dia no Horizonte de Saldos reusa este mesmo endpoint, em vez de ter um
próprio — a regra de qual lançamento entra na conta fica num lugar só.

A liquidação tem endpoint próprio (`/api/planejamento/lancamentos/<id>/liquidar/`)
porque a ação `pagar` do `ContasPagarViewSet` cobre apenas despesas, já que aquela
tela só lista despesas. O calendário mostra os dois tipos — e é também por isso que
o botão de ação muda de verbo conforme o lançamento: "Marcar como pago" para
despesa, "Marcar como recebido" para receita. Um rótulo único não descreveria os
dois casos.

O botão carrega **texto visível**, e não apenas um ícone com `aria-label`. Ver a
entrada correspondente em `A11Y-DECISIONS.md`: um nome acessível responde ao leitor
de tela, mas "o que este ícone faz?" é pergunta de quem está olhando a tela.

---

## O que ficou de fora, e por quê

**Orçamento e dívidas não existem como domínio no FreeCash** — não há modelo, tela
nem endpoint. A projeção consome lançamentos, faturas de cartão, recorrências e
metas, que cobrem a maior parte do fluxo de caixa.

Duas consequências para a leitura do horizonte:

1. **Dívidas com juros não são projetadas** como saldo devedor que evolui. Um
   financiamento aparece apenas pelas parcelas que estiverem lançadas como `Conta`.
2. **Não há limite de gasto por categoria.** O horizonte projeta o que está
   registrado; ele não avisa que o gasto com alimentação está acima do planejado,
   porque não existe planejado.

Ambos são domínios próprios, cada um com modelo, CRUD e tela.

**Gasto variável futuro não é estimado.** A projeção não extrapola a média de
gastos passados para os meses à frente. Isso é deliberado: uma extrapolação
apareceria com a mesma aparência de um compromisso real, e o usuário não teria como
distinguir o que assumiu do que o sistema supôs. O caminho para cobrir gasto
variável é cadastrá-lo como despesa fixa quando ele de fato for recorrente.
