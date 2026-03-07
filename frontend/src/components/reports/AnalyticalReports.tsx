import React, { useEffect } from "react";
import {
  Box,
  Typography,
  Paper,
  Grid,
  Divider,
  CircularProgress,
} from "@mui/material";
import { useTranslation } from "react-i18next";
import { useDispatch, useSelector } from "react-redux";
import { AppDispatch, RootState } from "../../store";
import { fetchDashboardData } from "../../store/reportSlice";
import ProductivityTable from "./ProductivityTable";
import EfficiencyLineChart from "./EfficiencyLineChart";

const AnalyticalReports: React.FC = () => {
  const { t } = useTranslation();
  const dispatch = useDispatch<AppDispatch>();
  const { dashboardData, loading } = useSelector(
    (state: RootState) => state.reports,
  );

  useEffect(() => {
    // For analytical reports, we reuse DG data or specialized analytical data
    dispatch(fetchDashboardData("dg"));
  }, [dispatch]);

  // Mock team data if not in dashboardData
  const teamData = dashboardData?.team_productivity || [
    { user_id: 1, name: "Sami Ben Ali", completed: 12, pending: 3, overdue: 1 },
    { user_id: 2, name: "Amel Trabelsi", completed: 8, pending: 5, overdue: 0 },
    {
      user_id: 3,
      name: "Mohamed Mahmoud",
      completed: 15,
      pending: 2,
      overdue: 2,
    },
  ];

  if (loading && !dashboardData) {
    return (
      <Box sx={{ display: "flex", justifyContent: "center", p: 5 }}>
        <CircularProgress />
      </Box>
    );
  }

  return (
    <Box sx={{ p: 3 }}>
      <Typography variant="h4" sx={{ mb: 3, fontWeight: "bold" }}>
        {t("sidebar.reports")}
      </Typography>

      <Grid container spacing={3}>
        {/* Productivity Table */}
        <Grid item xs={12} md={8}>
          <Paper sx={{ p: 3, borderRadius: 3 }}>
            <Typography variant="h6" gutterBottom>
              {t("dashboard.dept_performance")}
            </Typography>
            <Divider sx={{ mb: 2 }} />
            <ProductivityTable data={teamData} />
          </Paper>
        </Grid>

        {/* Efficiency Trend Placeholder */}
        <Grid item xs={12} md={4}>
          <Paper
            sx={{ p: 3, borderRadius: 3, bgcolor: "#f5f7fa", height: "100%" }}
          >
            <Typography variant="h6" gutterBottom>
              {t("dashboard.efficiency_trend")}
            </Typography>
            <Divider sx={{ mb: 2 }} />
            <Box sx={{ mt: 5, textAlign: "center" }}>
              <Typography color="textSecondary">
                Historical efficiency data is being processed by the AI engine.
              </Typography>
            </Box>
          </Paper>
        </Grid>
      </Grid>
    </Box>
  );
};

export default AnalyticalReports;
