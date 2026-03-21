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
  ListItemText
} from '@mui/material';
import { 
  Business as BusinessIcon, 
  AttachMoney as MoneyIcon,
  CheckCircle as ActiveIcon,
  Warning as PendingIcon 
} from '@mui/icons-material';
import adminService, { RevenueStats } from '../../services/adminService';

const AdminDashboard: React.FC = () => {
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

  if (loading) return <CircularProgress />;
  if (!stats) return <Typography color="error">Failed to load statistics.</Typography>;

  return (
    <Box sx={{ p: 3 }}>
      <Typography variant="h4" gutterBottom>System Administrator Dashboard</Typography>
      <Divider sx={{ mb: 4 }} />

      <Grid container spacing={3}>
        {/* KPI Cards */}
        <Grid item xs={12} sm={6} md={3}>
          <Card sx={{ bgcolor: 'primary.light', color: 'primary.contrastText' }}>
            <CardContent>
              <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
                <BusinessIcon sx={{ mr: 1 }} />
                <Typography variant="h6">Total Clients</Typography>
              </Box>
              <Typography variant="h3">{stats.total_clients}</Typography>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} sm={6} md={3}>
          <Card sx={{ bgcolor: 'success.light', color: 'success.contrastText' }}>
            <CardContent>
              <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
                <MoneyIcon sx={{ mr: 1 }} />
                <Typography variant="h6">Est. MRR</Typography>
              </Box>
              <Typography variant="h3">${stats.estimated_mrr_usd}</Typography>
            </CardContent>
          </Card>
        </Grid>
        
        <Grid item xs={12} sm={6} md={3}>
          <Card>
            <CardContent>
              <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
                <ActiveIcon color="success" sx={{ mr: 1 }} />
                <Typography variant="h6">Active Clients</Typography>
              </Box>
              <Typography variant="h4">{stats.status_distribution['ACTIVE'] || 0}</Typography>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} sm={6} md={3}>
          <Card>
            <CardContent>
              <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
                <PendingIcon color="warning" sx={{ mr: 1 }} />
                <Typography variant="h6">Pending Clients</Typography>
              </Box>
              <Typography variant="h4">{stats.status_distribution['PENDING'] || 0}</Typography>
            </CardContent>
          </Card>
        </Grid>

        {/* Detailed Breakdown */}
        <Grid item xs={12} md={6}>
          <Paper sx={{ p: 2 }}>
            <Typography variant="h6" gutterBottom>Plans Distribution</Typography>
            <List>
              {Object.entries(stats.plan_distribution).map(([plan, count]) => (
                <ListItem key={plan} divider>
                  <ListItemText primary={plan} secondary={`${count} clients`} />
                </ListItem>
              ))}
            </List>
          </Paper>
        </Grid>
        
        <Grid item xs={12} md={6}>
          <Paper sx={{ p: 2 }}>
            <Typography variant="h6" gutterBottom>Status Distribution</Typography>
            <List>
              {Object.entries(stats.status_distribution).map(([status, count]) => (
                <ListItem key={status} divider>
                  <ListItemText primary={status} secondary={`${count} clients`} />
                </ListItem>
              ))}
            </List>
          </Paper>
        </Grid>

      </Grid>
    </Box>
  );
};

export default AdminDashboard;