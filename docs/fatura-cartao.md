# Fatura de cartão

Referência para quem for mexer em compra de cartão, consolidação de fatura ou em
qualquer consulta que **some dinheiro**. Descreve o que o sistema faz, **por que** faz
assim e onde a coisa quebra em silêncio.

---

## O problema

Uma compra de R$ 300 no cartão não é um desembolso de R$ 300 naquele dia. O dinheiro
sai uma vez só, na fatura, junto com todas as outras compras do ciclo. Registrar
apenas a compra tornaria impossível conciliar com o extrato do banco; registrar apenas
a fatura tiraria do usuário o detalhe do que ele gastou.

O FreeCash registra **os dois**, na mesma tabela: `Conta`. A fatura é uma `Conta` com
`eh_fatura_cartao=True`; a compra é uma `Conta` com `cartao` preenchido e a flag falsa.

Isso resolve o cadastro e cria a única regra que realmente importa neste domínio.

---

## A invariante do filtro

Toda consulta que soma valor precisa escolher **um** dos dois níveis, nunca os dois:

```python
Q(cartao__isnull=True) | Q(eh_fatura_cartao=True)
```

Lê-se: pega o que não é de cartão, mais as faturas — e descarta as compras
individuais, que já estão dentro da fatura. Sem isso, cada compra de cartão é contada
duas vezes.

Esse filtro aparece hoje em **17 lugares** do backend: `dashboard_helper.py`,
`views/api.py`, `projecao_service.py`. As cópias **precisam concordar**. Se uma
divergir, o saldo de uma tela passa a medir um universo diferente do de outra, e o
número deixa de significar qualquer coisa — sem erro, sem alerta, só dois totais que
não fecham.

**Quem soma, filtra. Quem lista, não.** O Calendário de Pagamentos mostra a compra
individual no dia em que ela aconteceu, porque quem abre um calendário quer reconhecer
o que comprou; o filtro entra só nos **totais** do dia, que representam desembolso real.

---

## A consolidação acontece por signal

`monitorar_salvamento_conta` ([core/signals.py](../backend/core/signals.py)) dispara em
todo `post_save` de `Conta`. Se o registro tem `cartao` e não é fatura, ele chama
`_consolidar_fatura`, que:

1. acha ou cria a fatura do ciclo — `obter_ou_criar_fatura`
2. garante a categoria de cartão
3. recalcula o valor total — `atualizar_valor_fatura`

Consequência prática: **não existe compra de cartão isolada no banco**. Salvou a
compra, a fatura do período já está lá, criada ou atualizada. O `post_delete` faz o
caminho inverso, com `_reconsolidar_apos_exclusao`.

É por isso que os testes de projeção não verificam se a compra é ignorada, e sim se
compra e fatura **juntas** produzem um único desembolso.

---

## O vínculo é implícito, e isso tem um preço

Compra e fatura não têm chave estrangeira entre si. O vínculo é a tripla
**usuário + cartão + `data_prevista`**, e as funções que dependem disso —
`compras_da_fatura`, `atualizar_valor_fatura`, `pagar_fatura`, `excluir_fatura` — casam
por **data exata**:

```python
Conta.objects.filter(usuario=…, cartao=…, eh_fatura_cartao=False,
                     data_prevista=fatura.data_prevista)
```

`obter_ou_criar_fatura` usa **a mesma data exata**. Nem sempre foi assim: ele procurava
por mês e ano, e as duas regras só coincidiam porque `data_prevista` de uma compra de
cartão é normalizada para o vencimento do ciclo por
`calcular_vencimento_fatura(data_compra, dia_fechamento, dia_vencimento)`.

**A assimetria era uma armadilha de mão única.** Uma compra que entrasse com
`data_prevista` de outro dia do mesmo mês — por importação, por edição manual, por um
caminho de escrita novo — era consolidada na fatura pela busca de mês e ficava de fora
da soma, do pagamento e da exclusão, que casam por data exata. Órfã: aparece no
extrato, não entra na fatura, e ninguém é avisado.

Com as duas pontas na data exata, a mesma divergência produz uma **fatura a mais** no
mês — visível, registrada em `warning` e com caminho de correção. Errar para o lado do
duplicado é melhor que errar para o do invisível.

A normalização continua sendo a defesa de primeira linha: antes de criar qualquer
caminho novo que grave `Conta` com `cartao` preenchido, passe por
`calcular_vencimento_fatura`.

---

## Pagamento em cascata

`pagar_fatura` marca a fatura como paga **e** todas as compras do ciclo, em
`transaction.atomic`. `desfazer_pagamento_fatura` faz o inverso. As duas pontas
precisam andar juntas: fatura paga com compras pendentes deixaria o Horizonte de
Saldos projetando um desembolso que já ocorreu.

Fatura liquidada trava a edição — `fatura_pode_ser_editada` e
`despesa_pode_ser_editada`. Editar uma compra de fatura já paga mudaria o valor de um
desembolso que já aconteceu, e o saldo passado deixaria de bater com o extrato.

`atualizar_valor_fatura` também respeita isso: sai cedo se a fatura estiver paga, para
que uma compra lançada com atraso não altere um total já conciliado.

---

## Faturas duplicadas

`obter_ou_criar_fatura` tolera a base já ter mais de uma fatura no mesmo mês: ordena por
`id` para a escolha ser determinística, prioriza a que já foi liquidada — porque ela
carrega o histórico de pagamento — e registra um `warning`.

`deduplicar_faturas()` resolve, e é chamado ao final da restauração de backup, onde o
problema costuma nascer. `manage.py corrigir_faturas_duplicadas` é a porta de entrada
manual, com `--dry-run` e `--usuario`.

**A dedup move as compras.** Ela agrupa por mês, então pode juntar faturas de dias
diferentes — e apagar a de dia 15 deixaria as compras daquele dia sem fatura nenhuma,
exatamente a órfã que a seção anterior descreve. Por isso as compras das faturas
removidas são reatribuídas à `data_prevista` da mantida antes do `delete`.

---

## O que ficou de fora, e por quê

**Parcelamento não é um domínio.** Uma compra em 6x é registrada como 6 `Conta`, uma
por ciclo. Não há entidade que as agrupe, então não dá para editar "a compra" — só cada
parcela. O importador de faturas em PDF cria as parcelas futuras no ato.

**Limite não é validado.** `CartaoCredito.limite` alimenta o gauge de utilização e nada
mais: lançar uma compra acima do limite é aceito. O sistema registra o que aconteceu,
não autoriza a transação.

**Não há fechamento explícito.** A fatura não tem estado "fechada"; ela é aberta até ser
paga. Uma compra lançada com data de um ciclo já pago simplesmente não altera o total,
pelo guarda de `atualizar_valor_fatura` — mas também não avisa que foi ignorada.
