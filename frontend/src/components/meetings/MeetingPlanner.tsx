import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
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
  Alert,
  Stack,
  Select,
  InputLabel,
  FormControl,
  OutlinedInput
} from '@mui/material';
import {
  CalendarMonth as CalendarIcon,
  EventNote as EventIcon,
  Add as AddIcon,
  Warning as WarningIcon,
} from '@mui/icons-material';
import { useTranslation } from 'react-i18next';
import { useCulturalCalendar } from '../../hooks/useCulturalCalendar';
import { meetingsApi } from '../../services/meetings';

const MeetingPlanner: React.FC = () => {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { isHoliday, getHolidayName } = useCulturalCalendar();
  
  const [title, setTitle] = useState('');
  const [meetingDate, setMeetingDate] = useState('2026-03-03');
  const [selectedParticipants, setSelectedParticipants] = useState<number[]>([]);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const holidays = [
    { date: '2026-03-20', name: 'Independence Day' },
    { date: '2026-04-09', name: 'Martyrs\' Day' },
  ];

  const participantOptions = [
    { id: 1, name: 'Sami Ben Ali', email: 'dg@meeting.tn', role: 'DG' },
    { id: 2, name: 'Amel Trabelsi', email: 'manager@meeting.tn', role: 'Manager' },
    { id: 3, name: 'Mohamed Mahmoud', email: 'user@meeting.tn', role: 'Participant' },
  ];

  const holidayWarning = isHoliday(meetingDate) ? getHolidayName(meetingDate) : null;

  const handleCreate = async () => {
    if (!title || !!holidayWarning) return;
    setIsSubmitting(true);
    try {
      const participants = selectedParticipants.map(id => {
        const opt = participantOptions.find(p => p.id === id);
        return { email: opt?.email || '', name: opt?.name, role: opt?.role };
      });

      const meetingData = {
        title,
        description: 'Scheduled via UI',
        location: 'Virtual',
        status: 'planned',
        start_time: `${meetingDate}T10:00:00Z`,
        end_time: `${meetingDate}T11:00:00Z`,
        participants,
        agendas: []
      };

      const newMeeting = await meetingsApi.createMeeting(meetingData);
      // Redirect to the live meeting room
      navigate(`/meetings/live/${newMeeting.id}`);
    } catch (error: any) {
      console.error('Failed to create meeting', error);
      const errorMsg = error.response?.data?.detail || error.message || 'Unknown error';
      alert(`Error creating meeting: ${errorMsg}`);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <Box sx={{ p: 3 }}>
      <Typography variant="h4" sx={{ mb: 3 }}>
        {t('meetings.planner_title', 'Meeting Planner')}
      </Typography>

      <Grid container spacing={3}>
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
                value={title}
                onChange={(e) => setTitle(e.target.value)}
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

              <FormControl fullWidth>
                <InputLabel id="participants-label">{t('meetings.participants', 'Add Participants')}</InputLabel>
                <Select
                  labelId="participants-label"
                  multiple
                  value={selectedParticipants}
                  onChange={(e) => setSelectedParticipants(e.target.value as number[])}
                  input={<OutlinedInput label={t('meetings.participants', 'Add Participants')} />}
                >
                  {participantOptions.map((opt) => (
                    <MenuItem key={opt.id} value={opt.id}>
                      {opt.name} ({opt.role})
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>

              <Button 
                variant="contained" 
                size="large" 
                startIcon={<AddIcon />}
                disabled={!!holidayWarning || !title || isSubmitting}
                onClick={handleCreate}
              >
                {t('meetings.create', 'Create Meeting')}
              </Button>
            </Stack>
          </Paper>
        </Grid>

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

export default MeetingPlanner;
