# Carteiras de investimento

Referência para quem for mexer em custódia, posição por carteira ou transferência
entre corretoras. Descreve o que o sistema faz, **por que** faz assim e o que
deliberadamente ficou de fora.

---

## O problema

Antes desta feature a carteira era implícita: era o conjunto de todos os `Ativo` do
usuário. Quem tinha posição na XP, no Inter e no BTG via tudo num bolo só, sem
conseguir responder "quanto eu tenho *nesta* corretora".

E havia uma trava concreta: `Ativo.unique_together = ("usuario", "ticker")`. Era
impossível ter PETR4 na XP **e** no Inter — o segundo cadastro esbarrava na
constraint.

---

## A carteira fica na transação, não no ativo

Havia dois jeitos de resolver a constraint, e a escolha define todo o resto.

**Pendurar `carteira` no `Ativo`** e trocar a unique para `("usuario", "carteira",
"ticker")` seria a mudança menor: signals e `calculators` quase não mudariam. Mas
duplicaria o papel por corretora, e com ele três coisas:

1. **A série de `Cotacao`.** `Cotacao` é FK de `Ativo`, com unique `("ativo",
   "data")`. Dois `Ativo` para PETR4 significam duas séries idênticas e duas
   chamadas ao TradingView/CVM pelo mesmo papel, toda vez que se atualiza cotação.
2. **A tela.** PETR4 apareceria duas vezes em Meus Ativos, e a soma teria de ser
   feita a olho.
3. **O preço médio.** Ficaria por corretora. No Brasil o preço médio é apurado por
   CPF, no conjunto: o número que o usuário veria não seria o que ele declara.

**Pendurar `carteira` na `Transacao`** trata a carteira como **custódia**. O ativo
continua único, a cotação continua única, o preço médio consolidado continua
correto, e a posição por carteira vira um agregado derivado — `PosicaoCarteira`.

É também o único desenho em que "transferir da XP para o Inter" é uma operação de
verdade, e não uma venda seguida de compra que corromperia rentabilidade e
histórico de proventos.

### O ticker duplicado

Querer o mesmo papel em duas corretoras leva naturalmente a **cadastrá-lo de novo**,
e a `unique_together ("usuario", "ticker")` recusa. Isso é correto, mas o `usuario`
não está entre os campos do `AtivoSerializer` — ele é atribuído no `perform_create`
—, então o DRF não monta o `UniqueTogetherValidator` automático e a colisão chegava
ao banco como `IntegrityError`, saindo como **500 opaco**.

`AtivoSerializer.validate_ticker` faz a checagem explícita e devolve 400 com a
mensagem que aponta o caminho: o ativo é um só, e a segunda custódia vem de lançar
uma ordem de compra escolhendo a carteira.

### Por que a FK da custódia é CASCADE, e não PROTECT

A primeira versão usou `on_delete=PROTECT` em `Transacao.carteira`, para que excluir
uma carteira não levasse o histórico de rentabilidade junto. A intenção estava certa,
o lugar não: **o PROTECT quebrava a exclusão definitiva de conta**.

O coletor do Django encontra essa FK ao percorrer a cascata `User -> Carteira` e
levanta `ProtectedError` na fase de **coleta**, antes de emitir qualquer signal — não
existe gancho `pre_delete` cedo o bastante para limpar. O efeito prático: a exclusão
de conta exigida pela LGPD passava a falhar justamente para quem tem investimentos, e
a suíte não pegava porque o teste de exclusão não criava ordens.

"Não dá para excluir carteira com ordens" é regra de negócio sobre uma ação do
usuário, e mora em `CarteiraViewSet.destroy`, que responde 409 apontando o
arquivamento. `ExclusaoComInvestimentosTests` cobre os dois caminhos de exclusão de
usuário (individual e em lote).

---

## Os dois níveis de posição

```
Ativo.quantidade / preco_medio      → consolidado do CPF, é o que se declara no IR
PosicaoCarteira.quantidade / custo  → o que está em cada custódia
```

Os dois são **cache**, recalculados a partir das transações por
`investimento/calculators.py`. Duas decisões de implementação valem registrar:

**O recálculo cobre todas as carteiras do ativo, não só a da transação salva.**
Ao editar uma ordem e trocar a carteira, o signal só enxerga a carteira nova; a
antiga ficaria com uma posição obsoleta e nada a corrigiria. Recalcular todas custa
uma consulta a mais e elimina a classe inteira de bug.

