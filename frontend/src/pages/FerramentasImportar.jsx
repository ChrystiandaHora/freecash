/**
 * Tela de Importação Segura de Backup (Ferramentas — Importar).
 *
 * Restaura dados a partir do backup `.zip` gerado em Exportação & Backup, carregado por
 * drag-and-drop ou seleção manual. A senha é opcional: um ZIP extraído e recompactado
 * numa ferramenta comum pode voltar sem ela (ver docs/backup.md).
 *
 * Fluxo: o arquivo é validado por tipo MIME e exibido com nome e tamanho; ao confirmar,
 * sobe via `multipart/form-data` para `POST /api/ferramentas/importar/` com progresso; em
 * caso de sucesso, mostra o resumo dos registros importados por categoria.
 *
 * Segurança: a senha só é enviada se preenchida e é limpa da memória ao concluir.
 *
 * @returns {JSX.Element} Tela de importação de backup com drag-and-drop e progresso.
 */
import { useState, useCallback } from 'react';
import { useDropzone } from 'react-dropzone';
import { useMutation } from '@tanstack/react-query';
import {
  UploadCloud,
  FileText,
  CheckCircle2,
  AlertCircle,
  Loader2,
  X,
  FileSpreadsheet,
  Lock,
} from 'lucide-react';
import api from '../services/api';
import { Button } from '../components/ui/Button';
import { PasswordInput } from '../components/ui/PasswordInput';
import { SectionLabel } from '../components/ui/SectionLabel';
import { Alert } from '../components/ui/Alert';
import { ehBackupZip } from '../lib/exportacao';

// O Windows rotula ZIP como x-zip-compressed; sem ele o arquivo seria recusado ali
const ACCEPTED_TYPES = {
  'application/zip': ['.zip'],
  'application/x-zip-compressed': ['.zip'],
};

