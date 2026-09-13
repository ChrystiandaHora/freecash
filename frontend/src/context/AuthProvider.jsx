/** Provedor de contexto de autenticação JWT e gerenciamento de sessão do usuário. */
import { createContext, useContext, useState, useEffect, useCallback } from 'react';
import api, { setAccessToken } from '../services/api';
import { buscarPerfil } from '../services/auth';
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

const HAS_SESSION_KEY = 'freecash_has_session';

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [perfil, setPerfil] = useState(null);
  const [loading, setLoading] = useState(true);

  const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

  /** Carrega os dados mais recentes do perfil diretamente da API (/api/auth/me/). */
  const recarregarPerfil = useCallback(async () => {
    try {
      const dados = await buscarPerfil();
      setPerfil(dados);
      return dados;
    } catch {
      setPerfil(null);
      return null;
    }
  }, []);

  useEffect(() => {
    const initializeAuth = async () => {
      // Se não há indicador de sessão anterior (visitante anônimo ou usuário deslogado),
      // evita chamada desnecessária ao refresh que geraria ruído de Bad Request 400 no console.
      const hasSessionHint = localStorage.getItem(HAS_SESSION_KEY) === 'true';
      if (!hasSessionHint) {
        setLoading(false);
        return;
      }

      try {
        const response = await axios.post(`${API_URL}/api/token/refresh/`, {}, { withCredentials: true });
        const { access } = response.data;
        setAccessToken(access);
        const decoded = decodeToken(access);
        setUser(decoded);
        localStorage.setItem(HAS_SESSION_KEY, 'true');
        await recarregarPerfil();
      } catch {
        localStorage.removeItem(HAS_SESSION_KEY);
        setAccessToken(null);
        setUser(null);
        setPerfil(null);
      } finally {
        setLoading(false);
      }
    };

    initializeAuth();
  }, [API_URL, recarregarPerfil]);

  /** Autentica o usuário por e-mail ou username e atualiza o estado da sessão. */
  const login = async (identificador, password) => {
    const response = await api.post('/api/token/', { username: identificador, password });
    const { access } = response.data;
    setAccessToken(access);
    const decoded = decodeToken(access);
    setUser(decoded);
    localStorage.setItem(HAS_SESSION_KEY, 'true');
    await recarregarPerfil();
    return decoded;
  };

  const register = async (username, email, password, confirm) => {
    const response = await api.post('/api/register/', { username, email, password, confirm });
    const { access } = response.data;
    setAccessToken(access);
    const decoded = decodeToken(access);
    setUser(decoded);
    localStorage.setItem(HAS_SESSION_KEY, 'true');
    await recarregarPerfil();
    return decoded;
  };

  const logout = async () => {
    try {
      await api.post('/api/token/clear/');
    } catch (e) {
      console.error('Logout request failed', e);
    } finally {
      localStorage.removeItem(HAS_SESSION_KEY);
      setAccessToken(null);
      setUser(null);
      setPerfil(null);
    }
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        perfil,
        loading,
        login,
        register,
        logout,
        recarregarPerfil,
        isAuthenticated: !!user,
      }}
    >
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
