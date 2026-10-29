/** Tours das telas de Financeiro (dashboard, contas, cartões, receitas, transações, relatórios). Contrato em `./index.js`. */

export const toursDeFinanceiro = {
  '/dashboard': [
    {
      titulo: 'Seu painel financeiro',
      texto: 'O resumo de um mês: quanto entrou, quanto saiu, onde você mais gastou e como os meses seguintes devem fechar.',
    },
    {
      alvo: 'dashboard-periodo',
      titulo: 'Escolha o mês',
      texto: 'Todo o painel muda junto. Em Personalizado você abre qualquer mês e ano, inclusive futuros, para ver o que já está previsto.',
    },
    {
      alvo: 'dashboard-resumo',
      titulo: 'Receitas, despesas e saldo',
      texto: 'O percentual compara com o mês anterior. No cartão de saldo aparece também a taxa de poupança: quanto da receita sobrou.',
    },
    {
      alvo: 'dashboard-fora-orcamento',
      titulo: 'Gastos fora do orçamento',
      texto: 'Despesas de eventos, como viagens, ficam fora dos números acima para não distorcer suas médias, mas continuam saindo do caixa.',
    },
    {
      alvo: 'dashboard-fluxo-diario',
      titulo: 'Fluxo de caixa do mês',
      texto: 'Mostra dia a dia o que entrou e o que saiu, para você ver em que parte do mês o dinheiro aperta.',
    },
    {
      alvo: 'dashboard-maiores-gastos',
      titulo: 'Onde o dinheiro foi',
      texto: 'As categorias que mais pesaram no mês, com o gasto médio por dia logo abaixo. É o primeiro lugar para procurar cortes.',
    },
    {
      alvo: 'dashboard-projecao',
      titulo: 'Projeção de seis meses',
      texto: 'Dois meses antes e três depois do escolhido, com receitas, despesas e o saldo de cada mês. Mostra cedo um mês que vai fechar no vermelho.',
    },
  ],

  '/relatorios': [
    {
      titulo: 'Relatórios financeiros',
      texto: 'Sua vida financeira de um ano organizada como uma empresa faz: DRE, fluxo de caixa e a sazonalidade dos gastos.',
    },
    {
      alvo: 'relatorios-ano',
      titulo: 'Escolha o ano',
      texto: 'Receitas, despesas e proventos passam a mostrar o ano escolhido, até três anos atrás. A rentabilidade e o mapa de calor (últimos 6 meses) não mudam.',
    },
    {
      alvo: 'relatorios-resumo',
      titulo: 'Os números do período',
      texto: 'Receitas, despesas e proventos do ano, ao lado da rentabilidade acumulada da carteira até hoje.',
    },
    {
      alvo: 'relatorios-secoes',
      titulo: 'DRE, fluxo de caixa e sazonalidade',
      texto: 'Clique no título de uma seção para abri-la. O mapa de calor mostra em que dias da semana você mais gasta.',
    },
    {
      alvo: 'relatorios-imprimir',
      titulo: 'Imprimir ou salvar em PDF',
      texto: 'Abre a impressão com as três seções completas, mesmo as fechadas. Escolha "Salvar como PDF" para guardar o arquivo.',
    },
  ],

  '/contas-pagar': [
    {
      titulo: 'Contas a Pagar',
      texto: 'Tudo o que você tem para pagar, com o status calculado pelo vencimento: atrasada, vence em breve, pendente ou paga.',
    },
    {
      alvo: 'contas-pagar-nova',
      titulo: 'Cadastre uma conta',
      texto: 'Lance uma despesa com valor, vencimento e categoria. Ela entra aqui como pendente até você registrar o pagamento.',
    },
    {
      alvo: 'contas-pagar-lote',
      titulo: 'Várias contas de uma vez',
      texto: 'Abre uma planilha para lançar até 20 contas seguidas, útil no início do mês ou ao passar as contas fixas.',
    },
    {
      alvo: 'contas-pagar-resumo',
      titulo: 'Pendente, atrasado e pago',
      texto: 'Os três números somam só as contas que o filtro está mostrando. Mude o período e eles acompanham.',
    },
    {
      alvo: 'contas-pagar-vistas',
      titulo: 'Kanban ou tabela',
      texto: 'Duas formas de ver as mesmas contas. O filtro vale para as duas, e o app lembra qual você usou por último.',
    },
    {
      alvo: 'contas-pagar-quadro',
      titulo: 'Quadro por vencimento',
      texto: 'Começa no mês atual; mude o período em Filtrar por. Arraste um card para Pagas para registrar o pagamento.',
    },
    {
      alvo: 'contas-pagar-tabela',
      titulo: 'Tabela de contas',
      texto: 'Começa no mês atual; o funil de cada coluna muda o filtro. Na linha você paga, desfaz o pagamento, edita ou exclui.',
    },
  ],

  '/contas-pagar/lote': [
    {
      titulo: 'Cadastro em lote',
      texto: 'Uma planilha para lançar várias contas a pagar de uma só vez, sem abrir um formulário para cada uma.',
    },
    {
      alvo: 'contas-pagar-lote-linhas',
      titulo: 'Quantas linhas',
      texto: 'Escolha o tamanho da planilha. Atenção: diminuir o número de linhas descarta o que estava digitado nas últimas.',
    },
    {
      alvo: 'contas-pagar-lote-tabela',
      titulo: 'Preencha as contas',
      texto: 'Use Tab para pular de célula em célula. Linhas em branco são ignoradas; sem categoria, entra a categoria padrão.',
    },
    {
      alvo: 'contas-pagar-lote-pagas',
      titulo: 'Contas já pagas',
      texto: 'Ligue para lançar todas como pagas, por exemplo ao registrar despesas que já saíram da conta.',
    },
    {
      alvo: 'contas-pagar-lote-salvar',
      titulo: 'Salve o lote',
      texto: 'Grava as linhas preenchidas e volta para Contas a Pagar. A lista abre no mês atual; mude o filtro para ver as de outros meses.',
    },
  ],

  '/contas-kanban': [
    {
      titulo: 'Kanban de contas',
      texto: 'As contas do mês atual em colunas pelo prazo de vencimento, para ver de relance o que precisa ser pago primeiro.',
    },
    {
      alvo: 'contas-kanban-resumo',
      titulo: 'O mês em números',
      texto: 'Quanto ainda falta pagar, quanto já está atrasado e quantas contas do mês já foram quitadas.',
    },
    {
      alvo: 'contas-kanban-quadro',
      titulo: 'Colunas por prazo',
      texto: 'A coluna vem do vencimento e muda sozinha com os dias. Mover entre colunas não altera a data; só soltar em Pagas paga.',
    },
    {
      alvo: 'contas-kanban-dica',
      titulo: 'Editar e outras ações',
      texto: 'Clique no card para editar. Para outros meses, filtros ou exclusões, use a tela Contas a Pagar.',
    },
  ],

  '/cartoes': [
    {
      titulo: 'Meus Cartões',
      texto: 'Seus cartões lado a lado, com quanto há em compras ainda não pagas em cada um e quanto do limite ainda está livre.',
    },
    {
      alvo: 'cartoes-resumo',
      titulo: 'Todos os cartões somados',
      texto: 'Limite total, quanto já está comprometido em faturas e quanto crédito ainda resta, juntando todos os cartões.',
    },
    {
      alvo: 'cartoes-lista',
      titulo: 'Um bloco por cartão',
      texto: 'Os cartões são cadastrados em Financeiro > Pagamentos; depois de criados, aparecem aqui sozinhos.',
    },
    {
      alvo: 'cartoes-limite',
      titulo: 'Uso do limite',
      texto: 'O medidor fica verde até 70% do limite, amarelo até 90% e vermelho acima disso.',
    },
    {
      alvo: 'cartoes-fatura',
      titulo: 'Compras recentes',
      texto: 'Abra para ver as 8 compras mais recentes deste cartão, de qualquer fatura.',
    },
  ],

  '/receitas': [
    {
      titulo: 'Receitas',
      texto: 'Suas entradas de dinheiro, recorrentes ou avulsas, separadas entre as que já caíram e as que ainda estão previstas.',
    },
    {
      alvo: 'receitas-nova',
      titulo: 'Cadastre uma receita',
      texto: 'Lance um salário, um freela ou qualquer entrada. Se ela se repete, marque como recorrente e informe a frequência.',
    },
    {
      alvo: 'receitas-resumo',
      titulo: 'Previsto e recebido',
      texto: 'Os números somam só o que a tabela está mostrando: mudou o filtro, eles acompanham.',
    },
    {
      alvo: 'receitas-tabela',
      titulo: 'Lista de receitas',
      texto: 'Começa no mês atual; use o funil das colunas para mudar o período ou filtrar por status. O ícone de setas marca as recorrentes.',
    },
  ],

  '/transacoes': [
    {
      titulo: 'Transações',
      texto: 'O extrato do mês: entradas e saídas em ordem de data, num só lugar. Despesas só aparecem aqui depois de pagas.',
    },
    {
      alvo: 'transacoes-periodo',
      titulo: 'Escolha o mês',
      texto: 'O extrato mostra um mês por vez. Ao sair do mês atual, aparece um atalho para voltar a ele.',
    },
    {
      alvo: 'transacoes-resumo',
      titulo: 'Entradas, saídas e saldo',
      texto: 'Somam o que a tabela está mostrando. Filtre por categoria e veja quanto ela pesou no mês.',
    },
    {
      alvo: 'transacoes-tabela',
      titulo: 'O extrato',
      texto: 'Na linha você marca uma receita como recebida, volta um lançamento para pendente, edita ou exclui. Compras de cartão aparecem uma a uma; a fatura não entra aqui.',
    },
  ],
};
