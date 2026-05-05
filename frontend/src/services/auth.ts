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
      withCredentials: true, // Ensure httpOnly cookie is set
    });
    return response.data;
  },
  register: async (userData: any) => {
    const response = await api.post("/auth/register", userData);
    return response.data;
  },
  logout: async () => {
    try {
      // Backend should delete httpOnly cookie on logout
      await api.post("/auth/logout", {}, { withCredentials: true });
    } catch (e) {
      console.error("Logout error", e);
    }
  },
  getMe: async () => {
    const response = await api.get("/auth/me");
    return response.data;
  },
  validateToken: async () => {
    // Backend validates cookie-based token, no need to send anything
    const response = await api.get("/auth/validate");
    return response.data;
  },
};

export default authService;
