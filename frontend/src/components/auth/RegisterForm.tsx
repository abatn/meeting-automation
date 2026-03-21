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
import { AppDispatch } from '../../store';
import { setCredentials } from '../../store/authSlice';
import authService from '../../services/auth';

const RegisterForm: React.FC = () => {
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
    setLoading(true);

    try {
      // 1. Register User & Client
      await authService.register({
        email: formData.email,
        password: formData.password,
        full_name: formData.full_name,
        client_id: undefined, // Backend will create a new one based on company_name
      });

      // 2. Auto-login
      const loginData = await authService.login(formData.email, formData.password);
      dispatch(setCredentials(loginData));
      
      // 3. Redirect to dashboard
      navigate('/');
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Une erreur est survenue lors de l\'inscription.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <Box sx={{ 
      minHeight: '100vh', 
      display: 'flex', 
      alignItems: 'center', 
      bgcolor: '#F8FAFC',
      py: 8
    }}>
      <Container maxWidth="sm">
        <Paper elevation={0} sx={{ p: { xs: 3, md: 6 }, borderRadius: 4, border: '1px solid #E5EAF2' }}>
          <Box sx={{ textAlign: 'center', mb: 4 }}>
            <Typography variant="h4" fontWeight="800" gutterBottom>Créer votre compte</Typography>
            <Typography variant="body2" color="text.secondary">
              Commencez à automatiser vos réunions dès aujourd'hui.
            </Typography>
          </Box>

          {error && <Alert severity="error" sx={{ mb: 3 }}>{error}</Alert>}

          <form onSubmit={handleSubmit}>
            <Stack spacing={2.5}>
              <TextField
                label="Nom complet"
                name="full_name"
                required
                fullWidth
                value={formData.full_name}
                onChange={handleChange}
                InputProps={{
                  startAdornment: (
                    <InputAdornment position="start">
                      <PersonIcon color="action" />
                    </InputAdornment>
                  ),
                }}
              />

              <TextField
                label="Nom de l'entreprise"
                name="company_name"
                required
                fullWidth
                value={formData.company_name}
                onChange={handleChange}
                placeholder="Ex: Ma Société SAS"
                InputProps={{
                  startAdornment: (
                    <InputAdornment position="start">
                      <BusinessIcon color="action" />
                    </InputAdornment>
                  ),
                }}
              />

              <TextField
                label="Adresse Email"
                name="email"
                type="email"
                required
                fullWidth
                value={formData.email}
                onChange={handleChange}
                InputProps={{
                  startAdornment: (
                    <InputAdornment position="start">
                      <EmailIcon color="action" />
                    </InputAdornment>
                  ),
                }}
              />

              <TextField
                label="Mot de passe"
                name="password"
                type={showPassword ? 'text' : 'password'}
                required
                fullWidth
                value={formData.password}
                onChange={handleChange}
                InputProps={{
                  startAdornment: (
                    <InputAdornment position="start">
                      <LockIcon color="action" />
                    </InputAdornment>
                  ),
                  endAdornment: (
                    <InputAdornment position="end">
                      <IconButton onClick={() => setShowPassword(!showPassword)} edge="end">
                        {showPassword ? <VisibilityOff /> : <Visibility />}
                      </IconButton>
                    </InputAdornment>
                  ),
                }}
              />

              <TextField
                select
                label="Forfait choisi"
                name="plan"
                fullWidth
                value={formData.plan}
                onChange={handleChange}
              >
                <MenuItem value="GRATUIT">Gratuit (10 réunions/mois)</MenuItem>
                <MenuItem value="PRO">Pro (99$/mois - Illimité)</MenuItem>
                <MenuItem value="ENTREPRISE">Entreprise (499$/mois - Support dédié)</MenuItem>
              </TextField>

              <Button
                type="submit"
                variant="contained"
                fullWidth
                size="large"
                disabled={loading}
                sx={{ 
                  py: 1.5, 
                  borderRadius: 2, 
                  fontWeight: 700, 
                  textTransform: 'none',
                  fontSize: '1rem',
                  mt: 2
                }}
              >
                {loading ? <CircularProgress size={24} color="inherit" /> : 'Créer mon compte'}
              </Button>

              <Box sx={{ textAlign: 'center', mt: 2 }}>
                <Typography variant="body2" color="text.secondary">
                  Vous avez déjà ein compte ?{' '}
                  <Link 
                    component="button" 
                    type="button"
                    variant="body2" 
                    fontWeight="700" 
                    onClick={() => navigate('/login')}
                  >
                    Se connecter
                  </Link>
                </Typography>
              </Box>
            </Stack>
          </form>
        </Paper>
        
        <Typography variant="caption" display="block" textAlign="center" sx={{ mt: 4, color: 'text.secondary' }}>
          En vous inscrivant, vous acceptez nos Conditions d'Utilisation et notre Politique de Confidentialité.
          Conforme RGPD & ISO 27001.
        </Typography>
      </Container>
    </Box>
  );
};

export default RegisterForm;