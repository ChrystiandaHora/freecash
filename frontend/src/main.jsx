/**
 * Ponto de entrada da aplicação FreeCash.
 *
 * Inicializa a renderização React montando o componente raiz `App` no elemento
 * DOM com `id="root"`. Executa em `StrictMode` para detecção precoce de
 * efeitos colaterais e APIs depreciadas durante o desenvolvimento.
 *
 * O CSS global da aplicação (`index.css`) é importado aqui, garantindo que os
 * tokens de design e as utilidades de base estejam disponíveis globalmente
 * antes de qualquer componente ser renderizado.
 *
 * @module main
 * @see {@link App} Componente raiz que encapsula providers e rotas.
 */
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.jsx'

// Limpeza de artefato morto: a sidebar colapsavel foi substituida pela navbar
// superior, entao esta chave nao tem mais leitor. Sem isto ela sobreviveria para
// sempre no navegador de todo usuario atual. Remover depois de 2027-02.
localStorage.removeItem('sidebar-collapsed')

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
