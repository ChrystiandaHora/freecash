/**
 * Minha Conta — dados de acesso, credenciais e preferências.
 *
 * Acessível pelo menu da conta, no avatar do cabeçalho.
 *
 * A primeira versão herdou o vocabulário das telas públicas de autenticação (coluna
 * estreita, `h1` menor, sem animação) e parecia pertencer a outro produto. Foi
 * repaginada para a linguagem das telas autenticadas: largura total, grid e linha de
 * indicadores na abertura.
 *
 * Quatro decisões de leitura:
 *
 * **A tela abre mostrando, não pedindo.** Antes eram 9 campos e nenhuma informação;
 * agora a primeira linha responde quem sou, se o e-mail está confirmado e quantos
 * dispositivos estão conectados.
 *
 * **Senha e Sessões ficam lado a lado**, porque trocar a senha encerra as sessões — ver
 * as duas juntas é o que torna a consequência compreensível.
 *
 * **O vermelho vive no botão, não na moldura.** A borda vermelha permanente acendia o
 * sinal mais forte da interface para quem só queria trocar a moeda; a confirmação
 * passou para um `ui/Modal`.
 *
 * **Estado nunca depende só de cor:** o selo de e-mail usa ícone e texto, e os erros de
 * campo são ligados por `aria-describedby`.
 */
import { useEffect, useRef, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import {
  AlertCircle,
  AlertTriangle,
  Loader2,
  Mail,
  MonitorSmartphone,
  RefreshCw,
  ShieldCheck,
  Trash2,
  User as UserIcon,
} from 'lucide-react';

import { Alert } from '../components/ui/Alert';
import { Badge } from '../components/ui/Badge';
import { Button } from '../components/ui/Button';
import { Card, CardContent, CardHeader } from '../components/ui/Card';
import { Input } from '../components/ui/Input';
import { Modal } from '../components/ui/Modal';
import { PasswordInput } from '../components/ui/PasswordInput';
import { SectionLabel } from '../components/ui/SectionLabel';
import { Select } from '../components/ui/Select';
import { useAuth } from '../context/AuthProvider';
import { useToast } from '../context/ToastContext';
import { extrairErros } from '../lib/apiErros';
import { setAccessToken } from '../services/api';
import {
  alterarSenha,
  atualizarPerfil,
  buscarConta,
  buscarSessoes,
  cancelarTrocaEmail,
  encerrarOutrasSessoes,
  excluirConta,
  solicitarTrocaEmail,
} from '../services/auth';

const MOEDAS = [
  { valor: 'BRL', rotulo: 'Real (BRL)' },
  { valor: 'USD', rotulo: 'Dólar (USD)' },
  { valor: 'EUR', rotulo: 'Euro (EUR)' },
];

/**
 * Formata uma data ISO no formato curto brasileiro.
 *
 * @param {string} iso - Data em formato ISO.
 * @returns {string} Data legível, ou travessão quando ausente.
 */
function formatarData(iso) {
  if (!iso) return '—';
  return new Date(iso).toLocaleDateString('pt-BR', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
  });
}

/**
 * Mensagem de erro de um campo, ligada ao controle por `aria-describedby`.
 *
 * @param {string} props.id - Identificador referenciado pelo campo.
 * @param {string} [props.mensagem] - Texto do erro; nada é renderizado sem ele.
 * @returns {React.JSX.Element | null}
 */
function ErroCampo({ id, mensagem }) {
  if (!mensagem) return null;
  return (
    <p id={id} className="text-xs text-red-700 dark:text-red-400">
      {mensagem}
    </p>
  );
}

/**
 * Rótulo de campo de formulário, no tratamento tipográfico da casa.
 *
 * `text-sm font-medium text-foreground`, e não o uppercase pequeno — esse é
 * reservado a rótulo de indicador e cabeçalho de bloco. Usá-lo em campo colocava
 * campo e cabeçalho na mesma voz e achatava a hierarquia da tela.
 *
 * @param {string} props.htmlFor - Id do controle rotulado.
 * @param {React.ReactNode} props.children - Texto do rótulo.
 */
function Rotulo({ htmlFor, children }) {
  return (
    <label htmlFor={htmlFor} className="text-sm font-medium text-foreground">
      {children}
    </label>
  );
}

