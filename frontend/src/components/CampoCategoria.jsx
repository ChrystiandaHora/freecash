/**
 * Campo de categoria de um lançamento: select das categorias do usuário com uma
 * última opção, "+ Nova categoria…", que revela uma caixa para digitar o nome.
 *
 * É o `<select>` nativo (via `ui/Select`), não um combobox ARIA feito à mão — o
 * A11Y.md manda preferir o nativo. Escolher "+ Nova categoria…" só revela a caixa
 * logo abaixo, sem mover o foco: no Windows as setas trocam a opção de um select
 * fechado, e puxar o foco ali tiraria do campo quem só estava percorrendo a lista
 * (mudança de contexto na entrada, WCAG 3.2.2). O Tab seguinte chega na caixa.
 *
 * O valor emitido é sempre o nome da categoria; um nome que não existe vira
 * categoria nova ao salvar (`resolver_categoria_por_nome`).
 *
 * @param {Object} props
 * @param {string} props.id - Id do select; o `<label htmlFor>` do formulário aponta para ele.
 * @param {'R' | 'D'} props.tipo - Receita ou despesa: filtra as opções.
 * @param {string} [props.value] - Nome da categoria atual.
 * @param {(nome: string) => void} props.onChange
 * @param {() => void} [props.onBlur]
 * @param {React.Ref<HTMLSelectElement>} [props.ref] - Para o React Hook Form focar no erro.
 * @param {boolean} [props.obrigatorio] - Quando falso, a opção vazia vira "Categoria padrão".
 * @param {boolean} [props.readOnly] - Mostra o nome sem permitir troca (fatura de cartão).
 * @param {boolean} [props.invalid]
 * @param {string} [props.describedBy] - Ids de dica e erro, repassados aos dois controles.
 * @param {string} [props.ariaLabel] - Nome acessível quando não há `<label>` visível (tabela do lote).
 * @param {string} [props.className] - Classes extras dos controles (ex.: versão compacta).
 */
import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';

import { Input } from './ui/Input';
import { Select } from './ui/Select';
import { fetchCategorias } from '../services/financeiro';
import { opcoesCategoria } from '../lib/categorias';

const OPCAO_NOVA = '__nova__';

export function CampoCategoria({
  id,
  tipo,
  value = '',
  onChange,
  onBlur,
  ref,
  obrigatorio = true,
  readOnly = false,
  invalid = false,
  describedBy,
  ariaLabel,
  className,
}) {
  const [criando, setCriando] = useState(false);
  const { data: categorias } = useQuery({
    queryKey: ['categorias'],
    queryFn: fetchCategorias,
  });

  if (readOnly) {
    return (
      <Input
        id={id}
        value={value}
        readOnly
        aria-label={ariaLabel}
        aria-describedby={describedBy}
        className="bg-muted cursor-not-allowed"
      />
    );
  }

  const idNova = `${id}-nova`;
  const opcoes = opcoesCategoria(categorias, tipo, criando ? '' : value);

  const handleEscolha = (evento) => {
    const escolhida = evento.target.value;
    const vaiCriar = escolhida === OPCAO_NOVA;
    setCriando(vaiCriar);
    onChange(vaiCriar ? '' : escolhida);
  };

  return (
    <div className="space-y-2">
      <Select
        id={id}
        ref={ref}
        value={criando ? OPCAO_NOVA : value}
        onChange={handleEscolha}
        onBlur={onBlur}
        aria-label={ariaLabel}
        aria-invalid={invalid}
        aria-describedby={describedBy}
        className={className}
      >
        <option value="" disabled={obrigatorio}>
          {obrigatorio ? 'Selecione uma categoria' : 'Categoria padrão'}
        </option>
        {opcoes.map((nome) => (
          <option key={nome} value={nome}>{nome}</option>
        ))}
        <option value={OPCAO_NOVA}>+ Nova categoria…</option>
      </Select>

      {criando && (
        <div className="space-y-1">
          <label htmlFor={idNova} className="text-xs font-medium text-foreground">
            Nome da nova categoria
          </label>
          <Input
            id={idNova}
            value={value}
            onChange={(evento) => onChange(evento.target.value)}
            onBlur={onBlur}
            autoComplete="off"
            aria-label={ariaLabel ? `Nome da nova categoria (${ariaLabel})` : undefined}
            aria-invalid={invalid}
            aria-describedby={describedBy}
            className={className}
          />
        </div>
      )}
    </div>
  );
}
