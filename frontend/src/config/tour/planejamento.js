/** Tours das telas de planejamento e conta (metas, eventos, simulador, horizonte, calendário, pagamentos, conta, admin). Contrato em `./index.js`. */

export const toursDePlanejamento = {
  '/simulador': [
    {
      titulo: 'Simulador de Gastos',
      texto:
        'Teste o efeito de um gasto ou receita futura no seu fluxo dos próximos 12 meses antes de assumi-lo. Nada do que você simula entra nas suas finanças.',
    },
    {
      alvo: 'simulador-ponto-virada',
      titulo: 'Ponto de virada',
      texto:
        'Diz se e quando suas saídas passam as entradas e quanto de reserva seria preciso para atravessar o período. Em "Ver detalhes" está a conta completa.',
    },
    {
      alvo: 'simulador-kpis',
      titulo: 'Real x simulado',
      texto: 'Compare o fluxo deste mês só com o que já está lançado e com as suas simulações somadas.',
    },
    {
      alvo: 'simulador-novo',
      titulo: 'Crie uma simulação',
      texto:
        'Descreva o gasto ou a receita e escolha se é único, mensal ou parcelado. Ele entra na projeção na hora.',
    },
    {
      alvo: 'simulador-ativas',
      titulo: 'Simulações ativas',
      texto:
        'Tudo o que está em teste fica aqui. Remova uma por uma ou limpe tudo para voltar ao cenário real.',
    },
    {
      alvo: 'simulador-grafico',
      titulo: 'Fluxo dos próximos 6 meses',
      texto: 'Entradas, saídas e o fluxo líquido de cada mês, já com as simulações, para ver onde o caixa aperta.',
    },
    {
      alvo: 'simulador-analise',
      titulo: 'Análise detalhada',
      texto:
        'Abre a tabela mês a mês, com o saldo acumulado em conta, e o mapa de calor dia a dia da projeção.',
    },
  ],

  '/metas': [
    {
      titulo: 'Metas',
      texto:
        'Aqui sua renda e seu custo de vida viram alvos financeiros de referência, e você acompanha o progresso de cada um e das metas que criar.',
    },
    {
      alvo: 'metas-base',
      titulo: 'Comece pela base',
      texto:
        'Informe renda e custo de vida mensais, ou use a média dos seus lançamentos. Salve e gere as metas padrão a partir deles.',
    },
    {
      alvo: 'metas-padrao',
      titulo: 'As quatro metas padrão',
      texto:
        'Reserva de emergência, aporte mensal, patrimônio para viver de renda e teto de gastos essenciais, cada uma com sua barra de progresso.',
    },
    {
      alvo: 'metas-nova',
      titulo: 'Crie uma meta sua',
      texto: 'Para um objetivo próprio, como uma viagem ou a troca do celular, com valor-alvo e prazo.',
    },
    {
      alvo: 'metas-minhas',
      titulo: 'Suas metas',
      texto:
        'As metas que você criou ficam aqui. Nas de valor manual, registre o que guardar; as ligadas à carteira avançam sozinhas.',
    },
    {
      alvo: 'metas-multiplicadores',
      titulo: 'Ajuste os multiplicadores',
      texto:
        'Cada alvo é a base vezes um fator. Mude os fatores se os valores de referência não servirem para você.',
    },
    {
      alvo: 'metas-tabela',
      titulo: 'Todas as metas',
      texto: 'A lista completa, para registrar aportes, editar ou excluir qualquer meta, inclusive as padrão.',
    },
  ],

  '/eventos': [
    {
      titulo: 'Eventos',
      texto:
        'Para gastos fora da rotina, como viagens, reformas e festas: você define um orçamento e acompanha quanto já gastou sem distorcer suas médias mensais.',
    },
    {
      alvo: 'eventos-novo',
      titulo: 'Crie um evento',
      texto:
        'Defina o período, o teto de gastos e se as despesas dele ficam de fora do DRE e das médias do mês.',
    },
    {
      alvo: 'eventos-resumo',
      titulo: 'Visão geral',
      texto: 'Quanto você planejou para todos os eventos, quanto já pagou e quanto ainda sobra dentro dos tetos.',
    },
    {
      alvo: 'eventos-busca',
      titulo: 'Busque um evento',
      texto: 'Filtra os cartões pelo nome do evento.',
    },
    {
      alvo: 'eventos-lista',
      titulo: 'Seus eventos',
      texto: 'Cada cartão mostra o período, o orçamento e quanto dele já foi usado.',
    },
    {
      alvo: 'eventos-acoes-card',
      titulo: 'Lance e acompanhe',
      texto:
        '"Despesa" cria um gasto já vinculado ao evento. "Detalhes" abre os gastos por categoria e o extrato completo.',
    },
  ],

  '/eventos/:id': [
    {
      titulo: 'Detalhe do evento',
      texto: 'Tudo sobre um evento: quanto foi planejado, quanto já saiu e em que você gastou.',
    },
    {
      alvo: 'evento-status',
      titulo: 'Situação do evento',
      texto:
        'Os selos mostram se o evento está em andamento e se suas despesas ficam fora do DRE e das médias ou entram no orçamento do mês.',
    },
    {
      alvo: 'evento-adicionar',
      titulo: 'Adicione uma despesa',
      texto: 'Abre o cadastro de conta a pagar já vinculado a este evento.',
    },
    {
      alvo: 'evento-indicadores',
      titulo: 'Orçamento x gasto',
      texto:
        'Separa o que já foi pago do que está comprometido, ainda a pagar, e mostra quanto resta do teto.',
    },
    {
      alvo: 'evento-progresso',
      titulo: 'Consumo do orçamento',
      texto: 'A barra muda de cor ao chegar perto do teto e avisa quando ele é ultrapassado.',
    },
    {
      alvo: 'evento-categorias',
      titulo: 'Gastos por categoria',
      texto: 'Mostra para onde foi o dinheiro do evento e o peso de cada categoria no total.',
    },
    {
      alvo: 'evento-despesas',
      titulo: 'Despesas do evento',
      texto: 'Marque cada despesa como paga, desfaça um pagamento, edite ou exclua sem sair da tela.',
    },
  ],

  '/horizonte-saldos': [
    {
      titulo: 'Horizonte de Saldos',
      texto:
        'Projeta quanto você terá em caixa em cada dia dos próximos 12 meses, somando o que já está lançado e as recorrências.',
    },
    {
      alvo: 'horizonte-cabecalho',
      titulo: 'De onde a conta parte',
      texto:
        'A projeção começa no dinheiro que você tem hoje. O valor aplicado em investimentos fica de fora, salvo se você pedir.',
    },
    {
      alvo: 'horizonte-alerta',
      titulo: 'O dia que importa',
      texto: 'Avisa o primeiro dia em que o saldo fica negativo, ou confirma que isso não acontece no período.',
    },
    {
      alvo: 'horizonte-limite',
      titulo: 'Limite de atenção',
      texto: 'Seu piso de conforto: os dias com saldo abaixo dele ficam sinalizados na grade.',
    },
    {
      alvo: 'horizonte-cenarios',
      titulo: 'Outros cenários',
      texto:
        'Desconte o aporte mensal das metas ou some o valor investido: a grade e o alerta passam a mostrar esse cenário. Nada é gravado; desligue para voltar.',
    },
    {
      alvo: 'horizonte-abas',
      titulo: 'Grade ou composição',
      texto:
        'A grade mostra quanto haverá em cada dia; a composição explica de onde vem o saldo de abertura e o que move cada mês.',
    },
    {
      alvo: 'horizonte-grade',
      titulo: 'Saldo de cada dia',
      texto: 'Cada célula é um dia, colorida pela situação do saldo. Clique numa para ver os lançamentos previstos.',
    },
  ],

  '/calendario': [
    {
      titulo: 'Calendário de Pagamentos',
      texto:
        'O que vence e o que entra em cada dia do mês, com a opção de dar baixa nos lançamentos direto daqui.',
    },
    {
      alvo: 'calendario-meses',
      titulo: 'Troque de mês',
      texto: 'Avance ou volte um mês para planejar os próximos vencimentos ou conferir os anteriores.',
    },
    {
      alvo: 'calendario-hoje',
      titulo: 'Volte para hoje',
      texto: 'Leva de volta ao mês atual, onde o dia de hoje fica destacado na grade.',
    },
    {
      alvo: 'calendario-grade',
      titulo: 'O mês dia a dia',
      texto:
        'Cada dia soma o que entra, o que sai e quantos lançamentos seguem pendentes. Clique num dia para marcá-los como pagos ou recebidos.',
    },
  ],

  '/pagamentos': [
    {
      titulo: 'Formas de Pagamento',
      texto:
        'Cadastre seus cartões e contas, com cor e ícone, para escolhê-los ao registrar compras e lançamentos.',
    },
    {
      alvo: 'pagamentos-novo',
      titulo: 'Adicione um cartão',
      texto: 'Informe bandeira, limite e os dias de fechamento e vencimento da fatura.',
    },
    {
      alvo: 'pagamentos-lista',
      titulo: 'Seus cartões e contas',
      texto: 'Os que estão em uso, com limite e dia de vencimento à vista.',
    },
    {
      alvo: 'pagamentos-acoes',
      titulo: 'Desative em vez de excluir',
      texto:
        'Desativar tira o cartão de uso e você pode reativá-lo depois. Excluir é definitivo.',
    },
    {
      alvo: 'pagamentos-desativados',
      titulo: 'Desativados',
      texto: 'Os cartões e contas que você tirou de uso ficam aqui, prontos para voltar.',
    },
  ],

  '/conta': [
    {
      titulo: 'Minha Conta',
      texto: 'Seus dados de acesso, preferências e a segurança da sua conta.',
    },
    {
      alvo: 'conta-indicadores',
      titulo: 'Situação da conta',
      texto:
        'Mostra se o e-mail está confirmado, que é o que permite recuperar a senha, e quantos dispositivos estão conectados.',
    },
    {
      alvo: 'conta-perfil',
      titulo: 'Perfil e moeda',
      texto: 'Mude o nome de usuário e a moeda em que os valores aparecem.',
    },
    {
      alvo: 'conta-email',
      titulo: 'Troque o e-mail',
      texto:
        'O novo endereço só passa a valer depois que você abrir o link enviado a ele. Até lá, o atual continua funcionando.',
    },
    {
      alvo: 'conta-senha',
      titulo: 'Troque a senha',
      texto: 'Ao trocar, os outros dispositivos são desconectados. Esta janela continua aberta.',
    },
    {
      alvo: 'conta-sessoes',
      titulo: 'Onde você está conectado',
      texto: 'Se não reconhece algum acesso, encerre as outras sessões para desconectar os demais dispositivos.',
    },
    {
      alvo: 'conta-excluir',
      titulo: 'Excluir a conta',
      texto: 'Apaga a conta e todo o histórico, sem volta. Exporte um backup antes se quiser guardar seus dados.',
    },
  ],

  '/admin/usuarios': [
    {
      titulo: 'Contas de usuário',
      texto:
        'Administração de acesso às contas da plataforma. Os dados financeiros das pessoas não aparecem aqui.',
    },
    {
      alvo: 'admin-usuarios-busca',
      titulo: 'Encontre uma conta',
      texto: 'Busque pelo nome de usuário ou pelo e-mail.',
    },
    {
      alvo: 'admin-usuarios-estado',
      titulo: 'Filtre pelo estado',
      texto: 'Veja todas as contas, só as ativas ou só as suspensas.',
    },
    {
      alvo: 'admin-usuarios-tabela',
      titulo: 'As contas',
      texto:
        'Mostra se a conta está ativa, se o e-mail foi confirmado, o último acesso e o volume de uso de cada uma.',
    },
    {
      alvo: 'admin-usuarios-acao',
      titulo: 'Suspender ou reativar',
      texto:
        'Suspender bloqueia o acesso e desconecta a pessoa na hora. O motivo informado fica no histórico administrativo.',
    },
    {
      alvo: 'admin-usuarios-paginacao',
      titulo: 'Total e páginas',
      texto: 'Quantas contas atendem aos filtros e a navegação entre as páginas da lista.',
    },
  ],
};
