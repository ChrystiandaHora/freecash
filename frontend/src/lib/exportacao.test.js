/**
 * Testes dos helpers da tela de Exportação & Backup e da tela de Importar.
 *
 * Dois defeitos motivaram a extração para cá: o fim do período padrão era calculado
 * com `toISOString()`, em UTC — à noite, no fuso de Brasília, o relatório pedia o dia
 * seguinte —, e a regra da senha do backup precisa espelhar a do servidor, que recusa
 * menos de 12 caracteres porque o ZIP AES deriva a chave com poucas iterações.
 */
import { describe, expect, it } from 'vitest';

import {
  descreverUltimoBackup,
  ehBackupZip,
  nomeDoBackup,
  progressoDaSenha,
  nomeDoRelatorio,
  periodoPadrao,
  TIPOS_MIME,
  validarSenhaDoBackup,
} from './exportacao';

describe('periodoPadrao', () => {
  it('vai de 1º de janeiro até hoje no fuso local', () => {
    // 29/10 às 23h em UTC−3 já é 30/10 em UTC: o fim não pode virar o dia seguinte.
    const noite = new Date(2026, 9, 29, 23, 30);

    expect(periodoPadrao(noite)).toEqual({ inicio: '2026-01-01', fim: '2026-10-29' });
  });
});

describe('nomes dos arquivos', () => {
  it('identifica o relatório pelo período e pela extensão do formato', () => {
    expect(nomeDoRelatorio('excel', '2026-01-01', '2026-10-29')).toBe(
      'relatorio_financeiro_2026-01-01_a_2026-10-29.xlsx',
    );
    expect(nomeDoRelatorio('pdf', '2026-01-01', '2026-10-29')).toMatch(/\.pdf$/);
    expect(nomeDoRelatorio('csv', '2026-01-01', '2026-10-29')).toMatch(/\.csv$/);
  });

  it('dá ao backup a data e a hora locais da geração', () => {
    expect(nomeDoBackup(new Date(2026, 9, 29, 8, 5))).toBe(
      'freecash_meus-dados_2026-10-29_0805.zip',
    );
  });

  it('tem tipo MIME para cada formato baixado', () => {
    expect(TIPOS_MIME.zip).toBe('application/zip');
    expect(Object.keys(TIPOS_MIME)).toEqual(
      expect.arrayContaining(['excel', 'pdf', 'csv', 'zip']),
    );
  });
});

describe('validarSenhaDoBackup', () => {
  const forte = 'senha-do-backup-forte';

  it('aceita senha longa confirmada', () => {
    expect(validarSenhaDoBackup(forte, forte)).toBeNull();
  });

  it('exige a senha', () => {
    expect(validarSenhaDoBackup('', '')).toMatch(/Defina/);
  });

  it('recusa menos de 12 caracteres, como o servidor', () => {
    expect(validarSenhaDoBackup('a'.repeat(11), 'a'.repeat(11))).toMatch(/12 caracteres/);
    expect(validarSenhaDoBackup('a'.repeat(12), 'a'.repeat(12))).toBeNull();
  });

  it('recusa senha acima do teto do servidor', () => {
    const longa = 'a'.repeat(129);
    expect(validarSenhaDoBackup(longa, longa)).toMatch(/128 caracteres/);
  });

  it('exige a confirmação igual', () => {
    expect(validarSenhaDoBackup(forte, `${forte}x`)).toMatch(/não coincidem/);
  });
});

describe('descreverUltimoBackup', () => {
  const agora = new Date(2026, 9, 29, 10, 0);

  it('avisa quando nunca houve backup', () => {
    expect(descreverUltimoBackup(null, agora)).toEqual({
      rotulo: 'Nenhum backup feito ainda',
      atrasado: true,
    });
  });

  it('conta dias de calendário no fuso local, não blocos de 24 horas', () => {
    // 23h de ontem fica a 11h de agora, mas para quem lê é "ontem"
    expect(descreverUltimoBackup(new Date(2026, 9, 28, 23, 0).toISOString(), agora).rotulo).toBe(
      'Último backup ontem',
    );
    expect(descreverUltimoBackup(new Date(2026, 9, 29, 8, 0).toISOString(), agora).rotulo).toBe(
      'Último backup hoje',
    );
    expect(descreverUltimoBackup(new Date(2026, 9, 17, 9, 0).toISOString(), agora).rotulo).toBe(
      'Último backup há 12 dias',
    );
  });

  it('marca como atrasado depois de 30 dias', () => {
    expect(descreverUltimoBackup(new Date(2026, 8, 29).toISOString(), agora).atrasado).toBe(false);
    expect(descreverUltimoBackup(new Date(2026, 8, 28).toISOString(), agora).atrasado).toBe(true);
  });

  it('passa a contar em meses a partir de 60 dias', () => {
    expect(descreverUltimoBackup(new Date(2026, 4, 1).toISOString(), agora).rotulo).toBe(
      'Último backup há 5 meses',
    );
  });
});

describe('progressoDaSenha', () => {
  it('vai de 0 a 1 até o tamanho mínimo e para ali', () => {
    expect(progressoDaSenha('')).toBe(0);
    expect(progressoDaSenha('a'.repeat(6))).toBe(0.5);
    expect(progressoDaSenha('a'.repeat(40))).toBe(1);
  });
});

describe('ehBackupZip', () => {
  it('aceita só .zip, sem diferenciar maiúsculas', () => {
    expect(ehBackupZip('freecash_meus-dados.zip')).toBe(true);
    expect(ehBackupZip('BACKUP.ZIP')).toBe(true);
    expect(ehBackupZip('backup_freecash.fcbk')).toBe(false);
    expect(ehBackupZip('')).toBe(false);
  });
});
