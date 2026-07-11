/**
 * Tela de Autenticação e Cadastro de Usuário (Login / Register).
 *
 * Página pública da aplicação que opera em dois modos alternáveis:
 * - **Login:** autentica o usuário via `useAuth().login()` e redireciona para `/dashboard`.
 * - **Cadastro:** registra um novo usuário via `useAuth().register()` com validação
 *   de senha mínima (6 caracteres) e confirmação de senha.
 *
 * Funcionalidades:
 * - Layout split-screen: painel de branding (desktop, `lg:` e acima) + formulário.
 * - Toggle de tema claro/escuro persistido no `localStorage`.
 * - Toggle de mostrar/ocultar senha nos campos de senha.
 * - Feedback de erros HTTP granular (400 → dados inválidos, 401 → credenciais erradas).
 * - Estado de carregamento com spinner (`Loader2`) durante chamadas à API.
 * - Orbs de gradiente decorativos para identidade visual premium.
 *
 * Proteção de rota: usuários já autenticados são redirecionados para `/dashboard`
 * pelo componente `PublicRoute` definido em `App.jsx`.
 *
 * @module Login
 * @component
 * @returns {JSX.Element} Tela de login/cadastro responsiva e acessível.
 *
 * @example
 * // Rota pública configurada em App.jsx:
 * <Route path="/login" element={<PublicRoute><Login /></PublicRoute>} />
 */
import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthProvider';
import { Input } from '../components/ui/Input';
import { PasswordInput } from '../components/ui/PasswordInput';
import { Button } from '../components/ui/Button';
import { Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter } from '../components/ui/Card';
import { Alert } from '../components/ui/Alert';
import { cn } from '../lib/utils';
import { Wallet, Loader2, AlertCircle, ShieldCheck, Sun, Moon, TrendingUp, PieChart, BarChart3 } from 'lucide-react';

const HIGHLIGHTS = [
  { icon: TrendingUp, title: 'Métricas em tempo real', desc: 'Acompanhe seu patrimônio a cada atualização' },
  { icon: PieChart, title: 'Gestão de carteira', desc: 'Diversifique e balanceie seus ativos com clareza' },
  { icon: ShieldCheck, title: 'Segurança de nível bancário', desc: 'Dados criptografados de ponta a ponta' },
];

function BrandMark({ size = 'lg' }) {
  const isLg = size === 'lg';
  return (
    <div className="flex flex-col items-center lg:items-start text-center lg:text-left">
      <div
        className={cn(
          'rounded-2xl bg-primary flex items-center justify-center shadow-lg shadow-primary/20 transition-colors duration-300',
          isLg ? 'w-14 h-14 mb-4' : 'w-12 h-12 mb-3'
        )}
      >
        <Wallet className={isLg ? 'h-7 w-7 text-primary-foreground' : 'h-6 w-6 text-primary-foreground'} />
      </div>
      <h1
        className={cn(
          'font-bold tracking-tight text-primary transition-colors duration-300',
          isLg ? 'text-4xl xl:text-5xl' : 'text-3xl'
        )}
      >
        FreeCash
      </h1>
      <p
        className={cn(
          'text-muted-foreground transition-colors duration-300',
          isLg ? 'text-base mt-2 max-w-xs' : 'text-sm mt-1.5'
        )}
      >
        Clareza total sobre o seu dinheiro.
      </p>
    </div>
  );
}

