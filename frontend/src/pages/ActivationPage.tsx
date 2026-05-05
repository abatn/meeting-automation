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
import { AppDispatch } from "../store";
import { setCredentials, logout } from "../store/authSlice";
import axios from "axios";

const ActivationPage: React.FC = () => {
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
        setError("Invalid activation link: No token provided.");
        setLoading(false);
        return;
      }

      // Clear any existing session so the invited user can activate their account
      dispatch(logout());
      
      try {
        const response = await axios.get(`/api/v1/auth/activate/verify?token=${token}`);
        setEmail(response.data.email);
      } catch (err: any) {
        setError(err.response?.data?.detail || "Invalid or expired activation link.");
      } finally {
        setLoading(false);
      }
    };

    verifyToken();
  }, [token, dispatch]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (password !== confirmPassword) {
      setError("Passwords do not match");
      return;
    }
    if (password.length < 8) {
      setError("Password must be at least 8 characters long");
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
      setError(err.response?.data?.detail || "Failed to activate account. Please try again.");
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
          Activate Account
        </Typography>

        {error ? (
          <Alert severity="error" sx={{ mb: 2 }}>
            {error}
          </Alert>
        ) : success ? (
          <Alert severity="success" sx={{ mb: 2 }}>
            Account activated successfully! Redirecting to your dashboard...
          </Alert>
        ) : (
          <>
            <Typography variant="body2" color="text.secondary" align="center" sx={{ mb: 3 }}>
              Welcome! Please set a password for your account (<b>{email}</b>) to complete the setup.
            </Typography>

            <form onSubmit={handleSubmit}>
              <TextField
                fullWidth
                label="New Password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                margin="normal"
                required
              />
              <TextField
                fullWidth
                label="Confirm Password"
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
                {submitting ? <CircularProgress size={24} /> : "Activate Account"}
              </Button>
            </form>
          </>
        )}
      </Paper>
    </Box>
  );
};

export default ActivationPage;
