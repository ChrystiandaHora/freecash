/**
 * Tela de Conciliação de Extratos (envio de PDF e revisão linha a linha).
 *
 * Fluxo em dois tempos: o PDF sobe para `POST /api/ferramentas/conciliacao/upload/` e
 * vira uma fila de linhas pendentes; nada entra em Contas a Pagar enquanto o usuário
 * não aprovar. Cada extrato é um disclosure com sua tabela de linhas, seleção em lote e
 * as duas ações terminais — importar ou ignorar.
 *
 * O cartão é opcional, e é essa opcionalidade que separa esta tela de Compras Cartão:
 * sem cartão a linha aprovada vira conta a pagar avulsa; com cartão ela entra na fatura
 * do ciclo. Ver docs/importacao-extrato.md.
 *
 * @returns {React.JSX.Element} Tela de envio e conciliação de extratos.
 */
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useDropzone } from 'react-dropzone';
import {
  AlertCircle,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  FileText,
  Inbox,
  Loader2,
  RefreshCw,
  TrendingDown,
  TrendingUp,
  UploadCloud,
  X,
  XCircle,
} from 'lucide-react';
import api from '../services/api';
import { Button } from '../components/ui/Button';
import { Select } from '../components/ui/Select';
import { Alert } from '../components/ui/Alert';
import { SectionLabel } from '../components/ui/SectionLabel';
import { useToast } from '../context/ToastContext';
import { formatarMoeda } from '../lib/moeda';
import { formatarData } from '../lib/datas';

const BANCOS = [
  { value: 'generico', label: 'Genérico (varredura linha a linha)' },
  { value: 'nubank', label: 'Nubank' },
  { value: 'santander', label: 'Santander' },
  { value: 'inter', label: 'Banco Inter' },
  { value: 'itau', label: 'Itaú' },
  { value: 'bradesco', label: 'Bradesco' },
  { value: 'bb', label: 'Banco do Brasil' },
  { value: 'caixa', label: 'Caixa Econômica' },
];

const fetchConciliacao = async () => {
  const res = await api.get('/api/ferramentas/conciliacao/');
  return res.data;
};

const fetchCartoes = async () => {
  const res = await api.get('/api/financeiro/cartoes/');
  return res.data?.results || res.data || [];
};

/**
 * Checkbox de "selecionar todas" com o terceiro estado nativo.
 *
 * O `indeterminate` não existe como atributo em HTML: só como propriedade do nó, por
 * isso o ref. Sem ele, seleção parcial fica indistinguível de seleção vazia.
 *
 * @returns {React.JSX.Element} Checkbox controlado de seleção em lote.
 */
function CheckboxTodas({ id, checked, indeterminate, onChange, children }) {
  const ref = useRef(null);

  useEffect(() => {
    if (ref.current) ref.current.indeterminate = indeterminate;
  }, [indeterminate]);

  return (
    <>
      <input
        ref={ref}
        id={id}
        type="checkbox"
        checked={checked}
        onChange={onChange}
        className="h-4 w-4 rounded border-input accent-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-1"
      />
      <label htmlFor={id} className="sr-only">
        {children}
      </label>
    </>
  );
}

