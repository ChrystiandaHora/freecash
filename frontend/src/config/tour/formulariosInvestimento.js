/** Tours das telas de formulários de investimento (ativo, classe, ordem). Contrato em `./index.js`. */

// Carteira e posição inicial só existem no cadastro; arquivar, só na edição — o tour pula o que não está na tela
const PASSOS_ATIVO = [
  {
    alvo: 'ativo-form-subclasse',
    titulo: 'Subclasse do ativo',
    texto:
      'Define onde o ativo entra no balanceamento. Em renda fixa ou alternativos, aparecem também emissor, vencimento e indexador.',
  },
  {
    alvo: 'ativo-form-tipo-fiscal',
    titulo: 'Tipo fiscal',
    texto:
      'Na maioria dos casos pode ficar na dedução automática. Troque só se o ativo aparecer com a regra de IR errada nos sinais de venda.',
  },
  {
    alvo: 'ativo-form-carteira',
    titulo: 'Onde o ativo fica custodiado',
    texto: 'A corretora em que você tem o ativo. É nela que a posição inicial, se informada, é registrada.',
  },
  {
    alvo: 'ativo-form-posicao-inicial',
    titulo: 'Já tem esse ativo?',
    texto:
      'Abra e informe quantidade e preço: ao salvar, vira uma ordem de compra no histórico, sem precisar lançá-la depois.',
  },
  {
    alvo: 'ativo-form-arquivar',
    titulo: 'Arquivar em vez de excluir',
    texto: 'Para um ativo que você vendeu todo: o histórico fica guardado e ele deixa de pesar no balanceamento.',
  },
];

const PASSOS_CLASSE = [
  {
    titulo: 'Hierarquia ANBIMA',
    texto:
      'Aqui você cria ou renomeia um nível da classificação dos seus investimentos: classe, categoria ou subcategoria.',
  },
  {
    alvo: 'classe-form-titulo',
    titulo: 'O que você está editando',
    texto: 'O título diz o nível e, ao criar, dentro de qual classe ou categoria o novo item vai ficar.',
  },
  {
    alvo: 'classe-form-nome',
    titulo: 'Nome do nível',
    texto: 'Renomear não mexe nos ativos: eles continuam ligados ao mesmo item, só com o nome novo.',
  },
  {
    alvo: 'classe-form-salvar',
    titulo: 'Salvar',
    texto: 'Grava e volta para Classes, onde a hierarquia já aparece atualizada.',
  },
];

const PASSOS_ORDEM = [
  {
    alvo: 'ordem-form-tipo-lancamento',
    titulo: 'Compra/venda ou provento',
    texto: 'Compra e venda mudam a quantidade de cotas. Proventos e JCP só registram o dinheiro recebido.',
  },
  {
    alvo: 'ordem-form-ativo',
    titulo: 'Qual ativo',
    texto: 'A lista traz só ativos já cadastrados. Se o seu não aparece, cadastre-o antes em Meus Ativos.',
  },
  {
    alvo: 'ordem-form-carteira',
    titulo: 'Em qual corretora',
    texto: 'As cotas são contadas por carteira: escolha a corretora em que a ordem foi executada.',
  },
  {
    alvo: 'ordem-form-taxas',
    titulo: 'Taxas da operação',
    texto: 'Corretagem e emolumentos: somam ao custo na compra e descontam do valor recebido na venda.',
  },
];

export const toursDeFormulariosDeInvestimento = {
  '/investimentos/ativos/novo': [
    {
      titulo: 'Cadastrar ativo',
      texto: 'Cadastre um investimento para acompanhá-lo na carteira. Ao salvar, ele passa a aparecer em Meus Ativos.',
    },
    ...PASSOS_ATIVO,
  ],
  '/investimentos/ativos/editar/:id': [
    {
      titulo: 'Editar ativo',
      texto:
        'Ajuste os dados cadastrais do ativo. Quantidade e preço não mudam aqui: eles vêm das ordens do histórico.',
    },
    ...PASSOS_ATIVO,
  ],
  '/investimentos/classes/formulario': PASSOS_CLASSE,
  '/investimentos/historico/novo': [
    {
      titulo: 'Registrar ordem',
      texto: 'Lance uma compra, venda ou provento. Ao salvar, a posição e a rentabilidade da carteira são atualizadas.',
    },
    ...PASSOS_ORDEM,
  ],
  '/investimentos/historico/editar/:id': [
    {
      titulo: 'Editar ordem',
      texto:
        'Corrija os dados de uma ordem já lançada. Ao salvar, a posição e a rentabilidade da carteira são recalculadas.',
    },
    ...PASSOS_ORDEM,
  ],
};
