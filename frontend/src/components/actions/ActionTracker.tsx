import React from 'react';
import { Box, Typography, List } from '@mui/material';
import { useTranslation } from 'react-i18next';
import ActionCard from './ActionCard'; // Assuming ActionCard is in the same directory

interface Action {
  id: number;
  description: string;
  assignee: string;
  dueDate: string;
  status: 'pending' | 'in_progress' | 'completed';
}

interface ActionTrackerProps {
  actions: Action[];
}

const ActionTracker: React.FC<ActionTrackerProps> = ({ actions }) => {
  const { t } = useTranslation();

  return (
    <Box>
      <Typography variant="h6">{t('actionItems')}</Typography>
      <List>
        {actions.map((action) => (
          <ActionCard key={action.id} action={action} />
        ))}
      </List>
    </Box>
  );
};

export default ActionTracker;