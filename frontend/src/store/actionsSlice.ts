import { createSlice, PayloadAction } from "@reduxjs/toolkit";

interface ActionItem {
  id: string; // Corrected to string
  description: string;
  assignee_name: string;
  due_date: string;
  status: "pending" | "completed" | "overdue";
}

interface ActionsState {
  list: ActionItem[];
  loading: boolean;
  error: string | null;
}

const initialState: ActionsState = {
  list: [],
  loading: false,
  error: null,
};

const actionsSlice = createSlice({
  name: "actions",
  initialState,
  reducers: {
    setActions: (state, action: PayloadAction<ActionItem[]>) => {
      state.list = action.payload;
    },
    updateActionStatus: (
      state,
      action: PayloadAction<{ id: string; status: ActionItem["status"] }>,
    ) => {
      const index = state.list.findIndex((a) => a.id === action.payload.id);
      if (index !== -1) {
        state.list[index].status = action.payload.status;
      }
    },
    setLoading: (state, action: PayloadAction<boolean>) => {
      state.loading = action.payload;
    },
    setError: (state, action: PayloadAction<string | null>) => {
      state.error = action.payload;
    },
  },
});

export const { setActions, updateActionStatus, setLoading, setError } =
  actionsSlice.actions;
export default actionsSlice.reducer;
