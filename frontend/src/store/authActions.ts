import { AppDispatch } from "./index";
import { setAuthenticatedUser, logout, setLoading } from "./authSlice";
import authService from "../services/auth";

export const initializeAuth = () => async (dispatch: AppDispatch) => {
  const token = localStorage.getItem("accessToken");

  if (!token) {
    dispatch(logout());
    return;
  }

  try {
    const response = await authService.validateToken();
    if (response && response.user) {
      dispatch(setAuthenticatedUser(response.user));
    } else {
      dispatch(logout());
    }
  } catch (error) {
    console.error("Auth initialization failed", error);
    dispatch(logout());
  }
};

export const performLogout = () => async (dispatch: AppDispatch) => {
  try {
    // Notify the backend to blacklist the token
    await authService.logout();
  } catch (error) {
    console.error("Backend logout failed, proceeding with local logout", error);
  } finally {
    // Always clear local state
    dispatch(logout());
  }
};
