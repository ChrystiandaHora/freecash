/**
 * Tela de Importação Segura de Backup (Ferramentas — Importar).
 *
 * Interface para restauração de dados a partir de arquivos de backup
 * criptografados no formato proprietário `.fcbk`. Permite ao usuário
 * carregar o arquivo via drag-and-drop ou seleção manual, e opcionalmente
 * informar uma senha de proteção antes de submeter ao backend.
 *
 * Fluxo de Importação:
 * 1. Usuário arrasta ou seleciona um arquivo `.fcbk` na zona de upload.
 * 2. O arquivo é validado por tipo MIME e exibido com nome/tamanho.
 * 3. (Opcional) Usuário informa a senha de proteção do backup.
 * 4. Ao confirmar, o arquivo é enviado via `multipart/form-data` para
 *    `POST /api/ferramentas/importar/` com rastreamento de progresso.
 * 5. Em caso de sucesso, exibe um resumo dos registros importados por
 *    categoria (transações, receitas, contas, etc.) e oferece navegação
 *    para o Dashboard.
 *
 * Segurança: a senha é enviada somente se preenchida e é limpa da memória
 * imediatamente após a conclusão da importação.
 *
 * @module FerramentasImportar
 * @component
 * @returns {JSX.Element} Tela de importação de backup com drag-and-drop e progresso.
 *
 * @example
 * // Rota configurada em App.jsx:
 * <Route path="importar" element={<FerramentasImportar />} />
 */
import React, { useState, useCallback } from 'react';
import { useDropzone } from 'react-dropzone';
import { useMutation } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import {
  UploadCloud,
  FileText,
  CheckCircle2,
  AlertCircle,
  Loader2,
  ArrowRight,
  X,
  FileSpreadsheet,
  Lock,
  Eye,
  EyeOff,
} from 'lucide-react';
import api from '../services/api';
import { Button } from '../components/ui/Button';
import { Input } from '../components/ui/Input';

const ACCEPTED_TYPES = {
  'application/octet-stream': ['.fcbk'],
};

