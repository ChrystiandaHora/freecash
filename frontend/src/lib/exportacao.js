/**
 * Helpers puros das telas de Exportação & Backup e de Importar.
 *
 * O backup é um ZIP cifrado com AES-256 (dados.json + planilhas CSV + LEIA-ME); os
 * relatórios por período continuam em Excel, CSV e PDF. Ver `docs/backup.md`.
 */
import { paraISO } from './datas';
import { TAMANHO_MAXIMO, TAMANHO_MINIMO } from './politicaSenha';

const EXTENSOES = { excel: 'xlsx', pdf: 'pdf', csv: 'csv' };

export const TIPOS_MIME = {
  excel: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
  pdf: 'application/pdf',
  csv: 'text/csv;charset=utf-8;',
  zip: 'application/zip',
};

/**
 * Período padrão dos relatórios: de 1º de janeiro do ano corrente até hoje.
 *
 * @param {Date} [hoje] Data de referência (injetável para teste).
 * @returns {{inicio: string, fim: string}} Datas AAAA-MM-DD no fuso local.
 */
export function periodoPadrao(hoje = new Date()) {
  return { inicio: `${hoje.getFullYear()}-01-01`, fim: paraISO(hoje) };
}

/** Estampa de data/hora local no formato AAAA-MM-DD_HHMM, para nomes de arquivo. */
function estampaLocal(agora) {
  const pad = (valor) => String(valor).padStart(2, '0');
  return `${paraISO(agora)}_${pad(agora.getHours())}${pad(agora.getMinutes())}`;
}

/**
 * Nome do relatório baixado, identificado pelo período exportado.
 *
 * @param {'excel'|'pdf'|'csv'} formato Formato do relatório.
 * @param {string} dataInicio Início do período (AAAA-MM-DD).
 * @param {string} dataFim Fim do período (AAAA-MM-DD).
 * @returns {string} Nome do arquivo.
 */
export function nomeDoRelatorio(formato, dataInicio, dataFim) {
  return `relatorio_financeiro_${dataInicio}_a_${dataFim}.${EXTENSOES[formato]}`;
}

/**
 * Nome do backup baixado. Não tem período — abrange a conta inteira —, então leva a
 * data e a hora da geração.
 *
 * @param {Date} [agora] Momento da geração (injetável para teste).
 * @returns {string} Nome do arquivo `.zip`.
 */
export function nomeDoBackup(agora = new Date()) {
  return `freecash_meus-dados_${estampaLocal(agora)}.zip`;
}

/**
 * Valida a senha do backup com a mesma regra do servidor.
 *
 * @param {string} senha Senha digitada.
 * @param {string} confirmacao Repetição da senha.
 * @returns {string|null} Mensagem do primeiro problema, ou null se estiver tudo certo.
 */
export function validarSenhaDoBackup(senha, confirmacao) {
  if (!senha) return 'Defina uma senha para proteger o backup.';
  if (senha.length < TAMANHO_MINIMO) {
    return `A senha precisa ter pelo menos ${TAMANHO_MINIMO} caracteres.`;
  }
  if (senha.length > TAMANHO_MAXIMO) {
    return `A senha pode ter no máximo ${TAMANHO_MAXIMO} caracteres.`;
  }
  if (senha !== confirmacao) return 'As senhas não coincidem.';
  return null;
}

/** Chave do React Query para a data do último backup, invalidada a cada download. */
export const CHAVE_STATUS_DO_BACKUP = ['backup-status'];

/** A partir de quantos dias sem backup a tela passa a cobrar um novo. */
export const DIAS_PARA_BACKUP_ATRASADO = 30;

const DIAS_ATE_CONTAR_EM_MESES = 60;
const MS_POR_DIA = 24 * 60 * 60 * 1000;

/**
 * Descreve, em relação a hoje, quando foi o último backup.
 *
 * Conta dias de calendário no fuso local: um backup das 23h de ontem é "ontem", mesmo
 * que tenha sido há poucas horas.
 *
 * @param {string|null} isoDoUltimo Data/hora ISO do último backup, ou null se nunca houve.
 * @param {Date} [agora] Momento de referência (injetável para teste).
 * @returns {{rotulo: string, atrasado: boolean}} Texto para a tela e se já passou da hora.
 */
export function descreverUltimoBackup(isoDoUltimo, agora = new Date()) {
  if (!isoDoUltimo) return { rotulo: 'Nenhum backup feito ainda', atrasado: true };

  const ultimo = new Date(isoDoUltimo);
  const dias = Math.round(
    (new Date(agora.getFullYear(), agora.getMonth(), agora.getDate()) -
      new Date(ultimo.getFullYear(), ultimo.getMonth(), ultimo.getDate())) /
      MS_POR_DIA,
  );
  const atrasado = dias > DIAS_PARA_BACKUP_ATRASADO;

  if (dias <= 0) return { rotulo: 'Último backup hoje', atrasado };
  if (dias === 1) return { rotulo: 'Último backup ontem', atrasado };
  if (dias < DIAS_ATE_CONTAR_EM_MESES) return { rotulo: `Último backup há ${dias} dias`, atrasado };

  const meses =
    (agora.getFullYear() - ultimo.getFullYear()) * 12 +
    (agora.getMonth() - ultimo.getMonth()) -
    (agora.getDate() < ultimo.getDate() ? 1 : 0);
  return { rotulo: `Último backup há ${meses} meses`, atrasado };
}

/**
 * Quanto da senha já cobre o tamanho mínimo, para a barra de progresso do campo.
 *
 * @param {string} senha Senha digitada.
 * @returns {number} De 0 a 1; para em 1 ao atingir o mínimo.
 */
export function progressoDaSenha(senha) {
  return Math.min((senha || '').length / TAMANHO_MINIMO, 1);
}

/**
 * Diz se o arquivo escolhido para importar é um backup em ZIP.
 *
 * @param {string} nomeDoArquivo Nome do arquivo selecionado.
 * @returns {boolean} Verdadeiro para `.zip`.
 */
export function ehBackupZip(nomeDoArquivo) {
  return (nomeDoArquivo || '').toLowerCase().endsWith('.zip');
}
