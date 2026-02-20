import React from 'react';
import { 
  Grid, 
  Paper, 
  Typography, 
  Box, 
  List,
  ListItem,
  ListItemText,
  ListItemAvatar,
  Avatar,
  Divider,
  LinearProgress,
  Chip
} from '@mui/material';
import { 
  Group as GroupIcon, 
  CalendarMonth, 
  AssignmentLate, 
  PriorityHigh,
  WhatsApp
} from '@mui/icons-material';
import { useTranslation } from 'react-i18next';

const DashboardManager: React.FC = () => {
  const { t } = useTranslation();

  const teamActions = [
    { name: 'Sami Ben Ali', count: 12, completed: 8, overdue: 2 },
    { name: 'Amel Trabelsi', count: 8, completed: 7, overdue: 0 },
    { name: 'Mohamed Mahmoud', count: 15, completed: 5, overdue: 5 },
  ];

  const upcomingMeetings = [
    { title: 'Project Sync', time: '14:00', date: 'Today', countdown: '2h 15m' },
    { title: 'Budget Review', time: '09:00', date: 'Tomorrow', countdown: '21h 15m' },
  ];

  return (
    <Box sx={{ p: 3 }}>
      <Typography variant="h4" sx={{ mb: 3 }}>{t('dashboard.manager_title', 'Department Manager Dashboard')}</Typography>
      
      <Grid container spacing={3}>
        {/* Team Actions Overview */}
        <Grid item xs={12} md={6}>
          <Paper sx={{ p: 2, height: '100%' }}>
            <Typography variant="h6" gutterBottom>
              <GroupIcon sx={{ mr: 1, verticalAlign: 'middle' }} />
              {t('dashboard.team_overview', 'Team Overview: Pending Actions')}
            </Typography>
            <List>
              {teamActions.map((member, index) => (
                <Box key={index} sx={{ mb: 2 }}>
                  <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
                    <Typography variant="body2">{member.name}</Typography>
                    <Typography variant="caption">{member.completed}/{member.count} Done</Typography>
                  </Box>
                  <LinearProgress 
                    variant="determinate" 
                    value={(member.completed / member.count) * 100} 
                    color={member.overdue > 0 ? "error" : "primary"}
                    sx={{ height: 8, borderRadius: 4 }}
                  />
                </Box>
              ))}
            </List>
          </Paper>
        </Grid>

        {/* Meeting Calendar */}
        <Grid item xs={12} md={6}>
          <Paper sx={{ p: 2, height: '100%' }}>
            <Typography variant="h6" gutterBottom>
              <CalendarMonth sx={{ mr: 1, verticalAlign: 'middle' }} />
              {t('dashboard.upcoming_meetings', 'Next Meetings')}
            </Typography>
            <List>
              {upcomingMeetings.map((meeting, index) => (
                <ListItem key={index}>
                  <ListItemText 
                    primary={meeting.title} 
                    secondary={`${meeting.date} at ${meeting.time}`} 
                  />
                  <Chip label={meeting.countdown} size="small" color="secondary" />
                </ListItem>
              ))}
            </List>
          </Paper>
        </Grid>

        {/* PV Approvals */}
        <Grid item xs={12} md={6}>
          <Paper sx={{ p: 2 }}>
            <Typography variant="h6" gutterBottom>
              <AssignmentLate sx={{ mr: 1, verticalAlign: 'middle' }} />
              {t('dashboard.pv_pending', 'PVs Awaiting Validation')}
            </Typography>
            <Typography variant="body2" color="textSecondary">
              3 PVs pending your team's input.
            </Typography>
          </Paper>
        </Grid>

        {/* WhatsApp Notification Status */}
        <Grid item xs={12} md={6}>
          <Paper sx={{ p: 2 }}>
            <Typography variant="h6" gutterBottom>
              <WhatsApp sx={{ mr: 1, verticalAlign: 'middle' }} />
              {t('dashboard.whatsapp_status', 'WhatsApp Reminders')}
            </Typography>
            <Box sx={{ display: 'flex', gap: 1 }}>
              <Chip label="Sent: 12" color="success" variant="outlined" />
              <Chip label="Read: 10" color="primary" variant="outlined" />
              <Chip label="Failed: 0" color="error" variant="outlined" />
            </Box>
          </Paper>
        </Grid>
      </Grid>
    </Box>
  );
};

export default DashboardManager;