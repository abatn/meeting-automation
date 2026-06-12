import { configureStore } from "@reduxjs/toolkit";
import authReducer from "./authSlice";
import meetingsReducer from "./meetingsSlice";
import actionsReducer from "./actionsSlice";
import reportReducer from "./reportSlice";
import dashboardReducer from "./dashboardSlice";
import recordingReducer from "./recordingSlice";

export const store = configureStore({
  reducer: {
    auth: authReducer,
    meetings: meetingsReducer,
    actions: actionsReducer,
    reports: reportReducer,
    dashboard: dashboardReducer,
    recording: recordingReducer,
  },
});

export type RootState = ReturnType<typeof store.getState>;
export type AppDispatch = typeof store.dispatch;
