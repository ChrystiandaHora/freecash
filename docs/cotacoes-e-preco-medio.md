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

## Atualização periódica do telão

O telão de investimentos (`/investimentos/telao`) pede uma sincronização a cada 15
minutos em `POST /api/investimentos/telao/sincronizar/`. **Quem decide se a fonte é
consultada é o servidor** (`services/sincronizacao_mercado.py`), e não a tela. Várias
telas, abas ou recarregamentos não multiplicam requisições, e um bloqueio da fonte faz
o servidor inteiro recuar. As guardas, na ordem em que são avaliadas:

1. **Pregão.** Fim de semana, feriado da B3 ou horário fora das 09:55–18:30
   (Brasília) não têm consulta à fonte. A resposta é `fora_do_pregao`, com o `motivo`
   (por exemplo, "Finados") e `proxima_em` apontando para a próxima abertura. Os
   feriados ficam em `services/calendario_b3.py`, conferido contra o calendário
   oficial de 2026: datas fixas, mais Carnaval, Sexta-feira Santa e Corpus Christi
   calculados a partir da Páscoa. A Quarta-feira de Cinzas só abre às 13h. Antes do
   calendário, um feriado contava como pregão aberto, e a consulta gravava como
   cotação do dia o último fechamento repetido.
2. **Backoff global.** Um 403/429 do TradingView vira `TradingViewLimitado` e grava
   `backoff` no cache `mercado` (`services/limite_fonte.py`). A pausa dura o maior
   entre `Retry-After` e 30 minutos, com teto de 6 horas. É global porque o bloqueio é
   do IP, não do usuário. Vale também para o botão «Atualizar Cotações»: durante a
   pausa ele não consulta o TradingView, e se for ele quem tomar o 429, a pausa é
   gravada do mesmo jeito.
3. **Cooldown por usuário.** Uma consulta a cada 15 minutos (`em_cache` no meio tempo).
4. **Single-flight.** `cache.add` de um lock por usuário: duas telas que chegam juntas
   não disparam duas consultas.

Passadas as guardas, roda o mesmo passo do botão «Atualizar Cotações»
(`_atualizar_b3`). Se a fonte falhar por outro motivo (timeout, 5xx), a resposta é
`falhou`, sem gravar o cooldown, e o próximo pedido sai em 5 minutos. Há duas
diferenças em relação ao botão. A CVM roda no máximo **uma vez por dia**: o
informe é D-1 e vem num ZIP mensal pesado. A guarda é por usuário, então com N
usuários com fundos o ZIP é baixado N vezes por dia, o que é aceitável na escala do
projeto. A marca é gravada antes da consulta: se a CVM falhar, ela só é tentada de novo
no dia seguinte. O Yahoo fica **de fora**: é uma requisição
por ticker, e a série histórica não muda durante o pregão.

O cache `mercado` é `DatabaseCache` na mesma tabela do throttle. O `default` é
LocMem, por processo, e com três workers do gunicorn cada um teria o seu cooldown. As
guardas comparam o instante gravado no cache, não só a expiração da chave, para que
os testes possam injetar `agora`.

A tela agenda o próximo pedido pelo `proxima_em` da resposta, com 5 s de folga e teto
de 15 minutos. Sem a folga, um cliente que chegasse um instante antes do fim do
cooldown perderia o ciclo inteiro. Os dados anteriores ficam na tela enquanto os
novos chegam, e uma falha só muda o aviso na faixa do topo.

---

## O que ficou de fora, e por quê

**Não há atualização agendada no servidor.** Existe o comando `update_quotes` para
cron, mas nada o dispara por padrão. Bater em três serviços de terceiros de hora em
hora, sem contrato, convida bloqueio. A única atualização periódica é a do telão, que
só acontece com ele aberto e passa pelas guardas acima.

**Não há histórico intradiário.** `Cotacao.data` é `DateField`. O produto é
acompanhamento patrimonial, não trading.

**Não há câmbio.** `Ativo.moeda` existe e é sempre `BRL` na prática. Um ativo em dólar
seria somado ao patrimônio pelo valor nominal, sem conversão — por isso carteira em
moeda estrangeira está fora de escopo até haver taxa de câmbio no sistema.

**As três integrações não têm teste com resposta gravada.** É a maior lacuna de cobertura
do app `investimento`: os serviços mais descobertos são justamente os que fazem I/O
externo, e testá-los exige fixtures de resposta que ninguém gravou.
