import { AppDispatch } from "./index";
import { setAuthenticatedUser, logout } from "./authSlice";
import authService from "../services/auth";

export const initializeAuth = () => async (dispatch: AppDispatch) => {
  // Token is now in httpOnly cookie, managed by browser
  // Try to validate the cookie-based token with backend
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
    // Backend will delete httpOnly cookie on logout
    await authService.logout();
  } catch (error) {
    console.error("Backend logout failed, proceeding with local logout", error);
  } finally {
    // Always clear local state
    dispatch(logout());
  }
};
