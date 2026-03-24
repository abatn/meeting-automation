import api from "./api";

export const onlyOfficeApi = {
  getConfig: async (pvId: string, language: string = "fr") => {
    const response = await api.get(`/pv/${pvId}/onlyoffice/config?language=${language}`);
    return response.data;
  },
};
