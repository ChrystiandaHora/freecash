import { Plus } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/Card';
import { Button } from '../../components/ui/Button';
import { Input } from '../../components/ui/Input';
import { Select } from '../../components/ui/Select';
import { formatCurrency } from './formatters';

export default function LancamentoForm({
  onSubmit,
  descricao,
  setDescricao,
  tipo,
  setTipo,
  valor,
  setValor,
  categoria,
  setCategoria,
  categoriasSugeridas,
  mesInicio,
  setMesInicio,
  projectionMonths,
  dia,
  setDia,
  frequencia,
  setFrequencia,
  parcelas,
  setParcelas,
}) {
  return (
    <Card className="border-border bg-card/65 backdrop-blur-md">
      <CardHeader>
        <CardTitle className="text-lg font-semibold flex items-center gap-2">
          <Plus className="h-5 w-5 text-primary" /> Novo Lançamento Simulado
        </CardTitle>
      </CardHeader>
      <CardContent>
        <form onSubmit={onSubmit} className="space-y-4">
          <div>
            <label htmlFor="sim-descricao" className="mb-1.5 block text-xs font-semibold text-muted-foreground uppercase tracking-wider">
              Descrição
            </label>
            <Input
              value={descricao}
              onChange={e => setDescricao(e.target.value)}
              placeholder="Ex: Assinatura Streaming, Notebook Novo"
              required
              id="sim-descricao"
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label htmlFor="sim-tipo" className="mb-1.5 block text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                Tipo
              </label>
              <Select
                value={tipo}
                onChange={e => setTipo(e.target.value)}
                id="sim-tipo"
              >
                <option value="D">Despesa (Gasto)</option>
                <option value="R">Receita (Entrada)</option>
              </Select>
            </div>
            <div>
              <label htmlFor="sim-valor" className="mb-1.5 block text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                Valor (R$)
              </label>
              <Input
                value={valor}
                onChange={e => setValor(e.target.value)}
                type="number"
                step="0.01"
                placeholder="0,00"
                required
                id="sim-valor"
              />
            </div>
          </div>

          <div>
            <label htmlFor="sim-categoria" className="mb-1.5 block text-xs font-semibold text-muted-foreground uppercase tracking-wider">
              Categoria
            </label>
            <Input
              value={categoria}
              onChange={e => setCategoria(e.target.value)}
              placeholder="Ex: Casa, Lazer, Salário"
              list="sim-categorias-sugeridas"
              id="sim-categoria"
            />
            <datalist id="sim-categorias-sugeridas">
              {categoriasSugeridas.map(c => <option key={c} value={c} />)}
            </datalist>
          </div>

          <div className="grid grid-cols-3 gap-3">
            <div className="col-span-2">
              <label htmlFor="sim-mes-inicio" className="mb-1.5 block text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                Mês de Início
              </label>
              <Select
                value={mesInicio}
                onChange={e => setMesInicio(e.target.value)}
                id="sim-mes-inicio"
              >
                {projectionMonths.map(m => (
                  <option key={m.key} value={m.key}>{m.label}</option>
                ))}
              </Select>
            </div>
            <div>
              <label htmlFor="sim-dia" className="mb-1.5 block text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                Dia
              </label>
              <Select
                value={dia}
                onChange={e => setDia(e.target.value)}
                id="sim-dia"
                aria-describedby="sim-dia-ajuda"
              >
                {Array.from({ length: 31 }, (_, i) => i + 1).map(d => (
                  <option key={d} value={String(d)}>{d}</option>
                ))}
              </Select>
            </div>
            <p id="sim-dia-ajuda" className="col-span-3 text-xs text-muted-foreground">
              O dia posiciona o lançamento no mapa de calor. Em meses mais curtos ele
              cai no último dia disponível.
            </p>
          </div>

          <div>
            <label htmlFor="sim-frequencia" className="mb-1.5 block text-xs font-semibold text-muted-foreground uppercase tracking-wider">
              Frequência
            </label>
            <Select
              value={frequencia}
              onChange={e => setFrequencia(e.target.value)}
              id="sim-frequencia"
            >
              <option value="unica">Lançamento Único (Avulso)</option>
              <option value="recorrente">Mensal Recorrente (Fixo)</option>
              <option value="parcelada">Parcelado</option>
            </Select>
          </div>

          {frequencia === 'parcelada' && (
            <div className="animate-in slide-in-from-top-1 duration-200">
              <label htmlFor="sim-parcelas" className="mb-1.5 block text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                Quantidade de Parcelas (Meses)
              </label>
              <Select
                value={parcelas}
                onChange={e => setParcelas(e.target.value)}
                required
                id="sim-parcelas"
              >
                {[2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12].map((n) => {
                  const numericValor = parseFloat(valor);
                  const labelSuffix = (!isNaN(numericValor) && numericValor > 0)
                    ? ` (${n}x de ${formatCurrency(numericValor / n)})`
                    : '';
                  return (
                    <option key={n} value={String(n)}>
                      {n} meses{labelSuffix}
                    </option>
                  );
                })}
              </Select>
            </div>
          )}

          <Button type="submit" className="w-full flex items-center justify-center gap-2">
            <Plus className="h-4 w-4" /> Adicionar
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}