export default function Login() {
  const { login, register } = useAuth();
  const navigate = useNavigate();

  const [isRegister, setIsRegister] = useState(false);
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  // Theme Management
  const [theme, setTheme] = useState(() => {
    const saved = localStorage.getItem('theme');
    if (saved) return saved;
    return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
  });

  useEffect(() => {
    const root = window.document.documentElement;
    if (theme === 'dark') {
      root.classList.add('dark');
    } else {
      root.classList.remove('dark');
    }
  }, [theme]);

  const toggleTheme = () => {
    const nextTheme = theme === 'dark' ? 'light' : 'dark';
    setTheme(nextTheme);
    localStorage.setItem('theme', nextTheme);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!username || !password || (isRegister && !confirmPassword)) {
      setError('Por favor, preencha todos os campos.');
      return;
    }

    if (isRegister) {
      if (password.length < 6) {
        setError('A senha deve ter no mínimo 6 caracteres.');
        return;
      }
      if (password !== confirmPassword) {
        setError('As senhas não coincidem.');
        return;
      }
    }

    setError('');
    setLoading(true);

    try {
      if (isRegister) {
        await register(username, password, confirmPassword);
      } else {
        await login(username, password);
      }
      navigate('/dashboard');
    } catch (err) {
      console.error('Authentication error:', err);
      if (err.response?.status === 400) {
        setError(err.response?.data?.detail || 'Erro ao processar dados. Verifique suas informações.');
      } else if (err.response?.status === 401) {
        setError('Usuário ou senha incorretos.');
      } else {
        setError('Ocorreu um erro ao tentar processar. Tente novamente mais tarde.');
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen w-full flex bg-background text-foreground font-sans">

      {/* Dynamic Theme Switcher Toggle */}
      <Button
        variant="ghost"
        size="icon"
        onClick={toggleTheme}
        className="fixed top-5 right-5 sm:top-6 sm:right-6 z-40 rounded-xl hover:bg-muted/50 text-muted-foreground h-9 w-9"
        title="Alternar Tema"
      >
        {theme === 'dark' ? (
          <Sun className="h-[1.1rem] w-[1.1rem]" />
        ) : (
          <Moon className="h-[1.1rem] w-[1.1rem]" />
        )}
      </Button>

      {/* Brand Panel (desktop only) */}
      <aside
        aria-hidden="true"
        className="hidden lg:flex lg:w-1/2 relative flex-col justify-center overflow-hidden bg-gradient-to-br from-background via-background to-primary/5 border-r border-border/50 p-12 xl:p-16"
      >
        {/* Decorative Vibrant Glowing Orbs */}
        <div className="absolute top-[-15%] left-[-10%] w-[60%] h-[60%] rounded-full bg-primary/10 blur-[120px] pointer-events-none" />
        <div className="absolute bottom-[-15%] right-[-10%] w-[60%] h-[60%] rounded-full bg-primary/10 blur-[120px] pointer-events-none" />

        {/* Decorative floating chips */}
        <div className="absolute top-10 right-16 h-11 w-11 rounded-2xl bg-card/80 border border-border/50 shadow-sm flex items-center justify-center rotate-6 backdrop-blur-sm">
          <BarChart3 className="h-4.5 w-4.5 text-primary" />
        </div>
        <div className="absolute bottom-24 left-8 h-10 w-10 rounded-2xl bg-card/80 border border-border/50 shadow-sm flex items-center justify-center -rotate-6 backdrop-blur-sm">
          <TrendingUp className="h-4 w-4 text-primary" />
        </div>

        <div className="relative z-10 animate-fade-in">
          <BrandMark size="lg" />
        </div>

        <div className="relative z-10 mt-10 space-y-3 max-w-sm">
          {HIGHLIGHTS.map(({ icon: Icon, title, desc }, i) => (
            <div
              key={title}
              className="glass rounded-2xl p-4 flex items-start gap-3 animate-fade-in"
              style={{ animationDelay: `${150 + i * 120}ms`, animationFillMode: 'both' }}
            >
              <div className="w-9 h-9 rounded-xl bg-primary/10 flex items-center justify-center shrink-0">
                <Icon className="h-4.5 w-4.5 text-primary" />
              </div>
              <div>
                <p className="text-sm font-semibold text-foreground">{title}</p>
                <p className="text-xs text-muted-foreground mt-0.5">{desc}</p>
              </div>
            </div>
          ))}
        </div>
      </aside>

      {/* Form Panel */}
      <main className="w-full lg:w-1/2 flex items-center justify-center px-6 sm:px-10 lg:px-12 py-10 sm:py-12">
        <div className="w-full max-w-md">

          {/* Compact brand header (mobile/tablet only) */}
          <div className="flex lg:hidden flex-col items-center mb-8 animate-fade-in">
            <BrandMark size="sm" />
          </div>

          {/* Login Card */}
          <Card className="border-border/40 bg-card text-card-foreground shadow-lg rounded-2xl overflow-hidden">
            <CardHeader className="space-y-1.5 pb-4">
              <CardTitle className="text-xl font-bold text-foreground text-center">
                {isRegister ? 'Criar Nova Conta' : 'Boas-vindas'}
              </CardTitle>
              <CardDescription className="text-muted-foreground text-center text-xs">
                {isRegister ? 'Crie sua conta para inicializar seu ecossistema FreeCash' : 'Entre com as credenciais do seu painel SaaS'}
              </CardDescription>
            </CardHeader>

            <form onSubmit={handleSubmit}>
              <CardContent className="space-y-4">

                {/* Error Toast */}
                {error && (
                  <Alert variant="error" icon={AlertCircle} className="text-xs animate-shake">
                    <span className="font-medium leading-relaxed">{error}</span>
                  </Alert>
                )}

                <div className="space-y-1.5">
                  <label className="text-xs font-semibold text-muted-foreground tracking-wide uppercase">
                    Usuário
                  </label>
                  <Input
                    type="text"
                    placeholder="Seu nome de usuário"
                    value={username}
                    onChange={(e) => setUsername(e.target.value)}
                    className="rounded-xl"
                    disabled={loading}
                  />
                </div>

                <div className="space-y-1.5">
                  <div className="flex items-center justify-between">
                    <label className="text-xs font-semibold text-muted-foreground tracking-wide uppercase">
                      Senha
                    </label>
                  </div>
                  <PasswordInput
                    placeholder="••••••••"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    className="rounded-xl"
                    disabled={loading}
                  />
                </div>

                {/* Confirm Password (Registration Only) */}
                {isRegister && (
                  <div className="space-y-1.5 transition-all duration-300 ease-in-out">
                    <label className="text-xs font-semibold text-muted-foreground tracking-wide uppercase">
                      Confirmar Senha
                    </label>
                    <PasswordInput
                      placeholder="••••••••"
                      value={confirmPassword}
                      onChange={(e) => setConfirmPassword(e.target.value)}
                      className="rounded-xl"
                      disabled={loading}
                    />
                  </div>
                )}
              </CardContent>

              <CardFooter className="flex flex-col pt-2 pb-6 space-y-4">
                <Button
                  type="submit"
                  className="w-full rounded-xl h-11 font-semibold flex items-center justify-center gap-2"
                  disabled={loading}
                >
                  {loading ? (
                    <>
                      <Loader2 className="h-4 w-4 animate-spin text-primary-foreground" />
                      <span>{isRegister ? 'Registrando...' : 'Conectando...'}</span>
                    </>
                  ) : (
                    <span>{isRegister ? 'Criar e Entrar no Painel' : 'Entrar no Painel'}</span>
                  )}
                </Button>

                <button
                  type="button"
                  onClick={() => {
                    setIsRegister(!isRegister);
                    setError('');
                    setPassword('');
                    setConfirmPassword('');
                  }}
                  className="text-xs text-primary hover:text-primary/80 transition-colors font-medium"
                  disabled={loading}
                >
                  {isRegister ? 'Já possui uma conta? Voltar ao login' : 'Novo por aqui? Cadastre-se agora'}
                </button>

                <div className="flex items-center justify-center gap-1.5 text-[10px] text-muted-foreground uppercase tracking-wider font-semibold pt-1">
                  <ShieldCheck className="h-3.5 w-3.5 text-primary" />
                  <span>Ambiente Seguro Criptografado</span>
                </div>
              </CardFooter>
            </form>
          </Card>
        </div>
      </main>
    </div>
  );
}
