/**
 * helpContent.js – Dicionário Centralizado de Ajuda Contextual do FreeCash.
 * Mapeia rotas e padrões para explicações objetivas e de uso direto de cada tela.
 */

export const helpContent = {
  "/dashboard": {
    title: "Dashboard",
    overview: "Resumo financeiro do mês atual com saldos, gráficos de fluxo diário e projeção de 6 meses.",
    features: [
      "Indicadores rápidos de Receitas, Despesas, Saldo Mensal e Taxa de Poupança.",
      "Gráfico diário de fluxo de caixa (receitas x despesas por competência).",
      "Projeção de fluxo de caixa acumulado para os próximos 6 meses.",
      "Breakdown de maiores categorias de despesas."
    ],
    actions: {
      "Seletor de Período": "Altere o mês e ano de análise no cabeçalho para ver dados históricos."
    }
  },

  "/relatorios": {
    title: "Relatórios DRE",
    overview: "Demonstração do Resultado (DRE) anual consolidada com análise de EBITDA e sazonalidade.",
    features: [
      "Estrutura de DRE padrão (Receita Operacional, EBITDA e Resultado Líquido).",
      "Heatmap de sazonalidade de custos dos últimos 6 meses.",
      "Breakdown anual de despesas por categoria."
    ],
    actions: {
      "Filtro Anual": "Selecione o ano de exercício no menu superior.",
      "Exportar Relatório": "Clique para gerar planilha ou versão de impressão em PDF."
    }
  },

  "/contas-pagar": {
    title: "Contas a Pagar",
    overview: "Cadastro e controle de despesas e obrigações com status inteligente de vencimento.",
    features: [
      "Listagem com status: Atrasado, Pendente, Vence Hoje e Pago.",
      "Totalizadores rápidos de contas pagas e pendentes do período.",
      "Filtros de vencimento por mês/ano."
    ],
    actions: {
      "Nova Despesa": "Abre o formulário de cadastro rápido de obrigação financeira.",
      "Status Checkbox": "Marque ou desmarque uma conta como paga diretamente na linha.",
      "Lançamento em Lote": "Acesse a interface de edição em tabela para cadastros massivos."
    }
  },

  "/contas-pagar/lote": {
    title: "Lançamento em Lote",
    overview: "Interface de planilha dinâmica para cadastrar ou editar múltiplas despesas de uma vez só.",
    features: [
      "Tabela interativa com inserção rápida de linhas.",
      "Mapeamento automático de campos relacionais de categorias e cartões."
    ],
    actions: {
      "Adicionar Linha": "Insere uma nova linha vazia na tabela de lote.",
      "Salvar Lote": "Grava permanentemente todas as contas inseridas na tabela no banco de dados."
    }
  },

  "/contas-kanban": {
    title: "Pipeline Kanban",
    overview: "Controle visual ágil de contas a pagar divididas por proximidade de vencimento.",
    features: [
      "Separação automática em 5 colunas: Atrasadas, Para Hoje, Próximos 7 Dias, Final do Mês e Pagas.",
      "Ação integrada de pagamento rápido."
    ],
    actions: {
      "Mover Cartão": "Arraste qualquer conta para a coluna 'Pagas' para registrar o pagamento na API."
    }
  },

  "/cartoes": {
    title: "Meus Cartões",
    overview: "Gerenciamento de cartões de crédito cadastrados, utilização de limites e faturas.",
    features: [
      "Gauge visual de utilização de limite de crédito por cartão.",
      "Faturas organizadas com melhor dia de compra, fechamento e vencimento.",
      "Histórico de compras vinculadas ao cartão."
    ],
    actions: {
      "Novo Cartão": "Cadastre cartões com limites e dias de fechamento/vencimento.",
      "Importar Fatura PDF": "Importe extratos em PDF (Nubank, Santander) para lançar despesas em lote."
    }
  },

  "/receitas": {
    title: "Receitas",
    overview: "Gerenciamento de receitas recorrentes e avulsas previstas e recebidas.",
    features: [
      "Tabela de entradas financeiras organizadas no período.",
      "Indicadores rápidos de Total Previsto, Recebido e Saldo a Receber."
    ],
    actions: {
      "Nova Receita": "Registra uma nova previsão de entrada financeira.",
      "Status Recebido": "Marque se a receita foi depositada/realizada."
    }
  },

  "/transacoes": {
    title: "Transações",
    overview: "Extrato cronológico e unificado de todas as receitas e despesas realizadas.",
    features: [
      "Listagem cronológica diária das movimentações efetivadas.",
      "Busca rápida e filtros por descrição, valor ou categoria."
    ],
    actions: {
      "Filtro de Período": "Exiba apenas as transações de um mês e ano específicos."
    }
  },

  "/investimentos": {
    title: "Dashboard de Investimentos",
    overview: "Consolidação patrimonial, rentabilidade e árvore de alocação da carteira.",
    features: [
      "Evolução do patrimônio líquido e rentabilidade acumulada.",
      "Gráfico de alocação de carteira por classe de ativo.",
      "Árvore interativa de classificação ANBIMA em 3 níveis (Classe -> Categoria -> Subcategoria)."
    ],
    actions: {
      "Atualizar Cotações": "Clique para buscar preços atuais de mercado via Yahoo Finance (yfinance)."
    }
  },

  "/investimentos/ativos": {
    title: "Meus Ativos",
    overview: "Tabela de custódia dos ativos em carteira com quantidades, preços médios e retornos.",
    features: [
      "Cálculo de Preço Médio e Valor Total a mercado por ativo.",
      "Indicador colorido de ganho ou perda de capital (retorno %)."
    ],
    actions: {
      "Cadastrar Ativo": "Adicione novos papéis de renda fixa, variável ou cripto ativos à carteira."
    }
  },

  "/investimentos/ativos/:id": {
    title: "Detalhe do Ativo",
    overview: "Análise individualizada de performance e histórico de transações de um ativo específico.",
    features: [
      "Páginas em abas: Dados Gerais, Desempenho Histórico e Extrato de Operações.",
      "Histórico de rentabilidade contra o Ibovespa e CDI."
    ],
    actions: {
      "Registrar Operação": "Adicione transações de Compra (C), Venda (V) ou recebimento de Provento (D)."
    }
  },

  "/investimentos/balanceamento": {
    title: "Balanceador Ideal",
    overview: "Calculadora automática de aportes necessários para reequilibrar a carteira segundo suas metas.",
    features: [
      "Sliders interativos para definir o percentual ideal de alocação de cada ativo.",
      "Cálculo do aporte sugerido para reequilibrar a alocação sem vender ativos."
    ],
    actions: {
      "Simular Aporte": "Insira o valor que deseja investir e veja quais ativos comprar."
    }
  },

  "/investimentos/historico": {
    title: "Histórico da Carteira",
    overview: "Evolução histórica mensal da carteira de investimentos consolidada.",
    features: [
      "Gráfico comparativo de rentabilidade contra indexadores de referência (CDI e Ibovespa)."
    ],
    actions: {
      "Filtro de Janela": "Escolha o período histórico para plotagem no gráfico de rentabilidade."
    }
  },

  "/investimentos/classes": {
    title: "Classes e Metas",
    overview: "Estrutura macro de classes de investimentos e definição de pesos percentuais estratégicos.",
    features: [
      "Configuração de metas ideais de alocação macro (Ações, FIIs, Renda Fixa, Cripto)."
    ],
    actions: {
      "Ajustar Pesos": "Defina o peso estratégico de cada classe para balizar o simulador de balanceamento."
    }
  },

  "/importar": {
    title: "Importar Extrato",
    overview: "Ferramenta para importação e conciliação massiva de extratos bancários em formato de planilha.",
    features: [
      "Leitor de arquivos XLS/CSV de múltiplos bancos com mapeamento de colunas.",
      "Fila de conciliação assistida para evitar transações duplicadas."
    ],
    actions: {
      "Enviar Arquivo": "Arraste ou selecione o extrato e confirme os lançamentos para a base real."
    }
  },

  "/compras-cartao": {
    title: "Conciliar Cartão",
    overview: "Conciliação assistida de despesas individuais de faturas importadas.",
    features: [
      "Lista de compras da fatura com pareamento automático de valores e datas."
    ],
    actions: {
      "Confirmar Vínculo": "Selecione a despesa correspondente para conciliar a compra de cartão."
    }
  },

  "/backup": {
    title: "Backup de Dados",
    overview: "Ferramentas para exportar dados para planilhas ou criar backups criptografados locais.",
    features: [
      "Exportação em Excel (.xlsx), CSV ou PDF das transações.",
      "Geração e leitura de backups criptografados proprietários (.fcbk)."
    ],
    actions: {
      "Exportar Backup": "Defina uma senha de criptografia para baixar seu arquivo `.fcbk`.",
      "Restaurar Backup": "Selecione um arquivo `.fcbk`, digite a senha e recupere seu banco de dados."
    }
  },

  "/pagamentos": {
    title: "Ajustes de Pagamentos",
    overview: "Cadastro e configuração de meios de pagamento, cartões de crédito e contas bancárias.",
    features: [
      "Personalização visual de meios de pagamento com cores e ícones das instituições financeiras."
    ],
    actions: {
      "Novo Meio": "Adicione contas correntes, carteiras físicas ou novos cartões de crédito ativos."
    }
  },

  "/simulador": {
    title: "Simulador de Gastos",
    overview: "Ambiente sandbox em memória para testar o impacto de gastos futuros no seu fluxo de caixa.",
    features: [
      "KPIs interativos do fluxo líquido do mês atual (Real vs. Simulado) lado a lado.",
      "Gráfico de barras de Fluxo Projetado para 6 meses.",
      "Tabela detalhada de projeção anual (12 meses) com modal detalhado de simulações."
    ],
    actions: {
      "Cadastrar Simulação": "Defina despesas temporárias únicas, recorrentes ou parceladas em memória."
    }
  }
};
