import React from 'react';
import { Grid, Paper, Typography } from '@mui/material';
import { PieChart, Pie, Cell, ResponsiveContainer, Legend } from 'recharts';
import { useTranslation } from 'react-i18next';

// TODO: Replace with real data
const data = [
  { name: 'Completed', value: 400 },
  { name: 'In Progress', value: 300 },
  { name: 'Pending', value: 300 },
];
const COLORS = ['#0088FE', '#00C49F', '#FFBB28'];

const DashboardManager: React.FC = () => {
  const { t } = useTranslation();

  return (
    <Grid container spacing={3}>
      <Grid item xs={12} md={6}>
        <Paper sx={{ p: 2, display: 'flex', flexDirection: 'column', height: 240 }}>
          <Typography component="h2" variant="h6" color="primary" gutterBottom>
            {t('actionStatus')}
          </Typography>
          <ResponsiveContainer>
            <PieChart>
              <Pie
                data={data}
                cx="50%"
                cy="50%"
                labelLine={false}
                outerRadius={80}
                fill="#8884d8"
                dataKey="value"
              >
                {data.map((entry, index) => (
                  <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                ))}
              </Pie>
              <Legend />
            </PieChart>
          </ResponsiveContainer>
        </Paper>
      </Grid>
    </Grid>
  );
};

export default DashboardManager;