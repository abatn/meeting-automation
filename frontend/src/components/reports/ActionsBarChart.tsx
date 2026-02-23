import React from 'react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import { useTranslation } from 'react-i18next';
import { useTheme } from '@mui/material';

interface Props {
  data: {
    completed: number;
    pending: number;
    overdue: number;
  };
}

const ActionsBarChart: React.FC<Props> = ({ data }) => {
  const { t } = useTranslation();
  const theme = useTheme();

  const chartData = [
    {
      name: t('Actions'),
      completed: data.completed,
      pending: data.pending,
      overdue: data.overdue,
    }
  ];

  return (
    <ResponsiveContainer width="100%" height={300}>
      <BarChart
        data={chartData}
        margin={{
          top: 20,
          right: 30,
          left: 20,
          bottom: 5,
        }}
      >
        <CartesianGrid strokeDasharray="3 3" />
        <XAxis dataKey="name" />
        <YAxis />
        <Tooltip />
        <Legend />
        <Bar dataKey="completed" stackId="a" fill="#4caf50" name={t('Completed')} />
        <Bar dataKey="pending" stackId="a" fill="#ff9800" name={t('Pending')} />
        <Bar dataKey="overdue" stackId="a" fill="#f44336" name={t('Overdue')} />
      </BarChart>
    </ResponsiveContainer>
  );
};

export default ActionsBarChart;
