import React, { useEffect, useState, useRef } from 'react';
import {
  Box, Typography, Grid, Paper,
  CircularProgress, Stack, Chip,
  Card, CardContent, AppBar, Toolbar, Button, Divider,
  IconButton, Tooltip, List, ListItemButton, ListItemIcon,
  Dialog, DialogTitle, DialogContent, DialogActions, Table, TableBody,
  TableCell, TableContainer, TableHead, TableRow
} from '@mui/material';
import {
  Storage as DbIcon,
  CloudQueue as ServiceIcon,
  Storage as StorageIcon,
  Queue as QueueIcon,
  Code as CodeIcon,
  Psychology as AiIcon,
  Dns as DnsIcon,
  DarkMode as DarkModeIcon,
  LightMode as LightModeIcon,
  HealthAndSafety as HealthIcon,
  Sensors as ClusterIcon,
  RestartAlt as RestartIcon,
  Terminal as LogIcon,
} from '@mui/icons-material';
import { useDispatch, useSelector } from 'react-redux';
import { useTranslation } from 'react-i18next';
import { RootState, AppDispatch } from '../../store';
import { logout } from '../../store/authSlice';
import api from '../../services/api';
import { BarChart, Bar, XAxis, YAxis, Tooltip as RechartsTooltip, ResponsiveContainer } from 'recharts';

type ThemeMode = 'dark' | 'light';

interface ThemeColors {
  bg: string; card: string; border: string; text: string; textSec: string;
  accent: string; innerBg: string; appBar: string;
}

const THEMES: Record<ThemeMode, ThemeColors> = {
  dark: { bg: '#0a1929', card: '#001e3c', border: '#132f4c', text: '#ffffff', textSec: '#9aa5b4', accent: '#66b2ff', innerBg: '#0a1929', appBar: '#001e3c' },
  light: { bg: '#f4f6f8', card: '#ffffff', border: '#e0e0e0', text: '#1a1a2e', textSec: '#666666', accent: '#1565c0', innerBg: '#f9fafb', appBar: '#ffffff' },
};

const SIDEBAR_ITEMS = [
  { id: 'services', label: 'Services', icon: <HealthIcon fontSize="small" /> },
  { id: 'database', label: 'Database', icon: <DbIcon fontSize="small" /> },
  { id: 'monitoring', label: 'Monitoring', icon: <ClusterIcon fontSize="small" /> },
  { id: 'pods', label: 'Pods', icon: <DnsIcon fontSize="small" /> },
  { id: 'redis-mgmt', label: 'Redis', icon: <ServiceIcon fontSize="small" /> },
  { id: 'storage-mgmt', label: 'Storage', icon: <StorageIcon fontSize="small" /> },
  { id: 'backup-mgmt', label: 'Backup', icon: <StorageIcon fontSize="small" /> },
];

