/**
 * Painel de administração de contas de usuário.
 *
 * Lista as contas com busca e filtros, e permite suspender ou reativar o acesso.
 *
 * **Fronteira de privacidade:** a tela mostra metadados de conta — identificação,
 * datas, estado de confirmação e contagem de volume de uso. Nunca transações,
 * saldos ou valores. O servidor sequer devolve esses campos, e há um teste
 * automatizado que falha se algum for publicado.
 *
 * A suspensão é uma ação destrutiva do ponto de vista de quem a sofre: derruba a
 * sessão em curso e impede novo login. Por isso passa por confirmação em `ui/Modal`,
 * com campo de motivo — que fica registrado no histórico administrativo, para que
 * "minha conta foi bloqueada e ninguém sabe por quê" tenha resposta.
 *
 * @module AdminUsuarios
 * @component
 * @returns {React.JSX.Element}
 */
import { useEffect, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { AlertCircle, Loader2, Search, ShieldCheck, ShieldOff } from 'lucide-react';

import { Alert } from '../../components/ui/Alert';
import { Button } from '../../components/ui/Button';
import { Card, CardContent } from '../../components/ui/Card';
import { Input } from '../../components/ui/Input';
import { Modal } from '../../components/ui/Modal';
import { useAuth } from '../../context/AuthProvider';
import { useToast } from '../../context/ToastContext';
import { extrairErros } from '../../lib/apiErros';
import { listarUsuarios, reativarUsuario, suspenderUsuario } from '../../services/admin';

const FILTROS_ESTADO = [
  { valor: '', rotulo: 'Todas' },
  { valor: 'true', rotulo: 'Ativas' },
  { valor: 'false', rotulo: 'Suspensas' },
];

/**
 * Formata uma data ISO para leitura, tolerando valor nulo.
 *
 * @param {string|null} iso - Data em formato ISO.
 * @returns {string} Data formatada, ou um travessão quando ausente.
 */
function formatarData(iso) {
  if (!iso) return '—';
  return new Date(iso).toLocaleDateString('pt-BR', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
  });
}