/**
 * Indicador de estado da conta, na anatomia dos stat tiles do app.
 *
 * Rótulo em uppercase pequeno → valor em destaque → linha de apoio.
 *
 * @param {React.ComponentType} props.icon - Ícone ilustrativo.
 * @param {string} props.rotulo - Nome do indicador.
 * @param {React.ReactNode} props.valor - Conteúdo principal.
 * @param {React.ReactNode} [props.apoio] - Linha de contexto abaixo do valor.
 * @param {React.ReactNode} [props.acao] - Ação opcional no rodapé do card.
 */
function Indicador({ icon: Icon, rotulo, valor, apoio, acao }) {
  return (
    <Card className="border-border/40 shadow-sm">
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
            {rotulo}
          </span>
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary/10">
            <Icon className="h-4 w-4 text-primary" aria-hidden="true" />
          </div>
        </div>
      </CardHeader>
      <CardContent>
        <div className="text-2xl font-bold tracking-tight text-foreground">{valor}</div>
        {apoio && <div className="mt-2 text-xs text-muted-foreground">{apoio}</div>}
        {acao && <div className="mt-3">{acao}</div>}
      </CardContent>
    </Card>
  );
}

/**
 * Card de seção com cabeçalho e conteúdo.
 *
 * @param {React.ComponentType} props.icon - Ícone do cabeçalho.
 * @param {string} props.titulo - Título da seção.
 * @param {string} props.descricao - Linha de apoio.
 * @param {React.ReactNode} props.children - Conteúdo.
 */
function Secao({ icon, titulo, descricao, children, className = '' }) {
  return (
    <Card className={`flex flex-col border-border/40 shadow-sm ${className}`}>
      <CardHeader className="pb-4">
        {/* Heading real: a seção é estrutura permanente da página, não cromo
            transitório — ver a decisão de rótulo de seção em A11Y-DECISIONS.md. */}
        <SectionLabel as="h2" icon={icon}>
          {titulo}
        </SectionLabel>
        <p className="mt-1.5 text-sm text-muted-foreground">{descricao}</p>
      </CardHeader>
      <CardContent className="flex flex-1 flex-col">{children}</CardContent>
    </Card>
  );
}

/**
 * Barra de ações de formulário, à direita e separada por régua.
 *
 * @param {React.ReactNode} props.children - Botões da barra.
 */
function BarraAcoes({ children }) {
  return (
    <div className="mt-auto flex flex-wrap justify-end gap-2 border-t border-border/60 pt-4">
      {children}
    </div>
  );
}

/**
 * Esqueleto exibido durante o carregamento, na forma do conteúdo final.
 *
 * Preserva o cabeçalho da página: o spinner anterior substituía a tela inteira e o
 * layout "pulava" quando os dados chegavam.
 */
function EsqueletoConta() {
  return (
    <div role="status" aria-busy="true" className="space-y-6">
      <span className="sr-only">Carregando sua conta...</span>
      <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
        {[0, 1, 2].map((i) => (
          <div key={i} className="rounded-xl border border-border/40 p-5">
            <div className="h-3 w-1/3 animate-pulse rounded bg-muted" />
            <div className="mt-4 h-7 w-2/3 animate-pulse rounded bg-muted" />
            <div className="mt-3 h-3 w-1/2 animate-pulse rounded bg-muted" />
          </div>
        ))}
      </div>
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        {[0, 1].map((i) => (
          <div key={i} className="space-y-4 rounded-xl border border-border/40 p-6">
            <div className="h-4 w-1/4 animate-pulse rounded bg-muted" />
            <div className="h-10 animate-pulse rounded bg-muted" />
            <div className="h-10 animate-pulse rounded bg-muted" />
          </div>
        ))}
      </div>
    </div>
  );
}

/**
 * Formulário de dados do perfil.
 *
 * Componente próprio porque o estado dos campos nasce dos dados carregados. Ele só
 * é montado depois que a consulta responde, então `useState` inicializa direto das
 * props — sem o efeito que copiaria dados para estado a cada mudança.
 *
 * @param {Object} props.conta - Dados da conta já carregados.
 * @param {Object} props.erros - Erros por campo devolvidos pelo servidor.
 * @param {boolean} props.salvando - Se a gravação está em curso.
 * @param {(campos: Object) => void} props.onSalvar - Dispara a gravação.
 */
