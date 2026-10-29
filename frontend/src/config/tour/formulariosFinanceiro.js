/** Tours das telas de formulários financeiros (receita, conta a pagar, compra de cartão, pagamento). Contrato em `./index.js`. */

const passosReceita = [
  {
    alvo: 'receita-form-tipo',
    titulo: 'Única ou recorrente',
    texto:
      'Recorrente cria sozinha as próximas entradas, como um salário. Única entra uma vez só, na data que você informar.',
  },
  {
    alvo: 'receita-form-categoria',
    titulo: 'Categoria',
    texto: 'Agrupa a receita nos relatórios. Escreva o nome: se a categoria ainda não existe, ela é criada ao salvar.',
  },
  {
    alvo: 'receita-form-data',
    titulo: 'Quando o dinheiro deve entrar',
    texto:
      'É a data prevista, não a confirmação: marque como recebida no Calendário quando o dinheiro cair. Na recorrente, é a primeira ocorrência.',
  },
  {
    alvo: 'receita-form-frequencia',
    titulo: 'De quanto em quanto tempo',
    texto: 'Define o ritmo da repetição. Ao lado, deixe a data final vazia para a receita continuar sem prazo para acabar.',
  },
];

const passosContaPagar = [
  {
    alvo: 'conta-pagar-form-categoria',
    titulo: 'Categoria',
    texto: 'Agrupa a despesa nos relatórios. Escreva o nome: se a categoria ainda não existe, ela é criada ao salvar.',
  },
  {
    alvo: 'conta-pagar-form-vencimento',
    titulo: 'Até quando pagar',
    texto: 'Define em que mês a despesa aparece e a partir de quando ela passa a contar como atrasada.',
  },
  {
    alvo: 'conta-pagar-form-evento',
    titulo: 'Gasto de um evento',
    texto:
      'Ligue a despesa a uma viagem ou reforma. Ela sai do saldo normalmente e, se o evento estiver fora do orçamento, não entra nas médias do mês.',
  },
  {
    alvo: 'conta-pagar-form-fixa',
    titulo: 'Despesa que se repete',
    texto:
      'Marque para aluguel, assinaturas e contas de consumo: ela se repete sozinha e entra na projeção do Horizonte de Saldos. Só dá para definir ao cadastrar.',
  },
  {
    alvo: 'conta-pagar-form-pago',
    titulo: 'Conta já paga',
    texto: 'Se você marcou como paga por engano, desfazer o pagamento volta a conta para pendente.',
  },
];

const passosCompraCartao = [
  {
    alvo: 'compra-cartao-form-data',
    titulo: 'A data decide a fatura',
    texto:
      'Use o dia em que comprou. Compras feitas depois do dia de fechamento do cartão caem na fatura do mês seguinte.',
  },
  {
    alvo: 'compra-cartao-form-cartao',
    titulo: 'Em qual cartão',
    texto:
      'A compra entra na fatura deste cartão, que segue os dias de fechamento e vencimento cadastrados na tela Pagamentos.',
  },
  {
    alvo: 'compra-cartao-form-categoria',
    titulo: 'Categoria',
    texto: 'Separa o gasto nos relatórios. Sem escolher uma, a compra fica na categoria Cartão de Crédito.',
  },
];

const passosPagamento = [
  {
    alvo: 'pagamento-form-nome',
    titulo: 'Como ele aparece no app',
    texto: 'É o nome que você escolhe ao lançar uma compra no cartão. Use algo fácil de reconhecer, como o nome do banco.',
  },
  {
    alvo: 'pagamento-form-fatura',
    titulo: 'Fechamento e vencimento',
    texto:
      'Compras feitas até o dia de fechamento entram na fatura que vence no dia de vencimento. Depois dele, vão para a fatura seguinte.',
  },
  {
    alvo: 'pagamento-form-cor',
    titulo: 'Identificação visual',
    texto: 'A cor e o ícone marcam este cartão nas listas, para reconhecê-lo de relance. A prévia logo abaixo mostra o resultado.',
  },
];

export const toursDeFormulariosFinanceiros = {
  '/receitas/novo': [
    {
      titulo: 'Nova receita',
      texto: 'Registre um dinheiro que você espera receber, uma vez só ou repetindo de tempos em tempos.',
    },
    ...passosReceita,
  ],
  '/receitas/editar/:id': [
    {
      titulo: 'Editar receita',
      texto:
        'Corrija os dados desta entrada. Se ela for recorrente, as mudanças valem também para as próximas ocorrências ainda não recebidas.',
    },
    ...passosReceita,
  ],
  '/contas-pagar/novo': [
    {
      titulo: 'Nova conta a pagar',
      texto:
        'Registre uma despesa com vencimento, como aluguel ou boleto. Ela fica pendente em Contas a Pagar até você marcá-la como paga.',
    },
    ...passosContaPagar,
  ],
  '/contas-pagar/editar/:id': [
    {
      titulo: 'Editar conta a pagar',
      texto:
        'Corrija os dados desta despesa. Fatura de cartão fica travada aqui: ela é montada a partir das compras do cartão.',
    },
    ...passosContaPagar,
  ],
  '/compras-cartao/novo': [
    {
      titulo: 'Nova compra no cartão',
      texto:
        'Lance uma compra feita no crédito. Ela não sai do saldo agora: vai para a fatura do cartão, que aparece em Contas a Pagar.',
    },
    ...passosCompraCartao,
  ],
  '/compras-cartao/editar/:id': [
    {
      titulo: 'Editar compra no cartão',
      texto: 'Corrija os dados desta compra. Compras de uma fatura que já foi paga não podem mais ser alteradas.',
    },
    ...passosCompraCartao,
  ],
  '/pagamentos/novo': [
    {
      titulo: 'Novo cartão ou conta',
      texto:
        'Cadastre o cartão que você vai usar nas compras. Os dias de fechamento e vencimento são o que mais importa para as faturas.',
    },
    ...passosPagamento,
  ],
  '/pagamentos/editar/:id': [
    {
      titulo: 'Editar cartão ou conta',
      texto:
        'Altere os dados deste cartão. Mudar o fechamento ou o vencimento muda em qual fatura as próximas compras vão cair.',
    },
    ...passosPagamento,
  ],
};
