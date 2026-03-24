import React, { useEffect } from "react";
import { Routes, Route, Navigate, useLocation } from "react-router-dom";
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
import TeamManagement from "./pages/team/TeamManagement";
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
    dispatch(initializeAuth());
  }, [dispatch]);

  if (authState === "loading") {
    return (
      <Box sx={{ display: "flex", justifyContent: "center", alignItems: "center", height: "100vh", bgcolor: "background.default" }}>
        <CircularProgress />
      </Box>
    );
  }

  // Helper function to check roles
  const isBusinessAdmin = user?.role === "system_admin";
  const isTechAdmin = user?.role === "tech_admin";
  const isRegularUser = user && !isBusinessAdmin && !isTechAdmin;

  // Define components for regular users
  const getRegularDashboard = () => {
    switch (user?.role) {
      case "dg": return <DashboardDG />;
      case "manager": return <DashboardManager />;
      case "participant": return <DashboardParticipant />;
      default: return <DashboardParticipant />;
    }
  };

  // TECH ADMIN ROUTES (Exclusive to tech_admin, no MainLayout)
  if (authState === "authenticated" && isTechAdmin) {
    return (
      <ErrorBoundary>
        <AutoLogout>
          <Box sx={{ minHeight: "100vh", bgcolor: "#0a1929" }}>
            <CssBaseline />
            <Routes>
              <Route path="/admin/technik" element={<TechnikDashboard />} />
              <Route path="*" element={<Navigate to="/admin/technik" replace />} />
            </Routes>
          </Box>
        </AutoLogout>
      </ErrorBoundary>
    );
  }

  // BUSINESS ADMIN ROUTES (Exclusive to system_admin, with MainLayout)
  if (authState === "authenticated" && isBusinessAdmin) {
    return (
      <ErrorBoundary>
        <AutoLogout>
          <Box sx={{ minHeight: "100vh" }}>
            <CssBaseline />
            <Routes>
              <Route path="/" element={<MainLayout><AdminDashboard /></MainLayout>} />
              <Route path="/admin/clients" element={<MainLayout><ClientList /></MainLayout>} />
              <Route path="/admin/clients/:id" element={<MainLayout><ClientDetails /></MainLayout>} />
              <Route path="/billing" element={<MainLayout><BillingPanel /></MainLayout>} />
              <Route path="/settings" element={<MainLayout><Box sx={{ p: 3 }}><MFASetup qrCodeUrl="https://api.qrserver.com/v1/create-qr-code/?size=150x150&data=ExampleSecret" secret="JBSWY3DPEHPK3PXP" /></Box></MainLayout>} />
              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          </Box>
        </AutoLogout>
      </ErrorBoundary>
    );
  }

  // REGULAR USER ROUTES (Exclusive to non-admins, with MainLayout)
  if (authState === "authenticated" && isRegularUser) {
    return (
      <ErrorBoundary>
        <AutoLogout>
          <Box sx={{ minHeight: "100vh" }}>
            <CssBaseline />
            <Routes>
              <Route path="/" element={<MainLayout>{getRegularDashboard()}</MainLayout>} />
              <Route path="/meetings" element={<MainLayout><MeetingPlanner /></MainLayout>} />
              <Route path="/meetings/live/:id" element={<MainLayout><MeetingRoom /></MainLayout>} />
              <Route path="/actions" element={<MainLayout><ActionTracker /></MainLayout>} />
              <Route path="/reports" element={<MainLayout><AnalyticalReports /></MainLayout>} />
              <Route path="/team" element={<MainLayout><TeamManagement /></MainLayout>} />
              <Route path="/billing" element={<MainLayout><BillingPanel /></MainLayout>} />
              <Route path="/settings" element={<MainLayout><Box sx={{ p: 3 }}><MFASetup qrCodeUrl="https://api.qrserver.com/v1/create-qr-code/?size=150x150&data=ExampleSecret" secret="JBSWY3DPEHPK3PXP" /></Box></MainLayout>} />
              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          </Box>
        </AutoLogout>
      </ErrorBoundary>
    );
  }

  // PUBLIC ROUTES
  return (
    <ErrorBoundary>
      <Box sx={{ minHeight: "100vh" }}>
        <CssBaseline />
        <Routes>
          <Route path="/login" element={<LoginForm />} />
          <Route path="/register" element={<RegisterForm />} />
          <Route path="/" element={<LandingPage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </Box>
    </ErrorBoundary>
  );
}

export default App;
