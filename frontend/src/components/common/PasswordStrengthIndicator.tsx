import React from 'react';
import { Box, Typography, LinearProgress, Stack } from '@mui/material';
import { useTranslation } from 'react-i18next';
import { validatePassword } from '../../utils/passwordValidation';

interface PasswordStrengthIndicatorProps {
  password: string;
  label?: string;
}

const PasswordStrengthIndicator: React.FC<PasswordStrengthIndicatorProps> = ({ 
  password, 
  label 
}) => {
  const { t } = useTranslation();
  const effectiveLabel = label || t('common.password_strength');
  const validation = validatePassword(password);
  
  // Define colors based on strength
  const getColor = (strength: 'weak' | 'medium' | 'strong') => {
    switch (strength) {
      case 'weak': return 'error.main';
      case 'medium': return 'warning.main';
      case 'strong': return 'success.main';
      default: return 'grey.400';
    }
  };
  
  const getStrengthText = (strength: 'weak' | 'medium' | 'strong') => {
    switch (strength) {
      case 'weak': return t('common.password_weak');
      case 'medium': return t('common.password_medium');
      case 'strong': return t('common.password_strong');
      default: return t('common.password_very_weak');
    }
  };
  
  return (
    <Box sx={{ mb: 2 }}>
      <Typography variant="caption" color="text.secondary" sx={{ mb: 1 }}>
        {effectiveLabel}
      </Typography>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
        <Box sx={{ width: 200, position: 'relative' }}>
          <LinearProgress
            variant="determinate"
            value={validation.isValid ? 100 : Math.max(0, (3 - validation.errors.length) * 33)}
            sx={{ 
              height: 4, 
              borderRadius: 2,
              bgcolor: validation.isValid ? 'success.main' : 'grey.200'
            }}
          />
          {validation.isValid && (
            <Typography
              variant="caption"
              sx={{
                position: 'absolute',
                top: -2,
                left: 0,
                right: 0,
                textAlign: 'center',
                fontWeight: 600,
                color: 'white',
                fontSize: 10,
              }}
            >
              {getStrengthText(validation.strength)}
            </Typography>
          )}
        </Box>
        <Typography variant="body2" sx={{ minWidth: 80 }}>
          {validation.isValid ? getStrengthText(validation.strength) : 
            t('common.password_issues', { count: validation.errors.length })}
        </Typography>
      </Box>
      
      {!validation.isValid && (
        <Box sx={{ mt: 1 }}>
          <Typography variant="caption" color="error.main">
            {validation.errors.map((error, index) => (
              <Box key={index}>
                <span role="img" aria-label="error">•</span> {error}
              </Box>
            ))}
          </Typography>
        </Box>
      )}
    </Box>
  );
};

export default PasswordStrengthIndicator;