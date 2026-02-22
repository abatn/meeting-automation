import React from 'react';
import { render, screen } from '@testing-library/react';
import { Provider } from 'react-redux';
import { store } from '../../store';
import MeetingPlanner from '../../components/meetings/MeetingPlanner';
import { LocalizationProvider } from '@mui/x-date-pickers';
import { AdapterDayjs } from '@mui/x-date-pickers/AdapterDayjs';

describe('MeetingPlanner', () => {
  test('renders meeting planner fields', () => {
    render(
      <Provider store={store}>
        <LocalizationProvider dateAdapter={AdapterDayjs}>
          <MeetingPlanner />
        </LocalizationProvider>
      </Provider>
    );
    expect(screen.getByLabelText(/Title/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/Participants/i)).toBeInTheDocument();
  });
});
