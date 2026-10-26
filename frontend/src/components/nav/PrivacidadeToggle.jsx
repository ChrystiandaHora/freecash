/**
 * Olho da barra do topo: alterna o modo "ocultar valores" em todas as telas.
 *
 * Botão de alternância com nome fixo e estado em `aria-pressed`: o leitor de tela
 * anuncia "Ocultar valores, botão de alternância, pressionado". Trocar o nome a cada
 * clique ("Mostrar"/"Ocultar") junto com `aria-pressed` daria dois sinais contraditórios.
 *
 * O ícone segue o estado atual, como nos apps de banco: olho aberto com os valores à
 * mostra, olho riscado com eles ocultos.
 */
import { Eye, EyeOff } from 'lucide-react';
import { Button } from '../ui/Button';
import { usePrivacidade } from '../../context/PrivacidadeProvider';

export function PrivacidadeToggle() {
  const { valoresOcultos, alternarValores } = usePrivacidade();
  const Icone = valoresOcultos ? EyeOff : Eye;

  return (
    <Button
      variant="ghost"
      size="icon"
      onClick={alternarValores}
      aria-pressed={valoresOcultos}
      aria-label="Ocultar valores"
      className="rounded-xl text-muted-foreground hover:bg-muted/50 aria-pressed:text-primary"
    >
      <Icone className="h-[1.1rem] w-[1.1rem]" aria-hidden="true" />
    </Button>
  );
}
