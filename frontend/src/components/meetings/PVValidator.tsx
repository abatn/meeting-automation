import React from 'react';
import { Box, Typography, Button, Paper } from '@mui/material';
import { useTranslation } from 'react-i18next';

interface PVValidatorProps {
  pvContent: string;
}

const PVValidator: React.FC<PVValidatorProps> = ({ pvContent }) => {
  const { t } = useTranslation();

  const handleValidate = () => {
    // TODO: Handle PV validation
    console.log('PV Validated');
  };

  return (
    <Paper style={{ padding: 16 }}>
      <Typography variant="h6">{t('pvValidation')}</Typography>
      <Box my={2} p={2} border={1} borderColor="grey.300" borderRadius={1}>
        <pre>{pvContent}</pre>
      </Box>
      <Button variant="contained" color="primary" onClick={handleValidate}>
        {t('validatePV')}
      </Button>
    </Paper>
  );
};

export default PVValidator;