import { configureStore } from '@reduxjs/toolkit';
import authReducer from './authSlice';
import meetingsReducer from './meetingsSlice';
import actionsReducer from './actionsSlice';

export const store = configureStore({
  reducer: {
    auth: authReducer,
    meetings: meetingsReducer,
    actions: actionsReducer,
  },
});

export type RootState = ReturnType<typeof store.getState>;
export type AppDispatch = typeof store.dispatch;