export default function AdminUsuarios() {
  const { perfil } = useAuth();
  const { addToast } = useToast();
  const queryClient = useQueryClient();

  const [busca, setBusca] = useState('');
  const [buscaAplicada, setBuscaAplicada] = useState('');
  const [ativo, setAtivo] = useState('');
  const [pagina, setPagina] = useState(1);
  const [alvo, setAlvo] = useState(null);
  const [motivo, setMotivo] = useState('');

  // Debounce da busca: sem ele, cada tecla dispararia uma requisição.
  useEffect(() => {
    const id = setTimeout(() => {
      setBuscaAplicada(busca.trim());
      setPagina(1);
    }, 350);
    return () => clearTimeout(id);
  }, [busca]);

  const { data, isLoading, isError } = useQuery({
    queryKey: ['admin', 'usuarios', buscaAplicada, ativo, pagina],
    queryFn: () => listarUsuarios({ busca: buscaAplicada, ativo, page: pagina }),
  });

  const mutacao = useMutation({
    mutationFn: ({ id, suspender, detalhe }) =>
      suspender ? suspenderUsuario(id, detalhe) : reativarUsuario(id, detalhe),
    onSuccess: (resposta) => {
      queryClient.invalidateQueries({ queryKey: ['admin'] });
      addToast(resposta.detail, 'success');
      fecharConfirmacao();
    },
    onError: (erro) => {
      const { geral } = extrairErros(erro, 'Não foi possível concluir a ação.');
      addToast(geral, 'error');
    },
  });

  const fecharConfirmacao = () => {
    setAlvo(null);
    setMotivo('');
  };

  const confirmar = () => {
    if (!alvo) return;
    mutacao.mutate({
      id: alvo.id,
      suspender: alvo.is_active,
      detalhe: motivo.trim(),
    });
  };

  const total = data?.count ?? 0;
  const usuarios = data?.results ?? [];
  const temProxima = Boolean(data?.next);

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-bold tracking-tight text-foreground">
          Contas de usuário
        </h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Administração de acesso. Os dados financeiros das contas não são exibidos aqui.
        </p>
      </header>

      {/* Filtros numa única linha acima da lista. */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
        <div className="flex-1 space-y-1.5">
          <label
            htmlFor="admin-busca"
            className="text-xs font-semibold uppercase tracking-wide text-muted-foreground"
          >
            Buscar
          </label>
          <div className="relative">
            <Search
              className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground"
              aria-hidden="true"
            />
            <Input
              id="admin-busca"
              type="search"
              placeholder="Nome de usuário ou e-mail"
              value={busca}
              onChange={(e) => setBusca(e.target.value)}
              className="rounded-xl pl-9"
            />
          </div>
        </div>

        <div className="space-y-1.5">
          <span
            id="rotulo-filtro-estado"
            className="block text-xs font-semibold uppercase tracking-wide text-muted-foreground"
          >
            Estado
          </span>
          <div role="group" aria-labelledby="rotulo-filtro-estado" className="flex gap-1">
            {FILTROS_ESTADO.map(({ valor, rotulo }) => (
              <button
                key={rotulo}
                type="button"
                onClick={() => {
                  setAtivo(valor);
                  setPagina(1);
                }}
                aria-pressed={ativo === valor}
                className={
                  ativo === valor
                    ? 'rounded-lg bg-primary px-3 py-2 text-xs font-semibold text-primary-foreground'
                    : 'rounded-lg px-3 py-2 text-xs font-semibold text-muted-foreground transition-colors hover:bg-muted'
                }
              >
                {rotulo}
              </button>
            ))}
          </div>
        </div>
      </div>

      {isError && (
        <Alert variant="error" icon={AlertCircle}>
          <span className="font-medium">Não foi possível carregar as contas.</span>
        </Alert>
      )}

      {isLoading ? (
        <div role="status" className="flex flex-col items-center gap-3 py-16">
          <Loader2 className="h-7 w-7 animate-spin text-primary" aria-hidden="true" />
          <p className="text-sm text-muted-foreground">Carregando contas...</p>
        </div>
      ) : (
        <Card className="overflow-hidden rounded-2xl border-border/40">
          <CardContent className="p-0">
            <div className="overflow-x-auto">
              <table className="w-full min-w-[52rem] text-left text-sm">
                <caption className="sr-only">
                  Contas de usuário da plataforma, {total} no total
                </caption>
                <thead className="border-b border-border bg-muted/30">
                  <tr>
                    <th scope="col" className="px-4 py-3 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                      Conta
                    </th>
                    <th scope="col" className="px-4 py-3 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                      Estado
                    </th>
                    <th scope="col" className="px-4 py-3 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                      Cadastro
                    </th>
                    <th scope="col" className="px-4 py-3 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                      Último acesso
                    </th>
                    <th scope="col" className="px-4 py-3 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                      Volume
                    </th>
                    <th scope="col" className="px-4 py-3 text-right text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                      Ação
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {usuarios.length === 0 && (
                    <tr>
                      <td colSpan={6} className="px-4 py-10 text-center text-sm text-muted-foreground">
                        Nenhuma conta encontrada com esses filtros.
                      </td>
                    </tr>
                  )}

                  {usuarios.map((usuario) => {
                    const euMesmo = usuario.username === perfil?.username;
                    return (
                      <tr key={usuario.id} className="border-b border-border/40">
                        <td className="px-4 py-3">
                          <p className="font-medium text-foreground">
                            {usuario.username}
                            {usuario.is_staff && (
                              <span className="ml-2 rounded bg-primary/10 px-1.5 py-0.5 text-[0.65rem] font-semibold uppercase tracking-wide text-primary">
                                Admin
                              </span>
                            )}
                          </p>
                          <p className="text-xs text-muted-foreground">
                            {usuario.email || 'sem e-mail cadastrado'}
                          </p>
                        </td>

                        <td className="px-4 py-3">
                          {/* Estado por ícone + texto, não por cor apenas: o
                              significado sobrevive à escala de cinza e ao
                              daltonismo. */}
                          <span className="flex items-center gap-1.5 text-xs font-medium">
                            {usuario.is_active ? (
                              <>
                                <ShieldCheck className="h-3.5 w-3.5 text-emerald-800 dark:text-emerald-400" aria-hidden="true" />
                                <span className="text-foreground">Ativa</span>
                              </>
                            ) : (
                              <>
                                <ShieldOff className="h-3.5 w-3.5 text-red-700 dark:text-red-400" aria-hidden="true" />
                                <span className="text-foreground">Suspensa</span>
                              </>
                            )}
                          </span>
                          <span className="mt-0.5 block text-xs text-muted-foreground">
                            {usuario.email_verificado ? 'e-mail confirmado' : 'e-mail não confirmado'}
                          </span>
                        </td>

                        <td className="px-4 py-3 text-xs tabular-nums text-muted-foreground">
                          {formatarData(usuario.date_joined)}
                        </td>
                        <td className="px-4 py-3 text-xs tabular-nums text-muted-foreground">
                          {formatarData(usuario.last_login)}
                        </td>
                        <td className="px-4 py-3 text-xs tabular-nums text-muted-foreground">
                          {usuario.total_lancamentos} lanç. · {usuario.total_ativos} ativos
                        </td>

                        <td className="px-4 py-3 text-right">
                          <Button
                            type="button"
                            variant="outline"
                            onClick={() => setAlvo(usuario)}
                            disabled={euMesmo}
                            className="h-8 rounded-lg px-3 text-xs"
                          >
                            {usuario.is_active ? 'Suspender' : 'Reativar'}
                          </Button>
                          {euMesmo && (
                            <p className="mt-1 text-[0.65rem] text-muted-foreground">
                              sua própria conta
                            </p>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Paginação */}
      {total > 0 && (
        <div className="flex items-center justify-between gap-3">
          <p className="text-xs text-muted-foreground" role="status">
            {total} {total === 1 ? 'conta' : 'contas'} · página {pagina}
          </p>
          <div className="flex gap-2">
            <Button
              type="button"
              variant="outline"
              onClick={() => setPagina((p) => Math.max(1, p - 1))}
              disabled={pagina === 1}
              className="h-8 rounded-lg px-3 text-xs"
            >
              Anterior
            </Button>
            <Button
              type="button"
              variant="outline"
              onClick={() => setPagina((p) => p + 1)}
              disabled={!temProxima}
              className="h-8 rounded-lg px-3 text-xs"
            >
              Próxima
            </Button>
          </div>
        </div>
      )}

      <Modal
        isOpen={!!alvo}
        onClose={fecharConfirmacao}
        title={alvo?.is_active ? 'Suspender esta conta?' : 'Reativar esta conta?'}
        description={
          alvo?.is_active
            ? 'A pessoa será desconectada imediatamente e não conseguirá entrar novamente até a reativação.'
            : 'A pessoa voltará a conseguir entrar normalmente.'
        }
        size="sm"
      >
        <div className="space-y-4">
          <p className="text-sm text-foreground">
            Conta: <strong>{alvo?.username}</strong>
          </p>

          <div className="space-y-1.5">
            <label
              htmlFor="admin-motivo"
              className="text-xs font-semibold uppercase tracking-wide text-muted-foreground"
            >
              Motivo
            </label>
            <Input
              id="admin-motivo"
              type="text"
              placeholder="Registrado no histórico administrativo"
              value={motivo}
              onChange={(e) => setMotivo(e.target.value)}
              className="rounded-xl"
              aria-describedby="ajuda-admin-motivo"
            />
            <p id="ajuda-admin-motivo" className="text-xs text-muted-foreground">
              Opcional, mas recomendado: é o que permite explicar a decisão depois.
            </p>
          </div>

          <div className="flex justify-end gap-2 pt-2">
            <Button
              type="button"
              variant="outline"
              onClick={fecharConfirmacao}
              className="rounded-xl"
            >
              Cancelar
            </Button>
            <Button
              type="button"
              onClick={confirmar}
              disabled={mutacao.isPending}
              className="flex items-center gap-2 rounded-xl"
            >
              {mutacao.isPending && (
                <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
              )}
              {alvo?.is_active ? 'Suspender' : 'Reativar'}
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  );
}
