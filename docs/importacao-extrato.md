# Importação de extrato e conciliação

Referência para quem for mexer em leitura de PDF bancário, criação de lançamento a
partir de arquivo ou na fila de conciliação. Descreve o que o sistema faz, **por que**
faz assim e onde ele erra por não ter como saber.

---

## O problema

Extrato de banco não é formato: é aparência. Cada instituição imprime o PDF do jeito
que quer, muda o layout sem aviso, e não existe contrato. Qualquer leitor é heurística,
e heurística erra.

O desenho parte disso: **a importação não confia no que leu**. O arquivo vira uma fila
de linhas para o usuário conferir, não lançamentos prontos.

---

## Dois caminhos, e eles não são iguais

**Importação direta** (`FerramentasImportarExtratoAPIView`, `POST
/api/ferramentas/importar-extrato/`) cria `Conta` na hora, a partir do que o parser
extraiu, e **exige** um cartão. É o caminho da fatura, onde o usuário já sabe o que está
importando. A tela é *Compras Cartão*.

**Conciliação** (`ExtratoImportado` + `LinhaExtrato`) guarda cada linha com
`status="pendente"` e espera. O usuário aprova, descarta ou vincula a um lançamento que
já existe — `conta_vinculada`. Aqui o cartão é **opcional**, e é isso que faz a linha
aprovada poder virar conta a pagar avulsa. A tela é *Conciliação*.

A diferença não é técnica, é de confiança: numa fatura, toda linha é despesa nova; num
extrato, a maioria já está no sistema.

### A fila ficou anos sem entrada

Os models, os serializers e os dois endpoints de conciliação existem desde o começo, mas
até 2026-09-14 **nada os populava**: `ExtratoImportado.objects.create` não aparecia em
lugar nenhum fora dos testes. A fila estava sempre vazia, e a tela que a exibia foi
apagada em `adcceaa` sem que a peça faltante — o upload — tivesse sido escrita.

Quem preenche a lacuna é `FerramentasConciliacaoUploadAPIView` (`POST
/api/ferramentas/conciliacao/upload/`): roda o mesmo `processar_pdf`, mas grava linhas
pendentes em vez de `Conta`. Nada entra na base antes da aprovação — é o ponto inteiro
do caminho, e a razão de ele não reaproveitar o endpoint direto.

---

## O parser é por banco, com fallback

[`extrato_parser.py`](../backend/core/services/extrato_parser.py) usa `pdfplumber` e três
estratégias:

| Função | Quando |
|---|---|
| `parse_pdf_nubank` | Layout do Nubank, reconhecido por marcadores no texto |
| `parse_layout_colunas` | PDFs com colunas alinhadas, detectadas na primeira página |
| `parse_pdf_generico` | Varredura linha a linha com regex — o último recurso |

`processar_pdf(pdf_path, banco)` escolhe. `ExtratoImportado.BANCO_CHOICES` lista os
bancos conhecidos e é a **única enum de instituição do repositório** — se um dia houver
outra necessidade de nomear banco, é dela que se parte.

Layout novo não quebra a importação: cai no genérico e traz menos linhas, ou linhas
tortas. Por isso a fila de conciliação existe.

---

## A regra da data — leia antes de mexer

```python
def _ja_ocorreu(data_movimento: date) -> bool:
    return data_movimento <= timezone.localdate()
```

Só isso separa um lançamento **realizado** de um **previsto**. Uma versão anterior do
importador marcava tudo como realizado, e lançamentos com data futura entraram na base
como dinheiro que já entrou — inflando saldo e projeção. A correção foi esta função, e
ela é aplicada nos dois caminhos: importação direta (`:128`) e aprovação de conciliação
(`:250`).

**Compra de cartão é a exceção, e é deliberada:** `transacao_realizada = False` sempre,
independentemente da data. A compra só vira desembolso quando a fatura é paga — quem
liquida é `pagar_fatura`, em cascata. Ver [fatura-cartao.md](fatura-cartao.md).

Qualquer caminho novo que crie `Conta` a partir de arquivo precisa passar por
`_ja_ocorreu`, ou repetir o bug.

---

## Compra de cartão muda de data no caminho

Para cartão, a linha do PDF tem a data da **compra**, e o lançamento precisa da data do
**vencimento**. A importação separa as duas:

- `data_compra` ← o que estava no PDF
- `data_prevista` ← `calcular_vencimento_fatura(data_compra, dia_fechamento, dia_vencimento)`

Essa normalização é o que mantém todas as compras de um ciclo com a **mesma**
`data_prevista`, que é a chave implícita entre compra e fatura. Sem ela, a compra abre
uma fatura própria no mesmo mês, em vez de entrar na do ciclo — ver
[fatura-cartao.md](fatura-cartao.md).

`detectar_vencimento_fatura` complementa: calcula o vencimento de cada linha e devolve a
**moda**. Uma fatura traz compras de dias diferentes do ciclo, e a maioria aponta para o
vencimento certo; linhas fora do padrão não arrastam o conjunto.

---

## Duplicata é evitada por comparação de campos

Não há hash de arquivo nem identificador do banco. Antes de criar, a importação procura
uma `Conta` com **usuário, tipo, descrição, valor, cartão, `data_compra` e
`data_prevista`** idênticos, e pula se achar.

Isso torna reimportar o mesmo PDF inofensivo — o caso comum, quando o usuário não sabe
se já importou.

A conciliação aplica a **mesma** comparação, mas no momento da aprovação, e não do
upload: achando a `Conta` idêntica, a linha é marcada `importado` e apontada para ela em
vez de criar uma segunda. O usuário vê "N já existia(m) e foi(ram) vinculada(s)". Só a
aprovação pode fazer essa checagem, porque `data_prevista` de compra de cartão depende
do ciclo e não é conhecida enquanto a linha está na fila.

E tem o efeito colateral esperado: **duas compras genuinamente iguais no mesmo dia** —
dois cafés de R$ 8 na mesma padaria — são lidas como uma. O sistema erra para o lado de
não duplicar dinheiro, que é o lado menos ruim; a segunda entra à mão.

---

## O que ficou de fora, e por quê

**Não há OFX.** Só PDF. OFX é estruturado e seria mais confiável, mas nem todo banco
oferece, e o usuário costuma ter o PDF em mãos.

**Não há aprendizado de categoria.** A importação não adivinha que "PADARIA CENTRAL" é
Alimentação. Compras de cartão recebem a categoria de cartão, o resto vem sem. Um
classificador que erra em silêncio seria pior que campo vazio — existe
`categorizar_gastos_cartao` como comando, para rodar sob supervisão.

**O parser não valida totais.** Ele não confere se a soma das linhas bate com o total
impresso no PDF, o que pegaria página perdida ou linha mal lida. Seria a checagem de
maior retorno aqui, e não existe.

**Conciliação não tem vínculo manual.** `FerramentasConciliacaoProcessarAPIView` aceita
exatamente duas ações — `importar` e `ignorar` — e o `conta_vinculada` da linha só é
preenchido pela `Conta` que a aprovação criou, ou pela duplicata exata que ela achou.
Não existe "esta linha é aquele lançamento que eu já tinha digitado": para um pagamento
lançado à mão com descrição diferente, o caminho é descartar a linha. Casamento
aproximado por valor e data seria a evolução natural, e é o que falta.