**A linha de `PosicaoCarteira` nunca é apagada.** Ela guarda o cache *e* a
`meta_porcentagem`, que é intenção declarada pelo usuário. Se zerar a posição
removesse a linha, a meta configurada sumiria em silêncio junto. O recálculo
escreve apenas os campos de cache, com `update_fields`.

### Uma divergência de centavos que é esperada

`Ativo.preco_medio` tem 4 casas decimais. Cem cotas a 30 e cinquenta a 40 dão um
preço médio de 33,3333, que multiplicado por 150 fecha em **4.999,995** — enquanto
a soma das posições, que não passa por essa divisão, dá 5.000. A diferença é do
arredondamento do campo, não do cálculo, e some no `_centavos` de quem consome. Os
testes comparam esses dois números em centavos, de propósito.

---

## A transferência

Portabilidade não é venda. A operação tem tipos próprios (`TS` saída, `TE` entrada)
gravados em duas pernas que compartilham `grupo_transferencia`, dentro de um
`transaction.atomic` — meia transferência faria cotas sumirem ou aparecerem do nada.
Apagar uma perna apaga a outra, pelo mesmo motivo.

O preço carregado é o preço médio da carteira de origem no momento. Assim o custo
total do usuário fecha igual antes e depois, e:

- **`recalcular_ativo` ignora `TS`/`TE`.** Uma transferência muda onde o papel está,
  não quanto o investidor tem nem por quanto comprou. Considerá-las moveria o preço
  médio fiscal.
- **`recalcular_posicoes_do_ativo` trata `TS` como saída a custo e `TE` como
  entrada.** Dentro de cada carteira o custo continua coerente com a quantidade.
- **No `CarteiraHistorico`, `TE` entra como compra e `TS` como venda.** Sem isso, a
  carteira que recebe teria patrimônio sem custo correspondente, e sua rentabilidade
  apareceria absurdamente positiva. Somando as carteiras, a entrada e a saída se
  anulam — o consolidado fica idêntico ao de antes de a transferência existir.
- **No `DashboardInvestimentoService`, o capital aportado é
  `compras + transf_entrada − transf_saida`.** É a mesma regra acima, e ela precisa
  valer nas duas rotas: o serviço de snapshot alimenta o gráfico, e o de dashboard
  alimenta os KPIs ao lado dele. Numa primeira versão a regra existia só no snapshot,
  e o resultado foi um gráfico correto ao lado de um KPI que mostrava prejuízo de
  8 mil na carteira de origem e lucro de 8 mil na de destino.

  A subtração da perna de saída é o que preserva o consolidado: lá as duas pernas têm
  o mesmo valor e se cancelam, então o denominador da rentabilidade continua sendo só
  o que foi comprado de fato. Somar apenas a entrada inflaria esse denominador e
  mudaria o percentual consolidado sem que nada tivesse acontecido.

**Quando a transferência não é o instrumento certo.** Ela registra uma portabilidade
que aconteceu. Se o ativo apenas foi *cadastrado* na carteira errada, o conserto é
reatribuir a ordem original — o histórico deve mostrar a compra onde ela ocorreu, e
não uma mudança de custódia que nunca existiu. É por isso que o campo de carteira
fica no corpo do cadastro de ativo, e não atrás de um bloco recolhido: escondê-lo
transforma um erro de digitação numa transferência falsa no extrato.

---

## O snapshot histórico

`CarteiraHistorico` ganhou `carteira`, com unique `("usuario", "carteira", "data")`.
O consolidado é **agregação SQL** sobre essas linhas, e não uma linha com `carteira`
nulo: uma linha "consolidada" seria uma segunda fonte de verdade para o mesmo
número, livre para divergir das partes sem que nada acusasse. E como o Postgres
trata NULLs como distintos entre si, a unique nem impediria duplicá-la.

Na leitura sem filtro, `_linhas_diarias` soma as carteiras por dia e **recalcula** a
rentabilidade a partir dos totais somados. Somar a coluna `rentabilidade` das partes
daria o mesmo número por acaso, mas o percentual não sobrevive a uma soma — ele
precisa da base consolidada.

**O fallback de preço é o custo da própria carteira.** Sem cotação para o dia, o
patrimônio da custódia é avaliado pelo custo dela, e não pelo preço médio
consolidado do ativo. Usar o consolidado atribuiria à carteira um custo que não é o
dela: quem comprou a 30 na XP e a 40 no Inter veria as duas avaliadas a 33,33.

---

## O Horizonte de Saldos

