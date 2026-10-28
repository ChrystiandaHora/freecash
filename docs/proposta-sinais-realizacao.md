# Proposta: sinais de realização e rebalanceamento

Referência para quem for mexer no sinal que avisa, por posição, quando vender parte de
um ativo para voltar à meta da carteira. Registra a regra escolhida, **de onde ela
vem** e o que ficou de fora. Decisões tomadas em 2026-10-28.

---

## O que o sinal é, e o que não é

O sinal aplica uma regra de rebalanceamento sobre as metas que o **próprio usuário**
declarou em `PosicaoCarteira.meta_porcentagem`. Não é recomendação de investimento, e
o texto da tela precisa deixar isso claro: o sistema diz "esta posição saiu da faixa
que você definiu", não "venda PETR4".

O perfil atendido é um só: **longo prazo com rebalanceamento**. Escolas de trading
(alvo de +20–25% e stop de -7–8%, de O'Neil) foram consideradas e descartadas — no
longo prazo, um stop de 8% venderia toda correção comum.

---

## Por que o gatilho é desvio de peso, e não percentual de lucro

Nenhuma fonte de longo prazo usa "lucro de X% sobre o preço médio" como gatilho. Os
estudos de rebalanceamento medem o **desvio do peso** em relação à meta — e o lucro já
está dentro desse número: o ativo que valorizou é o que ganhou peso. Rebalancear por
banda *é* realizar lucro, de forma sistemática e sem um alvo arbitrário.

Por isso o peso é calculado **a mercado** (quantidade × cotação), e não pelo custo. O
`BalanceamentoAPIView` atual usa `valor_investido`, que serve para responder "onde
aportar", mas esconde exatamente a valorização que dispara a realização. O peso a
mercado entra **ao lado** do peso por custo, sem substituí-lo: trocar mudaria o plano
de aportes que a tela já mostra.

---

## A banda: regra 5/25

O sinal acende quando o peso a mercado passa da meta por mais que **o menor entre 5
pontos percentuais e 25% da própria meta** (Swedroe, adotada no Bogleheads). Combina o
limiar de 5 p.p. do estudo da Vanguard com uma banda relativa que funciona para metas
pequenas — e meta por ativo dentro de uma carteira quase sempre é pequena.

| Meta | Banda | Sinal acima de |
|---|---|---|
| 40% | 5 p.p. | 45% |
| 10% | 2,5 p.p. | 12,5% |
| 4% | 1 p.p. | 5% |

A venda sugerida leva a posição **de volta à meta**, não à borda da banda. A
quantidade é arredondada para baixo em cotas inteiras; se o excesso não chega a uma
cota, não há sinal — não existe ação possível.

A alternativa era a banda relativa de 20% de Daryanani. Ela foi desenhada para
assessores que olham a carteira a cada duas semanas, e acende mais tarde nas metas
grandes.

---

## Os sinais

| Sinal | Quando | O que a tela diz |
|---|---|---|
| **Vender com lucro** | Peso acima da banda, cotação ≥ preço médio | Vender N cotas; mostra o lucro realizado |
| **Vender com prejuízo** | Peso acima da banda, cotação < preço médio | Vender N cotas; o prejuízo compensa lucros futuros do mesmo tipo |
| **Revisar queda** | Cotação ≥ 20% abaixo do preço médio, sem sobrepeso | "Revise a tese antes de reforçar ou vender" |

A **queda relevante** também vale junto com sobrepeso: o sinal continua sendo de venda,
com a marca de queda ligada.

O lucro é sempre contra o preço médio **consolidado** (`Ativo.preco_medio`), que é o do
CPF e o que vai para a declaração. O sobrepeso é **da carteira**: a venda sai da
custódia que está acima da meta. Taxas da venda não entram no resultado — o sistema
não as conhece antes de a ordem existir.

### O conflito entre stop e rebalanceamento

Num perfil de rebalanceamento, o ativo que cai fica **abaixo** da meta, e a regra manda
comprar mais. Um stop clássico manda vender. Os dois na mesma tela dariam "compre" e
"venda" ao mesmo tempo.

A queda relevante resolve isso sem virar stop: ela não manda vender, manda **revisar**,
e suspende a sugestão de aporte naquele ativo até o usuário confirmar. Os 20% são a
convenção de mercado para "mercado em baixa", não resultado de estudo — Kaminski & Lo
mostram que stop só agrega valor quando há momentum, e nenhuma fonte de longo prazo
sustenta um percentual fixo.

### O que não gera sinal

- **Renda fixa**: não tem cotação de mercado, e o preço médio não mede valorização.
- **Sem cotação**: o fallback de `valor_total_atual` é o custo, e com ele o desvio
  seria só o de aquisição.
- **Meta zero**: lida como "sem meta", não como "zerar a posição". Do contrário, quem
  ainda não configurou metas veria sinal de venda em todos os ativos.

---

## Imposto de renda

A isenção de ações é sobre o **valor vendido no mês** (R$ 20 mil), não sobre o lucro. O
sinal soma as vendas de ações já registradas no mês com a venda sugerida e, se passar
do limite, informa quantas cotas cabem na isenção — para o usuário poder dividir a
venda entre dois meses.

Uma venda **com prejuízo** também pode estourar o limite, e com isso tornar tributáveis
as vendas lucrativas já feitas no mês. Por isso a isenção é avaliada para qualquer
venda, não só para as com lucro.

FII é sempre tributável (20%). ETF é tratado como tributável: as fontes divergiam entre
15% com isenção e 17,5% sem, e errar desse lado só mostra um aviso a mais.

O sistema só enxerga vendas registradas nele; uma venda em corretora não cadastrada
fica fora da soma, e o aviso diz isso.

### O tipo fiscal

Classe, categoria e subcategoria são nomes livres por usuário, e o ticker não resolve
(final 11 é FII, ETF ou unit). O `Ativo` ganha um campo de **tipo fiscal** — ação, FII,
ETF, BDR, fundo, renda fixa, outro — que é o que o sinal consulta.

---

## Fases

1. **Cálculo** — `investimento/sinais.py`, função pura sem I/O, com testes.
2. **Configuração e API** — campo de tipo fiscal no `Ativo`, peso a mercado no
   balanceamento, sinais no payload e um endpoint leve que conta e lista.
3. **Frontend** — badge com texto (não só cor) em Meus Ativos, Balanceamento e Detalhe
   do Ativo, contador na barra do topo, valores atrás do olho de privacidade.
4. **Central de alertas** (opcional) — dispensar/adiar, só se o contador incomodar.

---

## Fontes

- Vanguard (2010), *Best Practices for Portfolio Rebalancing* — 5 p.p., monitoração
  anual ou semestral; não há frequência ou limiar ótimo.
- Larry Swedroe, regra 5/25 — *Think, Act, and Invest Like Warren Buffett*.
- Gobind Daryanani (2008), *Opportunistic Rebalancing*, Journal of Financial Planning.
- Kaminski & Lo (2014), *When Do Stop-Loss Rules Stop Losses?*, Journal of Financial
  Markets 18.
- William O'Neil, *How to Make Money in Stocks* — regras de trading, descartadas.
- Benjamin Graham (1976), *Medical Economics* — +50% ou dois anos, regra de giro.
- Peter Lynch, *One Up on Wall Street* — contra vender só porque subiu.
- Isenção de R$ 20 mil — Lei 11.033/2004; MP 1.303 (alíquota única) não aprovada.
