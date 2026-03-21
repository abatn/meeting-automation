import React, { useEffect } from "react";
import { Routes, Route, Navigate } from "react-router-dom";
import { useDispatch, useSelector } from "react-redux";
import { RootState, AppDispatch } from "./store";
import { initializeAuth } from "./store/authActions";
import { Box, CircularProgress, CssBaseline } from "@mui/material";

import MainLayout from "./components/layout/MainLayout";
import LoginForm from "./components/auth/LoginForm";
import RegisterForm from "./components/auth/RegisterForm";
import DashboardDG from "./components/reports/DashboardDG";
import DashboardManager from "./components/reports/DashboardManager";
import DashboardParticipant from "./components/reports/DashboardParticipant";
import AnalyticalReports from "./components/reports/AnalyticalReports";
import MeetingPlanner from "./components/meetings/MeetingPlanner";
import MeetingRoom from "./components/meetings/MeetingRoom";
import ActionTracker from "./components/actions/ActionTracker";
import MFASetup from "./components/auth/MFASetup";
import ErrorBoundary from "./components/ErrorBoundary";
import AutoLogout from "./components/auth/AutoLogout";
import AdminDashboard from "./pages/admin/AdminDashboard";
import ClientList from "./pages/admin/ClientList";
import ClientDetails from "./pages/admin/ClientDetails";
import TechnikDashboard from "./pages/admin/TechnikDashboard";
import BillingPanel from "./pages/billing/BillingPanel";
import LandingPage from "./pages/LandingPage";

function App() {
  const dispatch = useDispatch<AppDispatch>();
  const { authState, user } = useSelector((state: RootState) => state.auth);

  useEffect(() => {
    // Initial check on mount
    dispatch(initializeAuth());
  }, [dispatch]);

  // Loading screen during token validation
  if (authState === "loading") {
    return (
      <Box
        sx={{
          display: "flex",
          justifyContent: "center",
          alignItems: "center",
          height: "100vh",
          bgcolor: "background.default",
        }}
      >
        <CircularProgress />
      </Box>
    );
  }

  // Dashboard component selection based on role
  const getDashboard = () => {
    switch (user?.role) {
      case "system_admin":
        return <AdminDashboard />;
      case "dg":
        return <DashboardDG />;
      case "manager":
        return <DashboardManager />;
      case "participant":
      default:
        return <DashboardParticipant />;
    }
  };

  return (
    <ErrorBoundary>
      <AutoLogout>
        <Box sx={{ minHeight: "100vh" }}>
          <CssBaseline />
          <Routes>
            {/* Public Landing Page */}
            <Route
              path="/"
              element={
                authState === "authenticated" && user ? (
                  <MainLayout>{getDashboard()}</MainLayout>
                ) : (
                  <LandingPage />
                )
              }
            />

            {/* Auth Routes */}
            <Route
              path="/login"
              element={
                authState === "authenticated" ? (
                  <Navigate to="/" replace />
                ) : (
                  <LoginForm />
                )
              }
            />

            <Route
              path="/register"
              element={
                authState === "authenticated" ? (
                  <Navigate to="/" replace />
                ) : (
                  <RegisterForm />
                )
              }
            />

            {/* Protected Feature Routes */}
            <Route
              path="/meetings"
              element={
                authState === "authenticated" && user ? (
                  <MainLayout>
                    <MeetingPlanner />
                  </MainLayout>
                ) : (
                  <Navigate to="/login" replace />
                )
              }
            />

            {/* Live Meeting Room Test Route */}
            <Route
              path="/meetings/live/:id"
              element={
                authState === "authenticated" && user ? (
                  <MainLayout>
                    <MeetingRoom />
                  </MainLayout>
                ) : (
                  <Navigate to="/login" replace />
                )
              }
            />

            <Route
              path="/actions"
              element={
                authState === "authenticated" && user ? (
                  <MainLayout>
                    <ActionTracker />
                  </MainLayout>
                ) : (
                  <Navigate to="/login" replace />
                )
              }
            />

            <Route
              path="/reports"
              element={
                authState === "authenticated" && user ? (
                  <MainLayout>
                    <AnalyticalReports />
                  </MainLayout>
                ) : (
                  <Navigate to="/login" replace />
                )
              }
            />

            <Route
              path="/settings"
              element={
                authState === "authenticated" && user ? (
                  <MainLayout>
                    <Box sx={{ p: 3 }}>
                      <MFASetup
                        qrCodeUrl="https://api.qrserver.com/v1/create-qr-code/?size=150x150&data=ExampleSecret"
                        secret="JBSWY3DPEHPK3PXP"
                      />
                    </Box>
                  </MainLayout>
                ) : (
                  <Navigate to="/login" replace />
                )
              }
            />

            {/* Protected Admin Routes */}
            <Route
              path="/admin/clients"
              element={
                authState === "authenticated" && user?.role === "system_admin" ? (
                  <MainLayout>
                    <ClientList />
                  </MainLayout>
                ) : (
                  <Navigate to="/" replace />
                )
              }
            />
            <Route
              path="/admin/clients/:id"
              element={
                authState === "authenticated" && user?.role === "system_admin" ? (
                  <MainLayout>
                    <ClientDetails />
                  </MainLayout>
                ) : (
                  <Navigate to="/" replace />
                )
              }
            />
            <Route
              path="/admin/technik"
              element={
                authState === "authenticated" && user?.role === "system_admin" ? (
                  <MainLayout>
                    <TechnikDashboard />
                  </MainLayout>
                ) : (
                  <Navigate to="/" replace />
                )
              }
            />

            <Route
              path="/billing"
              element={
                authState === "authenticated" ? (
                  <MainLayout>
                    <BillingPanel />
                  </MainLayout>
                ) : (
                  <Navigate to="/login" replace />
                )
              }
            />

            {/* Fallback */}
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </Box>
      </AutoLogout>
    </ErrorBoundary>
  );
}

export default App;
