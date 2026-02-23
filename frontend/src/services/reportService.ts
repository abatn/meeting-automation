import api from './api';

export const getManagerDashboard = async () => {
  const response = await api.get('/reports/manager/dashboard');
  return response.data;
};

export const getMeetingStats = async (period: string = 'month') => {
  const response = await api.get(`/reports/meetings/stats?period=${period}`);
  return response.data;
};

export const getActionCompletionRate = async (days: number = 30) => {
  const response = await api.get(`/reports/actions/completion?days=${days}`);
  return response.data;
};

export const getTeamProductivity = async () => {
  const response = await api.get('/reports/team/productivity');
  return response.data;
};

export const getEfficiencyTrend = async (months: number = 6) => {
  const response = await api.get(`/reports/efficiency/trend?months=${months}`);
  return response.data;
};
