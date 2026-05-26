import axios from 'axios';

// Variável em memória para o Access Token (segura contra XSS)
let _accessToken = null;

export const getAccessToken = () => _accessToken;
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

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;

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
