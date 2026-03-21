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
      await authService.register({
        email: formData.email,
        password: formData.password,
        full_name: formData.full_name,
        company_name: formData.company_name,
        plan: formData.plan
      });

      const loginData = await authService.login(formData.email, formData.password);
      dispatch(setCredentials(loginData));
      navigate('/');
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Une erreur est survenue lors de l\'inscription.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <Box sx={{ minHeight: '100vh', display: 'flex', alignItems: 'center', bgcolor: '#F8FAFC', py: 2 }}>
      <Container maxWidth="xs">
        <Paper elevation={0} sx={{ p: 3, borderRadius: 2, border: '1px solid #E5EAF2' }}>
          <Box sx={{ textAlign: 'center', mb: 2 }}>
            <Typography variant="h5" fontWeight="800">Créer votre compte</Typography>
            <Typography variant="caption" color="text.secondary">Commencez l'automatisation dès maintenant.</Typography>
          </Box>

          {error && <Alert severity="error" sx={{ mb: 2, py: 0 }}>{error}</Alert>}

          <form onSubmit={handleSubmit}>
            <Stack spacing={1.5}>
              <TextField
                label="Nom complet"
                name="full_name"
                required
                fullWidth
                size="small"
                value={formData.full_name}
                onChange={handleChange}
                InputProps={{ startAdornment: (<InputAdornment position="start"><PersonIcon fontSize="small" color="action" /></InputAdornment>) }}
              />

              <TextField
                label="Nom de l'entreprise"
                name="company_name"
                required
                fullWidth
                size="small"
                value={formData.company_name}
                onChange={handleChange}
                InputProps={{ startAdornment: (<InputAdornment position="start"><BusinessIcon fontSize="small" color="action" /></InputAdornment>) }}
              />

              <TextField
                label="Adresse Email"
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
                label="Mot de passe"
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

              <TextField
                select
                label="Plan"
                name="plan"
                fullWidth
                size="small"
                value={formData.plan}
                onChange={handleChange}
              >
                <MenuItem value="GRATUIT">Gratuit</MenuItem>
                <MenuItem value="PRO">Pro (99$/m)</MenuItem>
                <MenuItem value="ENTREPRISE">Entreprise (499$/m)</MenuItem>
              </TextField>

              <Button
                type="submit"
                variant="contained"
                fullWidth
                disabled={loading}
                sx={{ py: 1, borderRadius: 1.5, fontWeight: 700, textTransform: 'none', mt: 1 }}
              >
                {loading ? <CircularProgress size={20} color="inherit" /> : 'Créer mon compte'}
              </Button>

              <Box sx={{ textAlign: 'center' }}>
                <Typography variant="caption" color="text.secondary">
                  Déjà un compte ? <Link component="button" type="button" variant="caption" fontWeight="700" onClick={() => navigate('/login')}>Se connecter</Link>
                </Typography>
              </Box>
            </Stack>
          </form>
        </Paper>
      </Container>
    </Box>
  );
};

export default RegisterForm;