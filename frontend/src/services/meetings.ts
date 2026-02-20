import api from './api';

// TODO: Implement all meeting related API calls
export const getMeetings = async () => {
  const response = await api.get('/meetings');
  return response.data;
};