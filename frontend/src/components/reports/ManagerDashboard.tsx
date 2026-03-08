import React, { useEffect } from "react";
import {
  Box,
  Grid,
  Paper,
  Typography,
  CircularProgress,
  Alert,
} from "@mui/material";
import { useTranslation } from "react-i18next";
import { useDispatch, useSelector } from "react-redux";
import { fetchDashboardData } from "../../store/reportSlice";
import MeetingsPieChart from "./MeetingsPieChart";
import ActionsBarChart from "./ActionsBarChart";
import ProductivityTable from "./ProductivityTable";
import EfficiencyLineChart from "./EfficiencyLineChart";

const ManagerDashboard: React.FC = () => {
  const { t } = useTranslation();
  const dispatch = useDispatch<any>();
  const { dashboardData, loading, error } = useSelector(
    (state: any) => state.reports,
  );

  useEffect(() => {
    dispatch(fetchDashboardData("manager"));
  }, [dispatch]);

  if (loading)
    return (
      <Box display="flex" justifyContent="center" p={5}>
        <CircularProgress />
      </Box>
    );
  if (error) return <Alert severity="error">{error}</Alert>;
  if (!dashboardData) return null;

  const { meeting_stats, action_stats, team_productivity, efficiency_trend } =
    dashboardData;

  return (
    <Box sx={{ flexGrow: 1, p: 3 }}>
      <Typography variant="h4" gutterBottom>
        {t("Manager Dashboard")}
      </Typography>

      <Grid container spacing={3}>
        <Grid item xs={12} md={6}>
          <Paper sx={{ p: 3, height: "100%" }}>
            <Typography variant="h6" gutterBottom align="center">
              {t("Meeting Status")}
            </Typography>
            <MeetingsPieChart data={meeting_stats} />
          </Paper>
        </Grid>

        <Grid item xs={12} md={6}>
          <Paper sx={{ p: 3, height: "100%" }}>
            <Typography variant="h6" gutterBottom align="center">
              {t("Action Item Status")}
            </Typography>
            <ActionsBarChart data={action_stats} />
          </Paper>
        </Grid>

        <Grid item xs={12} md={6}>
          <Paper sx={{ p: 3, height: "100%", overflowY: "auto" }}>
            <Typography variant="h6" gutterBottom align="center">
              {t("Team Productivity")}
            </Typography>
            <ProductivityTable data={team_productivity} />
          </Paper>
        </Grid>

        <Grid item xs={12} md={6}>
          <Paper sx={{ p: 3, height: "100%" }}>
            <Typography variant="h6" gutterBottom align="center">
              {t("Efficiency Trend")}
            </Typography>
            <EfficiencyLineChart data={efficiency_trend} />
          </Paper>
        </Grid>
      </Grid>
    </Box>
  );
};

export default ManagerDashboard;
