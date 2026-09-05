/**
 * Componente Raiz da Aplicação FreeCash (App Router).
 *
 * Monta os provedores globais — autenticação, toasts e cache do TanStack Query — e o
 * roteador. `PublicRoute` manda o autenticado para `/dashboard`, `ProtectedRoute` manda
 * o anônimo para `/login`, e `AdminRoute` exige `perfil.is_staff` lido da API.
 *
 * As páginas autenticadas ficam sob o layout mestre `DashboardLayout`, em rotas filhas.
 *
 * @returns {JSX.Element} Árvore de provedores e roteador da aplicação.
 */
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { AuthProvider, useAuth } from './context/AuthProvider';
import { ThemeProvider } from './context/ThemeProvider';
import { CarteiraProvider } from './context/CarteiraProvider';
import { ToastProvider } from './context/ToastContext';
import { Loader2 } from 'lucide-react';


// Layouts & Pages
import DashboardLayout from './components/DashboardLayout';
import Login from './pages/Login';
import EsqueciSenha from './pages/EsqueciSenha';
import RedefinirSenha from './pages/RedefinirSenha';
import VerificarEmail from './pages/VerificarEmail';
import MinhaConta from './pages/MinhaConta';
import ConfirmarTrocaEmail from './pages/ConfirmarTrocaEmail';
import HorizonteSaldos from './pages/HorizonteSaldos';
import CalendarioPagamentos from './pages/CalendarioPagamentos';
import AdminUsuarios from './pages/admin/AdminUsuarios';
import AdminMetricas from './pages/admin/AdminMetricas';
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
import Metas from './pages/Metas';
import AtivosBalanceamento from './pages/AtivosBalanceamento';
import AtivosHistorico from './pages/AtivosHistorico';
import AtivosClasses from './pages/AtivosClasses';
import AtivosCarteiras from './pages/AtivosCarteiras';
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
      <div role="status" className="min-h-screen flex flex-col items-center justify-center bg-background text-foreground">
        <Loader2 className="h-8 w-8 text-primary animate-spin" aria-hidden="true" />
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
      <div role="status" className="min-h-screen flex flex-col items-center justify-center bg-background text-foreground">
        <Loader2 className="h-8 w-8 text-primary animate-spin" aria-hidden="true" />
        <p className="text-sm font-semibold text-muted-foreground mt-4 uppercase tracking-wider">
          Verificando sessão...
        </p>
      </div>
    );
  }

  return !isAuthenticated ? children : <Navigate to="/dashboard" replace />;
};

// Guard Route for Platform Admin Pages
//
// O papel vem de `perfil.is_staff`, lido de /api/auth/me/ a cada sessão, e NUNCA
// de uma claim do JWT: com ROTATE_REFRESH_TOKENS o payload do refresh é preservado
// na rotação, então um administrador rebaixado continuaria com o papel antigo por
// até sete dias.
//
// Este guard é conveniência de navegação, não segurança. Quem chamar /api/admin/*
// diretamente é recusado pela permission class IsAdminPlataforma no servidor.
const AdminRoute = ({ children }) => {
  const { isAuthenticated, perfil, loading } = useAuth();

  if (loading) {
    return (
      <div role="status" className="min-h-screen flex flex-col items-center justify-center bg-background text-foreground">
        <Loader2 className="h-8 w-8 text-primary animate-spin" aria-hidden="true" />
        <p className="text-sm font-semibold text-muted-foreground mt-4 uppercase tracking-wider">
          Verificando permissões...
        </p>
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  // Enquanto o perfil não chegou, não há como afirmar o papel — e mandar para o
  // dashboard seria expulsar um administrador legítimo por causa de latência.
  if (perfil === null) {
    return (
      <div role="status" className="min-h-screen flex flex-col items-center justify-center bg-background text-foreground">
        <Loader2 className="h-8 w-8 text-primary animate-spin" aria-hidden="true" />
        <p className="text-sm font-semibold text-muted-foreground mt-4 uppercase tracking-wider">
          Verificando permissões...
        </p>
      </div>
    );
  }

  return perfil.is_staff ? children : <Navigate to="/dashboard" replace />;
};

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <AuthProvider>
          <ThemeProvider>
            <CarteiraProvider>
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
              <Route
                path="/esqueci-senha"
                element={
                  <PublicRoute>
                    <EsqueciSenha />
                  </PublicRoute>
                }
              />
              <Route
                path="/redefinir-senha/:uid/:token"
                element={
                  <PublicRoute>
                    <RedefinirSenha />
                  </PublicRoute>
                }
              />

              {/* Confirmação de e-mail: deliberadamente FORA de PublicRoute e de
                  ProtectedRoute. Quem clica no link do e-mail muitas vezes já está
                  logado, e o PublicRoute mandaria essa pessoa para /dashboard sem
                  nunca confirmar o endereço — o link não funcionaria justamente no
                  caso mais comum. Já o ProtectedRoute exigiria sessão de quem
                  abriu o link em outro navegador. */}
              <Route path="/verificar-email/:uid/:token" element={<VerificarEmail />} />
              <Route path="/conta/confirmar-email/:uid/:token" element={<ConfirmarTrocaEmail />} />

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
                <Route path="conta" element={<MinhaConta />} />
                
                <Route path="contas-pagar" element={<ContasPagar />} />
                <Route path="contas-pagar/lote" element={<ContasPagarLote />} />
                <Route path="contas-kanban" element={<PipelineKanban />} />
                <Route path="cartoes" element={<MeusCartoes />} />
                <Route path="receitas" element={<Receitas />} />
                <Route path="transacoes" element={<Transacoes />} />
                <Route path="simulador" element={<SimuladorGastos />} />
                <Route path="metas" element={<Metas />} />
                <Route path="horizonte-saldos" element={<HorizonteSaldos />} />
                <Route path="calendario" element={<CalendarioPagamentos />} />

                <Route path="investimentos" element={<Investimentos />} />
                <Route path="investimentos/ativos" element={<MeusAtivos />} />
                <Route path="investimentos/ativos/:id" element={<AtivoDetalhes />} />
                <Route path="investimentos/balanceamento" element={<AtivosBalanceamento />} />
                <Route path="investimentos/historico" element={<AtivosHistorico />} />
                <Route path="investimentos/carteiras" element={<AtivosCarteiras />} />
                <Route path="investimentos/classes" element={<AtivosClasses />} />

                <Route path="importar" element={<FerramentasImportar />} />
                <Route path="compras-cartao" element={<ComprasCartao />} />
                <Route path="compras-cartao/novo" element={<CompraCartaoForm />} />
                <Route path="compras-cartao/editar/:id" element={<CompraCartaoForm />} />
                <Route path="backup" element={<FerramentasBackup />} />

                {/* Painel administrativo da plataforma */}
                <Route
                  path="admin/usuarios"
                  element={
                    <AdminRoute>
                      <AdminUsuarios />
                    </AdminRoute>
                  }
                />
                <Route
                  path="admin/metricas"
                  element={
                    <AdminRoute>
                      <AdminMetricas />
                    </AdminRoute>
                  }
                />

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
            </CarteiraProvider>
          </ThemeProvider>
        </AuthProvider>
      </ToastProvider>
    </QueryClientProvider>
  );
}

export default App;
