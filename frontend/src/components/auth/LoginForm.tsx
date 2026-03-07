import React from "react";
import { useForm } from "react-hook-form";
import {
  Box,
  Button,
  TextField,
  Typography,
  Paper,
  Container,
  Alert,
  CircularProgress,
} from "@mui/material";
import { useDispatch, useSelector } from "react-redux";
import { RootState, AppDispatch } from "../../store";
import { setCredentials, setLoading, setError } from "../../store/authSlice";
import authService from "../../services/auth";
import { useNavigate } from "react-router-dom";

const LoginForm: React.FC = () => {
  const dispatch = useDispatch<AppDispatch>();
  const navigate = useNavigate();
  const { loading, error } = useSelector((state: RootState) => state.auth);
  const { register, handleSubmit } = useForm();

  const onSubmit = async (data: any) => {
    console.log("LOGIN: Submit button clicked with data:", data);
    dispatch(setLoading(true));
    dispatch(setError(null));
    try {
      console.log("LOGIN: Calling authService.login...");
      const response = await authService.login(data.email, data.password);
      console.log("LOGIN: authService.login successful, response:", response);
      dispatch(setCredentials(response));
      console.log("LOGIN: setCredentials dispatched. Navigating to '/'...");
      navigate("/");
    } catch (err: any) {
      console.error("LOGIN: An error occurred in onSubmit:", err);
      const errorDetail =
        err.response?.data?.detail || "Login failed from catch block";
      console.log("LOGIN: Dispatching error:", errorDetail);
      dispatch(setError(errorDetail));
    } finally {
      console.log("LOGIN: Final block reached. Setting loading to false.");
      dispatch(setLoading(false));
    }
  };

  return (
    <Container maxWidth="sm">
      <Box sx={{ mt: 8 }}>
        <Paper elevation={3} sx={{ p: 4, textAlign: "center" }}>
          <Typography variant="h4" gutterBottom>
            Login
          </Typography>
          {error && (
            <Alert severity="error" sx={{ mb: 2 }}>
              {error}
            </Alert>
          )}
          <form onSubmit={handleSubmit(onSubmit)}>
            <TextField
              fullWidth
              label="Email"
              margin="normal"
              {...register("email")}
            />
            <TextField
              fullWidth
              label="Password"
              type="password"
              margin="normal"
              {...register("password")}
            />
            <Button
              fullWidth
              variant="contained"
              type="submit"
              disabled={loading}
              sx={{ mt: 3 }}
            >
              {loading ? <CircularProgress size={24} /> : "Sign In"}
            </Button>
          </form>
        </Paper>
      </Box>
    </Container>
  );
};

export default LoginForm;
