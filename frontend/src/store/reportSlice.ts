import { createSlice, createAsyncThunk } from '@reduxjs/toolkit';
import * as reportAPI from '../services/reportService';

interface ReportState {
  dashboardData: any | null;
  loading: boolean;
  error: string | null;
}

const initialState: ReportState = {
  dashboardData: null,
  loading: false,
  error: null,
};

export const fetchDashboardData = createAsyncThunk(
  'reports/fetchDashboardData',
  async (_, { rejectWithValue }) => {
    try {
      const data = await reportAPI.getManagerDashboard();
      return data;
    } catch (error: any) {
      return rejectWithValue(error.response?.data?.detail || 'Failed to fetch reports');
    }
  }
);

const reportSlice = createSlice({
  name: 'reports',
  initialState,
  reducers: {},
  extraReducers: (builder) => {
    builder
      .addCase(fetchDashboardData.pending, (state) => {
        state.loading = true;
        state.error = null;
      })
      .addCase(fetchDashboardData.fulfilled, (state, action) => {
        state.loading = false;
        state.dashboardData = action.payload;
      })
      .addCase(fetchDashboardData.rejected, (state, action) => {
        state.loading = false;
        state.error = action.payload as string;
      });
  },
});

export default reportSlice.reducer;
