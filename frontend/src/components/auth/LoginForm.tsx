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
      setError(err.response?.data?.detail || "Email ou mot de passe incorrect.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <Box sx={{ minHeight: '100vh', display: 'flex', alignItems: 'center', bgcolor: '#F8FAFC', py: 2 }}>
      <Container maxWidth="xs">
        <Box sx={{ textAlign: 'center', mb: 2, cursor: 'pointer' }} onClick={() => navigate('/')}>
            <Avatar sx={{ bgcolor: 'primary.main', mx: 'auto', mb: 1, width: 36, height: 36 }}>
                <IAIcon sx={{ fontSize: 22 }} />
            </Avatar>
            <Typography variant="h6" fontWeight="800">MeetingAutomation</Typography>
        </Box>

        <Paper elevation={0} sx={{ p: 3, borderRadius: 2, border: '1px solid #E5EAF2' }}>
          <Box sx={{ mb: 2 }}>
            <Typography variant="h5" fontWeight="800">Bon retour !</Typography>
            <Typography variant="caption" color="text.secondary">Connectez-vous à votre espace.</Typography>
          </Box>

          {error && <Alert severity="error" sx={{ mb: 2, py: 0 }}>{error}</Alert>}

          <form onSubmit={handleSubmit}>
            <Stack spacing={2}>
              <TextField
                label="Adresse Email"
                fullWidth
                required
                size="small"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                InputProps={{ startAdornment: (<InputAdornment position="start"><EmailIcon fontSize="small" color="action" /></InputAdornment>) }}
              />

              <TextField
                label="Mot de passe"
                type={showPassword ? "text" : "password"}
                fullWidth
                required
                size="small"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
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

              <Box sx={{ textAlign: 'right' }}>
                <Link component="button" type="button" variant="caption" fontWeight="600">Mot de passe oublié ?</Link>
              </Box>

              <Button
                type="submit"
                variant="contained"
                fullWidth
                disabled={loading}
                sx={{ py: 1, borderRadius: 1.5, fontWeight: 700, textTransform: 'none', mt: 1 }}
              >
                {loading ? <CircularProgress size={20} color="inherit" /> : "Se connecter"}
              </Button>

              <Box sx={{ textAlign: 'center' }}>
                <Typography variant="caption" color="text.secondary">
                  Nouveau ? <Link component="button" type="button" variant="caption" fontWeight="700" onClick={() => navigate('/register')}>Créer un compte</Link>
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