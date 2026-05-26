/**
 * Tela de Autenticação e Cadastro de Usuário (Login / Register).
 *
 * Página pública da aplicação que opera em dois modos alternáveis:
 * - **Login:** autentica o usuário via `useAuth().login()` e redireciona para `/dashboard`.
 * - **Cadastro:** registra um novo usuário via `useAuth().register()` com validação
 *   de senha mínima (6 caracteres) e confirmação de senha.
 *
 * Funcionalidades:
 * - Toggle de tema claro/escuro persistido no `localStorage`.
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
import { Button } from '../components/ui/Button';
import { Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter } from '../components/ui/Card';
import { Wallet, Loader2, AlertCircle, ShieldCheck, Sun, Moon } from 'lucide-react';

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
    <div className="min-h-screen flex items-center justify-center relative overflow-hidden bg-background text-foreground font-sans transition-colors duration-300">
      
      {/* Dynamic Theme Switcher Toggle */}
      <Button
        variant="ghost"
        size="icon"
        onClick={toggleTheme}
        className="absolute top-6 right-6 rounded-xl hover:bg-muted/50 text-muted-foreground h-9 w-9 z-20"
        title="Alternar Tema"
      >
        {theme === 'dark' ? (
          <Sun className="h-[1.1rem] w-[1.1rem]" />
        ) : (
          <Moon className="h-[1.1rem] w-[1.1rem]" />
        )}
      </Button>

      {/* Decorative Vibrant Glowing Orbs */}
      <div className="absolute top-[-20%] left-[-10%] w-[50%] h-[50%] rounded-full bg-primary/10 blur-[120px] pointer-events-none transition-colors duration-500" />
      <div className="absolute bottom-[-20%] right-[-10%] w-[50%] h-[50%] rounded-full bg-primary/10 blur-[120px] pointer-events-none transition-colors duration-500" />

      {/* Main Container */}
      <div className="w-full max-w-md px-6 z-10">
        
        {/* Brand Header */}
        <div className="flex flex-col items-center mb-8 animate-fade-in">
          <div className="w-12 h-12 rounded-2xl bg-primary flex items-center justify-center shadow-lg shadow-primary/20 mb-3 transition-colors duration-300">
            <Wallet className="h-6 w-6 text-primary-foreground" />
          </div>
          <h1 className="text-3xl font-bold tracking-tight text-primary transition-colors duration-300">
            FreeCash
          </h1>
          <p className="text-sm text-muted-foreground mt-1.5 transition-colors duration-300">
            Suíte Premium de Gestão e Investimentos
          </p>
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
                <div className="flex items-center gap-2.5 p-3.5 rounded-xl bg-destructive/10 border border-destructive/20 text-destructive text-xs animate-shake">
                  <AlertCircle className="h-4.5 w-4.5 shrink-0" />
                  <p className="font-medium leading-relaxed">{error}</p>
                </div>
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
                <Input
                  type="password"
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
                  <Input
                    type="password"
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
    </div>
  );
}
