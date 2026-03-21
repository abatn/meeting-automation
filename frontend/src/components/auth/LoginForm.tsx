import React, { useState } from "react";
import {
  Box,
  Button,
  TextField,
  Typography,
  Paper,
  Container,
  Alert,
  CircularProgress,
  InputAdornment,
  IconButton,
  Link,
  Stack,
  Avatar
} from "@mui/material";
import { 
  Visibility, 
  VisibilityOff, 
  Email as EmailIcon, 
  Lock as LockIcon,
  AutoFixHigh as IAIcon
} from "@mui/icons-material";
import { useNavigate } from "react-router-dom";
import { useDispatch } from "react-redux";
import { setCredentials } from "../../store/authSlice";
import authService from "../../services/auth";
import { AppDispatch } from "../../store";

const LoginForm: React.FC = () => {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const navigate = useNavigate();
  const dispatch = useDispatch<AppDispatch>();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);

    try {
      const data = await authService.login(email, password);
      dispatch(setCredentials(data));
      navigate("/");
    } catch (err: any) {
      setError(
        err.response?.data?.detail || "Email ou mot de passe incorrect."
      );
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
        <Box sx={{ textAlign: 'center', mb: 4, cursor: 'pointer' }} onClick={() => navigate('/')}>
            <Avatar sx={{ bgcolor: 'primary.main', mx: 'auto', mb: 2, width: 48, height: 48 }}>
                <IAIcon sx={{ fontSize: 30 }} />
            </Avatar>
            <Typography variant="h5" fontWeight="800">
                Meeting<Box component="span" sx={{ color: 'primary.main' }}>Automation</Box>
            </Typography>
        </Box>

        <Paper elevation={0} sx={{ p: { xs: 3, md: 6 }, borderRadius: 4, border: '1px solid #E5EAF2' }}>
          <Box sx={{ mb: 4 }}>
            <Typography variant="h4" fontWeight="800" gutterBottom>Bon retour !</Typography>
            <Typography variant="body2" color="text.secondary">
              Connectez-vous pour accéder à vos réunions.
            </Typography>
          </Box>

          {error && <Alert severity="error" sx={{ mb: 3 }}>{error}</Alert>}

          <form onSubmit={handleSubmit}>
            <Stack spacing={3}>
              <TextField
                label="Adresse Email"
                fullWidth
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
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
                type={showPassword ? "text" : "password"}
                fullWidth
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
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

              <Box sx={{ textAlign: 'right' }}>
                <Link href="#" variant="body2" fontWeight="600">Mot de passe oublié ?</Link>
              </Box>

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
                  boxShadow: '0 4px 14px 0 rgba(0,118,255,0.39)'
                }}
              >
                {loading ? <CircularProgress size={24} color="inherit" /> : "Se connecter"}
              </Button>

              <Box sx={{ textAlign: 'center', mt: 2 }}>
                <Typography variant="body2" color="text.secondary">
                  Nouveau sur la plateforme ?{' '}
                  <Link 
                    component="button" 
                    type="button"
                    variant="body2" 
                    fontWeight="700" 
                    onClick={() => navigate('/register')}
                  >
                    Créer un compte
                  </Link>
                </Typography>
              </Box>
            </Stack>
          </form>
        </Paper>
      </Container>
    </Box>
  );
};

export default LoginForm;