# Ativos e a árvore de classificação

Referência para quem for mexer no cadastro de ativo, na hierarquia ANBIMA ou no
serializer que os expõe. Para preço médio e cotação, ver
[cotacoes-e-preco-medio.md](cotacoes-e-preco-medio.md); para custódia, ver
[carteiras.md](carteiras.md).

---

## O ativo é único por ticker, e isso é a base de tudo

```python
class Meta:
    unique_together = ("usuario", "ticker")
```

PETR4 é PETR4, esteja em quantas corretoras estiver. Dessa decisão decorrem três coisas
que aparecem em todo o módulo:

- **uma série de `Cotacao` por papel** — o mercado não tem dois preços para o mesmo ativo;
- **um preço médio consolidado**, que é o número fiscal, apurado por CPF;
- **a custódia mora na transação**, não no ativo.

Tentar cadastrar o mesmo ticker duas vezes é o erro mais comum de quem acabou de criar a
segunda carteira. `AtivoSerializer.validate_ticker` devolve 400 com a mensagem que aponta
o caminho certo — lançar uma ordem escolhendo a carteira. Sem essa validação a colisão
chegava ao banco como `IntegrityError` e saía como **500 opaco**, porque `usuario` não
está entre os campos do serializer e o DRF não monta o `UniqueTogetherValidator` sozinho.

---

## Três níveis, e o ativo pendura no terceiro

```
ClasseAtivo        Renda Fixa, Renda Variável, Multimercado, Cambial, Criptoativos
  └── CategoriaAtivo    Pós-fixado, Ações, FIIs, ETFs, Moedas Digitais…
        └── SubcategoriaAtivo   Tesouro Selic, CDB/RDB, FII de Tijolo, Bitcoin…
              └── Ativo         PETR4, HGLG11, CDB-BTG
```

A hierarquia segue a ANBIMA, mas é **por usuário e editável** — cada nível tem FK para
`usuario`, e a tela `/investimentos/classes` permite criar, renomear e remover. Não é
tabela de sistema.

`Ativo.subcategoria` é `null=True` com `on_delete=SET_NULL`: apagar uma subcategoria não
pode levar o ativo junto. O ativo fica sem classificação e aparece como "Sem Classe" nos
gráficos de alocação — visível, e recuperável.

**A árvore inteira nasce com o usuário.** `criar_classificacao_padrao`, no `post_save` de
`User`, cria 5 classes, as categorias e 27 subcategorias — mais a Carteira Padrão. Sem
isso, o primeiro cadastro de ativo pediria ao usuário que montasse uma taxonomia antes de
registrar a primeira compra.

Nos testes, isso significa que o usuário já vem com a árvore montada: usar `get_or_create`
para classes e categorias, nunca `create`, ou o `unique_together` estoura.

---

## `DetalheRendaFixa` é uma tabela à parte, com payload achatado

Emissor, indexador, taxa e vencimento só existem para renda fixa. Deixá-los em `Ativo`
significaria quatro colunas permanentemente vazias para toda ação, FII e ETF — a maioria
dos registros. Por isso são um `OneToOne`.

Mas a API **não** expõe esse aninhamento. `AtivoSerializer` declara os quatro como campos
soltos e faz a ponte em três lugares:

| Método | O que faz |
|---|---|
| `to_representation` | Injeta os quatro no payload plano de saída |
| `create` | Extrai do `validated_data` e cria o `DetalheRendaFixa` se algum vier preenchido |
| `update` | `update_or_create`, para o detalhe nascer numa edição posterior |

O motivo é contrato: o payload continuou idêntico ao de antes da separação, e o frontend
não soube que a tabela foi dividida. Quem mexer em `DETALHE_RENDA_FIXA_FIELDS` precisa
mexer nos três.

---

## Os campos calculados são cache, não entrada

`quantidade` e `preco_medio` **não são editáveis** — estão em `read_only_fields`. Eles são
reescritos por `recalcular_ativo` a cada transação salva, editada ou removida. Um caminho
de escrita que os gravasse direto seria sobrescrito na transação seguinte, sem aviso.

A posição por carteira segue a mesma regra em `PosicaoCarteira`, com uma exceção
importante: ali `meta_porcentagem` é **intenção do usuário**, e o recálculo não a toca —
escreve só os campos de cache, com `update_fields`. É por isso que a linha nunca é apagada
quando a posição zera.

