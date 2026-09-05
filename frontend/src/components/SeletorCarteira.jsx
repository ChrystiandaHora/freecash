/**
 * Seletor da carteira em foco, para o cabeçalho das telas de investimento.
 *
 * Usa o `<select>` nativo com uma primeira opção "Todas as carteiras" — o mesmo
 * padrão já registrado para filtro de lista em MeusAtivos ("Todas as Classes").
 * `A11Y-DECISIONS.md` pede reusar o padrão gravado em vez de bifurcar: um
 * `radiogroup` funcionaria com duas ou três carteiras e viraria uma parede de
 * botões com dez.
 *
 * Some da tela quando o usuário tem uma carteira só, porque aí o filtro não
 * oferece escolha nenhuma — seria um controle que não faz nada.
 */
import { Select } from './ui/Select';
import { useCarteira } from '../context/CarteiraProvider';

/**
 * @param {{id?: string, className?: string}} props
 */
export default function SeletorCarteira({ id = 'filtro-carteira', className = '', showLabel = false }) {
  const { carteiraId, setCarteiraId, carteirasAtivas } = useCarteira();

  // Se tem apenas 1 ou nenhuma carteira ativa e nenhum filtro ligado, não precisa exibir seletor
  if (carteirasAtivas.length <= 1 && !carteiraId) return null;

  return (
    <div className={`w-full sm:w-60 flex items-center gap-2 ${className}`}>
      {showLabel && (
        <label htmlFor={id} className="text-xs font-semibold text-muted-foreground shrink-0">
          Carteira:
        </label>
      )}
      <div className="relative flex-1">
        <label htmlFor={id} className="sr-only">
          Filtrar por carteira de investimento
        </label>
        <Select
          id={id}
          value={carteiraId ?? ''}
          onChange={(e) => setCarteiraId(e.target.value)}
          className="h-10 text-xs rounded-xl font-semibold"
        >
          <option value="">Todas as carteiras (Consolidado)</option>
          {carteirasAtivas.map((carteira) => (
            <option key={carteira.id} value={carteira.id}>
              {carteira.instituicao
                ? `${carteira.nome} — ${carteira.instituicao}`
                : carteira.nome}
            </option>
          ))}
        </Select>
      </div>
    </div>
  );
}
