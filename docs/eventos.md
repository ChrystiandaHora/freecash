# Eventos Fora do Orçamento Mensal

## 1. Visão Geral e Propósito

O módulo de **Eventos Fora do Orçamento** permite cadastrar, planejar e controlar gastos de grandes ocasiões extraordinárias (como viagens, reformas da casa, casamentos ou festas) mantendo duas respostas financeiras essenciais íntegras:

1. **Liquidez Real e Caixa:** O dinheiro gasto deduz fielmente do saldo bancário e da liquidez (`saldo_liquidez_ate`, Horizonte de Saldos).
2. **Orçamento e Médias do Dia a Dia:** Quando o evento está configurado com `fora_dos_relatorios=True`, suas despesas **são automaticamente excluídas** do Dashboard mensal, séries históricas de 6 meses, DRE anual consolidado e cálculo do custo de vida médio que calibra as Metas de reserva de emergência e independência financeira.

---

## 2. Decisões Arquiteturais e Regras de Negócio

### 2.1 Modelo `Evento` (`backend/core/models.py`)
- Herda de `AuditoriaModel` (`criada_em`, `atualizada_em`).
- Campos:
  - `usuario`: isolamento multi-tenant (`ForeignKey` para o usuário).
  - `nome`: descrição do evento (ex.: "Viagem Santiago", "Reforma Sala").
  - `inicio`: data de início (obrigatória).
  - `fim`: data de término (opcional).
  - `orcamento`: teto orçamentário planejado em R$ (opcional).
  - `fora_dos_relatorios`: booleano (padrão `True`), indicando se os gastos são isolados dos relatórios mensais.
- Ordenação padrão: `['-inicio', 'nome']`.

### 2.2 Relacionamento com `Conta`
- `Conta.evento`: chave estrangeira `ForeignKey(Evento, on_delete=models.PROTECT, null=True, blank=True)`.
  - A proteção `PROTECT` garante integridade: um evento com despesas vinculadas não pode ser excluído acidentalmente no banco de dados.
- **Validações de Domínio (`Conta.clean()`):**
  - O lançamento vinculado ao evento deve ser estritamente uma despesa (`tipo == 'D'`).
  - O lançamento deve ser direto (Pix, boleto, débito ou dinheiro), e **não** pode ser uma fatura de cartão de crédito (`cartao is None`).
  - O usuário da conta deve coincidir com o proprietário do evento (`usuario == evento.usuario`).

### 2.3 `ContaQuerySet.do_orcamento()`
- O `ContaManager` estende `models.Manager.from_queryset(ContaQuerySet)`.
- O método `.do_orcamento()` aplica:
  ```python
  def do_orcamento(self):
      return self.exclude(evento__fora_dos_relatorios=True)
  ```
- Todas as consultas de períodos analíticos (totais de competência e realizadas, séries temporais, gráficos de categoria, DRE e comparativos) chamam `.do_orcamento()`.
- O cálculo de saldo em caixa (`saldo_liquidez_ate`) continua usando `Conta.objects` irrestrito, garantindo que a dedução do dinheiro seja 100% real.

### 2.4 Backup e Restauração (.fcbk)
- O modelo `Evento` foi registrado no dicionário de prioridades de `get_backupable_models()` com prioridade `3.5` (entre `Categoria` e `Conta`), garantindo restauração ordenada sem falhas de integridade referencial.

---

## 3. Endpoints da API REST

| Método | Endpoint | Descrição |
|---|---|---|
| `GET` | `/api/financeiro/eventos/` | Lista os eventos do usuário com KPIs pré-calculados (`total_gasto`, `total_previsto`, `saldo_restante`, `qtd_lancamentos`). |
| `POST` | `/api/financeiro/eventos/` | Cadastra um novo evento. |
| `GET` | `/api/financeiro/eventos/:id/` | Detalhes do evento. |
| `PUT` | `/api/financeiro/eventos/:id/` | Atualização do evento. |
| `DELETE` | `/api/financeiro/eventos/:id/` | Exclusão do evento (protegido contra eventos com despesas vinculadas). |
| `GET` | `/api/financeiro/eventos/:id/resumo/` | Resumo completo com KPIs, distribuição por categorias e extrato de despesas vinculadas. |
| `GET` | `/api/dashboard/` | Retorna o payload `gastos_fora_orcamento` com total e lista de eventos com gastos no mês. |

---

## 4. Frontend e Interface de Usuário

- **Rotas:**
  - `/eventos`: tela principal com grid de cards de eventos, KPIs consolidados globais, barras de progresso do orçamento e modal de criação/edição (`EventoFormModal`).
  - `/eventos/:id`: tela de detalhe com KPIs específicos do evento, gráfico/barras de distribuição por categoria e tabela interativa de lançamentos com ações de quitação direta e edição.
- **Navegação:**
  - Adicionado ao menu "Financeiro" em ordem alfabética estrita (`/eventos`).
  - Ajuda contextual cadastrada em `src/config/helpContent.js`.
- **Formulário de Contas a Pagar (`ContaPagarForm.jsx`):**
  - Campo seletor de eventos para despesas diretas.
  - Suporta preenchimento automático via parâmetro de busca na URL (`/contas-pagar/novo?evento=:id`).
- **Listagens de Contas a Pagar e Transações:**
  - Badge visual com ícone `Sparkles` identificando as contas atreladas a eventos.
- **Dashboard:**
  - Banner informativo amigável quando há gastos extraordinários no mês corrente, com link direto para `/eventos`.
