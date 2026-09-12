/**
 * Lista dos requisitos de senha com o estado de cada um, atualizada enquanto digita.
 *
 * Existe porque a recusa só aparecia depois do POST: o usuário escolhia a senha,
 * confirmava, clicava em avançar e só então descobria que ela não servia. Os requisitos
 * mostrados aqui são os que o cliente consegue conferir de verdade — ver
 * `lib/politicaSenha.js`, que espelha `backend/core/validacao_senha.py`.
 *
 * Três decisões de acessibilidade, registradas em A11Y-DECISIONS.md:
 *
 * - **Estado nunca por cor sozinha.** Cada item tem ícone distinto (✓ preenchido contra
 *   círculo vazio) e um texto `sr-only` dizendo o estado, além da cor.
 * - **O que vai ao vivo é o resumo, não a lista.** Marcar a `<ul>` como `aria-live`
 *   faria o leitor de tela anunciar item a item a cada tecla. Em vez disso um único
 *   `role="status"` invisível recebe a frase do que ainda falta, com atraso de
 *   `ATRASO_ANUNCIO_MS` depois da última tecla.
 * - **Requisito não conferível fica explícito.** Na redefinição por link a página não
 *   conhece usuário nem e-mail; o item aparece como «conferido ao salvar» em vez de
 *   verde — prometer o que não foi verificado é pior que não prometer.
 *
 * @param {object} props Propriedades.
 * @param {string} props.id Id do contêiner, para o `aria-describedby` do campo de senha.
 * @param {string} props.senha Senha digitada.
 * @param {string} [props.confirmacao] Valor do campo de confirmação, quando a tela tem um.
 * @param {{usuario?: string, email?: string, nome?: string}} [props.contexto] Identificadores conhecidos.
 * @param {boolean} [props.contextoConhecido] `false` quando a tela não conhece os identificadores.
 * @param {string} [props.className] Classes extras do contêiner.
 * @returns {React.JSX.Element} Lista de requisitos e a região de status que a acompanha.
 */
import { useEffect, useMemo, useState } from 'react';
import { Check, Circle, HelpCircle } from 'lucide-react';

import { avaliarSenha, termosDeContexto } from '../../lib/politicaSenha';
import { cn } from '../../lib/utils';

const ATRASO_ANUNCIO_MS = 700;

const APARENCIA = {
  atendido: {
    Icone: Check,
    classe: 'text-emerald-700 dark:text-emerald-400',
    estado: 'requisito atendido',
  },
  pendente: {
    Icone: Circle,
    classe: 'text-muted-foreground',
    estado: 'requisito ainda não atendido',
  },
  'no-servidor': {
    Icone: HelpCircle,
    classe: 'text-muted-foreground',
    estado: 'requisito conferido ao salvar',
  },
};

export function ChecklistSenha({
  id,
  senha,
  confirmacao,
  contexto,
  contextoConhecido = true,
  className,
}) {
  // Deps primitivas: quem chama monta o objeto no JSX, novo a cada renderização
  const { usuario, email, nome } = contexto || {};
  const termos = useMemo(
    () => termosDeContexto({ usuario, email, nome }),
    [usuario, email, nome]
  );
  const avaliacao = useMemo(
    () => avaliarSenha(senha, { termos, contextoConhecido, confirmacao }),
    [senha, termos, contextoConhecido, confirmacao]
  );

  // O anúncio espera a digitação parar; sem isso o leitor de tela lê a cada tecla
  const [anuncio, setAnuncio] = useState('');
  useEffect(() => {
    const timer = setTimeout(
      () => setAnuncio(senha ? avaliacao.resumo : ''),
      ATRASO_ANUNCIO_MS
    );
    return () => clearTimeout(timer);
  }, [senha, avaliacao.resumo]);

  return (
    <>
      <div id={id} className={cn('space-y-1.5', className)}>
        <ul aria-label="Requisitos da senha" className="space-y-1">
          {avaliacao.requisitos.map(({ id: requisito, rotulo, estado }) => {
            const { Icone, classe, estado: descricao } = APARENCIA[estado];
            return (
              <li
                key={requisito}
                className={cn('flex items-start gap-1.5 text-xs', classe)}
              >
                <Icone className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden="true" />
                <span>
                  {rotulo}
                  {estado === 'no-servidor' && ' (conferido ao salvar)'}
                  <span className="sr-only">: {descricao}</span>
                </span>
              </li>
            );
          })}
        </ul>
        <p className="text-xs text-muted-foreground">
          Senhas muito comuns também são recusadas. Uma frase que só você usa vale mais
          que símbolos no meio de uma palavra.
        </p>
      </div>
      <p role="status" className="sr-only">
        {anuncio}
      </p>
    </>
  );
}

export default ChecklistSenha;
