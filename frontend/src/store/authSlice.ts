import { createSlice, PayloadAction, createAsyncThunk } from "@reduxjs/toolkit";
import api from "../services/api";
import auditService from "../services/auditService";

export interface User {
  id: string;
  client_id: string;
  email: string;
  full_name: string;
  role: string;
}

export type AuthStateStatus = "loading" | "authenticated" | "unauthenticated";

interface AuthState {
  user: User | null;
  authState: AuthStateStatus;
  loading: boolean;
  error: string | null;
  isAuthenticated: boolean;
}

// Async thunk for logout (calls API, clears state, redirects)
export const logoutThunk = createAsyncThunk(
  "auth/logout",
  async (_, { getState }) => {
    const state = getState() as { auth: { user: User | null } };
    const user = state.auth.user;
    
    try {
      // Call backend logout endpoint (clears httpOnly cookie)
      await api.post("/auth/logout");
      
      // Log logout action for audit trail (ISO 27001)
      if (user) {
        await auditService.logLogout(user.id, user.client_id);
      }
      
      return true;
    } catch (error) {
      console.error("Logout failed:", error);
      // Log failed logout attempt for security audit
      if (user) {
        await auditService.logAction({
          action: "LOGOUT",
          resource: "auth",
          recordId: user.id,
          details: { clientId: user.client_id, error: "API call failed" },
        });
      }
      // Even if API call fails, we still need to clear local state
      // Return success so reducer can reset state
      return true;
    }
  },
);

const initialState: AuthState = {
  user: null,
  authState: "loading",
  loading: false,
  error: null,
  isAuthenticated: false,
};

const authSlice = createSlice({
  name: "auth",
  initialState,
  reducers: {
    setCredentials: (
      state,
      action: PayloadAction<{
        user: User;
      }>,
    ) => {
      state.user = action.payload.user;
      // Token is now stored in httpOnly cookie by backend
      // Do NOT store accessToken/refreshToken in state or localStorage
      state.authState = "authenticated";
      state.error = null;
      state.isAuthenticated = true;
      
      // Log successful login for audit trail (ISO 27001)
      // Async operations in reducers must be handled via thunks or separate dispatch
      // So we call auditService here (it's async but we don't await in reducer)
      void auditService.logLogin(action.payload.user.id, action.payload.user.client_id);
    },
    setAuthenticatedUser: (state, action: PayloadAction<User>) => {
      state.user = action.payload;
      state.authState = "authenticated";
      state.error = null;
      state.isAuthenticated = true;
    },
    logout: (state) => {
      state.user = null;
      // Token is cleared by backend via Set-Cookie with Max-Age=0
      state.authState = "unauthenticated";
      state.error = null;
      state.isAuthenticated = false;
      // No need to clear localStorage anymore - no tokens stored there
    },
    setLoading: (state, action: PayloadAction<boolean>) => {
      state.loading = action.payload;
    },
    setError: (state, action: PayloadAction<string | null>) => {
      state.error = action.payload;
    },
  },
  extraReducers: (builder) => {
    builder
      .addCase(logoutThunk.pending, (state) => {
        state.loading = true;
        state.error = null;
      })
      .addCase(logoutThunk.fulfilled, (state) => {
        // Reset state to initial on successful logout
        state.user = null;
        state.authState = "unauthenticated";
        state.error = null;
        state.isAuthenticated = false;
        state.loading = false;
      })
      .addCase(logoutThunk.rejected, (state, action) => {
        // Even on failure, clear auth state for security
        state.user = null;
        state.authState = "unauthenticated";
        state.error = action.payload as string || "Logout failed";
        state.isAuthenticated = false;
        state.loading = false;
      });
  },
});

export const {
  setCredentials,
  setAuthenticatedUser,
  logout,
  setLoading,
  setError,
} = authSlice.actions;
export default authSlice.reducer;
