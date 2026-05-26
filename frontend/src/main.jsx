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

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
