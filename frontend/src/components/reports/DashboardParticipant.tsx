import React from 'react';
import { 
  Grid, 
  Paper, 
  Typography, 
  Box, 
  List,
  ListItem,
  ListItemText,
  ListItemIcon,
  Divider,
  CircularProgress,
  Button,
  Card,
  CardContent
} from '@mui/material';
import { 
  Assignment as ActionIcon, 
  Groups as MeetingIcon, 
  History as HistoryIcon,
  Notifications as NotifyIcon,
  VideoCall as VideoIcon,
  CheckCircleOutline
} from '@mui/icons-material';
import { useTranslation } from 'react-i18next';

const DashboardParticipant: React.FC = () => {
  const { t } = useTranslation();

  const myActions = [
    { id: 1, title: 'Finalize Budget Report', due: '2026-02-22', priority: 'High' },
    { id: 2, title: 'Update HR Policy', due: '2026-02-25', priority: 'Medium' },
  ];

  const myMeetings = [
    { title: 'Weekly IT Sync', time: '10:00 AM', link: 'https://zoom.us/j/123' },
  ];

  const notifications = [
    { id: 1, text: 'New action assigned: "Q1 Planning"', time: '2h ago', type: 'WhatsApp' },
    { id: 2, text: 'PV for Board Meeting is ready', time: '5h ago', type: 'Email' },
  ];

  return (
    <Box sx={{ p: 3 }}>
      <Typography variant="h4" sx={{ mb: 3 }}>{t('dashboard.participant_title', 'My Dashboard')}</Typography>

      <Grid container spacing={3}>
        {/* Personal Stats Card */}
        <Grid item xs={12} md={4}>
          <Card sx={{ bgcolor: 'primary.main', color: 'white' }}>
            <CardContent sx={{ textAlign: 'center' }}>
              <Typography variant="h6">{t('dashboard.my_performance', 'Action Completion Rate')}</Typography>
              <Box sx={{ position: 'relative', display: 'inline-flex', my: 2 }}>
                <CircularProgress variant="determinate" value={85} size={80} sx={{ color: 'white' }} />
                <Box
                  sx={{
                    top: 0, left: 0, bottom: 0, right: 0,
                    position: 'absolute', display: 'flex',
                    alignItems: 'center', justifyContent: 'center',
                  }}
                >
                  <Typography variant="h6" component="div">85%</Typography>
                </Box>
              </Box>
              <Typography variant="body2">{t('dashboard.keep_it_up', 'You are doing great!')}</Typography>
            </CardContent>
          </Card>
        </Grid>

        {/* My Actions */}
        <Grid item xs={12} md={8}>
          <Paper sx={{ p: 2 }}>
            <Typography variant="h6" gutterBottom>
              <ActionIcon sx={{ mr: 1, verticalAlign: 'middle' }} />
              {t('dashboard.my_actions', 'My Pending Actions')}
            </Typography>
            <List>
              {myActions.map((action) => (
                <ListItem key={action.id} divider>
                  <ListItemText 
                    primary={action.title} 
                    secondary={`${t('common.due', 'Due')}: ${action.due}`} 
                  />
                  <Button size="small" variant="contained" color="success">
                    {t('common.complete', 'Mark Done')}
                  </Button>
                </ListItem>
              ))}
            </List>
          </Paper>
        </Grid>

        {/* Upcoming Meetings */}
        <Grid item xs={12} md={6}>
          <Paper sx={{ p: 2 }}>
            <Typography variant="h6" gutterBottom>
              <MeetingIcon sx={{ mr: 1, verticalAlign: 'middle' }} />
              {t('dashboard.upcoming_meetings', 'Next Meetings')}
            </Typography>
            <List>
              {myMeetings.map((m, i) => (
                <ListItem key={i} divider>
                  <ListItemText primary={m.title} secondary={m.time} />
                  <Button startIcon={<VideoIcon />} variant="outlined">Join</Button>
                </ListItem>
              ))}
            </List>
          </Paper>
        </Grid>

        {/* Notifications */}
        <Grid item xs={12} md={6}>
          <Paper sx={{ p: 2 }}>
            <Typography variant="h6" gutterBottom>
              <NotifyIcon sx={{ mr: 1, verticalAlign: 'middle' }} />
              {t('dashboard.notifications', 'Recent Notifications')}
            </Typography>
            <List>
              {notifications.map((n) => (
                <ListItem key={n.id}>
                  <ListItemText primary={n.text} secondary={`${n.time} via ${n.type}`} />
                </ListItem>
              ))}
            </List>
          </Paper>
        </Grid>
      </Grid>
    </Box>
  );
};

export default DashboardParticipant;