function formatBytes(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export default function FerramentasImportar() {
  const navigate = useNavigate();
  const [uploadedFile, setUploadedFile] = useState(null);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [resultado, setResultado] = useState(null);
  const [importPassword, setImportPassword] = useState('');
  const [showImportPassword, setShowImportPassword] = useState(false);

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
          msg: 'Formato inválido. Envie apenas arquivos de backup seguro no formato próprio .fcbk.',
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
    const isFcbk = uploadedFile.name.endsWith('.fcbk');
    if (isFcbk && !importPassword.trim()) {
      setResultado({
        tipo: 'erro',
        msg: 'A senha é obrigatória para importar arquivos de backup .fcbk.',
      });
      return;
    }
    setUploadProgress(0);
    importMutation.mutate({ file: uploadedFile, password: isFcbk ? importPassword : '' });
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
          Restaure seu banco de dados a partir do seu arquivo de backup seguro{' '}
          <span className="font-semibold text-primary">.fcbk</span>
        </p>
      </div>

      {/* Drop Zone Card */}
      <div className="grid lg:grid-cols-5 gap-6">
        <div className="lg:col-span-3 space-y-4">
          {/* Dropzone */}
          <div
            {...getRootProps()}
            id="dropzone-area"
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

                {/* Campo de Senha Dinâmico para arquivo .fcbk */}
                {uploadedFile.name.endsWith('.fcbk') && (
                  <div className="w-full max-w-sm mt-3 space-y-1.5 text-left" onClick={(e) => e.stopPropagation()}>
                    <label className="text-xs font-semibold text-slate-600 dark:text-slate-400 flex items-center gap-1">
                      <Lock className="h-3 w-3" />
                      Senha de Descriptografia
                    </label>
                    <div className="relative">
                      <Input
                        type={showImportPassword ? 'text' : 'password'}
                        placeholder="Digite a senha do backup..."
                        value={importPassword}
                        onChange={(e) => setImportPassword(e.target.value)}
                        className="pr-10 border-primary/30 focus-visible:ring-primary"
                        disabled={isPending}
                      />
                      <button
                        type="button"
                        onClick={() => setShowImportPassword(!showImportPassword)}
                        className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600 dark:hover:text-slate-300 transition-colors"
                        disabled={isPending}
                      >
                        {showImportPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                      </button>
                    </div>
                  </div>
                )}

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
                    Suporta apenas o formato seguro oficial .fcbk
                  </p>
                </div>
              </div>
            )}
          </div>

          {/* Upload Progress */}
          {isPending && (
            <div className="space-y-2">
              <div className="flex items-center justify-between text-sm">
                <span className="text-slate-600 dark:text-slate-400 flex items-center gap-2">
                  <Loader2 className="h-4 w-4 animate-spin text-primary" />
                  Restauração em andamento...
                </span>
                <span className="font-semibold text-primary">{uploadProgress}%</span>
              </div>
              <div className="w-full h-2 bg-slate-200 dark:bg-slate-800 rounded-full overflow-hidden">
                <div
                  className="h-full bg-primary rounded-full transition-all duration-300"
                  style={{ width: `${uploadProgress}%` }}
                />
              </div>
            </div>
          )}

          {/* Resultado */}
          {resultado && (
            <div
              className={`flex items-start gap-3 p-4 rounded-xl border ${
                resultado.tipo === 'sucesso'
                  ? 'bg-emerald-50 dark:bg-emerald-900/20 border-emerald-200 dark:border-emerald-800 text-emerald-800 dark:text-emerald-300'
                  : 'bg-red-50 dark:bg-red-900/20 border-red-200 dark:border-red-800 text-red-800 dark:text-red-300'
              }`}
            >
              {resultado.tipo === 'sucesso' ? (
                <CheckCircle2 className="h-5 w-5 shrink-0 mt-0.5" />
              ) : (
                <AlertCircle className="h-5 w-5 shrink-0 mt-0.5" />
              )}
              <div className="flex-1">
                {resultado.tipo === 'sucesso' ? (
                  <>
                    <p className="font-semibold">{resultado.dados?.msg || 'Restauração concluída!'}</p>
                    <div className="flex gap-4 mt-1 text-sm opacity-80">
                      <span>✓ {resultado.dados?.criados ?? 0} criados/restaurados</span>
                      <span>↻ {resultado.dados?.atualizados ?? 0} atualizados</span>
                      <span>— {resultado.dados?.ignorados ?? 0} ignorados</span>
                    </div>
                  </>
                ) : (
                  <p className="font-semibold">{resultado.msg}</p>
                )}
              </div>
            </div>
          )}

          {/* Action Buttons */}
          <div className="flex gap-3">
            <Button
              id="btn-importar"
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
          <h2 className="text-sm font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400">
            Backup Exclusivo FreeCash
          </h2>
          <div className="p-4 rounded-xl border border-violet-200 dark:border-violet-800 bg-violet-50 dark:bg-violet-900/20">
            <div className="flex items-center gap-2 mb-1">
              <FileText className="h-4 w-4 text-violet-600 dark:text-violet-400" />
              <span className="text-xs font-bold font-mono text-violet-600 dark:text-violet-400">.fcbk</span>
              <span className="text-xs font-semibold text-slate-700 dark:text-slate-200">Backup Criptografado</span>
            </div>
            <p className="text-xs text-slate-500 dark:text-slate-400">
              O formato <span className="font-semibold">.fcbk</span> é o padrão oficial de segurança do FreeCash. Ele contém todos os seus dados estruturados de forma protegida com criptografia simétrica forte AES-GCM.
            </p>
          </div>

          <div className="p-4 rounded-xl border border-amber-200 dark:border-amber-800 bg-amber-50 dark:bg-amber-900/20">
            <p className="text-xs text-amber-700 dark:text-amber-400">
              <span className="font-semibold">⚠️ Atenção:</span> A restauração substituirá integralmente todos os dados atuais da sua conta pelos dados contidos no backup. Certifique-se de que possui a senha de descriptografia correta.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
