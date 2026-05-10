import React, { useState } from 'react';
import {
  Box,
  Container,
  Typography,
  Paper,
  Button,
  Alert,
  CircularProgress,
  Link
} from '@mui/material';
import {
  Email as EmailIcon,
  ArrowBack as ArrowBackIcon,
  Refresh as RefreshIcon
} from '@mui/icons-material';
import { useNavigate, useLocation } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import authService from '../services/auth';

const CheckEmailPage: React.FC = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const { t } = useTranslation();
  
  const email = location.state?.email || '';
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  const handleResend = async () => {
    if (!email) {
      setError('No email provided');
      return;
    }

    setLoading(true);
    setError(null);
    setSuccess(false);

    try {
      await authService.resendActivation(email);
      setSuccess(true);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to resend activation email');
    } finally {
      setLoading(false);
    }
  };

  return (
    <Box sx={{ minHeight: '100vh', display: 'flex', alignItems: 'center', bgcolor: '#F8FAFC', py: 2 }}>
      <Container maxWidth="sm">
        <Paper elevation={0} sx={{ p: 4, borderRadius: 2, border: '1px solid #E5EAF2', textAlign: 'center' }}>
          <Box sx={{ mb: 3 }}>
            <EmailIcon sx={{ fontSize: 64, color: 'primary.main' }} />
          </Box>

          <Typography variant="h4" fontWeight={800} gutterBottom>
            {t('auth.check_email.title')}
          </Typography>

          <Typography variant="body1" color="text.secondary" sx={{ mb: 3 }}>
            {t('auth.check_email.message', { email })}
          </Typography>

          {error && (
            <Alert severity="error" sx={{ mb: 2 }}>
              {error}
            </Alert>
          )}

          {success && (
            <Alert severity="success" sx={{ mb: 2 }}>
              {t('auth.check_email.resend_success')}
            </Alert>
          )}

          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, mt: 3 }}>
            <Button
              variant="contained"
              fullWidth
              startIcon={loading ? <CircularProgress size={20} color="inherit" /> : <RefreshIcon />}
              onClick={handleResend}
              disabled={loading || !email}
              sx={{ py: 1.5, borderRadius: 1.5, fontWeight: 700, textTransform: 'none' }}
            >
              {loading ? t('auth.check_email.sending') : t('auth.check_email.resend')}
            </Button>

            <Button
              variant="text"
              startIcon={<ArrowBackIcon />}
              onClick={() => navigate('/login')}
              sx={{ textTransform: 'none' }}
            >
              {t('auth.check_email.back_to_login')}
            </Button>
          </Box>

          <Typography variant="caption" color="text.secondary" sx={{ mt: 3, display: 'block' }}>
            {t('auth.check_email.spam_notice')}
          </Typography>
        </Paper>
      </Container>
    </Box>
  );
};

export default CheckEmailPage;
