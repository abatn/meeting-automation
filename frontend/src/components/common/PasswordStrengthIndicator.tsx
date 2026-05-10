import React from 'react';
import { Box, Typography, LinearProgress, Stack } from '@mui/material';
import { validatePassword } from '../../utils/passwordValidation';

interface PasswordStrengthIndicatorProps {
  password: string;
  label?: string;
}

const PasswordStrengthIndicator: React.FC<PasswordStrengthIndicatorProps> = ({ 
  password, 
  label = 'Password Strength' 
}) => {
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
      case 'weak': return 'Weak';
      case 'medium': return 'Medium';
      case 'strong': return 'Strong';
      default: return 'Very Weak';
    }
  };
  
  return (
    <Box sx={{ mb: 2 }}>
      <Typography variant="caption" color="text.secondary" sx={{ mb: 1 }}>
        {label}
      </Typography>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
        <LinearProgress
          variant="determinate"
          value={validation.isValid ? 100 : Math.max(0, (3 - validation.errors.length) * 33)}
          sx={{ 
            width: 200, 
            height: 4, 
            borderRadius: 2,
            bgcolor: validation.isValid ? 'success.main' : 'grey.200'
          }}
        >
          {validation.isValid && (
            <Box 
              sx={{ 
                width: '100%', 
                height: '100%', 
                display: 'flex', 
                alignItems: 'center', 
                justifyContent: 'center',
                color: 'white',
                fontWeight: 600
              }}
            >
              {getStrengthText(validation.strength)}
            </Box>
          )}
        </LinearProgress>
        <Typography variant="body2" sx={{ minWidth: 80 }}>
          {validation.isValid ? getStrengthText(validation.strength) : 
            `${validation.errors.length} issues`}
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