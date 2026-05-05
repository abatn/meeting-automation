import api from "./api";
import auditService from "./auditService";

export const roomsApi = {
  getRooms: async () => {
    const response = await api.get("/rooms/");
    return response.data;
  },

  createRoom: async (data: any) => {
    const response = await api.post("/rooms/", data);
    // Log creation for audit trail
    if (response.data?.id) {
      await auditService.logCreate('rooms', response.data.id, data);
    }
    return response.data;
  },

  updateRoom: async (id: string, data: any) => {
    const response = await api.patch(`/rooms/${id}`, data);
    // Log update for audit trail
    await auditService.logUpdate('rooms', id, data);
    return response.data;
  },

  deleteRoom: async (id: string) => {
    const response = await api.delete(`/rooms/${id}`);
    // Log deletion for audit trail
    await auditService.logDelete('rooms', id);
    return response.data;
  },
};
