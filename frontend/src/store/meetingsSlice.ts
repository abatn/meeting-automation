import { createSlice, PayloadAction } from '@reduxjs/toolkit';

interface Meeting {
  id: number;
  title: string;
  description: string;
  status: 'planned' | 'in_progress' | 'completed';
  scheduled_at: string;
}

interface MeetingsState {
  list: Meeting[];
  currentMeeting: Meeting | null;
  loading: boolean;
  error: string | null;
}

const initialState: MeetingsState = {
  list: [],
  currentMeeting: null,
  loading: false,
  error: null,
};

const meetingsSlice = createSlice({
  name: 'meetings',
  initialState,
  reducers: {
    setMeetings: (state, action: PayloadAction<Meeting[]>) => {
      state.list = action.payload;
    },
    setCurrentMeeting: (state, action: PayloadAction<Meeting | null>) => {
      state.currentMeeting = action.payload;
    },
    setLoading: (state, action: PayloadAction<boolean>) => {
      state.loading = action.payload;
    },
    setError: (state, action: PayloadAction<string | null>) => {
      state.error = action.payload;
    },
  },
});

export const { setMeetings, setCurrentMeeting, setLoading, setError } = meetingsSlice.actions;
export default meetingsSlice.reducer;