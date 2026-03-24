import api from "./api";

export const roomsApi = {
  getRooms: async () => {
    const response = await api.get("/rooms/");
    return response.data;
  },

  createRoom: async (data: any) => {
    const response = await api.post("/rooms/", data);
    return response.data;
  },

  updateRoom: async (id: string, data: any) => {
    const response = await api.patch(`/rooms/${id}`, data);
    return response.data;
  },

  deleteRoom: async (id: string) => {
    const response = await api.delete(`/rooms/${id}`);
    return response.data;
  },
};