`valor_total`, `cotacao_atual`, `valor_total_atual`, `rentabilidade` e
`rentabilidade_percentual` são properties do modelo, calculadas na leitura.

---

## `historico_cotacoes` custa caro

`AtivoSerializer.get_historico_cotacoes` busca **`LIMITE_HISTORICO_COTACOES` cotações por
ativo** (hoje 45, ~2 meses de pregão), em toda serialização. Numa lista de 20 ativos são
20 consultas extras.

Foi o que motivou enxugar o payload do dashboard, que serializava quatro conjuntos de
ativos — lista completa, top 5 por valor, top rentabilidade e próximos vencimentos — sem
que nenhuma tela os lesse. Antes de acrescentar `AtivoSerializer(many=True)` em qualquer
endpoint, confira se a tela realmente consome.

É também a razão de o gráfico comparativo de Meus Ativos ter endpoint próprio
(`GET /api/investimentos/ativos/historico-cotacoes/`) em vez de ler este campo: a tabela
re-renderiza a cada tecla digitada no filtro, e carregar a série de todo mundo junto dela
pesaria em toda renderização.

---

## O gráfico de Meus Ativos não segue os filtros da tabela

Deliberado, e a fonte de confusão mais provável da tela. A busca por texto e o filtro de
classe mexem **só na tabela**. O gráfico tem seleção própria: abre com os 2 maiores e os 2
menores retornos e o usuário acrescenta ou remove ativos pelo campo de busca dele.

O que escopa o gráfico é a **aba** (Ativos/Arquivados) e a **carteira** — trocar qualquer
uma das duas refaz a seleção do zero, porque muda a identidade do universo.

Duas restrições explicam o desenho, e ambas são regra, não gosto:

- **Teto de 8 séries.** A paleta categórica validada tem 8 tons e 4 tracejados. Como 8 e 4
  não são coprimos, a nona linha repetiria cor **e** traço da primeira — sem canal nenhum
  que as separasse, o que reprova na SC 1.4.1. Acima da paleta não há par distinto a
  oferecer, então a saída é escolher o que ver.
- **Ativo liquidado fica fora do ranking.** `recalcular_ativo` zera o preço médio quando a
  quantidade zera, e `rentabilidade_percentual` devolve 0 como guarda quando não há valor
  investido — indistinguível de um papel que empatou. O critério do ranking é
  `preco_medio > 0`; sem ele, um ativo vendido ganharia a ponta de baixo e sumiria na hora
  de desenhar. Quando ninguém é rankeável (a aba Arquivados costuma ser assim), a seleção
  cai nos primeiros por ticker e a leitura útil ali passa a ser «Preço (R$)».

O eixo do Retorno é a cotação medida contra o preço médio, então o último ponto de cada
linha é o mesmo número da coluna «Retorno» da tabela — há teste travando essa igualdade em
`frontend/src/lib/cotacoesSerie.test.js`. O preço médio aplicado é o de **hoje**, inclusive
nos pregões passados: uma compra no meio do período mudou o preço médio de verdade, e a
linha não reflete isso. Só o último ponto é exato.

---

## Arquivar, não excluir

`Ativo.ativo = False` tira o papel das listas e dos cálculos sem apagar o histórico. Os
dashboards filtram por `ativo=True`.

Excluir de verdade leva as transações em cascata, e com elas a rentabilidade apurada. Para
um papel vendido por inteiro, o caminho é deixar a posição zerada — ela some das telas de
posição e continua no histórico de ordens.

---

## O que ficou de fora, e por quê

**A subcategoria não restringe nada.** Nada impede cadastrar PETR4 sob "Tesouro Selic". A
árvore classifica para efeito de gráfico e de meta; ela não valida.

**Não há validação de ticker contra a B3.** Um ticker inexistente é aceito e simplesmente
nunca recebe cotação — aparece na lista de erros da atualização. Validar exigiria uma
chamada externa no cadastro, e falha de rede impediria registrar a compra.

**`Ativo.moeda` não é usada.** Existe, aceita qualquer valor, e nenhum cálculo a consulta.
Um ativo em dólar entra no patrimônio pelo valor nominal. Ver a seção de câmbio em
[cotacoes-e-preco-medio.md](cotacoes-e-preco-medio.md).

**CNPJ só serve para a CVM.** É o que casa o ativo com o fundo nos dados abertos; para
ações e FIIs fica vazio. É normalizado para 14 dígitos no `save`.
