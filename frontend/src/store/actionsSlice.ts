import { createSlice, PayloadAction } from '@reduxjs/toolkit';

interface ActionsState {
  actions: any[]; // TODO: Define action type
  isLoading: boolean;
}

const initialState: ActionsState = {
  actions: [],
  isLoading: false,
};

const actionsSlice = createSlice({
  name: 'actions',
  initialState,
  reducers: {
    setActions(state, action: PayloadAction<any[]>) {
      state.actions = action.payload;
    },
  },
});

export const { setActions } = actionsSlice.actions;
export default actionsSlice.reducer;