function SecaoPerfil({ conta, erros, salvando, onSalvar }) {
  const [username, setUsername] = useState(conta.username);
  const [moeda, setMoeda] = useState(conta.moeda_padrao || 'BRL');

  return (
    <Secao
      icon={UserIcon}
      titulo="Dados do perfil"
      descricao="Como você é identificado no sistema."
    >
      <form
        className="flex flex-1 flex-col gap-4"
        onSubmit={(e) => {
          e.preventDefault();
          onSalvar({ username, moeda_padrao: moeda });
        }}
      >
        {erros._geral && (
          <Alert variant="error" icon={AlertCircle} className="text-xs">
            <span className="font-medium">{erros._geral}</span>
          </Alert>
        )}

        <div className="space-y-1.5">
          <Rotulo htmlFor="conta-username">Nome de usuário</Rotulo>
          <Input
            id="conta-username"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            autoComplete="username"
            aria-invalid={!!erros.username}
            aria-describedby={erros.username ? 'erro-conta-username' : undefined}
          />
          <ErroCampo id="erro-conta-username" mensagem={erros.username} />
        </div>

        <div className="space-y-1.5">
          <Rotulo htmlFor="conta-moeda">Moeda padrão</Rotulo>
          <Select
            id="conta-moeda"
            value={moeda}
            onChange={(e) => setMoeda(e.target.value)}
          >
            {MOEDAS.map((m) => (
              <option key={m.valor} value={m.valor}>{m.rotulo}</option>
            ))}
          </Select>
        </div>

        <BarraAcoes>
          <Button type="submit" disabled={salvando} className="gap-2">
            {salvando && <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />}
            Salvar perfil
          </Button>
        </BarraAcoes>
      </form>
    </Secao>
  );
}

