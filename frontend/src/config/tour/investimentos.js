/** Tours das telas de Investimentos. Contrato em `./index.js`. */

export const toursDeInvestimentos = {
  '/investimentos': [
    {
      titulo: 'Painel de Investimentos',
      texto:
        'A visão geral dos seus investimentos: quanto você tem, quanto já rendeu e como o patrimônio está distribuído.',
    },
    {
      alvo: 'investimentos-carteira',
      titulo: 'Escolha a carteira',
      texto: 'Mostra os números de uma corretora só. Em "Todas as carteiras" você vê o consolidado.',
    },
    {
      alvo: 'investimentos-atualizar',
      titulo: 'Cotações em dia',
      texto: 'Busca o preço de mercado mais recente de cada ativo. Use quando os valores parecerem defasados.',
    },
    {
      alvo: 'investimentos-resumo',
      titulo: 'O resumo do patrimônio',
      texto:
        'A variação mede só o quanto os ativos valorizaram. A rentabilidade soma a isso os proventos recebidos.',
    },
    {
      alvo: 'investimentos-evolucao',
      titulo: 'Como o patrimônio cresceu',
      texto:
        'Compara, mês a mês, o valor de mercado com o que você investiu. A distância entre as linhas é o seu ganho ou perda.',
    },
    {
      alvo: 'investimentos-alocacao',
      titulo: 'Onde o dinheiro está',
      texto: 'Quanto do patrimônio está em cada categoria de ativo, para ver se a carteira está concentrada demais.',
    },
    {
      alvo: 'investimentos-rentabilidade-mensal',
      titulo: 'Mês a mês',
      texto: 'O retorno de cada mês, ano a ano, para achar rápido os meses bons e os ruins.',
    },
  ],

  '/investimentos/ativos': [
    {
      titulo: 'Meus Ativos',
      texto: 'Tudo o que você tem investido, com quantidade, preço médio, valor atual e retorno de cada ativo.',
    },
    {
      alvo: 'ativos-cadastrar',
      titulo: 'Cadastre um ativo',
      texto: 'Comece por aqui: ação, FII, renda fixa ou cripto. A compra inicial pode ser lançada no mesmo cadastro.',
    },
    {
      alvo: 'ativos-atualizar',
      titulo: 'Atualize as cotações',
      texto: 'Busca os preços de mercado mais recentes. Se faltar histórico, clicar de novo continua de onde parou.',
    },
    {
      alvo: 'ativos-resumo',
      titulo: 'Os números da lista',
      texto:
        'Os totais acompanham os filtros da tabela. Com uma carteira escolhida, mostra também se as metas dela somam 100%.',
    },
    {
      alvo: 'ativos-grafico',
      titulo: 'Como cada ativo se moveu',
      texto:
        'Compara a cotação dos ativos no período. Escolha quais aparecem por aqui mesmo: o gráfico não segue os filtros da tabela.',
    },
    {
      alvo: 'ativos-filtros',
      titulo: 'Encontre um ativo',
      texto: 'Separe os ativos em carteira dos arquivados e filtre por nome, carteira ou classe.',
    },
    {
      alvo: 'ativos-lista',
      titulo: 'Sua custódia',
      texto:
        'Pelos botões de cada linha você abre o detalhe, edita, exclui ou transfere o ativo para outra carteira.',
    },
  ],

  '/investimentos/ativos/:id': [
    {
      titulo: 'Detalhe do ativo',
      texto: 'Tudo sobre um ativo: quanto vale hoje, quanto custou, onde está guardado e cada operação registrada.',
    },
    {
      alvo: 'ativo-detalhe-atualizar',
      titulo: 'Cotação deste ativo',
      texto: 'Busca o preço mais recente só deste ativo, sem esperar a atualização da carteira toda.',
    },
    {
      alvo: 'ativo-detalhe-transferir',
      titulo: 'Mude de corretora',
      texto: 'Move cotas para outra carteira sem registrar compra nem venda. O preço médio não muda.',
    },
    {
      alvo: 'ativo-detalhe-resumo',
      titulo: 'Quanto vale e quanto rendeu',
      texto:
        'Valor de mercado, custo original e o resultado acumulado. Os números somam todas as carteiras, mesmo com filtro.',
    },
    {
      alvo: 'investimentos-sinais',
      titulo: 'Sinais de rebalanceamento',
      texto: 'Avisa quando o ativo se afastou da meta que você definiu na carteira. É um alerta, não uma recomendação.',
    },
    {
      alvo: 'ativo-detalhe-abas',
      titulo: 'Três visões do ativo',
      texto: 'Dados cadastrais e custódia, o histórico de cotações e o extrato de compras, vendas e proventos.',
    },
  ],

  '/investimentos/balanceamento': [
    {
      titulo: 'Balanceamento',
      texto:
        'Aqui você define quanto cada ativo deve pesar na carteira e descobre onde aplicar o próximo aporte para chegar lá.',
    },
    {
      alvo: 'investimentos-carteira',
      titulo: 'Comece pela carteira',
      texto: 'As metas valem por carteira e somam 100% dentro dela. Escolha uma para ajustar metas e simular aportes.',
    },
    {
      alvo: 'balanceamento-ajustar-metas',
      titulo: 'Defina as metas',
      texto: 'Libera os controles de cada ativo para você distribuir os 100% da carteira. Salve quando a soma fechar.',
    },
    {
      alvo: 'investimentos-sinais',
      titulo: 'Quem saiu da meta',
      texto:
        'Lista os ativos que se afastaram da meta além da tolerância. É um alerta para rebalancear, não uma recomendação.',
    },
    {
      alvo: 'balanceamento-aporte',
      titulo: 'Aporte Mágico',
      texto:
        'Diga quanto quer investir e veja quantas cotas comprar de cada ativo, priorizando os mais longe da meta.',
    },
    {
      alvo: 'balanceamento-metas',
      titulo: 'Meta x posição atual',
      texto: 'Para cada ativo, a meta e o peso que ele tem hoje na carteira, com o aporte ou excesso para chegar lá.',
    },
    {
      alvo: 'balanceamento-entre-carteiras',
      titulo: 'Metas entre carteiras',
      texto: 'No consolidado, defina quanto do patrimônio deve ficar em cada corretora e quanto falta aportar em cada uma.',
    },
  ],

  '/investimentos/historico': [
    {
      titulo: 'Histórico de Ordens',
      texto: 'O registro de cada compra, venda, provento e transferência. É daqui que saem preço médio e rentabilidade.',
    },
    {
      alvo: 'historico-nova-ordem',
      titulo: 'Lance uma operação',
      texto: 'Registre uma compra, venda ou provento recebido. A posição e a rentabilidade da carteira se atualizam ao salvar.',
    },
    {
      alvo: 'historico-transferir',
      titulo: 'Transferência de custódia',
      texto: 'Para quando você leva cotas de uma corretora para outra. Não conta como venda e não mexe no preço médio.',
    },
    {
      alvo: 'investimentos-carteira',
      titulo: 'Filtre por carteira',
      texto: 'Mostra só as ordens executadas numa corretora. Em "Todas as carteiras" você vê o histórico completo.',
    },
    {
      alvo: 'historico-resumo',
      titulo: 'Totais por tipo',
      texto: 'Quantas compras, vendas e proventos há e quanto somam. Os totais acompanham os filtros da tabela.',
    },
    {
      alvo: 'historico-lista',
      titulo: 'O livro-razão',
      texto: 'Filtre por tipo, ativo ou carteira para achar uma ordem. Pelos botões da linha você edita ou exclui; transferência só se exclui.',
    },
  ],

  '/investimentos/carteiras': [
    {
      titulo: 'Carteiras',
      texto:
        'Uma carteira para cada corretora ou banco onde você investe. Ela diz onde cada posição está guardada.',
    },
    {
      alvo: 'carteiras-nova',
      titulo: 'Cadastre uma carteira',
      texto: 'Crie uma para cada instituição. Com mais de uma, aparece o filtro de carteira nas telas de investimento.',
    },
    {
      alvo: 'carteiras-cartao',
      titulo: 'Cada custódia',
      texto: 'Quanto está investido nesta carteira e em quantos ativos há posição. Editar muda nome, instituição e cor.',
    },
    {
      alvo: 'carteiras-horizonte',
      titulo: 'Conta como dinheiro disponível?',
      texto:
        'Diz se esta carteira entra quando você liga "Considerar valor investido" no Horizonte de Saldos. Ligue para a reserva e desligue para o que não vai resgatar.',
    },
    {
      alvo: 'carteiras-arquivar',
      titulo: 'Arquivar sem perder nada',
      texto: 'Tira a carteira dos filtros e preserva as ordens já lançadas. Use para uma corretora que deixou de usar.',
    },
  ],

  '/investimentos/classes': [
    {
      titulo: 'Classes de Ativos',
      texto:
        'Aqui você organiza a classificação dos ativos em três níveis, no padrão ANBIMA: classe, categoria e subcategoria.',
    },
    {
      alvo: 'classes-nova',
      titulo: 'Crie uma classe',
      texto: 'O primeiro nível, como Renda Fixa ou Renda Variável. Categorias e subcategorias nascem dentro dela.',
    },
    {
      alvo: 'classes-legenda',
      titulo: 'Os três níveis',
      texto: 'Cada ícone indica um nível. A subcategoria é a que você escolhe ao cadastrar um ativo.',
    },
    {
      alvo: 'classes-arvore',
      titulo: 'A árvore de classificação',
      texto: 'Clique numa classe ou categoria para abrir os níveis de baixo e gerenciar o que há dentro.',
    },
    {
      alvo: 'classes-acoes',
      titulo: 'Ações de cada nível',
      texto: 'O + cria um nível abaixo deste, o lápis renomeia e a lixeira exclui.',
    },
  ],
};
