import api from "./api";
import auditService from "./auditService";

export const teamApi = {
  getTeamMembers: async () => {
    const response = await api.get("/team/");
    return response.data;
  },

  createTeamMember: async (data: any) => {
    const response = await api.post("/team/", data);
    // Log creation for audit trail
    if (response.data?.id) {
      await auditService.logCreate('team', response.data.id, { email: data.email, role: data.role });
    }
    return response.data;
  },

  updateTeamMember: async (id: string, data: any) => {
    const response = await api.patch(`/team/${id}`, data);
    // Log update for audit trail
    await auditService.logUpdate('team', id, { role: data.role });
    return response.data;
  },

  deleteTeamMember: async (id: string) => {
    const response = await api.delete(`/team/${id}`);
    // Log deletion for audit trail
    await auditService.logDelete('team', id);
    return response.data;
  },

  searchTeam: async (query: string) => {
    const response = await api.get(`/team/search?q=${query}`);
    return response.data;
  },
};
