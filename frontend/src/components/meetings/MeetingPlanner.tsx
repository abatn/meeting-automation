import React, { useState } from 'react';
import {
  Box,
  Typography,
  Paper,
  Grid,
  Button,
  TextField,
  MenuItem,
  List,
  ListItem,
  ListItemText,
  ListItemIcon,
  Chip,
  IconButton,
  Alert,
} from '@mui/material';
import {
  CalendarMonth as CalendarIcon,
  EventNote as EventIcon,
  Add as AddIcon,
  Warning as WarningIcon,
  Delete as DeleteIcon,
} from '@mui/icons-material';
import { useTranslation } from 'react-i18next';
import { useCulturalCalendar } from '../../hooks/useCulturalCalendar';

const MeetingPlanner: React.FC = () => {
  const { t } = useTranslation();
  const { isHoliday, getHolidayName } = useCulturalCalendar();
  const [meetingDate, setMeetingDate] = useState('2026-03-20'); // Example: Independence Day Tunisia

  const holidays = [
    { date: '2026-03-20', name: 'Independence Day' },
    { date: '2026-04-09', name: 'Martyrs\' Day' },
  ];

  const participantOptions = [
    { id: 1, name: 'Sami Ben Ali', role: 'DG' },
    { id: 2, name: 'Amel Trabelsi', role: 'Manager' },
    { id: 3, name: 'Mohamed Mahmoud', role: 'IT' },
  ];

  const holidayWarning = isHoliday(meetingDate) ? getHolidayName(meetingDate) : null;

  return (
    <Box sx={{ p: 3 }}>
      <Typography variant="h4" sx={{ mb: 3 }}>
        {t('meetings.planner_title', 'Meeting Planner')}
      </Typography>

      <Grid container spacing={3}>
        {/* Left: Planning Form */}
        <Grid item xs={12} md={7}>
          <Paper sx={{ p: 3 }}>
            <Typography variant="h6" gutterBottom>
              {t('meetings.new_meeting', 'Schedule New Meeting')}
            </Typography>
            <Stack spacing={3} sx={{ mt: 2 }}>
              <TextField 
                fullWidth 
                label={t('meetings.title', 'Meeting Title')} 
                placeholder="e.g. Weekly Strategy"
              />
              
              <Box>
                <TextField
                  fullWidth
                  type="date"
                  label={t('meetings.date', 'Date')}
                  value={meetingDate}
                  onChange={(e) => setMeetingDate(e.target.value)}
                  InputLabelProps={{ shrink: true }}
                />
                {holidayWarning && (
                  <Alert severity="warning" icon={<WarningIcon />} sx={{ mt: 1 }}>
                    {t('meetings.holiday_warning', 'Selected date is a public holiday:')} {holidayWarning}
                  </Alert>
                )}
              </Box>

              <TextField select fullWidth label={t('meetings.participants', 'Add Participants')}>
                {participantOptions.map((opt) => (
                  <MenuItem key={opt.id} value={opt.id}>
                    {opt.name} ({opt.role})
                  </MenuItem>
                ))}
              </TextField>

              <Button 
                variant="contained" 
                size="large" 
                startIcon={<AddIcon />}
                disabled={!!holidayWarning}
              >
                {t('meetings.create', 'Create Meeting')}
              </Button>
            </Stack>
          </Paper>
        </Grid>

        {/* Right: Cultural Calendar Preview */}
        <Grid item xs={12} md={5}>
          <Paper sx={{ p: 2, bgcolor: 'action.hover' }}>
            <Typography variant="subtitle1" gutterBottom>
              <CalendarIcon sx={{ mr: 1, verticalAlign: 'middle' }} />
              {t('meetings.upcoming_holidays', 'Upcoming Holidays (Tunisia)')}
            </Typography>
            <List dense>
              {holidays.map((h, i) => (
                <ListItem key={i}>
                  <ListItemIcon><EventIcon fontSize="small" /></ListItemIcon>
                  <ListItemText primary={h.name} secondary={h.date} />
                  <Chip label="Holiday" size="small" color="error" variant="outlined" />
                </ListItem>
              ))}
            </List>
          </Paper>
        </Grid>
      </Grid>
    </Box>
  );
};

// Helper for layout
import { Stack } from '@mui/material';

export default MeetingPlanner;