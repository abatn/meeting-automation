import { createSlice, createAsyncThunk, PayloadAction } from '@reduxjs/toolkit';
import { getDashboardData } from '../services/reportService';

// Interfaces for data types
interface MeetingStats {
  total: number;
  completed: number;
  scheduled: number;
}

interface ActionStats {
  pending: number;
  completed: number;
}

interface ManagerDashboardData {
  meeting_stats: MeetingStats;
  action_stats: ActionStats;
  team_members_count: number;
}

interface ParticipantDashboardData {
  my_upcoming_meetings: number;
  my_open_actions: number;
}

// Interfaces for slice state
interface DashboardState {
  managerDashboard: {
    data: ManagerDashboardData | null;
    loading: boolean;
    error: string | null;
  };
  participantDashboard: {
    data: ParticipantDashboardData | null;
    loading: boolean;
    error: string | null;
  };
}

const initialState: DashboardState = {
  managerDashboard: {
    data: null,
    loading: false,
    error: null,
  },
  participantDashboard: {
    data: null,
    loading: false,
    error: null,
  },
};

// Async Thunks
export const fetchManagerDashboardData = createAsyncThunk(
  'dashboard/fetchManagerDashboardData',
  async (_, { rejectWithValue }) => {
    try {
      const response = await getDashboardData('manager');
      return response;
    } catch (error: any) {
      const detail = error.response?.data?.detail;
      const errorMessage = typeof detail === 'string' ? detail : JSON.stringify(detail || 'Failed to fetch manager dashboard data');
      return rejectWithValue(errorMessage);
    }
  }
);

export const fetchParticipantDashboardData = createAsyncThunk(
  'dashboard/fetchParticipantDashboardData',
  async (_, { rejectWithValue }) => {
    try {
      const response = await getDashboardData('participant');
      return response;
    } catch (error: any) {
      const detail = error.response?.data?.detail;
      const errorMessage = typeof detail === 'string' ? detail : JSON.stringify(detail || 'Failed to fetch participant dashboard data');
      return rejectWithValue(errorMessage);
    }
  }
);

const dashboardSlice = createSlice({
  name: 'dashboard',
  initialState,
  reducers: {},
  extraReducers: (builder) => {
    builder
      // Manager Dashboard Data
      .addCase(fetchManagerDashboardData.pending, (state) => {
        state.managerDashboard.loading = true;
        state.managerDashboard.error = null;
      })
      .addCase(fetchManagerDashboardData.fulfilled, (state, action: PayloadAction<ManagerDashboardData>) => {
        state.managerDashboard.loading = false;
        state.managerDashboard.data = action.payload;
      })
      .addCase(fetchManagerDashboardData.rejected, (state, action) => {
        state.managerDashboard.loading = false;
        state.managerDashboard.error = action.payload as string;
      })
      // Participant Dashboard Data
      .addCase(fetchParticipantDashboardData.pending, (state) => {
        state.participantDashboard.loading = true;
        state.participantDashboard.error = null;
      })
      .addCase(fetchParticipantDashboardData.fulfilled, (state, action: PayloadAction<ParticipantDashboardData>) => {
        state.participantDashboard.loading = false;
        state.participantDashboard.data = action.payload;
      })
      .addCase(fetchParticipantDashboardData.rejected, (state, action) => {
        state.participantDashboard.loading = false;
        state.participantDashboard.error = action.payload as string;
      });
  },
});

export default dashboardSlice.reducer;