const TechnikDashboard: React.FC = () => {
  const { t } = useTranslation();
  const [darkMode, setDarkMode] = useState<ThemeMode>('dark');
  const [metrics, setMetrics] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [activeSection, setActiveSection] = useState('services');
  const [logModal, setLogModal] = useState<{ pod: string; logs: string[] } | null>(null);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const dispatch = useDispatch<AppDispatch>();
  const { user } = useSelector((state: RootState) => state.auth);
  const theme = THEMES[darkMode];
  const contentRef = useRef<HTMLDivElement>(null);

  const fetchMetrics = async () => {
    try {
      const r = await api.get('/admin/system/performance');
      setMetrics(r.data);
    } catch (e) { console.error(e); }
    finally { setLoading(false); }
  };

  useEffect(() => {
    fetchMetrics();
    const i = setInterval(fetchMetrics, 15000);
    return () => clearInterval(i);
  }, []);

  useEffect(() => {
    const obs = new IntersectionObserver((entries) => {
      entries.forEach((e) => { if (e.isIntersecting) setActiveSection(e.target.id); });
    }, { rootMargin: '-20% 0px -60% 0px' });
    contentRef.current?.querySelectorAll('[id]').forEach((s) => obs.observe(s));
    return () => obs.disconnect();
  }, [loading]);

  const toggleTheme = () => setDarkMode(darkMode === 'dark' ? 'light' : 'dark');
  const severityColor = (s: string) => s === 'critical' ? '#f44336' : s === 'warning' ? '#ff9800' : '#90caf9';

  if (loading) return (
    <Box sx={{ height: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', bgcolor: theme.bg }}>
      <CircularProgress />
    </Box>
  );

  return (
    <Box sx={{ minHeight: '100vh', bgcolor: theme.bg, color: theme.text }}>
      <AppBar position="fixed" sx={{ bgcolor: theme.appBar, borderBottom: `1px solid ${theme.border}`, color: theme.text, zIndex: 1300 }} elevation={0}>
        <Toolbar>
          <HealthIcon sx={{ color: theme.accent, mr: 1 }} />
          <Typography variant="h6" sx={{ flexGrow: 1, fontWeight: 'bold', color: theme.accent }}>
            {t('admin.missionControl')} ({user?.full_name})
          </Typography>
          <IconButton onClick={toggleTheme} sx={{ color: theme.accent }}>
            {darkMode ? <LightModeIcon /> : <DarkModeIcon />}
          </IconButton>
          <Button variant="outlined" size="small" onClick={() => dispatch(logout())} sx={{ borderColor: theme.border, color: theme.textSec }}>
            {t('auth.logout')}
          </Button>
        </Toolbar>
      </AppBar>

      <Box sx={{ display: 'flex', pt: '64px' }}>
        <Box sx={{ width: 56, flexShrink: 0, borderRight: `1px solid ${theme.border}`, bgcolor: theme.card, height: 'calc(100vh - 64px)', position: 'sticky', top: 64 }}>
          <List dense disablePadding>
            {SIDEBAR_ITEMS.map((item) => (
              <ListItemButton key={item.id} selected={activeSection === item.id}
                onClick={() => document.getElementById(item.id)?.scrollIntoView({ behavior: 'smooth' })}
                sx={{ py: 1.5, justifyContent: 'center', color: activeSection === item.id ? theme.accent : theme.textSec, '&.Mui-selected': { bgcolor: `${theme.accent}15` } }}>
                <Tooltip title={item.label} placement="right"><ListItemIcon sx={{ minWidth: 0, justifyContent: 'center' }}>{item.icon}</ListItemIcon></Tooltip>
              </ListItemButton>
            ))}
          </List>
        </Box>

        <Box ref={contentRef} sx={{ flex: 1, p: 3, minWidth: 0 }}>
          {metrics && (
            <Grid container spacing={3}>
              {/* Services */}
              <Grid item xs={12} id="services">
                <Typography variant="h6" gutterBottom sx={{ color: theme.accent }}>{t('admin.service_status')}</Typography>
                <Grid container spacing={2}>
                  {[
                    { name: 'PostgreSQL', status: metrics.services.database.status },
                    { name: 'Redis', status: metrics.services.redis.status },
                    { name: 'RabbitMQ', status: metrics.services.rabbitmq.status },
                    { name: 'n8n', status: metrics.services.n8n.status },
                    { name: 'Mistral AI', status: metrics.services.ai_services.mistral.status },
                    { name: 'Gladia AI', status: metrics.services.ai_services.gladia.status },
                  ].map((s) => (
                    <Grid item xs={6} sm={4} md={2} key={s.name}>
                      <Card sx={{ bgcolor: theme.card, border: `1px solid ${theme.border}` }}>
                        <CardContent sx={{ textAlign: 'center' }}>
                          <Typography variant="body2" fontWeight="bold">{s.name}</Typography>
                          <Chip label={s.status.toUpperCase()} size="small" color={s.status === 'healthy' ? 'success' : 'error'} sx={{ mt: 1 }} />
                        </CardContent>
                      </Card>
                    </Grid>
                  ))}
                </Grid>
              </Grid>

              {/* Database */}
              <Grid item xs={12} id="database">
                <Typography variant="h6" gutterBottom sx={{ color: theme.accent }}>{t('admin.postgresql')}</Typography>
                <Paper sx={{ p: 3, bgcolor: theme.card, border: `1px solid ${theme.border}` }}>
                  <Grid container spacing={2}>
                    <Grid item xs={3}><Typography variant="caption" color="text.secondary">Connections</Typography><Typography variant="h6">{metrics.services.database.active_connections}</Typography></Grid>
                    <Grid item xs={3}><Typography variant="caption" color="text.secondary">Slow Queries</Typography><Typography variant="h6" color={metrics.services.database.slow_queries > 0 ? 'error' : 'inherit'}>{metrics.services.database.slow_queries}</Typography></Grid>
                    <Grid item xs={3}><Typography variant="caption" color="text.secondary">Cache Hit</Typography><Typography variant="h6" color="primary">{metrics.services.database.cache_hit_ratio.toFixed(2)}%</Typography></Grid>
                    <Grid item xs={3}><Typography variant="caption" color="text.secondary">Latency</Typography><Typography variant="h6">{Math.round(metrics.services.database.latency_ms)}ms</Typography></Grid>
                  </Grid>
                </Paper>
              </Grid>

              {/* Monitoring */}
              <Grid item xs={12} id="monitoring">
                <Typography variant="h6" gutterBottom sx={{ color: theme.accent }}>Monitoring</Typography>
                <Grid container spacing={2}>
                  <Grid item xs={12} md={6}>
                    <Paper sx={{ p: 3, bgcolor: theme.card, border: `1px solid ${theme.border}` }}>
                      <Typography variant="h6" gutterBottom><QueueIcon sx={{ verticalAlign: 'middle', mr: 1 }} />RabbitMQ</Typography>
                      <Typography variant="body2" color="text.secondary">Unacked: {metrics.services.rabbitmq.total_unacked}</Typography>
                      <Box sx={{ height: 200, mt: 2 }}>
                        {metrics.services.rabbitmq.queues?.length > 0 ? (
                          <ResponsiveContainer width="100%" height="100%">
                            <BarChart data={metrics.services.rabbitmq.queues}>
                              <XAxis dataKey="name" stroke={theme.textSec} fontSize={11} />
                              <YAxis stroke={theme.textSec} fontSize={11} />
                              <RechartsTooltip contentStyle={{ backgroundColor: theme.card, border: `1px solid ${theme.border}` }} />
                              <Bar dataKey="messages" fill="#29b6f6" />
                              <Bar dataKey="unacked" fill="#f44336" />
                            </BarChart>
                          </ResponsiveContainer>
                        ) : <Typography color="text.secondary">No queues</Typography>}
                      </Box>
                    </Paper>
                  </Grid>
                  <Grid item xs={12} md={6}>
                    <Paper sx={{ p: 3, bgcolor: theme.card, border: `1px solid ${theme.border}` }}>
                      <Typography variant="h6" gutterBottom><AiIcon sx={{ verticalAlign: 'middle', mr: 1 }} />AI Latency</Typography>
                      <Stack spacing={2}>
                        <Box><Typography variant="subtitle2" color="primary">Mistral</Typography><Grid container><Grid item xs={6}><Typography variant="caption" color="text.secondary">Latency</Typography><Typography variant="h6">{metrics.services.ai_services.mistral.avg_latency_s.toFixed(2)}s</Typography></Grid><Grid item xs={6}><Typography variant="caption" color="text.secondary">Errors</Typography><Typography variant="h6" color={metrics.services.ai_services.mistral.error_rate > 5 ? 'error' : 'inherit'}>{metrics.services.ai_services.mistral.error_rate.toFixed(1)}%</Typography></Grid></Grid></Box>
                        <Divider sx={{ borderColor: theme.border }} />
                        <Box><Typography variant="subtitle2" color="secondary">Gladia</Typography><Grid container><Grid item xs={6}><Typography variant="caption" color="text.secondary">Latency</Typography><Typography variant="h6">{metrics.services.ai_services.gladia.avg_latency_s.toFixed(2)}s</Typography></Grid><Grid item xs={6}><Typography variant="caption" color="text.secondary">Errors</Typography><Typography variant="h6" color={metrics.services.ai_services.gladia.error_rate > 5 ? 'error' : 'inherit'}>{metrics.services.ai_services.gladia.error_rate.toFixed(1)}%</Typography></Grid></Grid></Box>
                      </Stack>
                    </Paper>
                  </Grid>
                </Grid>
              </Grid>

              {/* Pod Manager */}
              <Grid item xs={12} id="pods"><PodManager theme={theme} /></Grid>

              {/* Redis Manager */}
              <Grid item xs={12} id="redis-mgmt"><RedisManager theme={theme} confirmOpen={confirmOpen} setConfirmOpen={setConfirmOpen} /></Grid>

              {/* Storage Manager */}
              <Grid item xs={12} id="storage-mgmt"><StorageManager theme={theme} /></Grid>

              {/* Backup Manager */}
              <Grid item xs={12} id="backup-mgmt"><BackupManager theme={theme} /></Grid>
            </Grid>
          )}
        </Box>
      </Box>

      {/* Log Modal */}
      <Dialog open={!!logModal} onClose={() => setLogModal(null)} maxWidth="md" fullWidth PaperProps={{ sx: { bgcolor: theme.card, color: theme.text } }}>
        <DialogTitle>Logs: {logModal?.pod}</DialogTitle>
        <DialogContent><pre style={{ fontFamily: 'monospace', fontSize: 12, whiteSpace: 'pre-wrap', color: theme.text, maxHeight: 400, overflow: 'auto' }}>{logModal?.logs?.join('\n') || 'Keine Logs'}</pre></DialogContent>
        <DialogActions><Button onClick={() => setLogModal(null)}>Schließen</Button></DialogActions>
      </Dialog>
    </Box>
  );
};

function PodManager({ theme }: { theme: ThemeColors }) {
  const [pods, setPods] = useState<any[]>([]);
  const [expanded, setExpanded] = useState(false);
  const [logModal, setLogModal] = useState<{ pod: string; logs: string[] } | null>(null);

  useEffect(() => {
    const load = async () => { try { const r = await api.get('/admin/management/pods'); setPods(r.data?.pods || []); } catch { /* ignore */ } };
    load(); const i = setInterval(load, 15000); return () => clearInterval(i);
  }, []);

  const restartPod = async (name: string) => { try { await api.post(`/admin/management/pods/${name}/restart`); setTimeout(() => api.get('/admin/management/pods').then(r => setPods(r.data?.pods || [])), 3000); } catch { /* ignore */ } };
  const showLogs = async (name: string) => { try { const r = await api.get(`/admin/management/pods/${name}/logs?lines=100`); setLogModal({ pod: name, logs: r.data?.logs || [] }); } catch { /* ignore */ } };

  return (
    <Paper sx={{ p: 3, bgcolor: theme.card, border: `1px solid ${theme.border}` }}>
      <Box display="flex" alignItems="center" justifyContent="space-between" onClick={() => setExpanded(!expanded)} sx={{ cursor: 'pointer' }}>
        <Typography variant="h6"><DnsIcon sx={{ verticalAlign: 'middle', mr: 1 }} />Pods ({pods.length})</Typography>
        <Chip label={expanded ? 'Weniger' : 'Alle'} size="small" />
      </Box>
      {expanded && (
        <TableContainer sx={{ mt: 2 }}>
          <Table size="small">
            <TableHead><TableRow><TableCell sx={{ color: theme.text }}>Name</TableCell><TableCell sx={{ color: theme.text }}>Status</TableCell><TableCell sx={{ color: theme.text }}>Restarts</TableCell><TableCell sx={{ color: theme.text }}>Aktionen</TableCell></TableRow></TableHead>
            <TableBody>
              {pods.map((pod) => (
                <TableRow key={pod.name}>
                  <TableCell sx={{ color: theme.text, fontSize: 11, fontFamily: 'monospace' }}>{pod.name}</TableCell>
                  <TableCell><Chip label={pod.status} size="small" color={pod.status === 'Running' ? 'success' : 'error'} /></TableCell>
                  <TableCell sx={{ color: theme.text }}>{pod.restarts}</TableCell>
                  <TableCell>
                    <Tooltip title="Restart"><IconButton size="small" onClick={() => restartPod(pod.name)}><RestartIcon fontSize="small" /></IconButton></Tooltip>
                    <Tooltip title="Logs"><IconButton size="small" onClick={() => showLogs(pod.name)}><LogIcon fontSize="small" /></IconButton></Tooltip>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      )}
    </Paper>
  );
}

function RedisManager({ theme, confirmOpen, setConfirmOpen }: { theme: ThemeColors; confirmOpen: boolean; setConfirmOpen: (v: boolean) => void }) {
  const [info, setInfo] = useState<any>(null);

  useEffect(() => {
    const load = async () => { try { const r = await api.get('/admin/management/redis/info'); setInfo(r.data); } catch { /* ignore */ } };
    load(); const i = setInterval(load, 30000); return () => clearInterval(i);
  }, []);

  const flushRedis = async () => { try { await api.post('/admin/management/redis/flush'); setConfirmOpen(false); } catch { /* ignore */ } };

  return (
    <Paper sx={{ p: 3, bgcolor: theme.card, border: `1px solid ${theme.border}` }}>
      <Box display="flex" alignItems="center" justifyContent="space-between">
        <Typography variant="h6"><ServiceIcon sx={{ verticalAlign: 'middle', mr: 1 }} />Redis {info && `(${info.memory_used})`}</Typography>
        <Button size="small" color="warning" onClick={() => setConfirmOpen(true)}>Flush</Button>
      </Box>
      {info && (
        <Grid container spacing={2} sx={{ mt: 1 }}>
          <Grid item xs={3}><Typography variant="caption" color="text.secondary">Version</Typography><Typography>{info.version}</Typography></Grid>
          <Grid item xs={3}><Typography variant="caption" color="text.secondary">Memory</Typography><Typography>{info.memory_used}</Typography></Grid>
          <Grid item xs={3}><Typography variant="caption" color="text.secondary">Keys</Typography><Typography>{info.total_keys}</Typography></Grid>
          <Grid item xs={3}><Typography variant="caption" color="text.secondary">Uptime</Typography><Typography>{info.uptime_seconds}s</Typography></Grid>
        </Grid>
      )}
      <Dialog open={confirmOpen} onClose={() => setConfirmOpen(false)} PaperProps={{ sx: { bgcolor: theme.card, color: theme.text } }}>
        <DialogTitle>Redis Flush</DialogTitle>
        <DialogContent><Typography>Alle Keys löschen?</Typography></DialogContent>
        <DialogActions><Button onClick={() => setConfirmOpen(false)}>Abbrechen</Button><Button color="error" onClick={flushRedis}>Flush</Button></DialogActions>
      </Dialog>
    </Paper>
  );
}

function StorageManager({ theme }: { theme: ThemeColors }) {
  const [buckets, setBuckets] = useState<any[]>([]);

  useEffect(() => {
    const load = async () => { try { const r = await api.get('/admin/management/storage/buckets'); setBuckets(r.data?.buckets || []); } catch { /* ignore */ } };
    load(); const i = setInterval(load, 30000); return () => clearInterval(i);
  }, []);

  return (
    <Paper sx={{ p: 3, bgcolor: theme.card, border: `1px solid ${theme.border}` }}>
      <Typography variant="h6"><StorageIcon sx={{ verticalAlign: 'middle', mr: 1 }} />Storage ({buckets.length} Buckets)</Typography>
      <TableContainer sx={{ mt: 2 }}>
        <Table size="small">
          <TableHead><TableRow><TableCell sx={{ color: theme.text }}>Bucket</TableCell><TableCell sx={{ color: theme.text }}>Size</TableCell><TableCell sx={{ color: theme.text }}>Objects</TableCell></TableRow></TableHead>
          <TableBody>
            {buckets.map((b) => (
              <TableRow key={b.name}><TableCell sx={{ color: theme.text }}>{b.name}</TableCell><TableCell sx={{ color: theme.text }}>{b.size_mb?.toFixed(2)} MB</TableCell><TableCell sx={{ color: theme.text }}>{b.objects}</TableCell></TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>
    </Paper>
  );
}

function BackupManager({ theme }: { theme: ThemeColors }) {
  const [settings, setSettings] = useState<any[]>([]);
  const [backups, setBackups] = useState<any[]>([]);
  const [editItem, setEditItem] = useState<any>(null);
  const [editForm, setEditForm] = useState({ backup_enabled: true, backup_frequency: 'daily', backup_retention_days: 30, backup_storage_class: 'standard', max_storage_mb: 5120, include_recordings: true });
  const [saving, setSaving] = useState(false);

  const load = async () => {
    try { const r = await api.get('/admin/backup-settings'); setSettings(r.data || []); } catch { /* ignore */ }
    try { const r = await api.get('/admin/management/storage/backup/list'); setBackups(r.data?.backups || []); } catch { /* ignore */ }
  };

  useEffect(() => { load(); const i = setInterval(load, 30000); return () => clearInterval(i); }, []);

  const openEdit = (s: any) => {
    setEditItem(s);
    setEditForm({
      backup_enabled: s.backup_enabled,
      backup_frequency: s.backup_frequency || 'daily',
      backup_retention_days: s.backup_retention_days || 30,
      backup_storage_class: s.backup_storage_class || 'standard',
      max_storage_mb: s.max_storage_mb || 5120,
      include_recordings: s.include_recordings ?? true,
    });
  };

  const save = async () => {
    if (!editItem) return;
    setSaving(true);
    try {
      await api.put(`/admin/backup-settings/${editItem.client_id}`, editForm);
      setEditItem(null);
      await load();
    } catch { /* ignore */ }
    setSaving(false);
  };

  return (
    <Paper sx={{ p: 3, bgcolor: theme.card, border: `1px solid ${theme.border}` }}>
      <Typography variant="h6"><StorageIcon sx={{ verticalAlign: 'middle', mr: 1 }} />Backup Management</Typography>

      {/* Backup Settings per Client */}
      <Typography variant="subtitle1" sx={{ mt: 2, mb: 1, color: theme.text }}>Client Backup Settings</Typography>
      <TableContainer>
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell sx={{ color: theme.text }}>Client ID</TableCell>
              <TableCell sx={{ color: theme.text }}>Enabled</TableCell>
              <TableCell sx={{ color: theme.text }}>Frequency</TableCell>
              <TableCell sx={{ color: theme.text }}>Retention</TableCell>
              <TableCell sx={{ color: theme.text }}>Storage Class</TableCell>
              <TableCell sx={{ color: theme.text }}>Max Storage</TableCell>
              <TableCell sx={{ color: theme.text }}>Actions</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {settings.map((s: any) => (
              <TableRow key={s.id}>
                <TableCell sx={{ color: theme.text }}>{s.client_id?.slice(0, 8)}...</TableCell>
                <TableCell sx={{ color: theme.text }}>{s.backup_enabled ? '✅' : '❌'}</TableCell>
                <TableCell sx={{ color: theme.text }}>{s.backup_frequency}</TableCell>
                <TableCell sx={{ color: theme.text }}>{s.backup_retention_days}d</TableCell>
                <TableCell sx={{ color: theme.text }}>{s.backup_storage_class}</TableCell>
                <TableCell sx={{ color: theme.text }}>{s.max_storage_mb ? `${s.max_storage_mb / 1024}GB` : '-'}</TableCell>
                <TableCell>
                  <Button size="small" variant="outlined" onClick={() => openEdit(s)} sx={{ color: theme.accent, borderColor: theme.accent }}>Edit</Button>
                </TableCell>
              </TableRow>
            ))}
            {settings.length === 0 && (
              <TableRow><TableCell sx={{ color: theme.text }} colSpan={7}>No backup settings configured</TableCell></TableRow>
            )}
          </TableBody>
        </Table>
      </TableContainer>

      {/* Backup Jobs */}
      <Typography variant="subtitle1" sx={{ mt: 3, mb: 1, color: theme.text }}>Backup Jobs</Typography>
      <TableContainer>
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell sx={{ color: theme.text }}>Type</TableCell>
              <TableCell sx={{ color: theme.text }}>Name</TableCell>
              <TableCell sx={{ color: theme.text }}>Status</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {backups.map((b: any, i: number) => (
              <TableRow key={i}>
                <TableCell sx={{ color: theme.text }}>{b.type}</TableCell>
                <TableCell sx={{ color: theme.text }}>{b.name}</TableCell>
                <TableCell sx={{ color: theme.text }}>{b.phase || b.schedule || '-'}</TableCell>
              </TableRow>
            ))}
            {backups.length === 0 && (
              <TableRow><TableCell sx={{ color: theme.text }} colSpan={3}>No backup jobs found</TableCell></TableRow>
            )}
          </TableBody>
        </Table>
      </TableContainer>

      {/* Edit Dialog */}
      <Dialog open={!!editItem} onClose={() => setEditItem(null)} maxWidth="sm" fullWidth PaperProps={{ sx: { bgcolor: theme.card, color: theme.text } }}>
        <DialogTitle>Edit Backup Settings — {editItem?.client_id?.slice(0, 8)}...</DialogTitle>
        <DialogContent>
          <Stack spacing={2} sx={{ mt: 1 }}>
            <Stack direction="row" spacing={2} alignItems="center">
              <Typography>Enabled:</Typography>
              <Button size="small" variant={editForm.backup_enabled ? 'contained' : 'outlined'} onClick={() => setEditForm({ ...editForm, backup_enabled: !editForm.backup_enabled })} sx={{ bgcolor: editForm.backup_enabled ? theme.accent : 'transparent', color: editForm.backup_enabled ? '#fff' : theme.text, borderColor: theme.accent }}>
                {editForm.backup_enabled ? 'YES' : 'NO'}
              </Button>
            </Stack>
            <Stack direction="row" spacing={2} alignItems="center">
              <Typography>Frequency:</Typography>
              <Button size="small" variant={editForm.backup_frequency === 'none' ? 'contained' : 'outlined'} onClick={() => setEditForm({ ...editForm, backup_frequency: 'none' })} sx={{ bgcolor: editForm.backup_frequency === 'none' ? theme.accent : 'transparent', color: editForm.backup_frequency === 'none' ? '#fff' : theme.text, borderColor: theme.accent }}>None</Button>
              <Button size="small" variant={editForm.backup_frequency === 'daily' ? 'contained' : 'outlined'} onClick={() => setEditForm({ ...editForm, backup_frequency: 'daily' })} sx={{ bgcolor: editForm.backup_frequency === 'daily' ? theme.accent : 'transparent', color: editForm.backup_frequency === 'daily' ? '#fff' : theme.text, borderColor: theme.accent }}>Daily</Button>
              <Button size="small" variant={editForm.backup_frequency === 'weekly' ? 'contained' : 'outlined'} onClick={() => setEditForm({ ...editForm, backup_frequency: 'weekly' })} sx={{ bgcolor: editForm.backup_frequency === 'weekly' ? theme.accent : 'transparent', color: editForm.backup_frequency === 'weekly' ? '#fff' : theme.text, borderColor: theme.accent }}>Weekly</Button>
              <Button size="small" variant={editForm.backup_frequency === 'monthly' ? 'contained' : 'outlined'} onClick={() => setEditForm({ ...editForm, backup_frequency: 'monthly' })} sx={{ bgcolor: editForm.backup_frequency === 'monthly' ? theme.accent : 'transparent', color: editForm.backup_frequency === 'monthly' ? '#fff' : theme.text, borderColor: theme.accent }}>Monthly</Button>
            </Stack>
            <Stack direction="row" spacing={2} alignItems="center">
              <Typography>Retention (days):</Typography>
              <Button size="small" variant={editForm.backup_retention_days === 7 ? 'contained' : 'outlined'} onClick={() => setEditForm({ ...editForm, backup_retention_days: 7 })} sx={{ color: theme.text, borderColor: theme.accent }}>7d</Button>
              <Button size="small" variant={editForm.backup_retention_days === 30 ? 'contained' : 'outlined'} onClick={() => setEditForm({ ...editForm, backup_retention_days: 30 })} sx={{ color: theme.text, borderColor: theme.accent }}>30d</Button>
              <Button size="small" variant={editForm.backup_retention_days === 60 ? 'contained' : 'outlined'} onClick={() => setEditForm({ ...editForm, backup_retention_days: 60 })} sx={{ color: theme.text, borderColor: theme.accent }}>60d</Button>
              <Button size="small" variant={editForm.backup_retention_days === 90 ? 'contained' : 'outlined'} onClick={() => setEditForm({ ...editForm, backup_retention_days: 90 })} sx={{ color: theme.text, borderColor: theme.accent }}>90d</Button>
            </Stack>
            <Stack direction="row" spacing={2} alignItems="center">
              <Typography>Storage Class:</Typography>
              <Button size="small" variant={editForm.backup_storage_class === 'standard' ? 'contained' : 'outlined'} onClick={() => setEditForm({ ...editForm, backup_storage_class: 'standard' })} sx={{ color: theme.text, borderColor: theme.accent }}>Standard</Button>
              <Button size="small" variant={editForm.backup_storage_class === 'cold' ? 'contained' : 'outlined'} onClick={() => setEditForm({ ...editForm, backup_storage_class: 'cold' })} sx={{ color: theme.text, borderColor: theme.accent }}>Cold</Button>
              <Button size="small" variant={editForm.backup_storage_class === 'archive' ? 'contained' : 'outlined'} onClick={() => setEditForm({ ...editForm, backup_storage_class: 'archive' })} sx={{ color: theme.text, borderColor: theme.accent }}>Archive</Button>
            </Stack>
            <Stack direction="row" spacing={2} alignItems="center">
              <Typography>Max Storage (MB):</Typography>
              <Button size="small" variant={editForm.max_storage_mb === 1024 ? 'contained' : 'outlined'} onClick={() => setEditForm({ ...editForm, max_storage_mb: 1024 })} sx={{ color: theme.text, borderColor: theme.accent }}>1GB</Button>
              <Button size="small" variant={editForm.max_storage_mb === 5120 ? 'contained' : 'outlined'} onClick={() => setEditForm({ ...editForm, max_storage_mb: 5120 })} sx={{ color: theme.text, borderColor: theme.accent }}>5GB</Button>
              <Button size="small" variant={editForm.max_storage_mb === 10240 ? 'contained' : 'outlined'} onClick={() => setEditForm({ ...editForm, max_storage_mb: 10240 })} sx={{ color: theme.text, borderColor: theme.accent }}>10GB</Button>
              <Button size="small" variant={editForm.max_storage_mb === 20480 ? 'contained' : 'outlined'} onClick={() => setEditForm({ ...editForm, max_storage_mb: 20480 })} sx={{ color: theme.text, borderColor: theme.accent }}>20GB</Button>
            </Stack>
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setEditItem(null)} sx={{ color: theme.text }}>Cancel</Button>
          <Button onClick={save} disabled={saving} variant="contained" sx={{ bgcolor: theme.accent }}>{saving ? 'Saving...' : 'Save'}</Button>
        </DialogActions>
      </Dialog>
    </Paper>
  );
}

export default TechnikDashboard;
