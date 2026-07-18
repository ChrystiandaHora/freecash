/**
 * Componente Raiz da Aplicação FreeCash (App Router).
 *
 * Configura a estrutura global da SPA: provedor de estado de autenticação
 * (`AuthProvider`), sistema de notificações (`ToastProvider`), cliente de
 * cache de dados remotos (`QueryClientProvider` / TanStack Query) e o roteador
 * declarativo (`BrowserRouter`).
 *
 * Padrão de Rotas:
 * - `PublicRoute`   → redireciona usuários autenticados para `/dashboard`.
 * - `ProtectedRoute` → redireciona usuários não-autenticados para `/login`.
 *
 * Todas as páginas autenticadas são renderizadas sob o layout mestre
 * `DashboardLayout` via rotas filhas (nested routes).
 *
 * @module App
 * @component
 * @returns {JSX.Element} Árvore de provedores e roteador da aplicação.
 *
 * @example
 * // Ponto de entrada (main.jsx)
 * createRoot(document.getElementById('root')).render(<App />);
 */
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { AuthProvider, useAuth } from './context/AuthProvider';
import { ToastProvider } from './context/ToastContext';
import { Loader2 } from 'lucide-react';


// Layouts & Pages
import DashboardLayout from './components/DashboardLayout';
import Login from './pages/Login';
import Dashboard from './pages/Dashboard';
import Investimentos from './pages/Investimentos';
import Relatorios from './pages/Relatorios';
import ContasPagar from './pages/ContasPagar';
import ContasPagarLote from './pages/ContasPagarLote';
import PipelineKanban from './pages/PipelineKanban';
import MeusCartoes from './pages/MeusCartoes';
import Receitas from './pages/Receitas';
import Transacoes from './pages/Transacoes';
import SimuladorGastos from './pages/SimuladorGastos';
import AtivosHistorico from './pages/AtivosHistorico';
import AtivosClasses from './pages/AtivosClasses';
import MeusAtivos from './pages/MeusAtivos';
import AtivoDetalhes from './pages/AtivoDetalhes';
import FerramentasImportar from './pages/FerramentasImportar';
import ComprasCartao from './pages/ComprasCartao';
import FerramentasBackup from './pages/FerramentasBackup';
import AjustesPagamentos from './pages/AjustesPagamentos';

// Forms
import ReceitaForm from './pages/forms/ReceitaForm';
import ContaPagarForm from './pages/forms/ContaPagarForm';
import AjustePagamentoForm from './pages/forms/AjustePagamentoForm';
import CompraCartaoForm from './pages/forms/CompraCartaoForm';
import AtivoForm from './pages/forms/AtivoForm';
import AtivosClassesForm from './pages/forms/AtivosClassesForm';
import OrdemForm from './pages/forms/OrdemForm';

// Create TanStack Query Client
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false, // Prevents aggressive background re-fetches
      retry: 1, // Retries failed requests once before showing error
    },
  },
});

// Guard Route for Protected Pages
const ProtectedRoute = ({ children }) => {
  const { isAuthenticated, loading } = useAuth();
  
  if (loading) {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center bg-background text-foreground">
        <Loader2 className="h-8 w-8 text-primary animate-spin" />
        <p className="text-sm font-semibold text-muted-foreground mt-4 uppercase tracking-wider">
          Iniciando sessão segura...
        </p>
      </div>
    );
  }
  
  return isAuthenticated ? children : <Navigate to="/login" replace />;
};

// Guard Route for Auth Pages (Prevents logged-in users from visiting login)
const PublicRoute = ({ children }) => {
  const { isAuthenticated, loading } = useAuth();
  
  if (loading) {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center bg-background text-foreground">
        <Loader2 className="h-8 w-8 text-primary animate-spin" />
      </div>
    );
  }
  
  return !isAuthenticated ? children : <Navigate to="/dashboard" replace />;
};

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <AuthProvider>
          <Router>
            <Routes>
              {/* Public Auth Routes */}
              <Route 
                path="/login" 
                element={
                  <PublicRoute>
                    <Login />
                  </PublicRoute>
                } 
              />

              {/* Protected SaaS Workspace Routes */}
              <Route 
                path="/" 
                element={
                  <ProtectedRoute>
                    <DashboardLayout />
                  </ProtectedRoute>
                }
              >
                <Route index element={<Navigate to="/dashboard" replace />} />
                <Route path="dashboard" element={<Dashboard />} />
                <Route path="relatorios" element={<Relatorios />} />
                
                <Route path="contas-pagar" element={<ContasPagar />} />
                <Route path="contas-pagar/lote" element={<ContasPagarLote />} />
                <Route path="contas-kanban" element={<PipelineKanban />} />
                <Route path="cartoes" element={<MeusCartoes />} />
                <Route path="receitas" element={<Receitas />} />
                <Route path="transacoes" element={<Transacoes />} />
                <Route path="simulador" element={<SimuladorGastos />} />

                <Route path="investimentos" element={<Investimentos />} />
                <Route path="investimentos/ativos" element={<MeusAtivos />} />
                <Route path="investimentos/ativos/:id" element={<AtivoDetalhes />} />
                <Route path="investimentos/historico" element={<AtivosHistorico />} />
                <Route path="investimentos/classes" element={<AtivosClasses />} />

                <Route path="importar" element={<FerramentasImportar />} />
                <Route path="compras-cartao" element={<ComprasCartao />} />
                <Route path="compras-cartao/novo" element={<CompraCartaoForm />} />
                <Route path="compras-cartao/editar/:id" element={<CompraCartaoForm />} />
                <Route path="backup" element={<FerramentasBackup />} />

                <Route path="pagamentos" element={<AjustesPagamentos />} />
                <Route path="pagamentos/novo" element={<AjustePagamentoForm />} />
                <Route path="pagamentos/editar/:id" element={<AjustePagamentoForm />} />

                {/* Sub-rotas de formulários para receitas, contas a pagar, ativos e classes */}
                <Route path="receitas/novo" element={<ReceitaForm />} />
                <Route path="receitas/editar/:id" element={<ReceitaForm />} />
                <Route path="contas-pagar/novo" element={<ContaPagarForm />} />
                <Route path="contas-pagar/editar/:id" element={<ContaPagarForm />} />
                <Route path="investimentos/ativos/novo" element={<AtivoForm />} />
                <Route path="investimentos/ativos/editar/:id" element={<AtivoForm />} />
                <Route path="investimentos/classes/formulario" element={<AtivosClassesForm />} />
                <Route path="investimentos/historico/novo" element={<OrdemForm />} />
                <Route path="investimentos/historico/editar/:id" element={<OrdemForm />} />
              </Route>

              {/* Fallback Redirect */}
              <Route path="*" element={<Navigate to="/dashboard" replace />} />
            </Routes>
          </Router>
        </AuthProvider>
      </ToastProvider>
    </QueryClientProvider>
  );
}

export default App;
