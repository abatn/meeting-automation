import api from './api';

export interface Client {
  id: string;
  company_name: string;
  subscription_plan: string;
  subscription_status: string;
  minutes_included: number;
  minutes_used: number;
  created_at: string;
  observations?: string;
}

export interface RevenueStats {
  total_clients: number;
  status_distribution: Record<string, number>;
  plan_distribution: Record<string, number>;
  estimated_mrr_usd: number;
}

const adminService = {
  getClients: async (status?: string, plan?: string) => {
    const params = new URLSearchParams();
    if (status) params.append('status', status);
    if (plan) params.append('plan', plan);
    
    const response = await api.get(`/admin/clients?${params.toString()}`);
    return response.data;
  },

  getClientDetails: async (clientId: string) => {
    const response = await api.get(`/admin/clients/${clientId}`);
    return response.data;
  },

  updateClientStatus: async (clientId: string, status: string) => {
    const response = await api.patch(`/admin/clients/${clientId}/status`, { status });
    return response.data;
  },

  addClientObservation: async (clientId: string, text: string) => {
    const response = await api.post(`/admin/clients/${clientId}/observations`, { text });
    return response.data;
  },

  getRevenueStats: async () => {
    const response = await api.get('/admin/revenue');
    return response.data;
  },

  getClientInvoices: async (clientId: string) => {
    const response = await api.get(`/billing/admin/client/${clientId}/invoices`);
    return response.data;
  },

  getClientUsage: async (clientId: string) => {
    // Note: This endpoint is handled via billing/usage if we are logged in as that user, 
    // but for admin we might need a specific admin/clients/{id}/usage endpoint later.
    // For now we query the general usage if permitted or mock.
    const response = await api.get(`/billing/usage?client_id=${clientId}`);
    return response.data;
  }
};

export default adminService;