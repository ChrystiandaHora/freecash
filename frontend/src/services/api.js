import axios from 'axios';
import {
  STATUS_CONEXAO,
  classificarFalha,
  definirStatusConexao,
  ehFalhaDeConexao,
} from '../lib/statusConexao';

// Variável em memória para o Access Token (segura contra XSS)
let _accessToken = null;

const getAccessToken = () => _accessToken;
export const setAccessToken = (token) => {
  _accessToken = token;
};

// URL Base da API (Backend Django)
const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

const api = axios.create({
  baseURL: API_URL,
  withCredentials: true, // Crucial para enviar/receber cookies HttpOnly (como o Refresh Token)
  headers: {
    'Content-Type': 'application/json',
  },
});

// Interceptor de Requisição: Injeta o Access Token se disponível
api.interceptors.request.use(
  (config) => {
    const token = getAccessToken();
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// Interceptor de Resposta: Renovação Silenciosa de JWT (Silent Refresh)
let isRefreshing = false;
let failedQueue = [];

const processQueue = (error, token = null) => {
  failedQueue.forEach((prom) => {
    if (error) {
      prom.reject(error);
    } else {
      prom.resolve(token);
    }
  });
  failedQueue = [];
};

/**
 * Consulta o healthcheck do backend para saber se a API voltou.
 *
 * Usa o axios puro, e não a instância `api`: o healthcheck não precisa de token e
 * não deve passar pelos interceptores, que reportariam a própria falha de volta ao
 * estado de conexão.
 *
 * @returns {Promise<boolean>} `true` quando a API e o banco respondem.
 */
export const verificarSaudeApi = async () => {
  try {
    await axios.get(`${API_URL}/api/health/`, { timeout: 8000 });
    return true;
  } catch {
    return false;
  }
};

api.interceptors.response.use(
  (response) => {
    // Qualquer resposta do servidor prova que ele está no ar.
    definirStatusConexao(STATUS_CONEXAO.ONLINE);
    return response;
  },
  async (error) => {
    const originalRequest = error.config;

    if (ehFalhaDeConexao(error)) {
      definirStatusConexao(classificarFalha(navigator.onLine));
      return Promise.reject(error);
    }

    // Se falhar por 401 e não for uma tentativa de login ou refresh
    if (error.response?.status === 401 && !originalRequest._retry && originalRequest.url !== '/api/token/' && originalRequest.url !== '/api/token/refresh/') {
      
      if (isRefreshing) {
        // Se já houver um processo de refresh em andamento, enfileira a requisição
        return new Promise((resolve, reject) => {
          failedQueue.push({ resolve, reject });
        })
          .then((token) => {
            originalRequest.headers.Authorization = `Bearer ${token}`;
            return api(originalRequest);
          })
          .catch((err) => Promise.reject(err));
      }

      originalRequest._retry = true;
      isRefreshing = true;

      try {
        // Tenta renovar o token chamando o endpoint de refresh
        // Como o refresh token está em um cookie HttpOnly, ele é enviado automaticamente
        const response = await axios.post(`${API_URL}/api/token/refresh/`, {}, { withCredentials: true });
        const { access } = response.data;
        
        setAccessToken(access);
        originalRequest.headers.Authorization = `Bearer ${access}`;
        
        processQueue(null, access);
        isRefreshing = false;
        
        return api(originalRequest);
      } catch (refreshError) {
        processQueue(refreshError, null);
        isRefreshing = false;

        // Servidor fora do ar não é sessão expirada: deslogar aqui mandaria para o
        // login quem não fez nada de errado. A tela de conexão assume, e a sessão
        // continua válida quando a API voltar.
        if (ehFalhaDeConexao(refreshError)) {
          definirStatusConexao(classificarFalha(navigator.onLine));
          return Promise.reject(refreshError);
        }

        // Se a renovação falhar (refresh token expirado ou inválido), desloga o usuário
        setAccessToken(null);
        // Só redireciona se não estiver na página de login para evitar loops
        if (!window.location.pathname.includes('/login')) {
          window.location.href = '/login';
        }
        return Promise.reject(refreshError);
      }
    }

    return Promise.reject(error);
  }
);

export default api;
