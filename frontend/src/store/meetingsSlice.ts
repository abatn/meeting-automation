import { createSlice, PayloadAction } from '@reduxjs/toolkit';

interface MeetingsState {
  meetings: any[]; // TODO: Define meeting type
  isLoading: boolean;
}

const initialState: MeetingsState = {
  meetings: [],
  isLoading: false,
};

const meetingsSlice = createSlice({
  name: 'meetings',
  initialState,
  reducers: {
    setMeetings(state, action: PayloadAction<any[]>) {
      state.meetings = action.payload;
    },
  },
});

export const { setMeetings } = meetingsSlice.actions;
export default meetingsSlice.reducer;