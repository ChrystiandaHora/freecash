/**
 * Provedor de Contexto de Autenticação JWT (AuthProvider).
 *
 * Gerencia o ciclo de vida completo da sessão do usuário utilizando
 * autenticação baseada em JWT com refresh token via cookie HTTP-only:
 *
 * - Na inicialização, tenta renovar silenciosamente o `access token` via
 *   `/api/token/refresh/` (usando o cookie de refresh persistido).
 * - Expõe `login`, `register` e `logout` para operações de autenticação.
 * - Armazena o token de acesso em memória (via `setAccessToken`) para evitar
 *   exposição ao localStorage e mitigar ataques XSS.
 * - O payload do JWT é decodificado localmente para popular o objeto `user`
 *   sem necessidade de chamada adicional à API.
 *
 * Contexto Exportado: `{ user, loading, login, register, logout, isAuthenticated }`
 *
 * @module AuthProvider
 * @component
 *
 * @param {object}      props          - Props do componente.
 * @param {React.ReactNode} props.children - Árvore de componentes filhos que
 *                                          terão acesso ao contexto de auth.
 * @returns {JSX.Element} Provider do contexto de autenticação.
 *
 * @example
 * // Uso do hook de autenticação em um componente filho:
 * const { user, login, logout, isAuthenticated } = useAuth();
 */
import { createContext, useContext, useState, useEffect } from 'react';
import api, { setAccessToken } from '../services/api';
import axios from 'axios';

const AuthContext = createContext(null);

const decodeToken = (token) => {
  try {
    const base64Url = token.split('.')[1];
    const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/');
    const jsonPayload = decodeURIComponent(
      window
        .atob(base64)
        .split('')
        .map((c) => '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2))
        .join('')
    );
    return JSON.parse(jsonPayload);
  } catch {
    return null;
  }
};

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

  useEffect(() => {
    const initializeAuth = async () => {
      try {
        // Tenta renovar silenciosamente na inicialização
        const response = await axios.post(`${API_URL}/api/token/refresh/`, {}, { withCredentials: true });
        const { access } = response.data;
        setAccessToken(access);
        const decoded = decodeToken(access);
        setUser(decoded);
      } catch {
        setAccessToken(null);
        setUser(null);
      } finally {
        setLoading(false);
      }
    };

    initializeAuth();
  }, [API_URL]);

  const login = async (username, password) => {
    const response = await api.post('/api/token/', { username, password });
    const { access } = response.data;
    setAccessToken(access);
    const decoded = decodeToken(access);
    setUser(decoded);
    return decoded;
  };

  const register = async (username, password, confirm) => {
    const response = await api.post('/api/register/', { username, password, confirm });
    const { access } = response.data;
    setAccessToken(access);
    const decoded = decodeToken(access);
    setUser(decoded);
    return decoded;
  };

  const logout = async () => {
    try {
      await api.post('/api/token/clear/');
    } catch (e) {
      console.error('Logout request failed', e);
    } finally {
      setAccessToken(null);
      setUser(null);
    }
  };

  return (
    <AuthContext.Provider value={{ user, loading, login, register, logout, isAuthenticated: !!user }}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};
