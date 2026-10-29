/**
 * Relatórios por período da tela de Exportação & Backup (Excel, CSV e PDF).
 *
 * São resumos para ler e analisar, recortados por período e conteúdo; não cobrem tudo
 * e não voltam para o sistema — o arquivo completo é o do `LevarMeusDados`. O formato
 * é um grupo de rádios nativos (setas trocam a opção, como o leitor de tela espera).
 *
 * @returns {JSX.Element} Seção com formato, período, conteúdo e o download.
 */
import { useState } from 'react';
import {
  AlertTriangle,
  CheckCircle2,
  FileDown,
  FileSpreadsheet,
  FileText,
  Loader2,
  Table2,
} from 'lucide-react';
import api from '../../services/api';
import { Button } from '../ui/Button';
import { Input } from '../ui/Input';
import { Select } from '../ui/Select';
import { ATALHOS_DE_PERIODO } from '../../lib/datas';
import { nomeDoRelatorio, periodoPadrao, TIPOS_MIME } from '../../lib/exportacao';
import { baixarArquivo, mensagemDeErro } from './baixarArquivo';

const FORMATOS = [
  { valor: 'excel', nome: 'Excel', icon: FileSpreadsheet, desc: 'Abas por assunto, para filtrar e somar.' },
  { valor: 'csv', nome: 'CSV', icon: Table2, desc: 'Uma tabela simples, abre em qualquer planilha.' },
  { valor: 'pdf', nome: 'PDF', icon: FileText, desc: 'Resumo com gráficos, para ler ou imprimir.' },
];

const IDS_DOS_ATALHOS = ['mes-atual', 'mes-anterior', 'ultimos-30'];

// "Este ano" aqui vai até hoje: relatório de dias que ainda não vieram não diz nada
const ATALHOS = [
  ...ATALHOS_DE_PERIODO.filter((a) => IDS_DOS_ATALHOS.includes(a.id)).map((a) => ({
    id: a.id,
    rotulo: a.rotulo,
    calcular: () => {
      const { from, to } = a.calcular();
      return { inicio: from, fim: to };
    },
  })),
  { id: 'ano-ate-hoje', rotulo: 'Este ano', calcular: () => periodoPadrao() },
];

const ROTULO_DE_GRUPO = 'text-sm font-medium text-foreground';

