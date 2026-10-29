/**
 * Tela de Ferramentas de Exportação e Backup.
 *
 * Hierarquia: o status do último backup no topo, o painel "Levar meus dados" (ZIP com
 * senha, AES-256, com planilhas CSV, `dados.json` e LEIA-ME) como ação principal, e
 * abaixo os relatórios por período e o caminho para restaurar. Ver `docs/backup.md`.
 *
 * O status é complementar: se a consulta falhar, ele some e o resto da tela segue
 * funcionando.
 *
 * @returns {React.JSX.Element} Página de exportação e backup.
 */
import { useQuery } from '@tanstack/react-query';
import { AlertTriangle, CheckCircle2, ShieldCheck } from 'lucide-react';
import api from '../services/api';
import { LevarMeusDados } from '../components/backup/LevarMeusDados';
import { RelatoriosPorPeriodo } from '../components/backup/RelatoriosPorPeriodo';
import { RestaurarBackup } from '../components/backup/RestaurarBackup';
import { CHAVE_STATUS_DO_BACKUP, descreverUltimoBackup } from '../lib/exportacao';

function StatusDoBackup() {
  const { data, isPending, isError } = useQuery({
    queryKey: CHAVE_STATUS_DO_BACKUP,
    queryFn: async () => (await api.get('/api/ferramentas/backup/')).data,
  });

  if (isPending) {
    return (
      <span role="status" className="block h-9 w-52 animate-pulse rounded-full bg-muted">
        <span className="sr-only">Consultando o último backup...</span>
      </span>
    );
  }
  if (isError) return null;

  const { rotulo, atrasado } = descreverUltimoBackup(data.ultimo_backup_em);
  const Icone = atrasado ? AlertTriangle : CheckCircle2;
  const quando = data.ultimo_backup_em
    ? new Date(data.ultimo_backup_em).toLocaleString('pt-BR', { dateStyle: 'long', timeStyle: 'short' })
    : null;

  return (
    <p
      className={`inline-flex items-center gap-2 self-start rounded-full border px-3.5 py-2 text-sm font-medium sm:self-auto ${
        atrasado
          ? 'border-amber-300 bg-amber-50 text-amber-900 dark:border-amber-700/60 dark:bg-amber-950/40 dark:text-amber-200'
          : 'border-emerald-200 bg-emerald-50 text-emerald-900 dark:border-emerald-800/60 dark:bg-emerald-950/40 dark:text-emerald-200'
      }`}
    >
      <Icone className="h-4 w-4 shrink-0" aria-hidden="true" />
      {quando ? <time dateTime={data.ultimo_backup_em} title={quando}>{rotulo}</time> : rotulo}
    </p>
  );
}

export default function FerramentasBackup() {
  return (
    <div className="space-y-6 animate-fade-in">
      <header className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h1 className="text-3xl font-extrabold tracking-tight text-foreground">
            Exportação & Backup
          </h1>
          <p className="mt-1 text-muted-foreground">
            Seus dados em formatos abertos, para guardar ou levar com você.
          </p>
        </div>
        <StatusDoBackup />
      </header>

      <LevarMeusDados />

      <div className="grid gap-6 lg:grid-cols-3">
        <RelatoriosPorPeriodo className="lg:col-span-2" />
        <RestaurarBackup />
      </div>

      <p className="flex items-start gap-2 px-1 text-xs leading-relaxed text-muted-foreground">
        <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
        Os dados são seus (LGPD, art. 18). JSON e CSV abrem em qualquer planilha ou serviço, e a
        senha do backup não fica guardada no freecash.
      </p>
    </div>
  );
}