O botão "Considerar valor investido" ganhou uma pergunta nova: *quais* carteiras
contam? `Carteira.considerar_no_saldo` responde — uma reserva de emergência em
Tesouro Selic é dinheiro com que o usuário conta; uma posição em ações, normalmente
não.

`_valor_investido` parte do consolidado em `Ativo` e **desconta** as posições das
carteiras marcadas para ficar de fora, em vez de somar as posições das que ficam. As
duas contas dão o mesmo número quando todo ativo tem posição materializada — mas só
esta continua correta para um ativo que não tem, e é ela que garante que quem nunca
mexeu na configuração veja exatamente o valor de antes.

---

## Backup `.fcbk` — leia antes de mexer na restauração

A regra geral está em [backup.md](backup.md): as chaves do arquivo são nomes de
classe e de campo, e o modo de falha é o pior possível — a restauração não dá erro,
apenas devolve a base sem os registros.

Esta feature acrescentou um segundo modo de falha, com a mesma assinatura silenciosa.
`Transacao.carteira` é NOT NULL, e um `.fcbk` gerado antes das carteiras não traz
`carteira_uuid`. O laço genérico da restauração grava `None` em toda FK cujo
`<campo>_uuid` esteja ausente; o insert seria rejeitado, o fallback falharia também,
e **todas as ordens do usuário seriam descartadas sem erro nenhum**.

A correção é `FKS_LEGADAS_COM_PADRAO`, em `import_service.py`, ao lado dos dois mapas
que já existiam. Ela garante a Carteira Padrão e preenche a FK ausente.
`RestauracaoDeBackupSemCarteiraTests` cobre isso, e **a próxima FK obrigatória
introduzida num modelo já exportado precisa da entrada correspondente**.

Dois outros pontos:

- `Carteira` entra com prioridade **6,5** e `PosicaoCarteira` com **9,5** no dict
  `priority`, que existe **duplicado** em `export_service.py` e `import_service.py`.
  Editar só um deixa a restauração meio quebrada.
- O recálculo pós-restauração reconstrói `PosicaoCarteira` junto com `Ativo`. Num
  backup antigo a posição nem existe no arquivo, e no formato novo ela é cache — o
  recálculo é a única fonte de verdade que sobrevive a qualquer versão.

`Ativo.meta_porcentagem` foi **removido** (a meta virou por carteira). Remover campo
é seguro para backups antigos: `filter_valid_fields` descarta o que não existe mais.

---

## As metas, em dois níveis

Com N carteiras, "quanto comprar" tem duas respostas:

- **`PosicaoCarteira.meta_porcentagem`** — o alvo do ativo *dentro* de uma carteira.
  Soma 100% por carteira. O plano por ativo é sempre de uma carteira só; sem
  `?carteira=`, o balanceador usa a primeira ativa. Somar as metas de todas daria
  100% vezes o número de custódias, e a validação da tela deixaria de significar algo.
- **`Carteira.meta_porcentagem`** — o peso alvo da carteira no patrimônio total.
  Responde "quanto aportar em cada corretora".

No relatório consolidado (PDF/Excel), `_meta_consolidada` pondera a meta de cada
posição pelo peso da sua carteira no total investido. Com uma carteira só o peso é 1
e o resultado é a própria meta declarada — o caso de quem nunca separou por corretora.

---

## O que ficou de fora, e por quê

**Vínculo com o financeiro.** `core.models.Conta` já tem `TIPO_INVESTIMENTO = "I"`,
mas nenhuma ligação com o app `investimento`. Amarrar aporte → lançamento de saída
fecharia o ciclo, e é um domínio próprio.

**Não existe modelo de conta bancária.** `ContasBancariasViewSet` é apenas um alias
que faz CRUD de `CartaoCredito`. Se um dia houver conta bancária de verdade,
`Carteira` seria irmã dela, não filha.

**Multi-moeda.** `Ativo.moeda` existe e é sempre `BRL` na prática. Carteira em USD
exigiria câmbio para consolidar, e some com a agregação simples que tudo aqui assume.

**Filtro por subconjunto de carteiras** (duas das três). O backend aceitaria
`?carteira=1&carteira=2` com `getlist` sem custo, mas a interface de multi-seleção é
um padrão de acessibilidade novo, ainda não registrado no `A11Y-DECISIONS.md`. O
seletor atual é o `<select>` com "Todas as carteiras", o mesmo padrão já usado no
filtro de classes em Meus Ativos.
