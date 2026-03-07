import { configureStore } from "@reduxjs/toolkit";
import authReducer from "./authSlice";
import meetingsReducer from "./meetingsSlice";
import actionsReducer from "./actionsSlice";
import reportReducer from "./reportSlice";
import dashboardReducer from "./dashboardSlice"; // Neu hinzugefügt

export const store = configureStore({
  reducer: {
    auth: authReducer,
    meetings: meetingsReducer,
    actions: actionsReducer,
    reports: reportReducer,
    dashboard: dashboardReducer, // Neu hinzugefügt
  },
});

export type RootState = ReturnType<typeof store.getState>;
export type AppDispatch = typeof store.dispatch;