export default function MinhaConta() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { addToast } = useToast();
  const { recarregarPerfil, logout } = useAuth();

  const { data: conta, isLoading, isError, isFetching, refetch } = useQuery({
    queryKey: ['conta'],
    queryFn: buscarConta,
  });

  const { data: sessoes } = useQuery({
    queryKey: ['conta', 'sessoes'],
    queryFn: buscarSessoes,
  });

  // Cada seção guarda os próprios erros: um erro de senha não deve marcar o
  // formulário de perfil como inválido.
  const [errosPerfil, setErrosPerfil] = useState({});
  const [errosEmail, setErrosEmail] = useState({});
  const [errosSenha, setErrosSenha] = useState({});
  const [errosExclusao, setErrosExclusao] = useState({});

  const [emailSenha, setEmailSenha] = useState('');
  const [novoEmail, setNovoEmail] = useState('');

  const [senhaAtual, setSenhaAtual] = useState('');
  const [novaSenha, setNovaSenha] = useState('');
  const [confirmarSenha, setConfirmarSenha] = useState('');

  const [exclusaoAberta, setExclusaoAberta] = useState(false);
  const [exclusaoSenha, setExclusaoSenha] = useState('');
  const [exclusaoConfirmacao, setExclusaoConfirmacao] = useState('');

  const avisoExclusaoRef = useRef(null);

  // O foco vai para o aviso quando o diálogo abre. O `ui/Modal` já foca o primeiro
  // elemento focável, mas aqui o primeiro é um campo de senha — e quem chegou até
  // aqui precisa ler o aviso antes de começar a digitar.
  useEffect(() => {
    if (exclusaoAberta) {
      avisoExclusaoRef.current?.focus();
    }
  }, [exclusaoAberta]);

  const aoFalhar = (setErros, padrao) => (erro) => {
    const { porCampo, geral } = extrairErros(erro, padrao);
    setErros({ ...porCampo, _geral: geral });
  };

  const mutPerfil = useMutation({
    mutationFn: atualizarPerfil,
    onMutate: () => setErrosPerfil({}),
    onSuccess: (dados) => {
      queryClient.setQueryData(['conta'], dados);
      recarregarPerfil();
      addToast('Perfil atualizado.', 'success');
    },
    onError: aoFalhar(setErrosPerfil, 'Não foi possível salvar o perfil.'),
  });

  const mutEmail = useMutation({
    mutationFn: solicitarTrocaEmail,
    onMutate: () => setErrosEmail({}),
    onSuccess: (dados) => {
      queryClient.invalidateQueries({ queryKey: ['conta'] });
      setEmailSenha('');
      setNovoEmail('');
      addToast(dados.detail, 'success');
    },
    onError: aoFalhar(setErrosEmail, 'Não foi possível solicitar a troca de e-mail.'),
  });

  const mutCancelarEmail = useMutation({
    mutationFn: cancelarTrocaEmail,
    onSuccess: (dados) => {
      queryClient.setQueryData(['conta'], dados);
      addToast('Troca de e-mail cancelada.', 'success');
    },
    onError: aoFalhar(setErrosEmail, 'Não foi possível cancelar a troca.'),
  });

  const mutSenha = useMutation({
    mutationFn: alterarSenha,
    onMutate: () => setErrosSenha({}),
    onSuccess: (dados) => {
      // A troca revoga tudo e devolve uma sessão nova: sem gravar o access, a
      // própria aba cairia na requisição seguinte.
      if (dados.access) setAccessToken(dados.access);
      queryClient.invalidateQueries({ queryKey: ['conta', 'sessoes'] });
      setSenhaAtual('');
      setNovaSenha('');
      setConfirmarSenha('');
      addToast(dados.detail, 'success');
    },
    onError: aoFalhar(setErrosSenha, 'Não foi possível alterar a senha.'),
  });

  const mutSessoes = useMutation({
    mutationFn: encerrarOutrasSessoes,
    onSuccess: (dados) => {
      if (dados.access) setAccessToken(dados.access);
      queryClient.invalidateQueries({ queryKey: ['conta', 'sessoes'] });
      addToast(dados.detail, 'success');
    },
    onError: (erro) => {
      const { geral } = extrairErros(erro, 'Não foi possível encerrar as sessões.');
      addToast(geral, 'error');
    },
  });

  const mutExcluir = useMutation({
    mutationFn: excluirConta,
    onMutate: () => setErrosExclusao({}),
    onSuccess: async () => {
      // `logout` limpa o token em memória e o estado do contexto. O cookie já foi
      // removido pelo servidor; sem esta limpeza o app seguiria se achando logado
      // numa conta que não existe mais.
      await logout();
      navigate('/login');
    },
    onError: aoFalhar(setErrosExclusao, 'Não foi possível excluir a conta.'),
  });

  const fecharExclusao = () => {
    setExclusaoAberta(false);
    setExclusaoSenha('');
    setExclusaoConfirmacao('');
    setErrosExclusao({});
  };

  const cabecalho = (
    <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
      <div>
        <h1 className="text-3xl font-extrabold tracking-tight text-foreground">
          Minha Conta
        </h1>
        <p className="mt-1 text-slate-500 dark:text-slate-400">
          Seus dados de acesso, credenciais e preferências
        </p>
      </div>
      <Button
        variant="outline"
        size="sm"
        onClick={() => refetch()}
        disabled={isFetching}
        className="shrink-0"
      >
        <RefreshCw
          className={`mr-1.5 h-4 w-4 ${isFetching ? 'animate-spin' : ''}`}
          aria-hidden="true"
        />
        Atualizar
      </Button>
    </div>
  );

  if (isLoading) {
    return (
      <div className="space-y-6 animate-fade-in">
        {cabecalho}
        <EsqueletoConta />
      </div>
    );
  }

  if (isError) {
    return (
      <div className="space-y-6 animate-fade-in">
        {cabecalho}
        <Alert variant="error" icon={AlertCircle}>
          <span className="font-medium">Não foi possível carregar os dados da conta.</span>
        </Alert>
      </div>
    );
  }

  return (
    <div className="space-y-6 animate-fade-in">
      {cabecalho}

      {/* ── Estado da conta ────────────────────────────────────────────────── */}
      <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
        <Indicador
          icon={UserIcon}
          rotulo="Conta"
          valor={<span className="break-all">{conta.username}</span>}
          apoio={`Membro desde ${formatarData(conta.data_cadastro)}`}
        />

        <Indicador
          icon={Mail}
          rotulo="E-mail"
          valor={
            <span className="break-all text-base font-semibold sm:text-lg">
              {conta.email || 'não cadastrado'}
            </span>
          }
          apoio={
            conta.email ? (
              <Badge variant={conta.email_verificado ? 'success' : 'warning'}>
                {conta.email_verificado ? (
                  <ShieldCheck className="mr-1 h-3 w-3" aria-hidden="true" />
                ) : (
                  <AlertTriangle className="mr-1 h-3 w-3" aria-hidden="true" />
                )}
                {conta.email_verificado ? 'confirmado' : 'não confirmado'}
              </Badge>
            ) : (
              <Badge variant="warning">
                <AlertTriangle className="mr-1 h-3 w-3" aria-hidden="true" />
                sem recuperação de senha
              </Badge>
            )
          }
        />

        <Indicador
          icon={MonitorSmartphone}
          rotulo="Sessões"
          valor={sessoes ? sessoes.ativas : '—'}
          apoio={
            sessoes
              ? `Dispositivos conectados nos últimos ${sessoes.janela_dias} dias`
              : 'Carregando...'
          }
          acao={
            sessoes && sessoes.ativas > 1 ? (
              <Button
                variant="outline"
                size="sm"
                onClick={() => mutSessoes.mutate()}
                disabled={mutSessoes.isPending}
                className="gap-1.5"
              >
                {mutSessoes.isPending && (
                  <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden="true" />
                )}
                Encerrar as outras
              </Button>
            ) : null
          }
        />
      </div>

      {/* ── Perfil e e-mail ────────────────────────────────────────────────── */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <SecaoPerfil
          conta={conta}
          erros={errosPerfil}
          salvando={mutPerfil.isPending}
          onSalvar={(campos) => mutPerfil.mutate(campos)}
        />

        <Secao
          icon={Mail}
          titulo="Endereço de e-mail"
          descricao="É por ele que você recupera o acesso caso esqueça a senha."
        >
          {conta.email_pendente ? (
            <div className="flex flex-1 flex-col gap-4">
              <Alert variant="info" icon={Mail} className="text-xs">
                <span className="font-medium leading-relaxed">
                  Enviamos um link de confirmação para{' '}
                  <strong className="break-all">{conta.email_pendente}</strong>. Seu
                  e-mail atual continua valendo até você abrir esse link.
                </span>
              </Alert>
              <BarraAcoes>
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => mutCancelarEmail.mutate()}
                  disabled={mutCancelarEmail.isPending}
                  className="gap-2"
                >
                  {mutCancelarEmail.isPending && (
                    <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
                  )}
                  Cancelar troca
                </Button>
              </BarraAcoes>
            </div>
          ) : (
            <form
              className="flex flex-1 flex-col gap-4"
              onSubmit={(e) => {
                e.preventDefault();
                mutEmail.mutate({ senha_atual: emailSenha, novo_email: novoEmail });
              }}
            >
              {errosEmail._geral && (
                <Alert variant="error" icon={AlertCircle} className="text-xs">
                  <span className="font-medium">{errosEmail._geral}</span>
                </Alert>
              )}

              <div className="space-y-1.5">
                <Rotulo htmlFor="conta-novo-email">Novo e-mail</Rotulo>
                <Input
                  id="conta-novo-email"
                  type="email"
                  autoComplete="email"
                  placeholder="seu@email.com"
                  value={novoEmail}
                  onChange={(e) => setNovoEmail(e.target.value)}
                  aria-invalid={!!errosEmail.novo_email}
                  aria-describedby={
                    errosEmail.novo_email ? 'erro-conta-novo-email' : undefined
                  }
                />
                <ErroCampo id="erro-conta-novo-email" mensagem={errosEmail.novo_email} />
              </div>

              <div className="space-y-1.5">
                <Rotulo htmlFor="conta-email-senha">Sua senha atual</Rotulo>
                <PasswordInput
                  id="conta-email-senha"
                  autoComplete="current-password"
                  placeholder="••••••••"
                  value={emailSenha}
                  onChange={(e) => setEmailSenha(e.target.value)}
                  aria-invalid={!!errosEmail.senha_atual}
                  aria-describedby={
                    errosEmail.senha_atual
                      ? 'erro-conta-email-senha'
                      : 'ajuda-conta-email-senha'
                  }
                />
                {errosEmail.senha_atual ? (
                  <ErroCampo
                    id="erro-conta-email-senha"
                    mensagem={errosEmail.senha_atual}
                  />
                ) : (
                  <p id="ajuda-conta-email-senha" className="text-xs text-muted-foreground">
                    Pedimos a senha porque é o e-mail que recupera sua conta.
                  </p>
                )}
              </div>

              <BarraAcoes>
                <Button type="submit" disabled={mutEmail.isPending} className="gap-2">
                  {mutEmail.isPending && (
                    <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
                  )}
                  Enviar confirmação
                </Button>
              </BarraAcoes>
            </form>
          )}
        </Secao>
      </div>

      {/* ── Senha e sessões ────────────────────────────────────────────────── */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <Secao
          icon={ShieldCheck}
          titulo="Senha"
          descricao="Ao trocar, as outras sessões da sua conta são encerradas."
        >
          <form
            className="flex flex-1 flex-col gap-4"
            onSubmit={(e) => {
              e.preventDefault();
              mutSenha.mutate({
                senha_atual: senhaAtual,
                nova_senha: novaSenha,
                confirmar: confirmarSenha,
              });
            }}
          >
            {errosSenha._geral && (
              <Alert variant="error" icon={AlertCircle} className="text-xs">
                <span className="font-medium">{errosSenha._geral}</span>
              </Alert>
            )}

            <div className="space-y-1.5">
              <Rotulo htmlFor="conta-senha-atual">Senha atual</Rotulo>
              <PasswordInput
                id="conta-senha-atual"
                autoComplete="current-password"
                placeholder="••••••••"
                value={senhaAtual}
                onChange={(e) => setSenhaAtual(e.target.value)}
                aria-invalid={!!errosSenha.senha_atual}
                aria-describedby={
                  errosSenha.senha_atual ? 'erro-conta-senha-atual' : undefined
                }
              />
              <ErroCampo id="erro-conta-senha-atual" mensagem={errosSenha.senha_atual} />
            </div>

            <div className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-1.5">
                <Rotulo htmlFor="conta-nova-senha">Nova senha</Rotulo>
                <PasswordInput
                  id="conta-nova-senha"
                  autoComplete="new-password"
                  placeholder="••••••••"
                  value={novaSenha}
                  onChange={(e) => setNovaSenha(e.target.value)}
                  aria-invalid={!!errosSenha.nova_senha}
                  aria-describedby={
                    errosSenha.nova_senha ? 'erro-conta-nova-senha' : 'ajuda-conta-nova-senha'
                  }
                />
                <ErroCampo id="erro-conta-nova-senha" mensagem={errosSenha.nova_senha} />
              </div>

              <div className="space-y-1.5">
                <Rotulo htmlFor="conta-confirmar-senha">Confirmar</Rotulo>
                <PasswordInput
                  id="conta-confirmar-senha"
                  autoComplete="new-password"
                  placeholder="••••••••"
                  value={confirmarSenha}
                  onChange={(e) => setConfirmarSenha(e.target.value)}
                  aria-invalid={!!errosSenha.confirmar}
                  aria-describedby={
                    errosSenha.confirmar ? 'erro-conta-confirmar-senha' : undefined
                  }
                />
                <ErroCampo
                  id="erro-conta-confirmar-senha"
                  mensagem={errosSenha.confirmar}
                />
              </div>
            </div>

            {!errosSenha.nova_senha && (
              <p id="ajuda-conta-nova-senha" className="text-xs text-muted-foreground">
                No mínimo 8 caracteres. Evite senhas comuns e parecidas com seu nome de usuário.
              </p>
            )}

            <BarraAcoes>
              <Button type="submit" disabled={mutSenha.isPending} className="gap-2">
                {mutSenha.isPending && (
                  <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
                )}
                Alterar senha
              </Button>
            </BarraAcoes>
          </form>
        </Secao>

        <Secao
          icon={MonitorSmartphone}
          titulo="Sessões ativas"
          descricao="Onde sua conta está conectada no momento."
        >
          <div className="flex flex-1 flex-col gap-4">
            <div className="rounded-xl bg-muted/40 px-4 py-3">
              <p className="text-sm text-foreground">
                <strong>{sessoes ? sessoes.ativas : '—'}</strong>{' '}
                {sessoes?.ativas === 1 ? 'sessão ativa' : 'sessões ativas'}
              </p>
              <p className="mt-1 text-xs text-muted-foreground">
                A contagem cobre os dispositivos que entraram nos últimos{' '}
                {sessoes?.janela_dias ?? 7} dias. Uma sessão fechada sem sair da conta
                continua contando até esse prazo vencer.
              </p>
            </div>

            <p className="text-xs text-muted-foreground">
              Encerrar as outras desconecta todos os demais dispositivos. Esta janela
              continua conectada.
            </p>

            <BarraAcoes>
              <Button
                type="button"
                variant="outline"
                onClick={() => mutSessoes.mutate()}
                disabled={mutSessoes.isPending || !sessoes || sessoes.ativas <= 1}
                className="gap-2"
              >
                {mutSessoes.isPending && (
                  <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
                )}
                Encerrar as outras sessões
              </Button>
            </BarraAcoes>
          </div>
        </Secao>
      </div>

      {/* ── Exclusão ───────────────────────────────────────────────────────── */}
      <Card className="border-border/40 shadow-sm">
        <CardContent className="flex flex-col gap-4 p-6 sm:flex-row sm:items-center sm:justify-between">
          <div>
            {/* Sem borda vermelha no card: a regra da casa é vermelho só no botão.
                Aceso permanentemente, o sinal mais forte da interface aparecia para
                quem só entrou para trocar a moeda padrão. */}
            <SectionLabel as="h2" icon={Trash2}>
              Excluir minha conta
            </SectionLabel>
            <p className="mt-1.5 text-sm text-muted-foreground">
              Apaga a conta e todo o histórico financeiro. Não há como desfazer.
            </p>
          </div>
          <Button
            type="button"
            variant="outline"
            onClick={() => setExclusaoAberta(true)}
            className="shrink-0 border-red-500/40 text-red-700 hover:bg-red-500/10 dark:text-red-400"
          >
            <Trash2 className="mr-1.5 h-4 w-4" aria-hidden="true" />
            Excluir minha conta
          </Button>
        </CardContent>
      </Card>

      <Modal
        isOpen={exclusaoAberta}
        onClose={fecharExclusao}
        title="Excluir minha conta"
        description="Esta ação é permanente e não pode ser desfeita."
        size="sm"
      >
        <form
          className="space-y-4"
          onSubmit={(e) => {
            e.preventDefault();
            mutExcluir.mutate({
              senha_atual: exclusaoSenha,
              confirmacao: exclusaoConfirmacao,
            });
          }}
        >
          <Alert
            ref={avisoExclusaoRef}
            tabIndex={-1}
            variant="error"
            icon={AlertTriangle}
            className="text-xs"
          >
            <span className="font-medium leading-relaxed">
              Serão apagados seus lançamentos, cartões, metas e investimentos.
              Exporte um backup antes, se quiser guardar seus dados.
            </span>
          </Alert>

          {errosExclusao._geral && (
            <Alert variant="error" icon={AlertCircle} className="text-xs">
              <span className="font-medium">{errosExclusao._geral}</span>
            </Alert>
          )}

          <div className="space-y-1.5">
            <Rotulo htmlFor="conta-excluir-senha">Sua senha atual</Rotulo>
            <PasswordInput
              id="conta-excluir-senha"
              autoComplete="current-password"
              placeholder="••••••••"
              value={exclusaoSenha}
              onChange={(e) => setExclusaoSenha(e.target.value)}
              aria-invalid={!!errosExclusao.senha_atual}
              aria-describedby={
                errosExclusao.senha_atual ? 'erro-conta-excluir-senha' : undefined
              }
            />
            <ErroCampo
              id="erro-conta-excluir-senha"
              mensagem={errosExclusao.senha_atual}
            />
          </div>

          <div className="space-y-1.5">
            <Rotulo htmlFor="conta-excluir-confirmacao">
              Digite <strong className="text-foreground">{conta.username}</strong> para confirmar
            </Rotulo>
            <Input
              id="conta-excluir-confirmacao"
              value={exclusaoConfirmacao}
              onChange={(e) => setExclusaoConfirmacao(e.target.value)}
              autoComplete="off"
              aria-invalid={!!errosExclusao.confirmacao}
              aria-describedby={
                errosExclusao.confirmacao ? 'erro-conta-excluir-confirmacao' : undefined
              }
            />
            <ErroCampo
              id="erro-conta-excluir-confirmacao"
              mensagem={errosExclusao.confirmacao}
            />
          </div>

          <div className="flex justify-end gap-2 pt-2">
            <Button type="button" variant="outline" onClick={fecharExclusao}>
              Cancelar
            </Button>
            <Button
              type="submit"
              variant="destructive"
              disabled={mutExcluir.isPending}
              className="gap-2"
            >
              {mutExcluir.isPending ? (
                <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
              ) : (
                <Trash2 className="h-4 w-4" aria-hidden="true" />
              )}
              Excluir permanentemente
            </Button>
          </div>
        </form>
      </Modal>
    </div>
  );
}
