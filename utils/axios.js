import axios from 'axios';

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL,
  withCredentials: true  // envia o cookie de sessão do Flask
});

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      window.location.href = '/login';  // ou use o router do React
    }
    if (error.response?.status === 403) {
      window.location.href = '/';       // redireciona para home
    }
    return Promise.reject(error);
  }
);

export default api;