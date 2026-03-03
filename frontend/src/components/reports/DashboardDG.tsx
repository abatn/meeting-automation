import React, { useEffect } from 'react';
import { 
  Grid, 
  Paper, 
  Typography, 
  Box, 
  Button, 
  Divider,
  List,
  ListItem,
  ListItemText,
  ListItemSecondaryAction,
  Chip,
  CircularProgress
} from '@mui/material';
import { 
  Download as DownloadIcon,
  TrendingUp,
  Assignment,
  CheckCircle,
  Warning,
  NotificationsActive 
} from '@mui/icons-material';
import { useTranslation } from 'react-i18next';
import { useDispatch, useSelector } from 'react-redux';
import { AppDispatch, RootState } from '../../store';
import { fetchDashboardData } from '../../store/reportSlice';

import MeetingsPieChart from './MeetingsPieChart';
import ActionsBarChart from './ActionsBarChart';

const DashboardDG: React.FC = () => {
  const { t } = useTranslation();
  const dispatch = useDispatch<AppDispatch>();
  const { dashboardData, loading } = useSelector((state: RootState) => state.reports);

  useEffect(() => {
    dispatch(fetchDashboardData('dg'));
  }, [dispatch]);

  if (loading && !dashboardData) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', p: 5 }}>
        <CircularProgress />
      </Box>
    );
  }

  // Data for Charts
  const meetingData = {
    completed: dashboardData?.completed_meetings || 0,
    scheduled: (dashboardData?.total_meetings || 0) - (dashboardData?.completed_meetings || 0),
    cancelled: 0 // Default for now
  };

  const actionData = {
    completed: dashboardData?.action_status_distribution?.completed || 0,
    pending: dashboardData?.action_status_distribution?.in_progress || 0,
    overdue: dashboardData?.action_status_distribution?.open || 0
  };

  // Map API data to KPI objects
  const kpis = [
    { 
      title: t('dashboard.meetings_month', 'Total Meetings'), 
      value: dashboardData?.total_meetings || '0', 
      icon: <TrendingUp color="primary" />, 
      trend: '+15%' 
    },
    { 
      title: t('dashboard.completion_rate', 'Completed Meetings'), 
      value: dashboardData?.completed_meetings || '0', 
      icon: <CheckCircle color="success" />, 
      trend: 'Stable' 
    },
    { 
      title: t('dashboard.pending_pvs', 'Pending Actions'), 
      value: dashboardData?.pending_actions || '0', 
      icon: <Assignment color="warning" />, 
      trend: 'Action Required' 
    },
  ];

  const recentActivities = [
    { id: 1, text: 'PV for Strategy 2026 generated', time: '2h ago', status: 'Success' },
    { id: 2, text: 'Budget Review Action assigned to Sami', time: '5h ago', status: 'Pending' },
    { id: 3, text: 'IT Sync meeting completed', time: '1d ago', status: 'Success' },
  ];

  return (
    <Box sx={{ flexGrow: 1, p: { xs: 2, md: 3 } }}>
      {/* Header */}
      <Box sx={{ display: 'flex', flexDirection: { xs: 'column', sm: 'row' }, justifyContent: 'space-between', mb: 4, alignItems: { xs: 'flex-start', sm: 'center' }, gap: 2 }}>
        <Typography variant="h4" sx={{ fontWeight: 'bold', color: 'text.primary' }}>
          {t('dashboard.dg_title', 'General Manager Dashboard')}
        </Typography>
        <Button 
          variant="contained" 
          startIcon={<DownloadIcon />} 
          color="primary"
          sx={{ borderRadius: 2, px: 3 }}
        >
          {t('common.export', 'Export Executive Report')}
        </Button>
      </Box>

      {/* KPI Section */}
      <Grid container spacing={3} sx={{ mb: 6 }}>
        {kpis.map((kpi, idx) => (
          <Grid item xs={12} sm={6} md={4} key={idx}>
            <Paper sx={{ p: 3, display: 'flex', alignItems: 'center', borderRadius: 4, boxShadow: '0 4px 12px rgba(0,0,0,0.05)', border: '1px solid rgba(0,0,0,0.05)', minHeight: 120 }}>
              <Box sx={{ 
                bgcolor: 'action.hover', 
                p: 2, 
                borderRadius: 3, 
                display: 'flex',
                mr: 3 
              }}>
                {kpi.icon}
              </Box>
              <Box sx={{ overflow: 'hidden' }}>
                <Typography color="textSecondary" variant="caption" sx={{ textTransform: 'uppercase', fontWeight: 'bold', letterSpacing: 1, display: 'block', mb: 0.5, whiteSpace: 'nowrap' }}>
                  {kpi.title}
                </Typography>
                <Typography variant="h5" sx={{ fontWeight: '800' }}>{kpi.value}</Typography>
                <Typography variant="caption" color="success.main" sx={{ fontWeight: 'bold' }}>
                  {kpi.trend}
                </Typography>
              </Box>
            </Paper>
          </Grid>
        ))}
      </Grid>

      {/* Analytical Charts Section */}
      <Grid container spacing={4} sx={{ mb: 4 }}>
        <Grid item xs={12} lg={6}>
          <Paper sx={{ p: 3, borderRadius: 4, height: '100%', boxShadow: '0 4px 12px rgba(0,0,0,0.05)' }}>
            <Typography variant="h6" sx={{ mb: 2, fontWeight: 'bold' }}>{t('dashboard.meeting_distribution', 'Meeting Status Distribution')}</Typography>
            <Divider sx={{ mb: 3 }} />
            <Box sx={{ height: 320, width: '100%' }}>
              <MeetingsPieChart data={meetingData} />
            </Box>
          </Paper>
        </Grid>
        <Grid item xs={12} lg={6}>
          <Paper sx={{ p: 3, borderRadius: 4, height: '100%', boxShadow: '0 4px 12px rgba(0,0,0,0.05)' }}>
            <Typography variant="h6" sx={{ mb: 2, fontWeight: 'bold' }}>{t('dashboard.action_summary', 'Action Item Summary')}</Typography>
            <Divider sx={{ mb: 3 }} />
            <Box sx={{ height: 320, width: '100%' }}>
              <ActionsBarChart data={actionData} />
            </Box>
          </Paper>
        </Grid>
      </Grid>

      <Grid container spacing={3}>
        {/* Recent Activity */}
        <Grid item xs={12} md={8}>
          <Paper sx={{ p: 3, borderRadius: 3, height: '100%' }}>
            <Typography variant="h6" gutterBottom display="flex" alignItems="center">
              <NotificationsActive sx={{ mr: 1 }} /> {t('dashboard.recent_activity', 'Recent System Activity')}
            </Typography>
            <Divider sx={{ mb: 2 }} />
            <List>
              {recentActivities.map((activity, idx) => (
                <React.Fragment key={activity.id}>
                  <ListItem disableGutters>
                    <ListItemText 
                      primary={activity.text} 
                      secondary={activity.time} 
                    />
                    <ListItemSecondaryAction>
                      <Chip 
                        label={activity.status} 
                        size="small" 
                        color={activity.status === 'Success' ? 'success' : 'warning'} 
                        variant="outlined"
                      />
                    </ListItemSecondaryAction>
                  </ListItem>
                  {idx < recentActivities.length - 1 && <Divider component="li" />}
                </React.Fragment>
              ))}
            </List>
          </Paper>
        </Grid>

        {/* System Health Summary */}
        <Grid item xs={12} md={4}>
          <Paper sx={{ p: 3, borderRadius: 3, bgcolor: '#f5f7fa' }}>
            <Typography variant="h6" gutterBottom>{t('dashboard.system_health', 'System Health')}</Typography>
            <Divider sx={{ mb: 2 }} />
            <Box sx={{ mb: 2 }}>
              <Typography variant="body2" color="textSecondary">API Connectivity</Typography>
              <Typography variant="subtitle1" color="success.main" sx={{ fontWeight: 'bold' }}>Excellent (99.9%)</Typography>
            </Box>
            <Box sx={{ mb: 2 }}>
              <Typography variant="body2" color="textSecondary">AI Transcription Load</Typography>
              <Typography variant="subtitle1" color="primary" sx={{ fontWeight: 'bold' }}>Normal</Typography>
            </Box>
            <Box>
              <Typography variant="body2" color="textSecondary">Storage Capacity</Typography>
              <Typography variant="subtitle1" color="warning.main" sx={{ fontWeight: 'bold' }}>85% Full</Typography>
            </Box>
          </Paper>
        </Grid>
      </Grid>
    </Box>
  );
};

export default DashboardDG;