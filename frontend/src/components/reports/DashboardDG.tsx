import React from 'react';
import { 
  Grid, 
  Paper, 
  Typography, 
  Box, 
  Button, 
  Card, 
  CardContent, 
  Divider,
  List,
  ListItem,
  ListItemText,
  ListItemSecondaryAction,
  IconButton
} from '@mui/material';
import { 
  BarChart, 
  Bar, 
  XAxis, 
  YAxis, 
  CartesianGrid, 
  Tooltip, 
  Legend, 
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
  LineChart,
  Line
} from 'recharts';
import { 
  Download as DownloadIcon, 
  TrendingUp, 
  Assignment, 
  CheckCircle,
  Warning
} from '@mui/icons-material';
import { useTranslation } from 'react-i18next';

// Mock data for charts
const meetingTrends = [
  { name: 'Sep', count: 12 },
  { name: 'Oct', count: 15 },
  { name: 'Nov', count: 10 },
  { name: 'Dec', count: 18 },
  { name: 'Jan', count: 14 },
  { name: 'Feb', count: 20 },
];

const actionStatus = [
  { name: 'Completed', value: 45, color: '#4caf50' },
  { name: 'In Progress', value: 30, color: '#2196f3' },
  { name: 'Overdue', value: 25, color: '#f44336' },
];

const deptPerformance = [
  { name: 'Sales', rate: 85 },
  { name: 'IT', rate: 92 },
  { name: 'HR', rate: 78 },
  { name: 'Finance', rate: 88 },
];

const overdueResponsible = [
  { id: 1, name: 'Sami Ben Ali', count: 5, dept: 'Sales' },
  { id: 2, name: 'Amel Trabelsi', count: 3, dept: 'HR' },
  { id: 3, name: 'Mohamed Mahmoud', count: 3, dept: 'IT' },
  { id: 4, name: 'Leila Ghariani', count: 2, dept: 'Finance' },
  { id: 5, name: 'Youssef Mansour', count: 2, dept: 'Logistics' },
];

const DashboardDG: React.FC = () => {
  const { t } = useTranslation();

  return (
    <Box sx={{ flexGrow: 1, p: 3 }}>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 3, alignItems: 'center' }}>
        <Typography variant="h4">{t('dashboard.dg_title', 'General Manager Dashboard')}</Typography>
        <Button 
          variant="contained" 
          startIcon={<DownloadIcon />}
          color="primary"
        >
          {t('common.export', 'Export Report')}
        </Button>
      </Box>

      {/* KPI Cards */}
      <Grid container spacing={3} sx={{ mb: 3 }}>
        {[
          { title: 'Meetings/Month', value: '20', icon: <TrendingUp color="primary" />, trend: '+15%' },
          { title: 'Action Completion Rate', value: '72%', icon: <CheckCircle color="success" />, trend: '-2%' },
          { title: 'Pending PV Approvals', value: '4', icon: <Assignment color="warning" />, trend: 'Urgent' },
        ].map((kpi, idx) => (
          <Grid item xs={12} md={4} key={idx}>
            <Paper sx={{ p: 2, display: 'flex', alignItems: 'center', height: '100%' }}>
              <Box sx={{ mr: 2 }}>{kpi.icon}</Box>
              <Box>
                <Typography color="textSecondary" variant="subtitle2">{t(`dashboard.${kpi.title}`, kpi.title)}</Typography>
                <Typography variant="h4">{kpi.value}</Typography>
                <Typography variant="caption" color={kpi.trend.startsWith('+') ? 'success.main' : 'error.main'}>
                  {kpi.trend}
                </Typography>
              </Box>
            </Paper>
          </Grid>
        ))}
      </Grid>

      <Grid container spacing={3}>
        {/* Meeting Trends Chart */}
        <Grid item xs={12} md={8}>
          <Paper sx={{ p: 2 }}>
            <Typography variant="h6" gutterBottom>{t('dashboard.meeting_trends', 'Meeting Trends')}</Typography>
            <ResponsiveContainer width="100%" height={300}>
              <LineChart data={meetingTrends}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="name" />
                <YAxis />
                <Tooltip />
                <Legend />
                <Line type="monotone" dataKey="count" stroke="#E70013" strokeWidth={2} activeDot={{ r: 8 }} />
              </LineChart>
            </ResponsiveContainer>
          </Paper>
        </Grid>

        {/* Action Status Chart */}
        <Grid item xs={12} md={4}>
          <Paper sx={{ p: 2 }}>
            <Typography variant="h6" gutterBottom>{t('dashboard.action_status', 'Action Status')}</Typography>
            <ResponsiveContainer width="100%" height={300}>
              <PieChart>
                <Pie
                  data={actionStatus}
                  cx="50%"
                  cy="50%"
                  innerRadius={60}
                  outerRadius={80}
                  paddingAngle={5}
                  dataKey="value"
                >
                  {actionStatus.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={entry.color} />
                  ))}
                </Pie>
                <Tooltip />
                <Legend />
              </PieChart>
            </ResponsiveContainer>
          </Paper>
        </Grid>

        {/* Department Performance */}
        <Grid item xs={12} md={6}>
          <Paper sx={{ p: 2 }}>
            <Typography variant="h6" gutterBottom>{t('dashboard.dept_performance', 'Department Performance (%)')}</Typography>
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={deptPerformance}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="name" />
                <YAxis />
                <Tooltip />
                <Bar dataKey="rate" fill="#003A6B" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </Paper>
        </Grid>

        {/* Overdue Responsible List */}
        <Grid item xs={12} md={6}>
          <Paper sx={{ p: 2 }}>
            <Typography variant="h6" gutterBottom>{t('dashboard.top_overdue', 'Top Overdue Responsible')}</Typography>
            <List>
              {overdueResponsible.map((person, idx) => (
                <React.Fragment key={person.id}>
                  <ListItem alignItems="flex-start">
                    <ListItemText
                      primary={person.name}
                      secondary={`${person.dept} — ${person.count} ${t('dashboard.actions_pending', 'actions overdue')}`}
                    />
                    <ListItemSecondaryAction>
                      <Button 
                        size="small" 
                        variant="outlined" 
                        color="error" 
                        startIcon={<Warning />}
                        sx={{ fontSize: '0.75rem' }}
                      >
                        {t('dashboard.escalate', 'Escalate')}
                      </Button>
                    </ListItemSecondaryAction>
                  </ListItem>
                  {idx < overdueResponsible.length - 1 && <Divider component="li" />}
                </React.Fragment>
              ))}
            </List>
          </Paper>
        </Grid>
      </Grid>
    </Box>
  );
};

export default DashboardDG;