export default function FerramentasConciliacao() {
  const queryClient = useQueryClient();
  const { addToast } = useToast();

  const [banco, setBanco] = useState('generico');
  const [cartao, setCartao] = useState('');
  const [arquivo, setArquivo] = useState(null);
  const [resultadoUpload, setResultadoUpload] = useState(null);
  const [selecionadas, setSelecionadas] = useState({});
  const [expandidos, setExpandidos] = useState({});

  const { data, isLoading, isError, refetch, isFetching } = useQuery({
    queryKey: ['conciliacao'],
    queryFn: fetchConciliacao,
  });

  const { data: cartoes = [] } = useQuery({
    queryKey: ['cartoes'],
    queryFn: fetchCartoes,
  });

  const extratos = useMemo(() => data?.extratos || [], [data]);
  const totalPendentes = extratos.reduce((soma, e) => soma + (e.linhas_pendentes || 0), 0);

  // Derivado, não semeado por efeito: o primeiro extrato com pendência abre sozinho até
  // o usuário decidir por conta própria, e volta a acompanhar a fila quando ela muda
  const primeiroPendente = extratos.find((e) => e.linhas_pendentes > 0)?.id;
  const estaAberto = (id) => expandidos[id] ?? id === primeiroPendente;

  const uploadMutation = useMutation({
    mutationFn: async ({ file, bancoSel, cartaoSel }) => {
      const formData = new FormData();
      formData.append('arquivo', file);
      formData.append('banco', bancoSel);
      if (cartaoSel) formData.append('cartao', cartaoSel);
      const res = await api.post('/api/ferramentas/conciliacao/upload/', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      return res.data;
    },
    onSuccess: (extrato) => {
      setArquivo(null);
      setResultadoUpload({
        tipo: 'sucesso',
        msg: `${extrato.linhas_encontradas} lançamento(s) lido(s) de "${extrato.arquivo_nome}". Nada foi gravado ainda — revise a fila abaixo.`,
      });
      setExpandidos((prev) => ({ ...prev, [extrato.id]: true }));
      queryClient.invalidateQueries({ queryKey: ['conciliacao'] });
    },
    onError: (error) => {
      setResultadoUpload({
        tipo: 'erro',
        msg: error?.response?.data?.erro || 'Não foi possível ler o arquivo.',
      });
    },
  });

  const processarMutation = useMutation({
    mutationFn: async (payload) => {
      const res = await api.post('/api/ferramentas/conciliacao/processar/', payload);
      return res.data;
    },
    onSuccess: (res, variaveis) => {
      setSelecionadas((prev) => ({ ...prev, [variaveis.extrato_id]: new Set() }));
      queryClient.invalidateQueries({ queryKey: ['conciliacao'] });

      if (variaveis.acao === 'ignorar') {
        addToast(`${res.ignoradas} linha(s) descartada(s).`, 'success');
        return;
      }

      queryClient.invalidateQueries({ queryKey: ['contas-pagar'] });
      queryClient.invalidateQueries({ queryKey: ['transacoes'] });
      queryClient.invalidateQueries({ queryKey: ['compras-cartao'] });

      const duplicadas = res.duplicadas
        ? ` ${res.duplicadas} já existia(m) e foi(ram) vinculada(s).`
        : '';
      addToast(`${res.importadas} lançamento(s) criado(s).${duplicadas}`, 'success');
    },
    onError: (error) => {
      addToast(
        error?.response?.data?.erro || 'Não foi possível processar as linhas.',
        'error'
      );
    },
  });

  const tipoMutation = useMutation({
    mutationFn: async ({ linhaId, tipo }) => {
      const res = await api.patch(`/api/ferramentas/conciliacao/linha/${linhaId}/`, { tipo });
      return res.data;
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['conciliacao'] }),
    onError: () => addToast('Não foi possível trocar a natureza da linha.', 'error'),
  });

  const onDrop = useCallback((aceitos) => {
    if (aceitos?.length) {
      setArquivo(aceitos[0]);
      setResultadoUpload(null);
    }
  }, []);

  const { getRootProps, getInputProps, isDragActive, open } = useDropzone({
    onDrop,
    accept: { 'application/pdf': ['.pdf'] },
    maxFiles: 1,
    multiple: false,
    noClick: true,
    noKeyboard: true,
  });

  const alternarExtrato = (id) =>
    setExpandidos((prev) => ({ ...prev, [id]: !estaAberto(id) }));

  const alternarLinha = (extratoId, linhaId) =>
    setSelecionadas((prev) => {
      const proxima = new Set(prev[extratoId] || []);
      if (proxima.has(linhaId)) proxima.delete(linhaId);
      else proxima.add(linhaId);
      return { ...prev, [extratoId]: proxima };
    });

  const alternarTodas = (extratoId, linhas) =>
    setSelecionadas((prev) => {
      const atual = prev[extratoId] || new Set();
      const todas = atual.size === linhas.length ? new Set() : new Set(linhas.map((l) => l.id));
      return { ...prev, [extratoId]: todas };
    });

  const processar = (extratoId, acao) => {
    const ids = Array.from(selecionadas[extratoId] || []);
    if (!ids.length) return;
    processarMutation.mutate({ extrato_id: extratoId, linha_ids: ids, acao });
  };

  return (
    <div className="space-y-6 animate-fade-in">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-3xl font-extrabold tracking-tight text-foreground">
            Conciliação de Extratos
          </h1>
          <p className="text-muted-foreground mt-1 max-w-2xl">
            Envie o PDF do extrato ou da fatura e confirme linha a linha o que deve virar
            lançamento. Nada é gravado antes da sua aprovação.
          </p>
        </div>
        <Button variant="outline" onClick={() => refetch()} disabled={isFetching} className="gap-2">
          {isFetching ? (
            <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
          ) : (
            <RefreshCw className="h-4 w-4" aria-hidden="true" />
          )}
          Atualizar fila
        </Button>
      </div>

      {/* ─── Envio do arquivo ─────────────────────────────────────────────── */}
      <section
        aria-labelledby="titulo-envio"
        className="rounded-2xl border border-border/40 bg-card p-5 shadow-sm space-y-4"
      >
        <SectionLabel as="h2" id="titulo-envio" icon={UploadCloud}>
          Enviar extrato em PDF
        </SectionLabel>

        <div className="grid sm:grid-cols-2 gap-4">
          <div className="space-y-1.5">
            <label
              htmlFor="conciliacao-banco"
              className="text-xs font-bold uppercase tracking-wider text-muted-foreground"
            >
              Banco / layout
            </label>
            <Select
              id="conciliacao-banco"
              value={banco}
              onChange={(e) => setBanco(e.target.value)}
              aria-describedby="ajuda-banco"
            >
              {BANCOS.map((b) => (
                <option key={b.value} value={b.value}>
                  {b.label}
                </option>
              ))}
            </Select>
            <p id="ajuda-banco" className="text-xs text-muted-foreground">
              Se o layout não for reconhecido, o genérico lê o que conseguir.
            </p>
          </div>

          <div className="space-y-1.5">
            <label
              htmlFor="conciliacao-cartao"
              className="text-xs font-bold uppercase tracking-wider text-muted-foreground"
            >
              Cartão de crédito (opcional)
            </label>
            <Select
              id="conciliacao-cartao"
              value={cartao}
              onChange={(e) => setCartao(e.target.value)}
              aria-describedby="ajuda-cartao"
            >
              <option value="">Nenhum — lançar como conta a pagar</option>
              {cartoes.map((c) => (
                <option key={c.uuid} value={c.uuid}>
                  {c.nome}
                  {c.ultimos_digitos ? ` — final ${c.ultimos_digitos}` : ''}
                </option>
              ))}
            </Select>
            <p id="ajuda-cartao" className="text-xs text-muted-foreground">
              Com cartão, as despesas entram na fatura do ciclo. Sem cartão, viram contas
              a pagar avulsas.
            </p>
          </div>
        </div>

        <div
          {...getRootProps({ role: undefined, tabIndex: -1 })}
          className={`flex flex-col items-center justify-center gap-3 rounded-xl border-2 border-dashed p-6 text-center transition-colors ${
            isDragActive ? 'border-primary bg-primary/5' : 'border-border bg-card'
          } ${arquivo ? 'border-primary/60 bg-primary/5' : ''}`}
        >
          <input {...getInputProps()} />

          {arquivo ? (
            <>
              <FileText className="h-8 w-8 text-primary" aria-hidden="true" />
              <p className="text-sm font-semibold text-foreground break-all">{arquivo.name}</p>
              <p className="text-xs text-muted-foreground">
                {(arquivo.size / 1024).toFixed(1)} KB
              </p>
              <Button variant="ghost" size="sm" className="gap-1.5" onClick={() => setArquivo(null)}>
                <X className="h-3.5 w-3.5" aria-hidden="true" />
                Remover arquivo
                <span className="sr-only"> {arquivo.name}</span>
              </Button>
            </>
          ) : (
            <>
              <UploadCloud className="h-8 w-8 text-muted-foreground" aria-hidden="true" />
              <p className="text-sm text-muted-foreground">
                {isDragActive ? 'Solte o PDF aqui' : 'Arraste o PDF para cá, ou'}
              </p>
              {/* Botão real, e não o div focável do dropzone: arrastar precisa de
                  alternativa convencional (SC 2.1.1 e 2.5.4) */}
              <Button variant="outline" className="gap-2" onClick={open}>
                <UploadCloud className="h-4 w-4" aria-hidden="true" />
                Selecionar arquivo PDF
              </Button>
            </>
          )}
        </div>

        {resultadoUpload && (
          <Alert
            variant={resultadoUpload.tipo === 'sucesso' ? 'success' : 'error'}
            icon={resultadoUpload.tipo === 'sucesso' ? CheckCircle2 : AlertCircle}
          >
            {resultadoUpload.msg}
          </Alert>
        )}

        <Button
          className="w-full gap-2"
          disabled={!arquivo || uploadMutation.isPending}
          onClick={() =>
            uploadMutation.mutate({ file: arquivo, bancoSel: banco, cartaoSel: cartao })
          }
        >
          {uploadMutation.isPending ? (
            <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
          ) : (
            <Inbox className="h-4 w-4" aria-hidden="true" />
          )}
          {uploadMutation.isPending ? 'Lendo o arquivo…' : 'Enviar para a fila'}
        </Button>
      </section>

      {/* ─── Fila de revisão ──────────────────────────────────────────────── */}
      <section aria-labelledby="titulo-fila" className="space-y-4">
        <div className="flex flex-wrap items-baseline justify-between gap-2">
          <SectionLabel as="h2" id="titulo-fila" icon={Inbox}>
            Fila de revisão
          </SectionLabel>
          <p className="text-sm text-muted-foreground" role="status">
            {totalPendentes} linha(s) aguardando revisão
          </p>
        </div>

        {isLoading && (
          <p className="flex items-center gap-2 text-sm text-muted-foreground" role="status">
            <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
            Carregando a fila…
          </p>
        )}

        {isError && (
          <Alert variant="error" icon={AlertCircle}>
            Não foi possível carregar a fila de conciliação.
          </Alert>
        )}

        {!isLoading && !isError && extratos.length === 0 && (
          <Alert variant="info" icon={Inbox}>
            Nenhum extrato enviado ainda. Suba um PDF acima para começar.
          </Alert>
        )}

        {extratos.map((extrato) => {
          const linhas = extrato.linhas || [];
          const marcadas = selecionadas[extrato.id] || new Set();
          const aberto = estaAberto(extrato.id);
          const painelId = `extrato-${extrato.id}`;
          // O parser genérico chuta crédito para toda linha sem sinal de menos
          const avisoNatureza =
            extrato.banco === 'generico' && linhas.some((l) => l.tipo === 'C');

          return (
            <div
              key={extrato.id}
              className="rounded-2xl border border-border/40 bg-card overflow-hidden shadow-sm"
            >
              <h3>
                <button
                  type="button"
                  onClick={() => alternarExtrato(extrato.id)}
                  aria-expanded={aberto}
                  aria-controls={painelId}
                  className="flex w-full items-center justify-between gap-3 p-4 text-left hover:bg-muted/40 transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-inset"
                >
                  <span className="flex items-center gap-3 min-w-0">
                    <span className="w-8 h-8 rounded-lg bg-primary/10 flex items-center justify-center shrink-0">
                      <FileText className="h-4 w-4 text-primary" aria-hidden="true" />
                    </span>
                    <span className="block min-w-0">
                      <span className="block font-semibold text-foreground text-sm truncate">
                        {extrato.arquivo_nome}
                      </span>
                      <span className="block text-xs text-muted-foreground mt-0.5">
                        {extrato.banco_display}
                        {extrato.cartao_detalhe ? ` · ${extrato.cartao_detalhe.nome}` : ' · sem cartão'}
                        {' · '}
                        {linhas.length} pendente(s) de {extrato.linhas_encontradas}
                      </span>
                    </span>
                  </span>
                  {aberto ? (
                    <ChevronUp className="h-4 w-4 text-muted-foreground shrink-0" aria-hidden="true" />
                  ) : (
                    <ChevronDown className="h-4 w-4 text-muted-foreground shrink-0" aria-hidden="true" />
                  )}
                </button>
              </h3>

              {aberto && (
                <div id={painelId} className="border-t border-border/40 p-4 space-y-4">
                  {linhas.length === 0 ? (
                    <p className="text-sm text-muted-foreground">
                      Todas as linhas deste extrato já foram revisadas.
                    </p>
                  ) : (
                    <>
                      {avisoNatureza && (
                        <Alert variant="warning" icon={AlertCircle} title="Confira a coluna Natureza">
                          O leitor genérico só reconhece despesa quando o valor vem com
                          sinal de menos, e marca todo o resto como receita. Se este
                          extrato lista contas a pagar, troque a natureza das linhas antes
                          de lançar — receita a mais infla o saldo e a projeção.
                        </Alert>
                      )}

                      <div className="overflow-x-auto">
                        <table className="w-full text-sm">
                          <caption className="sr-only">
                            Linhas pendentes de {extrato.arquivo_nome}
                          </caption>
                          <thead>
                            <tr className="border-b border-border/40 text-left">
                              <th scope="col" className="p-2 w-10">
                                <CheckboxTodas
                                  id={`todas-${extrato.id}`}
                                  checked={marcadas.size === linhas.length && linhas.length > 0}
                                  indeterminate={marcadas.size > 0 && marcadas.size < linhas.length}
                                  onChange={() => alternarTodas(extrato.id, linhas)}
                                >
                                  Selecionar todas as linhas de {extrato.arquivo_nome}
                                </CheckboxTodas>
                              </th>
                              <th scope="col" className="p-2 font-semibold text-muted-foreground">
                                Data
                              </th>
                              <th scope="col" className="p-2 font-semibold text-muted-foreground">
                                Descrição
                              </th>
                              <th scope="col" className="p-2 font-semibold text-muted-foreground text-right">
                                Valor
                              </th>
                              <th scope="col" className="p-2 font-semibold text-muted-foreground">
                                Natureza
                              </th>
                            </tr>
                          </thead>
                          <tbody>
                            {linhas.map((linha) => {
                              const credito = linha.tipo === 'C';
                              const rotulo = `${linha.descricao}, ${formatarMoeda(
                                linha.valor
                              )}, em ${formatarData(linha.data)}`;

                              return (
                                <tr
                                  key={linha.id}
                                  className="border-b border-border/20 last:border-0 hover:bg-muted/30"
                                >
                                  <td className="p-2">
                                    <input
                                      id={`linha-${linha.id}`}
                                      type="checkbox"
                                      checked={marcadas.has(linha.id)}
                                      onChange={() => alternarLinha(extrato.id, linha.id)}
                                      className="h-4 w-4 rounded border-input accent-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-1"
                                    />
                                    <label htmlFor={`linha-${linha.id}`} className="sr-only">
                                      {rotulo}
                                    </label>
                                  </td>
                                  <td className="p-2 whitespace-nowrap text-muted-foreground">
                                    {formatarData(linha.data)}
                                  </td>
                                  <td className="p-2 text-foreground">{linha.descricao}</td>
                                  <td
                                    className={`p-2 text-right whitespace-nowrap font-semibold ${
                                      credito
                                        ? 'text-emerald-700 dark:text-emerald-400'
                                        : 'text-foreground'
                                    }`}
                                  >
                                    {formatarMoeda(linha.valor)}
                                  </td>
                                  <td className="p-2">
                                    <Button
                                      variant="ghost"
                                      size="sm"
                                      className="gap-1.5 h-8"
                                      disabled={tipoMutation.isPending}
                                      onClick={() =>
                                        tipoMutation.mutate({
                                          linhaId: linha.id,
                                          tipo: credito ? 'D' : 'C',
                                        })
                                      }
                                    >
                                      {credito ? (
                                        <TrendingUp
                                          className="h-3.5 w-3.5 text-emerald-600"
                                          aria-hidden="true"
                                        />
                                      ) : (
                                        <TrendingDown className="h-3.5 w-3.5" aria-hidden="true" />
                                      )}
                                      {credito ? 'Receita' : 'Despesa'}
                                      <span className="sr-only">
                                        . Trocar para {credito ? 'despesa' : 'receita'}: {rotulo}
                                      </span>
                                    </Button>
                                  </td>
                                </tr>
                              );
                            })}
                          </tbody>
                        </table>
                      </div>

                      <div className="flex flex-wrap gap-2">
                        <Button
                          className="gap-2"
                          disabled={marcadas.size === 0 || processarMutation.isPending}
                          onClick={() => processar(extrato.id, 'importar')}
                        >
                          <CheckCircle2 className="h-4 w-4" aria-hidden="true" />
                          Lançar {marcadas.size} selecionada(s)
                          <span className="sr-only"> de {extrato.arquivo_nome}</span>
                        </Button>
                        <Button
                          variant="outline"
                          className="gap-2"
                          disabled={marcadas.size === 0 || processarMutation.isPending}
                          onClick={() => processar(extrato.id, 'ignorar')}
                        >
                          <XCircle className="h-4 w-4" aria-hidden="true" />
                          Descartar {marcadas.size} selecionada(s)
                          <span className="sr-only"> de {extrato.arquivo_nome}</span>
                        </Button>
                      </div>
                    </>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </section>
    </div>
  );
}
