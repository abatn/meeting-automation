import React, { useEffect, useState } from 'react';
import { 
  Box, 
  Typography, 
  Card, 
  CardContent, 
  Grid, 
  CircularProgress,
  Paper,
  Divider,
  List,
  ListItem,
  ListItemText,
  useTheme,
  alpha
} from '@mui/material';
import { 
  Business as BusinessIcon, 
  AttachMoney as MoneyIcon,
  CheckCircle as ActiveIcon,
  Warning as PendingIcon 
} from '@mui/icons-material';
import { useTranslation } from 'react-i18next';
import adminService, { RevenueStats } from '../../services/adminService';

const AdminDashboard: React.FC = () => {
  const { t } = useTranslation();
  const theme = useTheme();
  const [stats, setStats] = useState<RevenueStats | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchStats = async () => {
      try {
        const data = await adminService.getRevenueStats();
        setStats(data);
      } catch (error) {
        console.error('Failed to fetch admin stats', error);
      } finally {
        setLoading(false);
      }
    };
    fetchStats();
  }, []);

  if (loading) return <Box sx={{ display: 'flex', justifyContent: 'center', p: 5 }}><CircularProgress /></Box>;
  if (!stats) return <Typography color="error">{t('common.error')}</Typography>;

  return (
    <Box sx={{ maxWidth: 1200, mx: 'auto', p: { xs: 2, md: 4 } }}>
      <Box sx={{ mb: 5 }}>
        <Typography variant="h4" fontWeight="800" color="text.primary" gutterBottom>
          {t('admin.businessOverview')}
        </Typography>
        <Typography variant="body1" color="text.secondary">
          {t('admin.systemAdminDashboard')}
        </Typography>
      </Box>

      {/* KPI Cards */}
      <Grid container spacing={3} sx={{ mb: 5 }}>
        <Grid item xs={12} sm={6} md={3}>
          <Card elevation={0} sx={{ bgcolor: alpha(theme.palette.primary.main, 0.1), border: `1px solid ${alpha(theme.palette.primary.main, 0.2)}`, borderRadius: 3 }}>
            <CardContent>
              <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
                <Box sx={{ p: 1, borderRadius: 2, bgcolor: theme.palette.primary.main, color: 'white', display: 'flex', mr: 2 }}>
                  <BusinessIcon fontSize="small" />
                </Box>
                <Typography variant="subtitle2" color="text.secondary" fontWeight="600">
                  {t('admin.totalClients')}
                </Typography>
              </Box>
              <Typography variant="h3" fontWeight="800" color="primary.dark">{stats.total_clients}</Typography>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} sm={6} md={3}>
          <Card elevation={0} sx={{ bgcolor: alpha(theme.palette.success.main, 0.1), border: `1px solid ${alpha(theme.palette.success.main, 0.2)}`, borderRadius: 3 }}>
            <CardContent>
              <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
                <Box sx={{ p: 1, borderRadius: 2, bgcolor: theme.palette.success.main, color: 'white', display: 'flex', mr: 2 }}>
                  <MoneyIcon fontSize="small" />
                </Box>
                <Typography variant="subtitle2" color="text.secondary" fontWeight="600">
                  {t('admin.estMRR')}
                </Typography>
              </Box>
              <Typography variant="h3" fontWeight="800" color="success.dark">${stats.estimated_mrr_usd}</Typography>
            </CardContent>
          </Card>
        </Grid>
        
        <Grid item xs={12} sm={6} md={3}>
          <Card elevation={0} sx={{ border: '1px solid #E2E8F0', borderRadius: 3 }}>
            <CardContent>
              <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
                <Box sx={{ p: 1, borderRadius: 2, bgcolor: alpha(theme.palette.success.main, 0.1), color: theme.palette.success.main, display: 'flex', mr: 2 }}>
                  <ActiveIcon fontSize="small" />
                </Box>
                <Typography variant="subtitle2" color="text.secondary" fontWeight="600">
                  {t('admin.activeClients')}
                </Typography>
              </Box>
              <Typography variant="h4" fontWeight="800" color="text.primary">{stats.status_distribution['ACTIVE'] || 0}</Typography>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} sm={6} md={3}>
          <Card elevation={0} sx={{ border: '1px solid #E2E8F0', borderRadius: 3 }}>
            <CardContent>
              <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
                <Box sx={{ p: 1, borderRadius: 2, bgcolor: alpha(theme.palette.warning.main, 0.1), color: theme.palette.warning.dark, display: 'flex', mr: 2 }}>
                  <PendingIcon fontSize="small" />
                </Box>
                <Typography variant="subtitle2" color="text.secondary" fontWeight="600">
                  {t('admin.pendingClients')}
                </Typography>
              </Box>
              <Typography variant="h4" fontWeight="800" color="text.primary">{stats.status_distribution['PENDING'] || 0}</Typography>
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      {/* Detailed Breakdown */}
      <Grid container spacing={4}>
        <Grid item xs={12} md={6}>
          <Paper elevation={0} sx={{ p: 3, border: '1px solid #E2E8F0', borderRadius: 3, height: '100%' }}>
            <Typography variant="h6" fontWeight="700" gutterBottom sx={{ mb: 3 }}>
              {t('admin.plansDistribution')}
            </Typography>
            <List disablePadding>
              {Object.entries(stats.plan_distribution).map(([plan, count], index, arr) => (
                <Box key={plan}>
                  <ListItem sx={{ px: 0, py: 1.5 }}>
                    <ListItemText 
                      primary={<Typography fontWeight="600">{plan}</Typography>} 
                      secondary={`${count} ${t('admin.manageClients').toLowerCase()}`} 
                    />
                  </ListItem>
                  {index < arr.length - 1 && <Divider />}
                </Box>
              ))}
            </List>
          </Paper>
        </Grid>
        
        <Grid item xs={12} md={6}>
          <Paper elevation={0} sx={{ p: 3, border: '1px solid #E2E8F0', borderRadius: 3, height: '100%' }}>
            <Typography variant="h6" fontWeight="700" gutterBottom sx={{ mb: 3 }}>
              {t('admin.statusDistribution')}
            </Typography>
            <List disablePadding>
              {Object.entries(stats.status_distribution).map(([status, count], index, arr) => (
                <Box key={status}>
                  <ListItem sx={{ px: 0, py: 1.5 }}>
                    <ListItemText 
                      primary={<Typography fontWeight="600">{status}</Typography>} 
                      secondary={`${count} ${t('admin.manageClients').toLowerCase()}`} 
                    />
                  </ListItem>
                  {index < arr.length - 1 && <Divider />}
                </Box>
              ))}
            </List>
          </Paper>
        </Grid>
      </Grid>
    </Box>
  );
};

export default AdminDashboard;
