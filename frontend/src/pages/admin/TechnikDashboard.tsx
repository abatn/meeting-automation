import React, { useEffect, useState } from 'react';
import { 
  Box, Typography, Grid, Paper, Divider, 
  CircularProgress, LinearProgress, Stack, Chip,
  Card, CardContent
} from '@mui/material';
import { 
  Storage as DbIcon, 
  Memory as RamIcon, 
  Speed as CpuIcon,
  CloudQueue as ServiceIcon,
  CheckCircle as HealthyIcon,
  Error as UnhealthyIcon,
  Cloud as StorageIcon,
  People as PeopleIcon
} from '@mui/icons-material';
import api from '../../services/api';

const TechnikDashboard: React.FC = () => {
  const [metrics, setMetrics] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchMetrics = async () => {
      try {
        const response = await api.get('/admin/system/performance');
        setMetrics(response.data);
      } catch (error) {
        console.error('Failed to fetch system metrics', error);
      } finally {
        setLoading(false);
      }
    };
    
    fetchMetrics();
    const interval = setInterval(fetchMetrics, 30000); // Update every 30s
    return () => clearInterval(interval);
  }, []);

  if (loading) return <CircularProgress />;
  if (!metrics) return <Typography color="error">Failed to load system metrics.</Typography>;

  return (
    <Box sx={{ p: 3 }}>
      <Typography variant="h4" gutterBottom fontWeight="bold">System Health & Real-time Metrics</Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 4 }}>Monitoring global infrastructure performance and resource allocation.</Typography>
      <Divider sx={{ mb: 4 }} />

      <Grid container spacing={3}>
        {/* KPI Row */}
        <Grid item xs={12} sm={6} md={3}>
            <Card variant="outlined">
                <CardContent>
                    <Stack direction="row" spacing={1} alignItems="center" sx={{ mb: 1 }}>
                        <DbIcon color="primary" fontSize="small" />
                        <Typography variant="subtitle2" color="text.secondary">DB Connections</Typography>
                    </Stack>
                    <Typography variant="h4" fontWeight="bold">{metrics.services.database.active_connections}</Typography>
                </CardContent>
            </Card>
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
            <Card variant="outlined">
                <CardContent>
                    <Stack direction="row" spacing={1} alignItems="center" sx={{ mb: 1 }}>
                        <StorageIcon color="secondary" fontSize="small" />
                        <Typography variant="subtitle2" color="text.secondary">S3 Storage Usage</Typography>
                    </Stack>
                    <Typography variant="h4" fontWeight="bold">{Math.round(metrics.services.storage.usage_mb)} <Typography component="span" variant="h6">MB</Typography></Typography>
                </CardContent>
            </Card>
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
            <Card variant="outlined">
                <CardContent>
                    <Stack direction="row" spacing={1} alignItems="center" sx={{ mb: 1 }}>
                        <CpuIcon color="warning" fontSize="small" />
                        <Typography variant="subtitle2" color="text.secondary">CPU Load</Typography>
                    </Stack>
                    <Typography variant="h4" fontWeight="bold">{metrics.resources.cpu_percent}%</Typography>
                </CardContent>
            </Card>
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
            <Card variant="outlined">
                <CardContent>
                    <Stack direction="row" spacing={1} alignItems="center" sx={{ mb: 1 }}>
                        <RamIcon color="info" fontSize="small" />
                        <Typography variant="subtitle2" color="text.secondary">Process Mem</Typography>
                    </Stack>
                    <Typography variant="h4" fontWeight="bold">{Math.round(metrics.resources.process_memory_mb)} <Typography component="span" variant="h6">MB</Typography></Typography>
                </CardContent>
            </Card>
        </Grid>

        {/* Detailed Resource Charts (Simulated) */}
        <Grid item xs={12} md={7}>
          <Paper sx={{ p: 3, height: '100%' }}>
            <Typography variant="h6" gutterBottom>Resource Allocation</Typography>
            
            <Box sx={{ mb: 4, mt: 2 }}>
              <Stack direction="row" justifyContent="space-between" sx={{ mb: 1 }}>
                <Typography variant="body2">CPU Core Utilization</Typography>
                <Typography variant="body2" fontWeight="bold">{metrics.resources.cpu_percent}%</Typography>
              </Stack>
              <LinearProgress variant="determinate" value={metrics.resources.cpu_percent} sx={{ height: 10, borderRadius: 5 }} />
            </Box>

            <Box sx={{ mb: 4 }}>
              <Stack direction="row" justifyContent="space-between" sx={{ mb: 1 }}>
                <Typography variant="body2">System RAM Usage</Typography>
                <Typography variant="body2" fontWeight="bold">{metrics.resources.ram_percent}%</Typography>
              </Stack>
              <LinearProgress variant="determinate" value={metrics.resources.ram_percent} color="secondary" sx={{ height: 10, borderRadius: 5 }} />
            </Box>

            <Box>
                <Typography variant="subtitle2" gutterBottom>Database Latency</Typography>
                <Stack direction="row" spacing={1} alignItems="flex-end">
                    <Typography variant="h3" color="primary">{Math.round(metrics.services.database.latency_ms)}</Typography>
                    <Typography variant="h6" color="text.secondary" sx={{ pb: 1 }}>ms</Typography>
                </Stack>
            </Box>
          </Paper>
        </Grid>

        {/* Service Grid */}
        <Grid item xs={12} md={5}>
          <Paper sx={{ p: 3, height: '100%' }}>
            <Typography variant="h6" gutterBottom>Infrastructure Health</Typography>
            <Stack spacing={3} sx={{ mt: 2 }}>
              {[
                { name: "PostgreSQL", status: metrics.services.database.status, icon: <DbIcon /> },
                { name: "Redis Cache", status: metrics.services.redis.status, icon: <ServiceIcon /> },
                { name: "S3 Object Store", status: metrics.services.storage.status, icon: <StorageIcon /> },
                { name: "Celery Worker", status: metrics.services.celery.status, icon: <ServiceIcon /> },
                { name: "AI Engine (Mistral)", status: metrics.services.ai_services.status, icon: <IAIcon /> }
              ].map((s, i) => (
                <Box key={i} sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <Stack direction="row" spacing={2} alignItems="center">
                        <Avatar sx={{ bgcolor: s.status === 'healthy' ? 'success.light' : 'error.light', width: 40, height: 40 }}>
                            {s.icon}
                        </Avatar>
                        <Typography variant="body1" fontWeight="600">{s.name}</Typography>
                    </Stack>
                    <Chip 
                        label={s.status.toUpperCase()} 
                        color={s.status === 'healthy' ? 'success' : 'error'} 
                        size="small"
                        sx={{ fontWeight: 'bold' }}
                    />
                </Box>
              ))}
            </Stack>
          </Paper>
        </Grid>
      </Grid>
    </Box>
  );
};

export default TechnikDashboard;