import api from './api';

// TODO: Implement login, logout, refresh token, MFA setup
export const login = async (credentials: any) => {
  const response = await api.post('/auth/token', credentials);
  return response.data;
};