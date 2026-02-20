import React from 'react';
import { Grid, Paper, Typography } from '@mui/material';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import { useTranslation } from 'react-i18next';

// TODO: Replace with real data
const data = [
  { name: 'Jan', meetings: 40, actions: 24 },
  { name: 'Feb', meetings: 30, actions: 13 },
  // ...
];

const DashboardDG: React.FC = () => {
  const { t } = useTranslation();

  return (
    <Grid container spacing={3}>
      <Grid item xs={12}>
        <Paper sx={{ p: 2, display: 'flex', flexDirection: 'column', height: 240 }}>
          <Typography component="h2" variant="h6" color="primary" gutterBottom>
            {t('monthlyActivity')}
          </Typography>
          <ResponsiveContainer>
            <BarChart data={data}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="name" />
              <YAxis />
              <Tooltip />
              <Legend />
              <Bar dataKey="meetings" fill="#8884d8" />
              <Bar dataKey="actions" fill="#82ca9d" />
            </BarChart>
          </ResponsiveContainer>
        </Paper>
      </Grid>
    </Grid>
  );
};

export default DashboardDG;