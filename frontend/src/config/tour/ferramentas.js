/** Tours das telas do grupo Ferramentas. Contrato em `./index.js`. */

export const toursDeFerramentas = {
  '/importar': [
    {
      titulo: 'Restaurar um backup',
      texto:
        'Aqui você devolve à conta o backup .zip baixado em Exportação & Backup. Extrato ou fatura em PDF entram por Conciliação.',
    },
    {
      alvo: 'importar-arquivo',
      titulo: 'Escolha o arquivo',
      texto:
        'Um arquivo por vez. Antes de restaurar, o nome e o tamanho aparecem aqui para você conferir se é o backup certo.',
    },
    {
      alvo: 'importar-senha',
      titulo: 'Senha do backup',
      texto: 'Só é enviada se você preencher, e é apagada da tela assim que a restauração termina.',
    },
    {
      alvo: 'importar-leitura',
      titulo: 'O que é restaurado',
      texto:
        'Editar as planilhas do backup não muda o que volta para a conta. Para corrigir algo, restaure e ajuste nas telas.',
    },
    {
      alvo: 'importar-aviso',
      titulo: 'Os dados atuais saem',
      texto:
        'Tudo o que está na conta hoje é trocado pelo backup. Na dúvida, baixe antes um backup do estado atual em Exportação & Backup.',
    },
    {
      alvo: 'importar-restaurar',
      titulo: 'Confirme a restauração',
      texto: 'Envia o arquivo e, ao terminar, mostra quantos registros foram restaurados e quantos ficaram de fora.',
    },
  ],
  '/conciliacao': [
    {
      titulo: 'Conciliação de Extratos',
      texto:
        'Suba o PDF do extrato ou da fatura e revise linha a linha o que vira lançamento. Nada entra na base sem a sua aprovação.',
    },
    {
      alvo: 'conciliacao-banco',
      titulo: 'Banco do PDF',
      texto:
        'Cada banco tem um leitor que conhece o layout do PDF. O genérico é a reserva e pode errar a natureza das linhas.',
    },
    {
      alvo: 'conciliacao-cartao',
      titulo: 'Cartão é opcional',
      texto:
        'Escolha o cartão quando o PDF for a fatura dele, para as compras caírem no ciclo certo. Para extrato de conta, deixe em Nenhum.',
    },
    {
      alvo: 'conciliacao-arquivo',
      titulo: 'Envie o PDF',
      texto:
        'Arraste ou selecione o PDF e envie para a fila: ele é lido e vira linhas pendentes, ainda sem gravar nada.',
    },
    {
      alvo: 'conciliacao-fila',
      titulo: 'Fila de revisão',
      texto:
        'Confira data, valor e natureza de cada linha; clicar em Receita ou Despesa troca o tipo. Reenviar o PDF repete a fila, mas o lançamento não duplica.',
    },
    {
      alvo: 'conciliacao-acoes',
      titulo: 'Lançar ou descartar',
      texto:
        'Lançar cria os lançamentos das linhas marcadas (data futura nasce prevista). Descartar só as tira da fila, sem criar nada.',
    },
  ],
  '/compras-cartao': [
    {
      titulo: 'Compras do cartão',
      texto:
        'Aqui ficam as compras individuais dos seus cartões de crédito, lançadas à mão ou lidas do PDF da fatura.',
    },
    {
      alvo: 'compras-nova',
      titulo: 'Lançar uma compra',
      texto: 'Registra à mão uma compra que não veio numa fatura importada.',
    },
    {
      alvo: 'compras-importar',
      titulo: 'Importar a fatura em PDF',
      texto:
        'Escolha o cartão e o banco e suba o PDF: as compras lidas entram direto no histórico. Para revisar antes, use a Conciliação.',
    },
    {
      alvo: 'compras-lista',
      titulo: 'Histórico de compras',
      texto:
        'Abre filtrado nas faturas que vencem neste mês. Use os filtros das colunas para ver outros meses, cartões ou status.',
    },
    {
      alvo: 'compras-atualizar',
      titulo: 'Atualizar a lista',
      texto: 'Recarrega as compras depois de lançar ou importar algo em outra tela.',
    },
  ],
  '/backup': [
    {
      titulo: 'Exportação & Backup',
      texto:
        'Aqui você leva todos os seus dados num arquivo comum, gera relatórios de um período e encontra o caminho para restaurar um backup.',
    },
    {
      alvo: 'backup-status',
      titulo: 'Quando foi o último backup',
      texto: 'O selo fica amarelo se você nunca fez backup ou se já passou de 30 dias desde o último.',
    },
    {
      alvo: 'backup-senha',
      titulo: 'Defina uma senha',
      texto:
        'O arquivo sai protegido por senha, com pelo menos 12 caracteres. Anote-a: sem ela ninguém abre o backup, nem o freecash.',
    },
    {
      alvo: 'backup-baixar',
      titulo: 'Baixe seus dados',
      texto: 'Gera um .zip com tudo o que você registrou. Serve de backup e para levar seus dados para outro serviço.',
    },
    {
      alvo: 'backup-conteudo',
      titulo: 'O que vem no arquivo',
      texto:
        'Planilhas CSV para abrir no Excel, o dados.json que o freecash lê para importar de volta e um LEIA-ME explicando cada coluna.',
    },
    {
      alvo: 'backup-relatorios',
      titulo: 'Relatórios por período',
      texto: 'Para ler e analisar: escolha formato, período e conteúdo. Relatórios não voltam para o sistema.',
    },
    {
      alvo: 'backup-restaurar',
      titulo: 'Restaurar um backup',
      texto: 'Para voltar um backup, use Importar. Os dados atuais da conta são substituídos pelos do arquivo.',
    },
  ],
};
