import axios from "axios";
import type { RootState } from "../store";

const api = axios.create({
  baseURL: "/api/v1",
  headers: {
    "Content-Type": "application/json",
  },
  withCredentials: true, // Enable automatic cookie inclusion in requests
});

// Store reference (will be set by app initialization)
let reduxStore: { getState: () => RootState } | null = null;

// Function to initialize the store reference (called from main.tsx)
export function initializeApiStore(store: { getState: () => RootState }) {
  reduxStore = store;
}

api.interceptors.request.use(
  (config) => {
    // Token now comes from httpOnly cookie, no manual header needed
    // Browser automatically includes cookie in requests
    
    // Inject client_id from Redux state for multi-tenancy security
    if (reduxStore) {
      const state = reduxStore.getState();
      const clientId = state.auth.user?.client_id;
      
      if (clientId) {
        config.headers["X-Client-ID"] = clientId;
      } else {
        console.warn("No client_id found in Redux state - X-Client-ID header not set");
      }
    } else {
      console.warn("Redux store not initialized for API client");
    }
    
    return config;
  },
  (error) => Promise.reject(error),
);

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;
    
    // Handle 403 Forbidden - likely client_id mismatch
    if (error.response?.status === 403) {
      console.error(
        "Access Denied (403):",
        error.response.data?.detail || "Client ID mismatch or insufficient permissions"
      );
      // Could dispatch to show toast/modal here
      // For now, just log and continue
    }
    
    // Handle 401 Unauthorized - token expired or invalid
    if (error.response?.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true;
      // With httpOnly cookies, token refresh happens automatically
      // Backend should handle refresh token in cookie
      try {
        // Logic for refreshing token would go here
        // const response = await axios.post('/auth/refresh');
        // Backend sets new token in httpOnly cookie
        // return api(originalRequest);
      } catch (refreshError) {
        // On auth failure, redirect to login
        window.location.href = "/login";
      }
    }
    return Promise.reject(error);
  },
);

// Export logout function for use in logoutThunk
export async function logout(): Promise<void> {
  try {
    // Call backend logout endpoint
    // Backend clears httpOnly session cookie via Set-Cookie with Max-Age=0
    await api.post("/auth/logout");
  } catch (error) {
    // Log error but don't throw - frontend still needs to clear state
    console.error("Logout API call failed:", error);
    throw error;
  }
}

export default api;
