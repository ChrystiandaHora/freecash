/**
 * Tela de Cadastro de Contas a Pagar em Lote.
 * 
 * Permite que o usuário insira múltiplos compromissos financeiros e despesas simultaneamente
 * utilizando um layout tabular interativo (tabela editável). Facilita a criação rápida de registros,
 * com validação de campos em tempo real e envio unificado ao servidor.
 *
 * @component
 * @returns {React.JSX.Element} Formular tabular para inserção em lote de despesas futuras.
 */
import { useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { 
  ArrowLeft, Layers, Table, Info, Save, Trash2,
  CheckSquare, Square, Loader2, AlertCircle
} from 'lucide-react';

import { createContasPagarLote } from '../services/financeiro';
import { Button } from '../components/ui/Button';
import { Input } from '../components/ui/Input';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/Card';
import { Alert } from '../components/ui/Alert';

const createEmptyRows = (count) => {
  return Array.from({ length: count }, () => ({
    descricao: '',
    valor: '',
    data_vencimento: '',
    categoria: ''
  }));
};

export default function ContasPagarLote() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [rowCount, setRowCount] = useState(5);
  const [rows, setRows] = useState(() => createEmptyRows(5));
  const [todasPagas, setTodasPagas] = useState(false);
  const [errorAlert, setErrorAlert] = useState('');

  const bulkMutation = useMutation({
    mutationFn: createContasPagarLote,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['contasPagar'] });
      queryClient.invalidateQueries({ queryKey: ['dashboard'] });
      navigate('/contas-pagar');
    },
    onError: (err) => {
      const responseErrors = err?.response?.data?.erros;
      if (Array.isArray(responseErrors) && responseErrors.length > 0) {
        setErrorAlert(responseErrors.join(' | '));
      } else {
        setErrorAlert(err?.response?.data?.detail || 'Erro ao salvar contas em lote.');
      }
    }
  });

  const handleRowCountChange = (count) => {
    setRowCount(count);
    setErrorAlert('');
    setRows((prev) => {
      if (count > prev.length) {
        // Expand
        return [...prev, ...createEmptyRows(count - prev.length)];
      } else {
        // Contract
        return prev.slice(0, count);
      }
    });
  };

  const handleRowValueChange = (index, field, value) => {
    setErrorAlert('');
    setRows((prev) => {
      const next = [...prev];
      next[index] = { ...next[index], [field]: value };
      return next;
    });
  };

  const handleClearRow = (index) => {
    setRows((prev) => {
      const next = [...prev];
      next[index] = { descricao: '', valor: '', data_vencimento: '', categoria: '' };
      return next;
    });
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    setErrorAlert('');

    // Filter out completely empty rows
    const filledRows = rows.filter(
      (r) => r.descricao.trim() !== '' || r.valor !== '' || r.data_vencimento !== ''
    );

    if (filledRows.length === 0) {
      setErrorAlert('Preencha ao menos uma linha da tabela.');
      return;
    }

    // Prepare payload
    const payload = {
      itens: filledRows.map((r) => ({
        descricao: r.descricao,
        valor: r.valor,
        data_vencimento: r.data_vencimento,
        categoria: r.categoria
      })),
      todas_pagas: todasPagas
    };

    bulkMutation.mutate(payload);
  };

  return (
    <div className="space-y-6 animate-fade-in text-foreground">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-6">
        <div>
          <div className="flex items-center gap-3">
            <button
              onClick={() => navigate('/contas-pagar')}
              className="p-2 -ml-2 rounded-xl text-slate-400 hover:text-slate-900 dark:hover:text-white hover:bg-slate-100 dark:hover:bg-slate-800 transition-all"
              title="Voltar"
            >
              <ArrowLeft className="h-5 w-5" />
            </button>
            <h1 className="text-3xl font-extrabold tracking-tight text-foreground flex items-center gap-3">
              <Layers className="h-7 w-7 text-primary animate-pulse-slow" />
              Cadastro em Lote — Contas a Pagar
            </h1>
          </div>
          <p className="text-sm text-slate-500 dark:text-slate-400 mt-1 md:ml-12">
            Cadastre múltiplos lançamentos de despesas financeiras em lote rapidamente.
          </p>
        </div>

        {/* Quantidade Selector */}
        <div className="bg-muted border border-border/40 p-1.5 rounded-xl flex items-center gap-1 self-start md:self-center">
          {[5, 10, 15, 20].map((n) => (
            <button
              key={n}
              onClick={() => handleRowCountChange(n)}
              className={`px-4 py-2 rounded-lg text-xs font-bold transition-all relative ${
                rowCount === n
                  ? 'bg-card text-primary shadow-sm'
                  : 'text-muted-foreground hover:text-foreground hover:bg-accent/40'
              }`}
            >
              {n} linhas
            </button>
          ))}
        </div>
      </div>

      {/* Erro */}
      {errorAlert && (
        <Alert variant="error" icon={AlertCircle} className="animate-in fade-in duration-300">
          <span className="text-xs font-semibold leading-relaxed">{errorAlert}</span>
        </Alert>
      )}

      {/* Main Table Form */}
      <form onSubmit={handleSubmit} className="space-y-6">
        <Card className="border border-border/40 bg-card shadow-sm">
          <CardHeader className="border-b border-border/40 bg-muted/20 px-6 py-4 flex flex-row items-center justify-between">
            <div className="flex items-center gap-2">
              <Table className="h-4.5 w-4.5 text-slate-400" />
              <CardTitle className="text-sm font-semibold text-foreground">
                Tabela de Lançamentos
              </CardTitle>
            </div>
            <CardDescription className="text-xs text-muted-foreground hidden sm:block">
              Linhas completamente em branco serão ignoradas na importação.
            </CardDescription>
          </CardHeader>
          <CardContent className="p-0">
            <div className="overflow-x-auto">
              <table className="w-full text-xs text-left border-collapse min-w-[700px]">
                <thead>
                  <tr className="border-b border-border/40 bg-muted/40 text-muted-foreground font-semibold">
                    <th className="px-5 py-3 w-12 text-center">#</th>
                    <th className="px-5 py-3">Descrição *</th>
                    <th className="px-5 py-3 w-40">Valor (R$) *</th>
                    <th className="px-5 py-3 w-48">Vencimento *</th>
                    <th className="px-5 py-3 w-48">Categoria</th>
                    <th className="px-5 py-3 w-16 text-center">Limpar</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border/40">
                  {rows.map((row, idx) => (
                    <tr key={idx} className="hover:bg-muted/10 transition-colors group">
                      <td className="px-5 py-3.5 text-center font-bold text-muted-foreground/60 group-hover:text-foreground">
                        {idx + 1}
                      </td>
                      <td className="px-3 py-2">
                        <Input
                          placeholder="Ex: Conta de Luz, Internet..."
                          value={row.descricao}
                          onChange={(e) => handleRowValueChange(idx, 'descricao', e.target.value)}
                          className="h-9 text-xs rounded-lg"
                        />
                      </td>
                      <td className="px-3 py-2">
                        <div className="relative">
                          <span className="absolute left-3 top-1/2 -translate-y-1/2 text-xs font-bold text-muted-foreground">R$</span>
                          <Input
                            placeholder="0,00"
                            type="number"
                            step="0.01"
                            value={row.valor}
                            onChange={(e) => handleRowValueChange(idx, 'valor', e.target.value)}
                            className="pl-8 h-9 text-xs rounded-lg font-bold"
                          />
                        </div>
                      </td>
                      <td className="px-3 py-2">
                        <Input
                          type="date"
                          value={row.data_vencimento}
                          onChange={(e) => handleRowValueChange(idx, 'data_vencimento', e.target.value)}
                          className="h-9 text-xs rounded-lg cursor-pointer"
                        />
                      </td>
                      <td className="px-3 py-2">
                        <Input
                          placeholder="Ex: Contas Fixas"
                          value={row.categoria}
                          onChange={(e) => handleRowValueChange(idx, 'categoria', e.target.value)}
                          className="h-9 text-xs rounded-lg"
                        />
                      </td>
                      <td className="px-5 py-3.5 text-center">
                        <button
                          type="button"
                          onClick={() => handleClearRow(idx)}
                          className="p-1 rounded-lg text-slate-400 hover:text-red-500 hover:bg-red-500/10 transition-all opacity-0 group-hover:opacity-100"
                          title="Limpar Linha"
                        >
                          <Trash2 className="h-3.5 w-3.5" />
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </CardContent>

          {/* Footer Actions Inside Card */}
          <div className="px-6 py-4 bg-muted/20 border-t border-border/40 flex flex-col sm:flex-row gap-4 sm:items-center sm:justify-between">
            <div className="flex flex-col sm:flex-row sm:items-center gap-3 sm:gap-6">
              <label className="flex items-center gap-2 cursor-pointer select-none group">
                <button
                  type="button"
                  onClick={() => setTodasPagas(!todasPagas)}
                  className="p-0.5 rounded-lg text-slate-500 hover:text-primary transition-all shrink-0"
                >
                  {todasPagas ? (
                    <CheckSquare className="h-5 w-5 text-primary" />
                  ) : (
                    <Square className="h-5 w-5" />
                  )}
                </button>
                <span className="text-xs font-semibold text-slate-600 dark:text-slate-400 group-hover:text-primary transition-colors">
                  Marcar todas como pagas / liquidadas
                </span>
              </label>
            </div>

            <div className="flex gap-3 w-full sm:w-auto">
              <Button
                variant="outline"
                type="button"
                onClick={() => navigate('/contas-pagar')}
                disabled={bulkMutation.isPending}
                className="flex-1 sm:flex-none rounded-xl h-10 text-xs font-bold"
              >
                Cancelar
              </Button>
              <Button
                type="submit"
                disabled={bulkMutation.isPending}
                className="flex-1 sm:flex-none rounded-xl h-10 text-xs font-extrabold bg-primary hover:bg-primary/90 text-primary-foreground border-0 flex items-center justify-center gap-1.5 shadow-lg shadow-primary/25"
              >
                {bulkMutation.isPending ? (
                  <Loader2 className="h-4 w-4 animate-spin text-white" />
                ) : (
                  <Save className="h-4 w-4 text-white" />
                )}
                <span>Salvar Lançamentos</span>
              </Button>
            </div>
          </div>
        </Card>
      </form>

      {/* Info Tips Card */}
      <div className="p-4 rounded-2xl bg-muted/30 border border-border/40 flex gap-3.5">
        <div className="flex-shrink-0 w-8 h-8 rounded-lg bg-primary/10 flex items-center justify-center">
          <Info className="h-4 w-4 text-primary" />
        </div>
        <div>
          <h4 className="text-xs font-bold text-foreground">Dica de Lançamento</h4>
          <p className="text-xs text-muted-foreground mt-1 leading-relaxed">
            Pressione <kbd className="px-1.5 py-0.5 rounded bg-muted border border-border/60 text-[10px] font-mono">Tab</kbd> para navegar facilmente entre as células. Se não especificar a Categoria, usaremos a categoria padrão configurada em seus cadastros.
          </p>
        </div>
      </div>
    </div>
  );
}
