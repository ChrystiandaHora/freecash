/**
 * Painel principal da tela de Exportação & Backup: baixa todos os dados do usuário
 * num ZIP protegido com AES-256.
 *
 * Dois passos à esquerda (definir a senha, baixar) e, à direita, o manifesto do que
 * vem no arquivo. O mesmo ZIP serve de backup (volta por Ferramentas › Importar) e de
 * portabilidade. A senha vai no corpo de um POST, nunca na URL, e é apagada da memória
 * depois do download.
 *
 * O botão nunca fica desabilitado por senha inválida: botão morto não diz o que falta.
 * O envio valida, mostra o problema junto do campo e leva o foco até ele.
 *
 * @returns {JSX.Element} Seção com os passos, o feedback do download e o manifesto.
 */
import { useRef, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { AlertTriangle, Check, CheckCircle2, Download, Loader2 } from 'lucide-react';
import api from '../../services/api';
import { Button } from '../ui/Button';
import { PasswordInput } from '../ui/PasswordInput';
import { Alert } from '../ui/Alert';
import { TAMANHO_MINIMO } from '../../lib/politicaSenha';
import {
  CHAVE_STATUS_DO_BACKUP,
  nomeDoBackup,
  progressoDaSenha,
  TIPOS_MIME,
  validarSenhaDoBackup,
} from '../../lib/exportacao';
import { baixarArquivo, mensagemDeErro } from './baixarArquivo';
import { ConteudoDoArquivo } from './ConteudoDoArquivo';

function MarcadorDoPasso({ numero, concluido }) {
  return (
    <span
      aria-hidden="true"
      className={`relative z-10 flex h-7 w-7 shrink-0 items-center justify-center rounded-full border-2 text-xs font-bold transition-colors ${
        concluido
          ? 'border-primary bg-primary text-primary-foreground'
          : 'border-primary bg-card text-foreground'
      }`}
    >
      {concluido ? <Check className="h-3.5 w-3.5" strokeWidth={3} /> : numero}
    </span>
  );
}

export function LevarMeusDados() {
  const queryClient = useQueryClient();
  const campoSenha = useRef(null);
  const campoConfirmacao = useRef(null);

  const [senha, setSenha] = useState('');
  const [confirmacao, setConfirmacao] = useState('');
  const [confirmacaoTocada, setConfirmacaoTocada] = useState(false);
  const [gerando, setGerando] = useState(false);
  const [resultado, setResultado] = useState(null);

  const problema = validarSenhaDoBackup(senha, confirmacao);
  const senhaCurta = senha.length < TAMANHO_MINIMO;
  const coincidem = Boolean(confirmacao) && senha === confirmacao;
  const mostrarProblema = confirmacaoTocada && Boolean(problema) && !senhaCurta;
  const progresso = progressoDaSenha(senha);
  const senhaRecusada = resultado?.tipo === 'erro' && senhaCurta;

  const handleSubmit = async (evento) => {
    evento.preventDefault();
    if (problema) {
      setConfirmacaoTocada(true);
      setResultado({ tipo: 'erro', msg: problema });
      (senhaCurta ? campoSenha : campoConfirmacao).current?.focus();
      return;
    }

    setGerando(true);
    setResultado(null);
    try {
      const resposta = await api.post('/api/ferramentas/backup/', { senha }, { responseType: 'blob' });
      const nome = nomeDoBackup();
      baixarArquivo(resposta.data, nome, TIPOS_MIME.zip);
      setSenha('');
      setConfirmacao('');
      setConfirmacaoTocada(false);
      setResultado({ tipo: 'sucesso', nome });
      queryClient.invalidateQueries({ queryKey: CHAVE_STATUS_DO_BACKUP });
    } catch (erro) {
      setResultado({
        tipo: 'erro',
        msg: await mensagemDeErro(erro, 'Não foi possível gerar o backup. Tente de novo em instantes.'),
      });
    } finally {
      setGerando(false);
    }
  };

  return (
    <section
      aria-labelledby="levar-dados-titulo"
      className="overflow-hidden rounded-2xl border border-border/60 bg-card shadow-sm"
    >
      <div className="grid lg:grid-cols-[minmax(0,1fr)_minmax(0,22rem)]">
        <div className="p-6 sm:p-8">
          <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
            Backup completo
          </p>
          <h2 id="levar-dados-titulo" className="mt-1 text-2xl font-bold tracking-tight text-foreground">
            Levar meus dados
          </h2>
          <p className="mt-2 max-w-prose text-sm leading-relaxed text-muted-foreground">
            Tudo o que você registrou, num arquivo{' '}
            <strong className="font-semibold text-foreground">.zip</strong> protegido por senha. Serve para
            guardar uma cópia, importar de volta quando quiser ou levar seus dados para outro lugar.
          </p>

          <form onSubmit={handleSubmit} noValidate className="mt-8">
            <ol className="space-y-8">
              <li
                data-tour="backup-senha"
                className="relative flex gap-4 before:absolute before:bottom-[-2rem] before:left-[13px] before:top-7 before:w-0.5 before:bg-border before:content-['']">
                <MarcadorDoPasso numero={1} concluido={!problema} />
                <div className="min-w-0 flex-1 space-y-4">
                  <h3 className="pt-0.5 text-sm font-semibold text-foreground">Defina uma senha</h3>

                  <div className="grid items-start gap-4 xl:grid-cols-2">
                    <div className="space-y-1.5">
                      <label htmlFor="backup-senha" className="text-sm font-medium text-foreground">
                        Senha do arquivo
                      </label>
                      <PasswordInput
                        id="backup-senha"
                        ref={campoSenha}
                        autoComplete="new-password"
                        value={senha}
                        onChange={(e) => setSenha(e.target.value)}
                        disabled={gerando}
                        aria-invalid={senhaRecusada}
                        aria-describedby="backup-senha-dica"
                        className={senhaRecusada ? 'border-red-600 focus-visible:ring-red-600' : ''}
                      />
                      <div className="flex items-center gap-3" aria-hidden="true">
                        <div className="h-1 flex-1 overflow-hidden rounded-full bg-muted">
                          <div
                            className="h-full rounded-full bg-primary transition-[width] duration-200 motion-reduce:transition-none"
                            style={{ width: `${progresso * 100}%` }}
                          />
                        </div>
                        <span className="w-28 shrink-0 text-right text-xs tabular-nums text-muted-foreground">
                          {senhaCurta ? `${senha.length} de ${TAMANHO_MINIMO}` : 'Tamanho ok'}
                        </span>
                      </div>
                      <p id="backup-senha-dica" className="text-xs text-muted-foreground">
                        Pelo menos {TAMANHO_MINIMO} caracteres. Uma frase curta é mais fácil de lembrar.
                      </p>
                    </div>

                    <div className="space-y-1.5">
                      <label htmlFor="backup-confirmar-senha" className="text-sm font-medium text-foreground">
                        Repita a senha
                      </label>
                      <PasswordInput
                        id="backup-confirmar-senha"
                        ref={campoConfirmacao}
                        autoComplete="new-password"
                        value={confirmacao}
                        onChange={(e) => setConfirmacao(e.target.value)}
                        onBlur={() => setConfirmacaoTocada(true)}
                        disabled={gerando}
                        aria-invalid={mostrarProblema}
                        aria-describedby={mostrarProblema ? 'backup-senha-erro' : undefined}
                        className={mostrarProblema ? 'border-red-600 focus-visible:ring-red-600' : ''}
                      />
                      {mostrarProblema && (
                        <p
                          id="backup-senha-erro"
                          className="flex items-center gap-1.5 text-xs font-medium text-red-700 dark:text-red-400"
                        >
                          <AlertTriangle className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
                          {problema}
                        </p>
                      )}
                      {coincidem && !senhaCurta && (
                        <p className="flex items-center gap-1.5 text-xs font-medium text-emerald-700 dark:text-emerald-400">
                          <CheckCircle2 className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
                          As senhas coincidem
                        </p>
                      )}
                    </div>
                  </div>
                </div>
              </li>

              <li className="relative flex gap-4">
                <MarcadorDoPasso numero={2} concluido={resultado?.tipo === 'sucesso'} />
                <div className="min-w-0 flex-1 space-y-4">
                  <div>
                    <h3 className="pt-0.5 text-sm font-semibold text-foreground">Baixe e guarde</h3>
                    <p className="mt-1 text-sm text-muted-foreground">
                      A senha não fica guardada em lugar nenhum. Sem ela, nem você nem o freecash conseguem
                      abrir o arquivo.
                    </p>
                  </div>

                  <Button
                    type="submit"
                    id="btn-baixar-dados"
                      data-tour="backup-baixar"
                    size="lg"
                    disabled={gerando}
                    aria-describedby={resultado ? 'backup-resultado' : undefined}
                    className="w-full gap-2 sm:w-auto"
                  >
                    {gerando ? (
                      <>
                        <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
                        Gerando o arquivo...
                      </>
                    ) : (
                      <>
                        <Download className="h-4 w-4" aria-hidden="true" />
                        Baixar meus dados
                      </>
                    )}
                  </Button>

                  <div id="backup-resultado">
                    {resultado?.tipo === 'sucesso' && (
                      <Alert variant="success" icon={CheckCircle2} title="Download iniciado">
                        <span className="break-all font-mono">{resultado.nome}</span>. Guarde o arquivo e a
                        senha em lugares diferentes.
                      </Alert>
                    )}
                    {resultado?.tipo === 'erro' && (
                      <Alert variant="error" icon={AlertTriangle}>
                        <span className="font-medium">{resultado.msg}</span>
                      </Alert>
                    )}
                  </div>
                </div>
              </li>
            </ol>
          </form>
        </div>

        <aside
          data-tour="backup-conteudo"
          aria-label="Conteúdo do backup"
          className="border-t border-border/60 bg-muted/40 p-6 sm:p-8 lg:border-l lg:border-t-0"
        >
          <ConteudoDoArquivo />
        </aside>
      </div>
    </section>
  );
}
