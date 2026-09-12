# Cotações e preço médio

Referência para quem for mexer em atualização de cotação, integração com fonte externa
ou no cálculo de preço médio. São dois números diferentes que a tela mostra lado a lado,
e confundi-los é o erro mais fácil de cometer aqui.

---

## Os dois números

| | O que é | De onde vem | Muda quando |
|---|---|---|---|
| **Preço médio** | Quanto o investidor **pagou** | Calculado das transações | Ele compra |
| **Cotação** | Quanto o mercado **paga hoje** | Fonte externa | O mercado se move |

`valor_investido` usa o primeiro; `valor_total_atual`, o segundo. A diferença entre eles
é a rentabilidade. Nenhum dos dois é editável à mão — o preço médio é derivado, e a
cotação é do mercado.

---

## O preço médio é fiscal, não contábil

`recalcular_ativo` ([calculators.py](../backend/investimento/calculators.py)) varre o
histórico ordenado e aplica a regra da Receita:

- **Compra** soma quantidade e custo. O custo inclui as taxas: corretagem faz parte do
  que se pagou pelo papel.
- **Venda** abate quantidade e custo **na proporção**, e **não altera o preço médio**.
  Vender metade da posição não muda quanto custou a outra metade.
- **Provento** não mexe em nada. É entrada de caixa, não aquisição.
- **Transferência entre carteiras** é ignorada. Mudar de corretora não é comprar nem
  vender — ver [carteiras.md](carteiras.md).

O número resultante é o **do CPF**, não o da corretora: no Brasil o preço médio é apurado
no conjunto. É por isso que `Ativo.quantidade` e `Ativo.preco_medio` são consolidados, e
a posição por custódia mora em `PosicaoCarteira`.

`Ativo.preco_medio` tem 4 casas decimais. Cento e cinquenta cotas a 33,3333 fecham em
4.999,995, e não em 5.000 — a diferença é do arredondamento do campo e some no
`_centavos` de quem consome. Os testes comparam esses números em centavos, de propósito.

---

## Três fontes, cada uma para um tipo de ativo

| Fonte | Para quê | Como |
|---|---|---|
| **TradingView** | Ações, FIIs, ETFs da B3 | `scanner.tradingview.com/brazil/scan`, em **lote** |
| **CVM** | Fundos de investimento | ZIP mensal de dados abertos, casado por CNPJ |
| **Yahoo Finance** | Um ativo por vez, sob demanda | `query1.finance.yahoo.com`, 30 dias de histórico |

Tudo por `urllib` da biblioteca padrão — **não há dependência de `yfinance`** nem de
cliente de API. São três chamadas HTTP com parsing próprio, e isso é deliberado: a
alternativa seria carregar um SDK inteiro para fazer um GET.

`atualizar_cotacoes` chama TradingView em lote primeiro. Quem não aparecer lá mas tiver
CNPJ cai na CVM; quem não tiver nem uma coisa nem outra vira erro na lista devolvida — a
atualização **não** aborta no primeiro problema, ela reporta o que falhou e segue.

---

## O escopo por usuário não é detalhe de performance

`atualizar_cotacoes(usuario=None)` aceita rodar sobre todos os ativos — é assim que o
comando `update_quotes` funciona. Mas o endpoint **sempre** passa `usuario=request.user`.

Sem isso, um usuário clicando "atualizar cotações" dispararia consultas com os tickers de
todo mundo, e a lista de erros devolvida a ele nomearia papéis de outras pessoas. É
vazamento de dado por mensagem de erro, e o cuidado está anotado no código.

---

## Normalização de ticker

`_normalize_to_tradingview_symbol` resolve três formatos que convivem na base:

- `NASDAQ:AAPL` — já tem bolsa, passa direto
- `PETR4.SA` — sufixo do padrão Yahoo, é removido
- `PETR4` — recebe o prefixo `BMFBOVESPA:`

O caso do **fracionário** é o que exige atenção: `PETR4F` é o mesmo papel de `PETR4`, e a
cotação é idêntica. O código consulta o lote padrão para o fracionário — o mercado não
tem dois preços para o mesmo ativo.

---

## Uma cotação por ticker e por dia

`Cotacao` tem `unique_together = ("ativo", "data")` e é FK de `Ativo`, não de
`PosicaoCarteira`. A carteira não muda o preço de mercado do papel.

Isso é o que sustenta a decisão de as carteiras ficarem na transação: se o ativo fosse
duplicado por corretora, cada cópia teria a própria série de cotação, e a atualização
faria **duas chamadas externas pelo mesmo papel**.

A gravação usa `update_or_create`, então reexecutar a atualização no mesmo dia
sobrescreve em vez de duplicar.

---

## Falha de fonte externa não pode quebrar a tela

`cotacao_atual` devolve `None` quando não há cotação, e `valor_total_atual` cai para o
**custo de aquisição**. É o fallback conservador: sem preço de mercado, o sistema mostra
o que foi pago, e a rentabilidade aparece como zero em vez de como prejuízo.

O mesmo vale no snapshot histórico, com uma diferença que já causou erro: ali o fallback
é o custo **daquela carteira**, não o preço médio consolidado. Usar o consolidado
atribuiria à custódia um custo que não é o dela.

---

## O que ficou de fora, e por quê

**Não há atualização automática agendada.** Existe o comando `update_quotes` para cron,
mas nada o dispara por padrão. Bater em três serviços de terceiros de hora em hora, sem
contrato, convida bloqueio.

**Não há histórico intradiário.** `Cotacao.data` é `DateField`. O produto é
acompanhamento patrimonial, não trading.

**Não há câmbio.** `Ativo.moeda` existe e é sempre `BRL` na prática. Um ativo em dólar
seria somado ao patrimônio pelo valor nominal, sem conversão — por isso carteira em
moeda estrangeira está fora de escopo até haver taxa de câmbio no sistema.

**As três integrações não têm teste com resposta gravada.** É a maior lacuna de cobertura
do app `investimento`: os serviços mais descobertos são justamente os que fazem I/O
externo, e testá-los exige fixtures de resposta que ninguém gravou.
