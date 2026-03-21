import React from 'react';
import { Box, Typography, LinearProgress, Paper } from '@mui/material';

interface UsageProgressBarProps {
  used: number;
  total: number;
  label?: string;
  unit?: string;
}

const UsageProgressBar: React.FC<UsageProgressBarProps> = ({ used, total, label = "Minutes Usage", unit = "min" }) => {
  const percentage = Math.min(Math.round((used / total) * 100), 100);
  const color = percentage > 90 ? 'error' : percentage > 75 ? 'warning' : 'primary';

  return (
    <Paper sx={{ p: 2, mb: 2 }}>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
        <Typography variant="subtitle2" color="text.secondary">{label}</Typography>
        <Typography variant="subtitle2" fontWeight="bold">
          {used} / {total} {unit} ({percentage}%)
        </Typography>
      </Box>
      <LinearProgress 
        variant="determinate" 
        value={percentage} 
        color={color}
        sx={{ height: 10, borderRadius: 5 }}
      />
    </Paper>
  );
};

export default UsageProgressBar;