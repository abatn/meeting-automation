import { createSlice, PayloadAction } from "@reduxjs/toolkit";

interface User {
  id: string;
  email: string;
  full_name: string;
  role: string;
}

export type AuthStateStatus = "loading" | "authenticated" | "unauthenticated";

interface AuthState {
  user: User | null;
  accessToken: string | null;
  refreshToken: string | null;
  authState: AuthStateStatus;
  loading: boolean;
  error: string | null;
  isAuthenticated: boolean; // Hinzugefügt
}

const initialState: AuthState = {
  user: null,
  accessToken: localStorage.getItem("accessToken"),
  refreshToken: localStorage.getItem("refreshToken"),
  authState: "loading",
  loading: false,
  error: null,
  isAuthenticated: !!localStorage.getItem("accessToken"), // Hinzugefügt: Basierend auf Token-Existenz
};

const authSlice = createSlice({
  name: "auth",
  initialState,
  reducers: {
    setCredentials: (
      state,
      action: PayloadAction<{
        user: User;
        access_token: string;
        refresh_token?: string;
      }>,
    ) => {
      state.user = action.payload.user;
      state.accessToken = action.payload.access_token;
      state.refreshToken = action.payload.refresh_token || state.refreshToken; // Keep old refresh token if new one not provided
      state.authState = "authenticated";
      state.error = null;
      state.isAuthenticated = true; // Hinzugefügt
      localStorage.setItem("accessToken", action.payload.access_token);
      if (action.payload.refresh_token) {
        localStorage.setItem("refreshToken", action.payload.refresh_token);
      }
    },
    setAuthenticatedUser: (state, action: PayloadAction<User>) => {
      state.user = action.payload;
      state.authState = "authenticated";
      state.error = null;
      state.isAuthenticated = true; // Hinzugefügt
    },
    logout: (state) => {
      state.user = null;
      state.accessToken = null;
      state.refreshToken = null;
      state.authState = "unauthenticated";
      state.error = null;
      state.isAuthenticated = false; // Hinzugefügt
      localStorage.clear();
      sessionStorage.clear();
    },
    setLoading: (state, action: PayloadAction<boolean>) => {
      state.loading = action.payload;
    },
    setError: (state, action: PayloadAction<string | null>) => {
      state.error = action.payload;
    },
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
