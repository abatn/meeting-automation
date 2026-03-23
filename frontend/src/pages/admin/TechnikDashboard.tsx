import React, { useEffect, useState } from 'react';
import { 
  Box, Typography, Grid, Paper, 
  CircularProgress, Stack, Chip,
  Card, CardContent, AppBar, Toolbar, Button, Avatar, Divider
} from '@mui/material';
import { 
  Storage as DbIcon, 
  Memory as RamIcon, 
  Speed as CpuIcon,
  CloudQueue as ServiceIcon,
  Storage as StorageIcon,
  Queue as QueueIcon,
  Code as CodeIcon,
  Psychology as AiIcon,
  Dns as DnsIcon
} from '@mui/icons-material';
import { useDispatch, useSelector } from 'react-redux';
import { useTranslation } from 'react-i18next';
import { RootState, AppDispatch } from '../../store';
import { logout } from '../../store/authSlice';
import api from '../../services/api';
import {
  BarChart, Bar, XAxis, YAxis, Tooltip as RechartsTooltip, ResponsiveContainer
} from 'recharts';

const TechnikDashboard: React.FC = () => {
  const { t } = useTranslation();
  const [metrics, setMetrics] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const dispatch = useDispatch<AppDispatch>();
  const { user } = useSelector((state: RootState) => state.auth);

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

  useEffect(() => {
    fetchMetrics();
    const interval = setInterval(fetchMetrics, 15000);
    return () => clearInterval(interval);
  }, []);

  if (loading) {
    return (
      <Box sx={{ height: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', bgcolor: '#0a1929' }}>
        <CircularProgress color="primary" />
      </Box>
    );
  }

  const handleLogout = () => {
    dispatch(logout());
  };

  const getContainerData = () => {
    if (!metrics?.containers) return [];
    return [
      { name: 'Backend', cpu: metrics.containers.backend.cpu_percent, ram: metrics.containers.backend.ram_mb },
      { name: 'Frontend', cpu: metrics.containers.frontend.cpu_percent, ram: metrics.containers.frontend.ram_mb },
      { name: 'Celery', cpu: metrics.containers.celery.cpu_percent, ram: metrics.containers.celery.ram_mb },
    ];
  };

  return (
    <Box sx={{ minHeight: '100vh', bgcolor: '#0a1929', color: '#fff' }}>
      <AppBar position="static" sx={{ bgcolor: '#001e3c', borderBottom: '1px solid #132f4c' }} elevation={0}>
        <Toolbar>
          <Typography variant="h6" component="div" sx={{ flexGrow: 1, fontWeight: 'bold', color: '#66b2ff' }}>
            {t('admin.missionControl')} ({user?.full_name})
          </Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mr: 2 }}>
            {t('admin.lastUpdate')} {metrics ? new Date(metrics.timestamp * 1000).toLocaleTimeString() : 'N/A'}
          </Typography>
          <Button variant="outlined" color="error" size="small" onClick={handleLogout}>
            Logout
          </Button>
        </Toolbar>
      </AppBar>

      <Box sx={{ p: 4 }}>
        {!metrics ? (
          <Typography color="error">{t('admin.systemOffline')}</Typography>
        ) : (
          <Grid container spacing={3}>
            
            {/* 1. Container Telemetry */}
            <Grid item xs={12}>
              <Typography variant="h6" gutterBottom sx={{ color: '#66b2ff' }}>Container Telemetry</Typography>
              <Grid container spacing={3}>
                {getContainerData().map((c) => (
                  <Grid item xs={12} sm={4} key={c.name}>
                     <Card sx={{ bgcolor: '#001e3c', border: '1px solid #132f4c', color: 'white' }}>
                      <CardContent>
                        <Typography variant="subtitle1" gutterBottom sx={{ fontWeight: 'bold' }}><DnsIcon sx={{verticalAlign:'middle', mr:1, color: '#90caf9'}}/>{c.name}</Typography>
                        <Stack direction="row" justifyContent="space-between" sx={{ mt: 2 }}>
                          <Box>
                            <Typography variant="body2" color="text.secondary">CPU</Typography>
                            <Typography variant="h5" sx={{ color: c.cpu > 80 ? '#f44336' : '#fff' }}>{c.cpu}%</Typography>
                          </Box>
                          <Box>
                            <Typography variant="body2" color="text.secondary">RAM</Typography>
                            <Typography variant="h5" sx={{ color: c.ram > 1500 ? '#f44336' : '#fff' }}>{c.ram} MB</Typography>
                          </Box>
                        </Stack>
                      </CardContent>
                    </Card>
                  </Grid>
                ))}
              </Grid>
            </Grid>

            {/* 2. Core Services Status */}
            <Grid item xs={12} md={4}>
              <Paper sx={{ p: 3, bgcolor: '#001e3c', border: '1px solid #132f4c', color: 'white', height: '100%' }}>
                <Typography variant="h6" gutterBottom>Services Health</Typography>
                <Stack spacing={2} sx={{ mt: 2 }}>
                  {[
                    { name: "PostgreSQL", status: metrics.services.database.status, icon: <DbIcon /> },
                    { name: "Redis", status: metrics.services.redis.status, icon: <ServiceIcon /> },
                    { name: "RabbitMQ", status: metrics.services.rabbitmq.status, icon: <QueueIcon /> },
                    { name: "n8n", status: metrics.services.n8n.status, icon: <CodeIcon /> },
                    { name: "Mistral AI", status: metrics.services.ai_services.mistral.status, icon: <AiIcon /> },
                    { name: "Gladia AI", status: metrics.services.ai_services.gladia.status, icon: <AiIcon /> }
                  ].map((s, i) => (
                    <Box key={i} sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <Stack direction="row" spacing={2} alignItems="center">
                        <Avatar sx={{ width: 32, height: 32, bgcolor: s.status === 'healthy' ? 'rgba(102,187,106,0.1)' : 'rgba(244,67,54,0.1)', color: s.status === 'healthy' ? '#66bb6a' : '#f44336' }}>
                          {React.cloneElement(s.icon as React.ReactElement, { fontSize: 'small' })}
                        </Avatar>
                        <Typography variant="body2">{s.name}</Typography>
                      </Stack>
                      <Chip label={s.status.toUpperCase()} size="small" color={s.status === 'healthy' ? "success" : "error"} />
                    </Box>
                  ))}
                </Stack>
              </Paper>
            </Grid>

            {/* 3. Database Deep Dive */}
            <Grid item xs={12} md={4}>
               <Paper sx={{ p: 3, bgcolor: '#001e3c', border: '1px solid #132f4c', color: 'white', height: '100%' }}>
                  <Typography variant="h6" gutterBottom><DbIcon sx={{verticalAlign:'middle', mr:1}}/>PostgreSQL</Typography>
                  <Divider sx={{ borderColor: '#132f4c', my: 2 }} />
                  <Stack spacing={2}>
                    <Box display="flex" justifyContent="space-between">
                      <Typography variant="body2" color="text.secondary">Active Connections</Typography>
                      <Typography fontWeight="bold">{metrics.services.database.active_connections}</Typography>
                    </Box>
                    <Box display="flex" justifyContent="space-between">
                      <Typography variant="body2" color="text.secondary">Slow Queries (&gt;100ms)</Typography>
                      <Typography fontWeight="bold" color={metrics.services.database.slow_queries > 0 ? "error" : "success.main"}>
                        {metrics.services.database.slow_queries}
                      </Typography>
                    </Box>
                    <Box display="flex" justifyContent="space-between">
                      <Typography variant="body2" color="text.secondary">Cache Hit Ratio</Typography>
                      <Typography fontWeight="bold" color="primary">{metrics.services.database.cache_hit_ratio.toFixed(2)}%</Typography>
                    </Box>
                    <Box display="flex" justifyContent="space-between">
                      <Typography variant="body2" color="text.secondary">Latency</Typography>
                      <Typography fontWeight="bold">{Math.round(metrics.services.database.latency_ms)} ms</Typography>
                    </Box>
                  </Stack>
               </Paper>
            </Grid>

             {/* 4. Redis & Storage */}
             <Grid item xs={12} md={4}>
               <Stack spacing={3} height="100%">
                  <Paper sx={{ p: 3, bgcolor: '#001e3c', border: '1px solid #132f4c', color: 'white', flex: 1 }}>
                    <Typography variant="h6" gutterBottom><ServiceIcon sx={{verticalAlign:'middle', mr:1}}/>Redis Cache</Typography>
                    <Divider sx={{ borderColor: '#132f4c', my: 1 }} />
                    <Grid container spacing={1}>
                      <Grid item xs={6}>
                        <Typography variant="body2" color="text.secondary">Hit Ratio</Typography>
                        <Typography variant="h5" color="primary">{metrics.services.redis.hit_rate.toFixed(1)}%</Typography>
                      </Grid>
                      <Grid item xs={6}>
                        <Typography variant="body2" color="text.secondary">Memory</Typography>
                        <Typography variant="h5">{metrics.services.redis.memory_mb.toFixed(1)} MB</Typography>
                      </Grid>
                      <Grid item xs={12}>
                        <Typography variant="body2" color="text.secondary">Evicted Keys: {metrics.services.redis.evicted_keys}</Typography>
                      </Grid>
                    </Grid>
                  </Paper>
                  <Paper sx={{ p: 3, bgcolor: '#001e3c', border: '1px solid #132f4c', color: 'white', flex: 1 }}>
                    <Typography variant="h6" gutterBottom><StorageIcon sx={{verticalAlign:'middle', mr:1}}/>S3 / MinIO</Typography>
                    <Divider sx={{ borderColor: '#132f4c', my: 1 }} />
                    <Grid container spacing={1}>
                      <Grid item xs={6}>
                        <Typography variant="body2" color="text.secondary">Total Size</Typography>
                        <Typography variant="h5" color="secondary">{metrics.services.storage.usage_mb.toFixed(2)} MB</Typography>
                      </Grid>
                      <Grid item xs={6}>
                        <Typography variant="body2" color="text.secondary">Objects</Typography>
                        <Typography variant="h5">{metrics.services.storage.object_count}</Typography>
                      </Grid>
                    </Grid>
                  </Paper>
               </Stack>
            </Grid>

            {/* 5. RabbitMQ & AI Latency */}
            <Grid item xs={12} md={6}>
              <Paper sx={{ p: 3, bgcolor: '#001e3c', border: '1px solid #132f4c', color: 'white', height: '100%' }}>
                <Typography variant="h6" gutterBottom><QueueIcon sx={{verticalAlign:'middle', mr:1}}/>RabbitMQ Queues</Typography>
                <Typography variant="body2" color="text.secondary" gutterBottom>
                  Total Unacknowledged: {metrics.services.rabbitmq.total_unacked}
                </Typography>
                <Box sx={{ height: 200, mt: 2 }}>
                  {metrics.services.rabbitmq.queues && metrics.services.rabbitmq.queues.length > 0 ? (
                    <ResponsiveContainer width="100%" height="100%">
                      <BarChart data={metrics.services.rabbitmq.queues}>
                        <XAxis dataKey="name" stroke="#aab4be" fontSize={12} />
                        <YAxis stroke="#aab4be" fontSize={12} />
                        <RechartsTooltip contentStyle={{ backgroundColor: '#0a1929', border: 'none' }} />
                        <Bar dataKey="messages" fill="#29b6f6" name="Messages" />
                        <Bar dataKey="unacked" fill="#f44336" name="Unacked" />
                      </BarChart>
                    </ResponsiveContainer>
                  ) : (
                    <Typography variant="body2" color="text.secondary">No active queues</Typography>
                  )}
                </Box>
              </Paper>
            </Grid>

            <Grid item xs={12} md={6}>
               <Paper sx={{ p: 3, bgcolor: '#001e3c', border: '1px solid #132f4c', color: 'white', height: '100%' }}>
                <Typography variant="h6" gutterBottom><AiIcon sx={{verticalAlign:'middle', mr:1}}/>AI Latency & Errors</Typography>
                <Stack spacing={3} sx={{ mt: 2 }}>
                  <Box>
                    <Typography variant="subtitle2" color="primary">Mistral AI</Typography>
                    <Grid container>
                      <Grid item xs={6}>
                        <Typography variant="body2" color="text.secondary">Avg Latency</Typography>
                        <Typography variant="h6">{metrics.services.ai_services.mistral.avg_latency_s.toFixed(2)} s</Typography>
                      </Grid>
                      <Grid item xs={6}>
                        <Typography variant="body2" color="text.secondary">Error Rate</Typography>
                        <Typography variant="h6" color={metrics.services.ai_services.mistral.error_rate > 5 ? "error" : "white"}>
                          {metrics.services.ai_services.mistral.error_rate.toFixed(1)}%
                        </Typography>
                      </Grid>
                    </Grid>
                  </Box>
                  <Divider sx={{ borderColor: '#132f4c' }} />
                  <Box>
                    <Typography variant="subtitle2" color="secondary">Gladia V2</Typography>
                    <Grid container>
                      <Grid item xs={6}>
                        <Typography variant="body2" color="text.secondary">Avg Latency</Typography>
                        <Typography variant="h6">{metrics.services.ai_services.gladia.avg_latency_s.toFixed(2)} s</Typography>
                      </Grid>
                      <Grid item xs={6}>
                        <Typography variant="body2" color="text.secondary">Error Rate</Typography>
                        <Typography variant="h6" color={metrics.services.ai_services.gladia.error_rate > 5 ? "error" : "white"}>
                          {metrics.services.ai_services.gladia.error_rate.toFixed(1)}%
                        </Typography>
                      </Grid>
                    </Grid>
                  </Box>
                </Stack>
              </Paper>
            </Grid>

          </Grid>
        )}
      </Box>
    </Box>
  );
};

export default TechnikDashboard;
