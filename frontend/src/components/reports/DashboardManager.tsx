import React, { useEffect } from 'react';
import { Box, Typography, Paper, Grid, CircularProgress, Alert } from '@mui/material';
import { useTranslation } from 'react-i18next';
import { useDispatch, useSelector } from 'react-redux';
import { RootState, AppDispatch } from '../../store';
import { fetchManagerDashboardData } from '../../store/dashboardSlice';
import MeetingsPieChart from './MeetingsPieChart';
import ActionsBarChart from './ActionsBarChart';
import KPICard from '../common/KPICard';

// Material UI Icons
import EventIcon from '@mui/icons-material/Event';
import EventAvailableIcon from '@mui/icons-material/EventAvailable';
import AssignmentIcon from '@mui/icons-material/Assignment';
import GroupsIcon from '@mui/icons-material/Groups';

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

const DashboardManager: React.FC = () => {
  const { t } = useTranslation();
  const dispatch = useDispatch<AppDispatch>();
  const { data, loading, error } = useSelector(
    (state: RootState) => state.dashboard.managerDashboard
  );

  useEffect(() => {
    dispatch(fetchManagerDashboardData());
  }, [dispatch]);

  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', mt: 4 }}>
        <CircularProgress />
      </Box>
    );
  }

  if (error) {
    return (
      <Box sx={{ p: 3 }}>
        <Alert severity="error">{t('dashboard.error_loading_data', 'Error loading dashboard data:')} {error}</Alert>
      </Box>
    );
  }

  if (!data) {
    return (
      <Box sx={{ p: 3 }}>
        <Alert severity="info">{t('dashboard.no_data_available', 'No dashboard data available.')}</Alert>
      </Box>
    );
  }

  return (
    <Box sx={{ p: 3 }}>
      <Typography variant="h4" gutterBottom>
        {t('dashboard.manager_title', 'Department Manager Dashboard')}
      </Typography>

      <Grid container spacing={3} sx={{ mt: 2 }}>
        {/* KPI Cards */}
        <Grid item xs={12} sm={6} md={3}>
          <KPICard 
            title={t('dashboard.total_team_meetings', 'Total Team Meetings')} 
            value={data.meeting_stats.total} 
            icon={<EventIcon color="primary" fontSize="large" />} 
          />
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <KPICard 
            title={t('dashboard.completed_team_meetings', 'Completed Team Meetings')} 
            value={data.meeting_stats.completed} 
            icon={<EventAvailableIcon color="success" fontSize="large" />} 
          />
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <KPICard 
            title={t('dashboard.pending_team_actions', 'Pending Team Actions')} 
            value={data.action_stats.pending} 
            icon={<AssignmentIcon color="warning" fontSize="large" />} 
          />
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <KPICard 
            title={t('dashboard.team_members', 'Team Members')} 
            value={data.team_members_count} 
            icon={<GroupsIcon color="info" fontSize="large" />} 
          />
        </Grid>

        {/* Charts */}
        <Grid item xs={12} md={6}>
          <Paper sx={{ p: 2, height: 350 }}>
            <Typography variant="h6" gutterBottom>{t('dashboard.meeting_status_distribution', 'Team Meeting Status')}</Typography>
            <Box sx={{ height: '90%' }}>
              <MeetingsPieChart 
                data={{
                  completed: data.meeting_stats.completed,
                  scheduled: data.meeting_stats.scheduled,
                  cancelled: 0 // Annahme, da backend noch keine cancels liefert
                }}
              />
            </Box>
          </Paper>
        </Grid>
        <Grid item xs={12} md={6}>
          <Paper sx={{ p: 2, height: 350 }}>
            <Typography variant="h6" gutterBottom>{t('dashboard.action_status_distribution', 'Team Action Status')}</Typography>
            <Box sx={{ height: '90%' }}>
              <ActionsBarChart 
                data={{
                  completed: data.action_stats.completed,
                  pending: data.action_stats.pending,
                  overdue: 0 // Annahme
                }}
              />
            </Box>
          </Paper>
        </Grid>

        {/* Placeholder for Data Table */}
        <Grid item xs={12}>
          <Paper sx={{ p: 2 }}>
            <Typography variant="h6" gutterBottom>{t('dashboard.team_tasks', 'Team Tasks')}</Typography>
            <Box sx={{ height: 300, overflow: 'auto', display: 'flex', alignItems: 'center', justifyContent: 'center', backgroundColor: '#f5f5f5' }}>
              <Typography color="text.secondary">{t('dashboard.team_tasks_placeholder', 'Team task list with pagination/virtualization will go here.')}</Typography>
            </Box>
          </Paper>
        </Grid>
      </Grid>
    </Box>
  );
};

export default DashboardManager;