import React from 'react';
import { PieChart, Pie, Cell, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import { useTranslation } from 'react-i18next';
import { useTheme } from '@mui/material';

interface Props {
  data: {
    completed: number;
    scheduled: number;
    cancelled: number;
  };
}

const COLORS = ['#4caf50', '#2196f3', '#f44336'];

const MeetingsPieChart: React.FC<Props> = ({ data }) => {
  const { t } = useTranslation();
  const theme = useTheme();

  const chartData = [
    { name: t('Completed'), value: data.completed },
    { name: t('Scheduled'), value: data.scheduled },
    { name: t('Cancelled'), value: data.cancelled },
  ];

  return (
    <ResponsiveContainer width="100%" height={300}>
      <PieChart>
        <Pie
          data={chartData}
          cx="50%"
          cy="50%"
          labelLine={false}
          label={({ name, percent }) => `${name}: ${(percent * 100).toFixed(0)}%`}
          outerRadius={100}
          fill="#8884d8"
          dataKey="value"
        >
          {chartData.map((entry, index) => (
            <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
          ))}
        </Pie>
        <Tooltip />
        <Legend />
      </PieChart>
    </ResponsiveContainer>
  );
};

export default MeetingsPieChart;
