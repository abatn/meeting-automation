import api from "./api";

export const authService = {
  login: async (email: string, password: string) => {
    // FastAPI OAuth2 expects form data, not JSON
    const params = new URLSearchParams();
    params.append("username", email);
    params.append("password", password);

    const response = await api.post("/auth/login", params, {
      headers: {
        "Content-Type": "application/x-www-form-urlencoded",
      },
    });
    return response.data;
  },
  logout: async () => {
    try {
      await api.post("/auth/logout");
    } catch (e) {
      console.error("Logout error", e);
    }
  },
  getMe: async () => {
    const response = await api.get("/auth/me");
    return response.data;
  },
  validateToken: async () => {
    const response = await api.get("/auth/validate");
    return response.data;
  },
};

export default authService;
