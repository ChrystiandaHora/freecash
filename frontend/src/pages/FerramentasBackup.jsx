/**
 * Tela de Ferramentas de Exportação e Backup.
 * 
 * Permite que o usuário exporte relatórios consolidados em formatos populares
 * (Excel, CSV, PDF) ou realize um backup criptografado seguro de toda a base de dados
 * com o formato proprietário (.fcbk), protegido pelo algoritmo criptográfico AES-GCM.
 *
 * @component
 * @returns {React.JSX.Element} Painel contendo formulários de configuração de exportação e informações de privacidade.
 */
import React, { useState } from 'react';
import {
  DownloadCloud,
  FileSpreadsheet,
  FileText,
  Lock,
  ShieldCheck,
  Database,
  AlertTriangle,
  CheckCircle2,
  Loader2,
  Info,
  Eye,
  EyeOff,
  Calendar,
  Layers,
  FileCheck
} from 'lucide-react';
import api from '../services/api';
import { Button } from '../components/ui/Button';
import { Input } from '../components/ui/Input';

function downloadBlob(data, filename, mimeType) {
  const blob = new Blob([data], { type: mimeType });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

const timestamp = () => Date.now();

export default function FerramentasBackup() {
  const [formato, setFormato] = useState('excel');
  const [escopo, setEscopo] = useState('completo');
  const [dataInicio, setDataInicio] = useState(() => {
    const d = new Date();
    // Default to start of current year for comprehensive data
    return `${d.getFullYear()}-01-01`;
  });
  const [dataFim, setDataFim] = useState(() => {
    const d = new Date();
    return d.toISOString().split('T')[0];
  });
  
  const [isDownloading, setIsDownloading] = useState(false);
  const [feedback, setFeedback] = useState(null);
  const [backupPassword, setBackupPassword] = useState('');
  const [showBackupPassword, setShowBackupPassword] = useState(false);

  const handleDownload = async () => {
    if (formato === 'fcbk' && !backupPassword.trim()) {
      setFeedback({ tipo: 'erro', msg: 'Por favor, digite uma senha para proteger seu backup seguro.' });
      return;
    }
    
    setIsDownloading(true);
    setFeedback(null);
    try {
      const params = { 
        formato,
        escopo: formato === 'fcbk' ? 'completo' : escopo,
        data_inicio: dataInicio,
        data_fim: dataFim
      };
      
      if (formato === 'fcbk') {
        params.senha = backupPassword;
      }
      
      const response = await api.get('/api/ferramentas/exportar/', {
        params,
        responseType: 'blob',
      });

      let filename = `relatorio_financeiro_${timestamp()}.${formato === 'excel' ? 'xlsx' : formato === 'pdf' ? 'pdf' : formato === 'csv' ? 'csv' : 'fcbk'}`;
      let mimeType = 'application/octet-stream';
      
      if (formato === 'excel') {
        mimeType = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet';
      } else if (formato === 'pdf') {
        mimeType = 'application/pdf';
      } else if (formato === 'csv') {
        mimeType = 'text/csv;charset=utf-8;';
      }

      downloadBlob(response.data, filename, mimeType);
      
      if (formato === 'fcbk') {
        setBackupPassword(''); // Limpa a senha por segurança
      }

      setFeedback({ tipo: 'sucesso', msg: 'Download iniciado com sucesso!' });
    } catch (err) {
      let errorMsg = 'Erro ao gerar arquivo. Tente novamente.';
      if (err.response?.data instanceof Blob) {
        try {
          const text = await err.response.data.text();
          const parsed = JSON.parse(text);
          errorMsg = parsed.erro || errorMsg;
        } catch (_) {}
      } else {
        errorMsg = err?.response?.data?.erro || errorMsg;
      }
      setFeedback({
        tipo: 'erro',
        msg: errorMsg,
      });
    } finally {
      setIsDownloading(false);
    }
  };

  return (
    <div className="space-y-8 animate-fade-in">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-extrabold tracking-tight text-foreground">
          Exportação & Backup
        </h1>
        <p className="text-slate-500 dark:text-slate-400 mt-1">
          Exporte seus relatórios financeiros detalhados ou faça um backup completo criptografado
        </p>
      </div>

      {/* Feedback */}
      {feedback && (
        <div
          className={`flex items-center gap-3 p-4 rounded-xl border ${
            feedback.tipo === 'sucesso'
              ? 'bg-emerald-50 dark:bg-emerald-900/20 border-emerald-200 dark:border-emerald-800 text-emerald-700 dark:text-emerald-300'
              : 'bg-red-50 dark:bg-red-900/20 border-red-200 dark:border-red-800 text-red-700 dark:text-red-300'
          }`}
        >
          {feedback.tipo === 'sucesso' ? (
            <CheckCircle2 className="h-5 w-5 shrink-0" />
          ) : (
            <AlertTriangle className="h-5 w-5 shrink-0" />
          )}
          <p className="font-medium">{feedback.msg}</p>
        </div>
      )}

      {/* Main Export Card */}
      <div className="grid lg:grid-cols-5 gap-6">
        <div className="lg:col-span-3 p-6 rounded-2xl border border-border/40 bg-card shadow-sm space-y-6">
          <h2 className="text-lg font-bold text-foreground flex items-center gap-2">
            <DownloadCloud className="h-5 w-5 text-primary" />
            Configurar Download
          </h2>
          
          <div className="space-y-4">
            {/* Formato */}
            <div className="space-y-1.5">
              <label className="text-xs font-bold uppercase text-slate-500 dark:text-slate-400 flex items-center gap-1.5">
                <FileCheck className="h-3.5 w-3.5" />
                Formato do Arquivo
              </label>
              <select
                value={formato}
                onChange={(e) => {
                  setFormato(e.target.value);
                  if (e.target.value === 'fcbk') setEscopo('completo');
                }}
                className="w-full rounded-xl border border-border/60 bg-card/60 px-3 py-2.5 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary transition-all"
              >
                <option value="excel">Planilha Excel (.xlsx) - Com abas detalhadas</option>
                <option value="csv">Planilha CSV (.csv)</option>
                <option value="pdf">Relatório PDF (.pdf) - Com gráficos</option>
                <option value="fcbk">Backup Seguro Criptografado (.fcbk)</option>
              </select>
            </div>

            {/* Escopo */}
            <div className="space-y-1.5">
              <label className="text-xs font-bold uppercase text-slate-500 dark:text-slate-400 flex items-center gap-1.5">
                <Layers className="h-3.5 w-3.5" />
                Tipo de Dados / Escopo
              </label>
              <select
                value={escopo}
                onChange={(e) => setEscopo(e.target.value)}
                disabled={formato === 'fcbk'}
                className="w-full rounded-xl border border-border/60 bg-card/60 px-3 py-2.5 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary transition-all disabled:opacity-60"
              >
                <option value="completo">Completo (Geral + Investimentos)</option>
                <option value="geral">Geral (Movimentações e Resumo)</option>
                <option value="investimentos">Investimentos (Carteira e Transações)</option>
              </select>
            </div>

            {/* Date Range */}
            {formato !== 'fcbk' && (
              <div className="grid sm:grid-cols-2 gap-4">
                <div className="space-y-1.5">
                  <label className="text-xs font-bold uppercase text-slate-500 dark:text-slate-400 flex items-center gap-1.5">
                    <Calendar className="h-3.5 w-3.5" />
                    Data de Início
                  </label>
                  <Input
                    type="date"
                    value={dataInicio}
                    onChange={(e) => setDataInicio(e.target.value)}
                    className="w-full focus-visible:ring-primary bg-card"
                  />
                </div>
                <div className="space-y-1.5">
                  <label className="text-xs font-bold uppercase text-slate-500 dark:text-slate-400 flex items-center gap-1.5">
                    <Calendar className="h-3.5 w-3.5" />
                    Data de Fim
                  </label>
                  <Input
                    type="date"
                    value={dataFim}
                    onChange={(e) => setDataFim(e.target.value)}
                    className="w-full focus-visible:ring-primary bg-card"
                  />
                </div>
              </div>
            )}

            {/* Password input for fcbk */}
            {formato === 'fcbk' && (
              <div className="p-4 rounded-xl border border-primary/20 bg-primary/5 space-y-3">
                <div className="space-y-1.5">
                  <label className="text-xs font-semibold text-slate-600 dark:text-slate-400 flex items-center gap-1.5">
                    <Lock className="h-3.5 w-3.5" />
                    Senha de Criptografia
                  </label>
                  <div className="relative">
                    <Input
                      type={showBackupPassword ? 'text' : 'password'}
                      placeholder="Defina uma senha forte para seu backup..."
                      value={backupPassword}
                      onChange={(e) => setBackupPassword(e.target.value)}
                      className="pr-10 border-primary/30 focus-visible:ring-primary bg-card"
                      disabled={isDownloading}
                    />
                    <button
                      type="button"
                      onClick={() => setShowBackupPassword(!showBackupPassword)}
                      className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600 dark:hover:text-slate-300 transition-colors"
                      disabled={isDownloading}
                    >
                      {showBackupPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                    </button>
                  </div>
                </div>
                <p className="text-[10px] text-muted-foreground">
                  * Importante: Sem esta senha, não será possível restaurar seus dados caso precise utilizar o backup futuramente.
                </p>
              </div>
            )}
          </div>

          <Button
            id="btn-exportar"
            onClick={handleDownload}
            disabled={isDownloading || (formato === 'fcbk' && !backupPassword.trim())}
            className="w-full gap-2 py-3 text-sm font-bold animate-pulse-slow"
          >
            {isDownloading ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                Gerando arquivo...
              </>
            ) : (
              <>
                <DownloadCloud className="h-4 w-4" />
                Iniciar Download
              </>
            )}
          </Button>
        </div>

        {/* Notice Panel */}
        <div className="lg:col-span-2 space-y-4">
          <div className="p-4 rounded-xl border border-border/40 bg-card space-y-3">
            <h3 className="text-xs font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400 flex items-center gap-1.5">
              <ShieldCheck className="h-4 w-4 text-primary" />
              Garantia de Privacidade
            </h3>
            <p className="text-xs text-muted-foreground leading-relaxed">
              Todos os seus dados exportados são gerados em tempo real diretamente da base de dados e transmitidos por conexões seguras HTTPS. Backups do tipo <strong>.fcbk</strong> recebem uma camada de proteção adicional com o algoritmo de criptografia militar robusto AES-GCM.
            </p>
          </div>

          <div className="p-4 rounded-xl border border-blue-200 dark:border-blue-800 bg-blue-50 dark:bg-blue-900/20">
            <div className="flex gap-2">
              <Info className="h-4 w-4 text-blue-600 dark:text-blue-400 shrink-0 mt-0.5" />
              <div className="space-y-1">
                <h4 className="text-xs font-bold text-blue-800 dark:text-blue-300">Formatos Recomendados</h4>
                <p className="text-[11px] text-blue-700/80 dark:text-blue-400">
                  - Use <strong>Excel (.xlsx)</strong> para auditorias, dashboards manuais e análises de balanceamento por abas.<br/>
                  - Use <strong>PDF</strong> para uma apresentação visual limpa da carteira com gráficos de pizza inclusos.
                </p>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Privacy Notice footer block */}
      <div className="rounded-2xl border border-border/40 bg-card p-6 space-y-4">
        <div className="flex items-center gap-3">
          <ShieldCheck className="h-5 w-5 text-primary shrink-0" />
          <h2 className="font-bold text-foreground">Seus Dados, Seu Controle</h2>
        </div>

        <div className="grid sm:grid-cols-3 gap-4">
          {[
            {
              icon: Database,
              title: 'O que armazenamos',
              desc: 'Movimentações financeiras, categorias, cartões de crédito e configurações de conta. Nunca armazenamos senhas bancárias.',
              color: 'text-primary',
            },
            {
              icon: Lock,
              title: 'Criptografia',
              desc: 'Todos os dados são transmitidos via HTTPS. Os backups .fcbk usam criptografia AES-GCM com chave derivada da sua senha.',
              color: 'text-primary',
            },
            {
              icon: Info,
              title: 'Direito de portabilidade',
              desc: 'Você pode exportar e deletar seus dados a qualquer momento, em conformidade com a LGPD e boas práticas de privacidade.',
              color: 'text-primary',
            },
          ].map(({ icon: Icon, title, desc, color }) => (
            <div key={title} className="space-y-2">
              <div className="flex items-center gap-2">
                <Icon className={`h-4 w-4 ${color}`} />
                <span className="text-sm font-semibold text-foreground">{title}</span>
              </div>
              <p className="text-xs text-muted-foreground leading-relaxed">{desc}</p>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
