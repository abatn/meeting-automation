import api from "./api";

export const teamApi = {
  getTeamMembers: async () => {
    const response = await api.get("/team/");
    return response.data;
  },

  createTeamMember: async (data: any) => {
    const response = await api.post("/team/", data);
    return response.data;
  },

  updateTeamMember: async (id: string, data: any) => {
    const response = await api.patch(`/team/${id}`, data);
    return response.data;
  },

  deleteTeamMember: async (id: string) => {
    const response = await api.delete(`/team/${id}`);
    return response.data;
  },

  searchTeam: async (query: string) => {
    const response = await api.get(`/team/search?q=${query}`);
    return response.data;
  },
};
