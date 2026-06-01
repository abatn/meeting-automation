import React, { useState, useEffect } from "react";
import {
  Box,
  Button,
  TextField,
  Typography,
  Paper,
  CircularProgress,
  Alert,
} from "@mui/material";
import { useSearchParams, useNavigate } from "react-router-dom";
import { useDispatch } from "react-redux";
import { useTranslation } from "react-i18next";
import { AppDispatch } from "../store";
import { setCredentials, logout } from "../store/authSlice";
import axios from "axios";
import PasswordStrengthIndicator from "../components/common/PasswordStrengthIndicator";

const ActivationPage: React.FC = () => {
  const { t } = useTranslation();
  const [searchParams] = useSearchParams();
  const token = searchParams.get("token");
  const navigate = useNavigate();
  const dispatch = useDispatch<AppDispatch>();

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [email, setEmail] = useState<string | null>(null);
  
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [success, setSuccess] = useState(false);

  useEffect(() => {
    const verifyToken = async () => {
      if (!token) {
        setError(t('auth.activate.invalid_token'));
        setLoading(false);
        return;
      }

      // Clear any existing session so the invited user can activate their account
      dispatch(logout());
      
      try {
        const response = await axios.get(`/api/v1/auth/activate/verify?token=${token}`);
        setEmail(response.data.email);
      } catch (err: any) {
        setError(err.response?.data?.detail || t('auth.activate.expired_link'));
      } finally {
        setLoading(false);
      }
    };

    verifyToken();
  }, [token, dispatch]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (password !== confirmPassword) {
      setError(t('auth.activate.passwords_mismatch'));
      return;
    }
    if (password.length < 8) {
      setError(t('auth.activate.password_min_length'));
      return;
    }

    setSubmitting(true);
    setError(null);

    try {
      const response = await axios.post("/api/v1/auth/activate/confirm", {
        token: token,
        new_password: password,
      });

      // Dispatch setCredentials to store user data (token is in httpOnly cookie)
      dispatch(setCredentials({
        user: response.data.user,
        // Token is now in httpOnly cookie set by backend
      }));

      setSuccess(true);

      // Navigate to home dashboard (App.tsx will route based on role)
      setTimeout(() => {
        navigate("/");
      }, 2000);
    } catch (err: any) {
      setError(err.response?.data?.detail || t('auth.activate.failed'));
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) {
    return (
      <Box sx={{ display: "flex", justifyContent: "center", alignItems: "center", height: "100vh" }}>
        <CircularProgress />
      </Box>
    );
  }

  return (
    <Box
      sx={{
        display: "flex",
        justifyContent: "center",
        alignItems: "center",
        minHeight: "100vh",
        backgroundColor: "background.default",
        p: 2,
      }}
    >
      <Paper elevation={3} sx={{ p: 4, maxWidth: 400, width: "100%", borderRadius: 3 }}>
        <Typography variant="h5" component="h1" gutterBottom align="center" fontWeight={600}>
          {t('auth.activate.title')}
        </Typography>

        {error ? (
          <Alert severity="error" sx={{ mb: 2 }}>
            {error}
          </Alert>
        ) : success ? (
          <Alert severity="success" sx={{ mb: 2 }}>
            {t('auth.activate.success')}
          </Alert>
        ) : (
          <>
            <Typography variant="body2" color="text.secondary" align="center" sx={{ mb: 3 }}>
              {t('auth.activate.welcome_message', { email })}
            </Typography>

            <form onSubmit={handleSubmit}>
              <TextField
                fullWidth
                label={t('auth.activate.new_password')}
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                margin="normal"
                required
              />
              <PasswordStrengthIndicator password={password} />
              <TextField
                fullWidth
                label={t('auth.activate.confirm_password')}
                type="password"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                margin="normal"
                required
              />
              <Button
                type="submit"
                fullWidth
                variant="contained"
                size="large"
                sx={{ mt: 3 }}
                disabled={submitting}
              >
                {submitting ? <CircularProgress size={24} /> : t('auth.activate.button')}
              </Button>
            </form>
          </>
        )}
      </Paper>
    </Box>
  );
};

export default ActivationPage;