export function RelatoriosPorPeriodo({ className = '' }) {
  const [formato, setFormato] = useState('excel');
  const [escopo, setEscopo] = useState('completo');
  const [periodo, setPeriodo] = useState(() => periodoPadrao());
  const [gerando, setGerando] = useState(false);
  const [resultado, setResultado] = useState(null);

  const periodoInvalido = Boolean(periodo.inicio && periodo.fim && periodo.inicio > periodo.fim);

  const handleSubmit = async (evento) => {
    evento.preventDefault();
    if (!periodo.inicio || !periodo.fim || periodoInvalido) {
      setResultado({ tipo: 'erro', msg: 'Escolha um período em que o início venha antes do fim.' });
      return;
    }
    setGerando(true);
    setResultado(null);
    try {
      const resposta = await api.get('/api/ferramentas/exportar/', {
        params: { formato, escopo, data_inicio: periodo.inicio, data_fim: periodo.fim },
        responseType: 'blob',
      });
      const nome = nomeDoRelatorio(formato, periodo.inicio, periodo.fim);
      baixarArquivo(resposta.data, nome, TIPOS_MIME[formato]);
      setResultado({ tipo: 'sucesso', nome });
    } catch (erro) {
      setResultado({
        tipo: 'erro',
        msg: await mensagemDeErro(erro, 'Não foi possível gerar o relatório. Tente de novo em instantes.'),
      });
    } finally {
      setGerando(false);
    }
  };

  return (
    <section
      aria-labelledby="relatorios-titulo"
      className={`rounded-2xl border border-border/60 bg-card p-6 shadow-sm sm:p-8 ${className}`}
    >
      <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
        Para ler e analisar
      </p>
      <h2 id="relatorios-titulo" className="mt-1 text-lg font-bold tracking-tight text-foreground">
        Relatórios por período
      </h2>
      <p className="mt-1 text-sm text-muted-foreground">
        Resumos de um intervalo de datas. Não voltam para o sistema — para isso, use o backup.
      </p>

      <form onSubmit={handleSubmit} noValidate className="mt-6 space-y-6">
        <fieldset>
          <legend className={ROTULO_DE_GRUPO}>Formato</legend>
          <div className="mt-2 grid gap-3 sm:grid-cols-3">
            {FORMATOS.map(({ valor, nome, icon: Icon, desc }) => (
              <label
                key={valor}
                htmlFor={`relatorio-formato-${valor}`}
                className="grid cursor-pointer grid-cols-[auto_minmax(0,1fr)] items-center gap-x-3 gap-y-0.5 rounded-xl border border-border p-3 transition-colors hover:bg-muted/50 has-[:checked]:border-primary has-[:checked]:bg-primary/5 has-[:focus-visible]:ring-2 has-[:focus-visible]:ring-ring has-[:focus-visible]:ring-offset-2"
              >
                <input
                  type="radio"
                  id={`relatorio-formato-${valor}`}
                  name="relatorio-formato"
                  value={valor}
                  checked={formato === valor}
                  onChange={() => setFormato(valor)}
                  className="h-4 w-4 accent-[#007acc]"
                />
                <span className="flex items-center gap-1.5 text-sm font-semibold text-foreground">
                  <Icon className="h-4 w-4 text-primary" aria-hidden="true" />
                  {nome}
                </span>
                <span className="col-start-2 text-xs text-muted-foreground">{desc}</span>
              </label>
            ))}
          </div>
        </fieldset>

        <fieldset>
          <legend className={ROTULO_DE_GRUPO}>Período</legend>
          <div className="mt-2 flex flex-wrap gap-2">
            {ATALHOS.map((atalho) => {
              const alvo = atalho.calcular();
              const ativo = alvo.inicio === periodo.inicio && alvo.fim === periodo.fim;
              return (
                <button
                  key={atalho.id}
                  type="button"
                  aria-pressed={ativo}
                  onClick={() => setPeriodo(atalho.calcular())}
                  className={`h-11 rounded-full border px-4 text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 ${
                    ativo
                      ? 'border-foreground bg-foreground text-background'
                      : 'border-border bg-card text-foreground hover:bg-muted/60'
                  }`}
                >
                  {atalho.rotulo}
                </button>
              );
            })}
          </div>
          <div className="mt-3 grid grid-cols-2 gap-3 sm:max-w-md">
            <div className="space-y-1.5">
              <label htmlFor="relatorio-data-inicio" className="text-xs font-medium text-muted-foreground">
                De
              </label>
              <Input
                id="relatorio-data-inicio"
                type="date"
                value={periodo.inicio}
                onChange={(e) => setPeriodo((atual) => ({ ...atual, inicio: e.target.value }))}
                aria-invalid={periodoInvalido}
                aria-describedby={periodoInvalido ? 'relatorio-periodo-erro' : undefined}
              />
            </div>
            <div className="space-y-1.5">
              <label htmlFor="relatorio-data-fim" className="text-xs font-medium text-muted-foreground">
                Até
              </label>
              <Input
                id="relatorio-data-fim"
                type="date"
                value={periodo.fim}
                onChange={(e) => setPeriodo((atual) => ({ ...atual, fim: e.target.value }))}
                aria-invalid={periodoInvalido}
                aria-describedby={periodoInvalido ? 'relatorio-periodo-erro' : undefined}
              />
            </div>
          </div>
          {periodoInvalido && (
            <p id="relatorio-periodo-erro" className="mt-2 flex items-center gap-1.5 text-xs font-medium text-red-700 dark:text-red-400">
              <AlertTriangle className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
              O início precisa vir antes do fim.
            </p>
          )}
        </fieldset>

        <div className="space-y-1.5 sm:max-w-md">
          <label htmlFor="relatorio-escopo" className={ROTULO_DE_GRUPO}>
            Conteúdo
          </label>
          <Select id="relatorio-escopo" value={escopo} onChange={(e) => setEscopo(e.target.value)}>
            <option value="completo">Tudo (movimentações e investimentos)</option>
            <option value="geral">Só movimentações</option>
            <option value="investimentos">Só investimentos</option>
          </Select>
        </div>

        <div className="flex flex-col gap-3 border-t border-border/60 pt-5 sm:flex-row sm:items-center">
          <Button
            type="submit"
            id="btn-baixar-relatorio"
            variant="outline"
            disabled={gerando}
            aria-describedby={resultado ? 'relatorio-resultado' : undefined}
            className="h-11 gap-2"
          >
            {gerando ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
                Gerando o relatório...
              </>
            ) : (
              <>
                <FileDown className="h-4 w-4" aria-hidden="true" />
                Baixar relatório
              </>
            )}
          </Button>
          <div id="relatorio-resultado" className="min-w-0 flex-1">
            {resultado?.tipo === 'sucesso' && (
              <p role="status" className="flex items-center gap-1.5 text-sm font-medium text-emerald-700 dark:text-emerald-400">
                <CheckCircle2 className="h-4 w-4 shrink-0" aria-hidden="true" />
                <span className="break-all">Download iniciado: {resultado.nome}</span>
              </p>
            )}
            {resultado?.tipo === 'erro' && (
              <p role="alert" className="flex items-center gap-1.5 text-sm font-medium text-red-700 dark:text-red-400">
                <AlertTriangle className="h-4 w-4 shrink-0" aria-hidden="true" />
                {resultado.msg}
              </p>
            )}
          </div>
        </div>
      </form>
    </section>
  );
}
