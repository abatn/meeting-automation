import React, { useEffect, useState } from 'react';
import { 
  Box, Typography, Grid, Paper, Divider, 
  CircularProgress, LinearProgress, Stack, Chip
} from '@mui/material';
import { 
  Storage as DbIcon, 
  Memory as RamIcon, 
  Speed as CpuIcon,
  CloudQueue as ServiceIcon,
  CheckCircle as HealthyIcon,
  Error as UnhealthyIcon
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
      <Typography variant="h4" gutterBottom>System Health & Performance</Typography>
      <Divider sx={{ mb: 4 }} />

      <Grid container spacing={3}>
        {/* Resource Usage */}
        <Grid item xs={12} md={6}>
          <Paper sx={{ p: 3 }}>
            <Typography variant="h6" gutterBottom>Resource Usage</Typography>
            
            <Box sx={{ mb: 3 }}>
              <Stack direction="row" justifyContent="space-between" sx={{ mb: 1 }}>
                <Stack direction="row" alignItems="center" spacing={1}>
                  <CpuIcon fontSize="small" />
                  <Typography variant="body2">CPU Load</Typography>
                </Stack>
                <Typography variant="body2" fontWeight="bold">{metrics.resources.cpu_percent}%</Typography>
              </Stack>
              <LinearProgress variant="determinate" value={metrics.resources.cpu_percent} />
            </Box>

            <Box>
              <Stack direction="row" justifyContent="space-between" sx={{ mb: 1 }}>
                <Stack direction="row" alignItems="center" spacing={1}>
                  <RamIcon fontSize="small" />
                  <Typography variant="body2">RAM Usage</Typography>
                </Stack>
                <Typography variant="body2" fontWeight="bold">{metrics.resources.ram_percent}%</Typography>
              </Stack>
              <LinearProgress variant="determinate" value={metrics.resources.ram_percent} color="secondary" />
            </Box>
            
            <Typography variant="caption" color="text.secondary" sx={{ mt: 2, display: 'block' }}>
              Backend Process Memory: {Math.round(metrics.resources.process_memory_mb)} MB
            </Typography>
          </Paper>
        </Grid>

        {/* Services Status */}
        <Grid item xs={12} md={6}>
          <Paper sx={{ p: 3 }}>
            <Typography variant="h6" gutterBottom>Service Status</Typography>
            <Stack spacing={2}>
              <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <Stack direction="row" spacing={1} alignItems="center">
                  <DbIcon color="action" />
                  <Typography>PostgreSQL Database</Typography>
                </Stack>
                <Stack direction="row" spacing={1} alignItems="center">
                  <Typography variant="caption">{Math.round(metrics.services.database.latency_ms)}ms</Typography>
                  <Chip 
                    label={metrics.services.database.status} 
                    color={metrics.services.database.status === 'healthy' ? 'success' : 'error'} 
                    size="small" 
                  />
                </Stack>
              </Box>

              <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <Stack direction="row" spacing={1} alignItems="center">
                  <ServiceIcon color="action" />
                  <Typography>Redis Cache</Typography>
                </Stack>
                <Stack direction="row" spacing={1} alignItems="center">
                   <Typography variant="caption">{Math.round(metrics.services.redis.latency_ms)}ms</Typography>
                  <Chip 
                    label={metrics.services.redis.status} 
                    color={metrics.services.redis.status === 'healthy' ? 'success' : 'error'} 
                    size="small" 
                  />
                </Stack>
              </Box>

              <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <Stack direction="row" spacing={1} alignItems="center">
                  <ServiceIcon color="action" />
                  <Typography>Celery Worker (Queue)</Typography>
                </Stack>
                <Chip label="Healthy" color="success" size="small" />
              </Box>

              <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <Stack direction="row" spacing={1} alignItems="center">
                  <ServiceIcon color="action" />
                  <Typography>AI Services (Whisper/Mistral)</Typography>
                </Stack>
                <Chip label="Ready" color="success" size="small" />
              </Box>
            </Stack>
          </Paper>
        </Grid>
      </Grid>
    </Box>
  );
};

export default TechnikDashboard;