function formatBytes(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export default function FerramentasImportar() {
  const [uploadedFile, setUploadedFile] = useState(null);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [resultado, setResultado] = useState(null);
  const [importPassword, setImportPassword] = useState('');

  const importMutation = useMutation({
    mutationFn: async ({ file, password }) => {
      const formData = new FormData();
      formData.append('arquivo', file);
      if (password) {
        formData.append('password', password);
      }
      const response = await api.post('/api/ferramentas/importar/', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
        onUploadProgress: (progressEvent) => {
          if (progressEvent.total) {
            const percent = Math.round((progressEvent.loaded * 100) / progressEvent.total);
            setUploadProgress(percent);
          }
        },
      });
      return response.data;
    },
    onSuccess: (data) => {
      setResultado({ tipo: 'sucesso', dados: data });
      setImportPassword(''); // Limpa a senha após importação concluída
    },
    onError: (error) => {
      const msg = error?.response?.data?.erro || 'Ocorreu um erro durante a importação.';
      setResultado({ tipo: 'erro', msg });
    },
  });

  const onDrop = useCallback(
    (acceptedFiles, rejectedFiles) => {
      if (rejectedFiles.length > 0) {
        setResultado({
          tipo: 'erro',
          msg: 'Formato inválido. Envie o backup .zip gerado em Exportação & Backup.',
        });
        return;
      }
      if (acceptedFiles.length === 0) return;

      const file = acceptedFiles[0];
      setUploadedFile(file);
      setResultado(null);
      setUploadProgress(0);
      setImportPassword('');
    },
    []
  );

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: ACCEPTED_TYPES,
    maxFiles: 1,
    multiple: false,
  });

  const handleImportar = () => {
    if (!uploadedFile) return;
    if (!ehBackupZip(uploadedFile.name)) {
      setResultado({ tipo: 'erro', msg: 'Envie o backup .zip gerado em Exportação & Backup.' });
      return;
    }
    setUploadProgress(0);
    importMutation.mutate({ file: uploadedFile, password: importPassword });
  };

  const handleReset = () => {
    setUploadedFile(null);
    setResultado(null);
    setUploadProgress(0);
    setImportPassword('');
    importMutation.reset();
  };

  const isPending = importMutation.isPending;

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-extrabold tracking-tight text-foreground">
          Importar Backup
        </h1>
        <p className="text-slate-500 dark:text-slate-400 mt-1">
          Restaure sua conta a partir do arquivo{' '}
          <span className="font-semibold text-primary">.zip</span> gerado em Exportação & Backup
        </p>
      </div>

      {/* Drop Zone Card */}
      <div className="grid lg:grid-cols-5 gap-6">
        <div className="lg:col-span-3 space-y-4">
          {/* Dropzone */}
          <div
            {...getRootProps()}
            id="dropzone-area"
            data-tour="importar-arquivo"
            className={`
              relative flex flex-col items-center justify-center gap-4 rounded-2xl
              border-2 border-dashed transition-all duration-300 cursor-pointer
              min-h-[280px] p-8 text-center
              ${isDragActive
                ? 'border-primary bg-primary/5 dark:bg-primary/10 scale-[1.01]'
                : 'border-border bg-card/50 hover:border-primary/50 hover:bg-primary/5 dark:hover:bg-primary/10'
              }
              ${uploadedFile ? 'border-primary/60 bg-primary/5 dark:bg-primary/10' : ''}
            `}
          >
            <input {...getInputProps()} id="file-input" />

            {uploadedFile ? (
              <div className="flex flex-col items-center gap-3">
                <div className="w-16 h-16 rounded-2xl bg-primary/10 flex items-center justify-center border border-primary/20">
                  <FileSpreadsheet className="h-8 w-8 text-primary" />
                </div>
                <div>
                  <p className="font-semibold text-slate-800 dark:text-slate-200 text-lg">
                    {uploadedFile.name}
                  </p>
                  <p className="text-sm text-slate-500 dark:text-slate-400">
                    {formatBytes(uploadedFile.size)}
                  </p>
                </div>

                <button
                  onClick={(e) => { e.stopPropagation(); handleReset(); }}
                  className="flex items-center gap-1 text-xs text-slate-400 hover:text-red-500 transition-colors mt-1"
                  disabled={isPending}
                >
                  <X className="h-3.5 w-3.5" />
                  Remover arquivo
                </button>
              </div>
            ) : (
              <div className="flex flex-col items-center gap-4">
                <div
                  className={`w-20 h-20 rounded-full flex items-center justify-center transition-all duration-300
                    ${isDragActive
                      ? 'bg-primary/15 border-2 border-primary scale-110'
                      : 'bg-muted border-2 border-border/50'
                    }
                  `}
                >
                  <UploadCloud
                    className={`h-9 w-9 transition-colors duration-300
                      ${isDragActive ? 'text-primary' : 'text-slate-400 dark:text-slate-500'}
                    `}
                  />
                </div>
                <div>
                  <p className="text-lg font-semibold text-slate-700 dark:text-slate-200">
                    {isDragActive ? 'Solte o arquivo aqui!' : 'Arraste e solte seu arquivo de backup'}
                  </p>
                  <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
                    ou <span className="text-primary font-medium">clique para selecionar</span>
                  </p>
                  <p className="text-xs text-slate-400 dark:text-slate-500 mt-2">
                    Aceita o backup .zip do freecash
                  </p>
                </div>
              </div>
            )}
          </div>

          {/* Fora da área de soltar: um campo dentro dela abriria o seletor de arquivo ao clicar */}
          {uploadedFile && (
            <div className="space-y-1.5" data-tour="importar-senha">
              <label htmlFor="importar-senha" className="text-xs font-semibold text-slate-600 dark:text-slate-400 flex items-center gap-1">
                <Lock className="h-3 w-3" aria-hidden="true" />
                Senha do arquivo
              </label>
              {/* Usa o PasswordInput compartilhado, que já traz aria-label/aria-pressed dinâmicos no toggle */}
              <PasswordInput
                id="importar-senha"
                autoComplete="off"
                value={importPassword}
                onChange={(e) => setImportPassword(e.target.value)}
                className="border-primary/30 focus-visible:ring-primary"
                disabled={isPending}
                aria-describedby="importar-senha-dica"
              />
              <p id="importar-senha-dica" className="text-xs text-slate-500 dark:text-slate-400">
                A que você definiu ao baixar. Deixe em branco se o ZIP não tiver senha.
              </p>
            </div>
          )}

          {/* Upload Progress */}
          {isPending && (
            <div className="space-y-2" role="status">
              <div className="flex items-center justify-between text-sm">
                <span className="text-slate-600 dark:text-slate-400 flex items-center gap-2">
                  <Loader2 className="h-4 w-4 animate-spin text-primary" aria-hidden="true" />
                  Restauração em andamento...
                </span>
                <span className="font-semibold text-primary">{uploadProgress}%</span>
              </div>
              <div
                role="progressbar"
                aria-label="Progresso da restauração"
                aria-valuenow={uploadProgress}
                aria-valuemin={0}
                aria-valuemax={100}
                className="w-full h-2 bg-slate-200 dark:bg-slate-800 rounded-full overflow-hidden"
              >
                <div
                  className="h-full bg-primary rounded-full transition-all duration-300"
                  style={{ width: `${uploadProgress}%` }}
                />
              </div>
            </div>
          )}

          {/* Resultado */}
          {resultado && (
            <Alert
              variant={resultado.tipo === 'sucesso' ? 'success' : 'error'}
              icon={resultado.tipo === 'sucesso' ? CheckCircle2 : AlertCircle}
              title={resultado.tipo === 'sucesso' ? (resultado.dados?.msg || 'Restauração concluída!') : undefined}
            >
              {resultado.tipo === 'sucesso' ? (
                <div className="flex gap-4 text-sm">
                  <span>+ {resultado.dados?.criados ?? 0} criados/restaurados</span>
                  <span>~ {resultado.dados?.atualizados ?? 0} atualizados</span>
                  <span>- {resultado.dados?.ignorados ?? 0} ignorados</span>
                </div>
              ) : (
                <span className="font-semibold">{resultado.msg}</span>
              )}
            </Alert>
          )}

          {/* Action Buttons */}
          <div className="flex gap-3">
            <Button
              id="btn-importar"
              data-tour="importar-restaurar"
              onClick={handleImportar}
              disabled={!uploadedFile || isPending}
              className="flex-1 gap-2"
            >
              {isPending ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Restaurando...
                </>
              ) : (
                <>
                  <UploadCloud className="h-4 w-4" />
                  Restaurar Backup
                </>
              )}
            </Button>
          </div>
        </div>

        {/* Info Panel */}
        <div className="lg:col-span-2 space-y-3">
          <SectionLabel as="h2">O que é lido do arquivo</SectionLabel>
          <div className="p-4 rounded-xl border border-violet-200 dark:border-violet-800 bg-violet-50 dark:bg-violet-900/20" data-tour="importar-leitura">
            <div className="flex items-center gap-2 mb-1">
              <FileText className="h-4 w-4 text-violet-600 dark:text-violet-400" aria-hidden="true" />
              <span className="text-xs font-bold font-mono text-violet-600 dark:text-violet-400">dados.json</span>
            </div>
            <p className="text-xs text-slate-500 dark:text-slate-400">
              A restauração lê o <span className="font-semibold">dados.json</span> de dentro do ZIP. As planilhas CSV e o LEIA-ME são para você consultar e não interferem na importação.
            </p>
          </div>

          <Alert variant="warning" icon={AlertCircle} title="Atenção" className="text-xs" data-tour="importar-aviso">
            A restauração substituirá integralmente todos os dados atuais da sua conta pelos dados contidos no backup.
          </Alert>
        </div>
      </div>
    </div>
  );
}
