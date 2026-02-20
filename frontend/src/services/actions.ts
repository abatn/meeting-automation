import api from './api';

// TODO: Implement all action related API calls
export const getActions = async () => {
  const response = await api.get('/actions');
  return response.data;
};