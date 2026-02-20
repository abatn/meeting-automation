import React from 'react';
import { Box, Typography, List, ListItem, ListItemText } from '@mui/material';
import { useTranslation } from 'react-i18next';

// TODO: Replace with real data
const myActions = [
  { id: 1, description: 'Prepare slides for presentation', status: 'in_progress' },
  { id: 2, description: 'Review project proposal', status: 'pending' },
];

const DashboardParticipant: React.FC = () => {
  const { t } = useTranslation();

  return (
    <Box>
      <Typography variant="h6">{t('myOpenActions')}</Typography>
      <List>
        {myActions.map((action) => (
          <ListItem key={action.id}>
            <ListItemText primary={action.description} secondary={action.status} />
          </ListItem>
        ))}
      </List>
    </Box>
  );
};

export default DashboardParticipant;