import api from './api';

export const authService = {
  login: async (email: string, password: string) => {
    const response = await api.post('/auth/login', { email, password });
    return response.data;
  },
  logout: async () => {
    await api.post('/auth/logout');
  },
  getMe: async () => {
    const response = await api.get('/auth/me');
    return response.data;
  },
};

export default authService;