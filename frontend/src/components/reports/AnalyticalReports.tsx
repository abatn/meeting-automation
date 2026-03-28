import React, { useEffect } from "react";
import {
  Box,
  Typography,
  Grid,
  CircularProgress,
  alpha
} from "@mui/material";
import { useTranslation } from "react-i18next";
import { useDispatch, useSelector } from "react-redux";
import { AppDispatch, RootState } from "../../store";
import { fetchDashboardData } from "../../store/reportSlice";
import ProductivityTable from "./ProductivityTable";

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

  // Real team data from dashboardData
  const teamData = dashboardData?.team_productivity || [];

  if (loading && !dashboardData) {
    return (
      <Box sx={{ display: "flex", justifyContent: "center", alignItems: "center", height: "60vh" }}>
        <CircularProgress size={30} sx={{ color: "#000" }} />
      </Box>
    );
  }

  return (
    <Box sx={{ p: { xs: 2, md: 6 }, maxWidth: 1400, mx: "auto" }}>
      <Typography sx={{ fontSize: 18, fontWeight: 600, color: "text.primary", mb: 4 }}>
        {t("sidebar.reports")}
      </Typography>

      <Grid container spacing={4}>
        {/* Productivity Table */}
        <Grid item xs={12} md={8}>
          <Box sx={{ borderRadius: 3, border: "1px solid", borderColor: "divider", overflow: "hidden" }}>
            <Box sx={{ px: 3, py: 2, borderBottom: "1px solid", borderColor: "divider", bgcolor: alpha("#000", 0.02) }}>
              <Typography sx={{ fontSize: 16, fontWeight: 600 }}>
                {t("dashboard.dept_performance")}
              </Typography>
            </Box>
            
            <Box sx={{ p: 0 }}>
              {teamData.length === 0 ? (
                <Box sx={{ p: 8, textAlign: 'center' }}>
                  <Typography sx={{ fontSize: 14, color: "text.secondary" }}>
                    {t("dashboard.no_team_data") || "No productivity data available yet. Start completing actions to see results."}
                  </Typography>
                </Box>
              ) : (
                <ProductivityTable data={teamData} />
              )}
            </Box>
          </Box>
        </Grid>

        {/* Efficiency Trend Placeholder */}
        <Grid item xs={12} md={4}>
          <Box sx={{ borderRadius: 3, border: "1px solid", borderColor: "divider", overflow: "hidden", height: "100%" }}>
            <Box sx={{ px: 3, py: 2, borderBottom: "1px solid", borderColor: "divider", bgcolor: alpha("#000", 0.02) }}>
              <Typography sx={{ fontSize: 16, fontWeight: 600 }}>
                {t("dashboard.efficiency_trend")}
              </Typography>
            </Box>
            
            <Box sx={{ p: 6, textAlign: "center" }}>
              <Typography sx={{ fontSize: 14, color: "text.secondary", mt: 2 }}>
                {t("dashboard.efficiency_processing")}
              </Typography>
            </Box>
          </Box>
        </Grid>
      </Grid>
    </Box>
  );
};

export default AnalyticalReports;
