import React from 'react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import { useTranslation } from 'react-i18next';

interface TrendData {
  month: string;
  avg_duration_minutes: number;
  actions_per_meeting: number;
}

interface Props {
  data: TrendData[];
}

const EfficiencyLineChart: React.FC<Props> = ({ data }) => {
  const { t } = useTranslation();

  return (
    <ResponsiveContainer width="100%" height={300}>
      <LineChart
        data={data}
        margin={{
          top: 5,
          right: 30,
          left: 20,
          bottom: 5,
        }}
      >
        <CartesianGrid strokeDasharray="3 3" />
        <XAxis dataKey="month" />
        <YAxis yAxisId="left" />
        <YAxis yAxisId="right" orientation="right" />
        <Tooltip />
        <Legend />
        <Line yAxisId="left" type="monotone" dataKey="avg_duration_minutes" stroke="#8884d8" name={t('Avg Duration (min)')} activeDot={{ r: 8 }} />
        <Line yAxisId="right" type="monotone" dataKey="actions_per_meeting" stroke="#82ca9d" name={t('Actions per Meeting')} />
      </LineChart>
    </ResponsiveContainer>
  );
};

export default EfficiencyLineChart;
