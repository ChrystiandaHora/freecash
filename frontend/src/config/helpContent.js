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
    concepts: {
      "Variação": "Diferença entre o valor de mercado atual da carteira e o custo total de aquisição dos ativos (preço médio × quantidade). Reflete exclusivamente o ganho ou perda de capital (a mercado), sem considerar dividendos.",
      "Rentabilidade": "Retorno total histórico da carteira: soma o ganho de capital com todos os proventos e dividendos recebidos. Fórmula: (Patrimônio + Vendas + Dividendos - Compras) / Compras.",
      "Evolução do Patrimônio": "O gráfico exibe duas linhas mensais: Patrimônio (valor de mercado no último dia do mês) e Valor Investido (compras acumuladas menos vendas). A diferença entre as linhas é o ganho ou perda de capital no período.",
      "Lucro Total": "Resultado financeiro consolidado: Ganho de Capital (mercado - custo) mais Dividendos recebidos nos últimos 12 meses. Pode ser positivo mesmo com ganho de capital negativo se os proventos compensarem."
    },
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
      "Ajustar Pesos": "Defina o peso estratégico de cada classe para balizar a alocação macro."
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
  },

  "/receitas/novo": {
    title: "Formulário de Receita",
    overview: "Insira os dados da sua entrada de receita única ou recorrente.",
    features: [
      "Escolha o tipo de receita (única ou recorrente).",
      "Defina descrição, valor, data de recebimento e termos de recorrência."
    ],
    actions: {
      "Salvar": "Grava a receita na base de dados."
    }
  },
  "/receitas/editar/:id": {
    title: "Editar Receita",
    overview: "Altere os dados da sua receita cadastrada no sistema.",
    features: [
      "Corrija valores, descrição, datas ou recorrências das parcelas."
    ],
    actions: {
      "Salvar": "Salva as alterações na receita."
    }
  },

  "/contas-pagar/novo": {
    title: "Formulário de Conta a Pagar",
    overview: "Cadastre uma nova despesa ou obrigação financeira no sistema.",
    features: [
      "Defina a descrição, categoria, valor e vencimento da despesa."
    ],
    actions: {
      "Salvar": "Grava a despesa na base de dados."
    }
  },
  "/contas-pagar/editar/:id": {
    title: "Editar Conta a Pagar",
    overview: "Altere as informações de uma despesa a pagar cadastrada.",
    features: [
      "Corrija descrição, categoria, valor ou data de vencimento."
    ],
    actions: {
      "Salvar": "Salva as alterações na despesa."
    }
  },

  "/compras-cartao/novo": {
    title: "Nova Compra no Cartão",
    overview: "Lance uma nova despesa individual de compra no cartão de crédito.",
    features: [
      "Selecione o cartão de crédito e a categoria correspondente.",
      "Defina descrição, valor e a data real da transação."
    ],
    actions: {
      "Salvar": "Salva a compra na fatura correspondente do cartão."
    }
  },
  "/compras-cartao/editar/:id": {
    title: "Editar Compra no Cartão",
    overview: "Altere os dados de uma compra individual lançada no cartão.",
    features: [
      "Corrija descrição, valor, data ou altere o cartão vinculado à compra."
    ],
    actions: {
      "Salvar": "Salva as alterações da compra."
    }
  },

  "/pagamentos/novo": {
    title: "Cadastrar Meio de Pagamento",
    overview: "Configure uma nova conta bancária ou cartão de crédito no sistema.",
    features: [
      "Defina limite, dia de fechamento e dia de vencimento de faturas de cartões.",
      "Defina cores e selecione um ícone para personalização e identificação visual do meio de pagamento."
    ],
    actions: {
      "Salvar": "Grava as configurações do novo meio de pagamento."
    }
  },
  "/pagamentos/editar/:id": {
    title: "Editar Meio de Pagamento",
    overview: "Altere os dados cadastrais da conta ou cartão de crédito.",
    features: [
      "Ajuste limites, datas de fatura, ícone representativo ou cores do cartão."
    ],
    actions: {
      "Salvar": "Salva as alterações no meio de pagamento."
    }
  },

  "/investimentos/ativos/novo": {
    title: "Cadastrar Novo Ativo",
    overview: "Adicione um novo ativo para investimentos à custódia da carteira.",
    features: [
      "Defina ticker, nome, subclasse ANBIMA e meta estratégica de alocação.",
      "Lance detalhes de renda fixa (emissor, indexadores, vencimento) e quantidade/preço de compra inicial."
    ],
    actions: {
      "Salvar": "Cadastra o ativo e lança a ordem de compra inicial (se informada)."
    }
  },
  "/investimentos/ativos/editar/:id": {
    title: "Editar Ativo",
    overview: "Altere as configurações cadastrais e metas de alocação do ativo.",
    features: [
      "Ajuste a meta de alocação %, indexador, taxa contratada ou arquive o ativo."
    ],
    actions: {
      "Salvar": "Salva as alterações nas configurações do ativo."
    }
  },

  "/investimentos/classes/formulario": {
    title: "Hierarquia ANBIMA",
    overview: "Gerencie os níveis de classificação ANBIMA dos ativos.",
    features: [
      "Insira ou modifique o nome de Classes, Categorias ou Subcategorias."
    ],
    actions: {
      "Salvar": "Grava a alteração da classificação no sistema."
    }
  },

  "/investimentos/historico/novo": {
    title: "Registrar Nova Ordem",
    overview: "Registre uma operação de compra, venda ou provento de investimento.",
    features: [
      "Vincule a transação ao ativo correspondente na carteira.",
      "Informe quantidade, preço unitário, taxas ou valor total de dividendos recebidos."
    ],
    actions: {
      "Salvar": "Registra a transação e atualiza a rentabilidade e saldo da carteira."
    }
  },
  "/investimentos/historico/editar/:id": {
    title: "Editar Ordem de Investimento",
    overview: "Corrija os dados lançados de uma transação no histórico.",
    features: [
      "Ajuste a quantidade, preço médio, taxas ou valor dos proventos."
    ],
    actions: {
      "Salvar": "Salva as correções do lançamento da ordem."
    }
  }
};
