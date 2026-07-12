import React, { useState, useEffect } from 'react';
import { 
  Box, 
  Container, 
  Typography, 
  TextField, 
  Button, 
  Paper, 
  Stack, 
  Link,
  Alert,
  CircularProgress,
  MenuItem,
  InputAdornment,
  IconButton
} from '@mui/material';
import { 
  Visibility, 
  VisibilityOff, 
  Business as BusinessIcon,
  Email as EmailIcon,
  Person as PersonIcon,
  Lock as LockIcon
} from '@mui/icons-material';
import { useNavigate, useLocation } from 'react-router-dom';
import { useDispatch } from 'react-redux';
import { useTranslation } from 'react-i18next';
import { AppDispatch } from '../../store';
import { setCredentials } from '../../store/authSlice';
import authService from '../../services/auth';
import PasswordStrengthIndicator from '../../components/common/PasswordStrengthIndicator';
import ConsentDialog from '../consent/ConsentDialog';

const RegisterForm: React.FC = () => {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const location = useLocation();
  const dispatch = useDispatch<AppDispatch>();
  
  const [formData, setFormData] = useState({
    email: '',
    password: '',
    full_name: '',
    company_name: '',
    plan: 'GRATUIT'
  });
  
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [consentOpen, setConsentOpen] = useState(false);
  const [consents, setConsents] = useState<{consent_type: string; consented: boolean; consent_version: string}[]>([]);

  useEffect(() => {
    const params = new URLSearchParams(location.search);
    const planParam = params.get('plan');
    if (planParam && ['GRATUIT', 'PRO', 'ENTREPRISE'].includes(planParam.toUpperCase())) {
      setFormData(prev => ({ ...prev, plan: planParam.toUpperCase() }));
    }
  }, [location]);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setFormData({ ...formData, [e.target.name]: e.target.value });
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setConsentOpen(true);
  };

  const handleConsentConfirm = async (consentData: {consent_type: string; consented: boolean; consent_version: string}[]) => {
    setConsents(consentData);
    setConsentOpen(false);
    setLoading(true);

    try {
      await authService.register({
        email: formData.email,
        password: formData.password,
        full_name: formData.full_name,
        company_name: formData.company_name,
        plan: formData.plan,
        consents: consentData
      });

      navigate('/check-email', { state: { email: formData.email } });
    } catch (err: any) {
      setError(err.response?.data?.detail || t('auth.register.error'));
    } finally {
      setLoading(false);
    }
  };

  return (
    <Box sx={{ minHeight: '100vh', display: 'flex', alignItems: 'center', bgcolor: '#F8FAFC', py: 2 }}>
      <Container maxWidth="xs">
        <Paper elevation={0} sx={{ p: 3, borderRadius: 2, border: '1px solid #E5EAF2' }}>
          <Box sx={{ textAlign: 'center', mb: 2 }}>
            <Typography variant="h5" fontWeight="800">{t('auth.register.title')}</Typography>
            <Typography variant="caption" color="text.secondary">{t('auth.register.subtitle')}</Typography>
          </Box>

          {error && <Alert severity="error" sx={{ mb: 2, py: 0 }}>{error}</Alert>}

          <form onSubmit={handleSubmit}>
            <Stack spacing={1.5}>
              <TextField
                label={t('team.full_name')}
                name="full_name"
                required
                fullWidth
                size="small"
                value={formData.full_name}
                onChange={handleChange}
                InputProps={{ startAdornment: (<InputAdornment position="start"><PersonIcon fontSize="small" color="action" /></InputAdornment>) }}
              />

              <TextField
                label={t('auth.register.company_name')}
                name="company_name"
                required
                fullWidth
                size="small"
                value={formData.company_name}
                onChange={handleChange}
                InputProps={{ startAdornment: (<InputAdornment position="start"><BusinessIcon fontSize="small" color="action" /></InputAdornment>) }}
              />

              <TextField
                label={t('auth.email')}
                name="email"
                type="email"
                required
                fullWidth
                size="small"
                value={formData.email}
                onChange={handleChange}
                InputProps={{ startAdornment: (<InputAdornment position="start"><EmailIcon fontSize="small" color="action" /></InputAdornment>) }}
              />

               <TextField
                  label={t('auth.password')}
                 name="password"
                 type={showPassword ? 'text' : 'password'}
                 required
                 fullWidth
                 size="small"
                 value={formData.password}
                 onChange={handleChange}
                 InputProps={{
                   startAdornment: (<InputAdornment position="start"><LockIcon fontSize="small" color="action" /></InputAdornment>),
                   endAdornment: (
                     <InputAdornment position="end">
                       <IconButton size="small" onClick={() => setShowPassword(!showPassword)} edge="end">
                         {showPassword ? <VisibilityOff fontSize="small" /> : <Visibility fontSize="small" />}
                       </IconButton>
                     </InputAdornment>
                   ),
                 }}
               />
               <PasswordStrengthIndicator password={formData.password} />

              <TextField
                select
                label={t('auth.register.plan')}
                name="plan"
                fullWidth
                size="small"
                value={formData.plan}
                onChange={handleChange}
              >
                <MenuItem value="GRATUIT">{t('auth.register.plan_free')}</MenuItem>
                <MenuItem value="PRO">{t('auth.register.plan_pro')}</MenuItem>
                <MenuItem value="ENTREPRISE">{t('auth.register.plan_enterprise')}</MenuItem>
              </TextField>

              <Button
                type="submit"
                variant="contained"
                fullWidth
                disabled={loading}
                sx={{ py: 1, borderRadius: 1.5, fontWeight: 700, textTransform: 'none', mt: 1 }}
              >
                {loading ? <CircularProgress size={20} color="inherit" /> : t('auth.register.submit')}
              </Button>

              <Box sx={{ textAlign: 'center' }}>
                <Typography variant="caption" color="text.secondary">
                  {t('auth.register.has_account')} <Link component="button" type="button" variant="caption" fontWeight="700" onClick={() => navigate('/login')}>{t('auth.signIn')}</Link>
                </Typography>
              </Box>
            </Stack>
          </form>
        </Paper>
      </Container>
      <ConsentDialog
        open={consentOpen}
        onClose={() => setConsentOpen(false)}
        onConfirm={handleConsentConfirm}
      />
    </Box>
  );
};

export default RegisterForm;