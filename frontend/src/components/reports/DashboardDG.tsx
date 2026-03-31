import React, { useEffect, useState } from "react";
import {
  Grid,
  Paper,
  Typography,
  Box,
  Button,
  Divider,
  List,
  ListItem,
  ListItemText,
  ListItemSecondaryAction,
  Chip,
  CircularProgress,
  Stack,
  useTheme,
  alpha
} from "@mui/material";
import {
  Download as DownloadIcon,
  TrendingUp,
  Assignment,
  CheckCircle,
  Warning,
  NotificationsActive,
} from "@mui/icons-material";
import { useTranslation } from "react-i18next";
import { useDispatch, useSelector } from "react-redux";
import { AppDispatch, RootState } from "../../store";
import { fetchDashboardData } from "../../store/reportSlice";
import api from "../../services/api";

import MeetingsPieChart from "./MeetingsPieChart";
import ActionsBarChart from "./ActionsBarChart";
import UsageProgressBar from "../common/UsageProgressBar";

interface ActionPattern {
  title: string;
  count: number;
}

interface ActionStatistics {
  suggested_assignee: string | null;
  total_suggestions: number;
  accepted_count: number;
  rejected_count: number;
}

const DashboardDG: React.FC = () => {
  const { t, i18n } = useTranslation();
  const theme = useTheme();
  const dispatch = useDispatch<AppDispatch>();
  const isRtl = i18n.dir() === 'rtl';
  const { dashboardData, loading } = useSelector(
    (state: RootState) => state.reports,
  );

  const [patterns, setPatterns] = useState<ActionPattern[]>([]);
  const [stats, setStats] = useState<ActionStatistics[]>([]);

  useEffect(() => {
    dispatch(fetchDashboardData("dg"));

    const fetchAnalytics = async () => {
      try {
        const [patRes, statRes] = await Promise.all([
          api.get(`/actions/patterns?lang=${i18n.language}`),
          api.get(`/actions/statistics/recurring?lang=${i18n.language}`)
        ]);
        setPatterns(patRes.data);
        setStats(statRes.data);
      } catch (err) {
        console.error("Failed to fetch analytics", err);
      }
    };
    fetchAnalytics();
  }, [dispatch, i18n.language]);

  if (loading && !dashboardData) {
    return (
      <Box sx={{ display: "flex", justifyContent: "center", p: 5 }}>
        <CircularProgress />
      </Box>
    );
  }

  const glassStyle = {
    p: 3,
    height: '100%',
    borderRadius: "16px",
    background: theme.palette.mode === 'dark' 
      ? alpha(theme.palette.background.paper, 0.05) 
      : alpha(theme.palette.background.paper, 0.8),
    backdropFilter: "blur(12px)",
    border: `1px solid ${theme.palette.mode === 'dark' 
      ? 'rgba(255, 255, 255, 0.08)' 
      : 'rgba(0, 0, 0, 0.05)'}`,
    boxShadow: "none",
  };

  // Data for Charts
  const meetingData = {
    completed: dashboardData?.completed_meetings || 0,
    scheduled:
      (dashboardData?.total_meetings || 0) -
      (dashboardData?.completed_meetings || 0),
    cancelled: 0, // Default for now
  };

  const actionData = {
    completed: dashboardData?.action_status_distribution?.completed || 0,
    pending: dashboardData?.action_status_distribution?.in_progress || 0,
    overdue: dashboardData?.action_status_distribution?.open || 0,
  };

  // Map API data to KPI objects
  const kpis = [
    {
      title: t("dashboard.meetings_month"),
      value: dashboardData?.total_meetings || "0",
      icon: <TrendingUp color="primary" />,
      trend: t("dashboard.trend_15"),
    },
    {
      title: t("dashboard.completion_rate"),
      value: dashboardData?.completed_meetings || "0",
      icon: <CheckCircle color="success" />,
      trend: t("dashboard.trend_stable"),
    },
    {
      title: t("dashboard.pending_pvs"),
      value: dashboardData?.pending_actions || "0",
      icon: <Assignment color="warning" />,
      trend: t("dashboard.trend_actionrequired"),
    },
  ];

  const recentActivities = [
    {
      id: 1,
      text: t("dashboard.activity_pv_generated"),
      time: t("dashboard.time_2h_ago"),
      status: t("common.success"),
    },
    {
      id: 2,
      text: t("dashboard.activity_action_assigned"),
      time: t("dashboard.time_5h_ago"),
      status: t("common.pending"),
    },
    {
      id: 3,
      text: t("dashboard.activity_meeting_completed"),
      time: t("dashboard.time_1d_ago"),
      status: t("common.success"),
    },
  ];

  return (
    <Box sx={{ flexGrow: 1, p: { xs: 2, md: 3 }, animation: 'fadeIn 0.5s ease-in-out', '@keyframes fadeIn': { from: { opacity: 0 }, to: { opacity: 1 } } }}>
      {/* Header */}
      <Box
        sx={{
          display: "flex",
          flexDirection: { xs: "column", sm: "row" },
          justifyContent: "space-between",
          mb: 4,
          alignItems: { xs: "flex-start", sm: "center" },
          gap: 2,
        }}
      >
        <Box>
          <Typography
            variant="h4"
            sx={{ fontWeight: "bold", color: "text.primary", mb: 0.5 }}
          >
            {t("dashboard.dg_title")}
          </Typography>
          <Typography variant="body2" color="text.secondary">
            {new Date().toLocaleDateString(i18n.language, { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' })}
          </Typography>
        </Box>

        <Stack direction="row" spacing={2} alignItems="center" sx={{ width: { xs: '100%', sm: 'auto' } }}>
          {dashboardData?.client_usage && (
            <Box sx={{ width: 250, p: 1.5, borderRadius: '12px', bgcolor: alpha(theme.palette.primary.main, 0.03), border: `1px solid ${alpha(theme.palette.primary.main, 0.1)}` }}>
              <UsageProgressBar 
                used={dashboardData.client_usage.minutes_used} 
                total={dashboardData.client_usage.minutes_included} 
              />
            </Box>
          )}
          <Button
            variant="contained"
            startIcon={<DownloadIcon />}
            color="primary"
            sx={{ borderRadius: 2, px: 3, textTransform: "none", height: 48 }}
          >
            {t("common.export")}
          </Button>
        </Stack>
      </Box>

      {/* KPI Section */}
      <Grid container spacing={3} sx={{ mb: 6 }}>
        {kpis.map((kpi, idx) => (
          <Grid item xs={12} sm={6} md={4} key={idx}>
            <Paper
              sx={{
                ...glassStyle,
                display: "flex",
                alignItems: "center",
                minHeight: 120,
              }}
            >
              <Box
                sx={{
                  bgcolor: alpha(theme.palette.primary.main, 0.05),
                  p: 2,
                  borderRadius: 3,
                  display: "flex",
                  marginInlineEnd: 3,
                }}
              >
                {kpi.icon}
              </Box>
              <Box sx={{ overflow: "hidden" }}>
                <Typography
                  color="textSecondary"
                  variant="caption"
                  sx={{
                    textTransform: "uppercase",
                    fontWeight: "bold",
                    letterSpacing: 1,
                    display: "block",
                    mb: 0.5,
                    whiteSpace: "nowrap",
                  }}
                >
                  {kpi.title}
                </Typography>
                <Typography variant="h5" sx={{ fontWeight: "800" }}>
                  {kpi.value}
                </Typography>
                <Typography
                  variant="caption"
                  color="success.main"
                  sx={{ fontWeight: "bold" }}
                >
                  {kpi.trend}
                </Typography>
              </Box>
            </Paper>
          </Grid>
        ))}
      </Grid>

      {/* Analytical Charts Section */}
      <Grid container spacing={4} sx={{ mb: 4 }}>
        <Grid item xs={12} lg={6}>
          <Paper sx={glassStyle}>
            <Typography variant="h6" sx={{ mb: 2, fontWeight: "bold" }}>
              {t("dashboard.meeting_distribution")}
            </Typography>
            <Divider sx={{ mb: 3 }} />
            <Box sx={{ height: 320, width: "100%" }}>
              <MeetingsPieChart data={meetingData} />
            </Box>
          </Paper>
        </Grid>
        <Grid item xs={12} lg={6}>
          <Paper sx={glassStyle}>
            <Typography variant="h6" sx={{ mb: 2, fontWeight: "bold" }}>
              {t("dashboard.action_summary")}
            </Typography>
            <Divider sx={{ mb: 3 }} />
            <Box sx={{ height: 320, width: "100%" }}>
              <ActionsBarChart data={actionData} />
            </Box>
          </Paper>
        </Grid>
      </Grid>

      {/* AI & ML Analytics Section */}
      <Grid container spacing={4} sx={{ mb: 4 }}>
        <Grid item xs={12} lg={6}>
          <Paper sx={glassStyle}>
            <Typography variant="h6" sx={{ mb: 2, fontWeight: "bold", display: 'flex', alignItems: 'center' }}>
              <Warning sx={{ marginInlineEnd: 1, color: 'warning.main' }} /> {t("dashboard.recurring_patterns")}
            </Typography>
            <Divider sx={{ mb: 2 }} />
            <List>
              {patterns.map((pat, idx) => (
                <React.Fragment key={idx}>
                  <ListItem disableGutters>
                    <ListItemText primary={pat.title} />
                    <ListItemSecondaryAction>
                      <Chip label={`${pat.count} ${t("dashboard.stat_pending")}`} color="warning" size="small" />
                    </ListItemSecondaryAction>
                  </ListItem>
                  {idx < patterns.length - 1 && <Divider component="li" />}
                </React.Fragment>
              ))}
              {patterns.length === 0 && <Typography variant="body2" color="textSecondary">{t("dashboard.no_patterns_found")}</Typography>}
            </List>
          </Paper>
        </Grid>
        <Grid item xs={12} lg={6}>
          <Paper sx={glassStyle}>
            <Typography variant="h6" sx={{ mb: 2, fontWeight: "bold", display: 'flex', alignItems: 'center' }}>
              <Assignment sx={{ marginInlineEnd: 1, color: 'secondary.main' }} /> {t("dashboard.ai_suggestion_stats")}
            </Typography>
            <Divider sx={{ mb: 2 }} />
            <List>
              {stats.map((stat, idx) => (
                <React.Fragment key={idx}>
                  <ListItem disableGutters>
                    <ListItemText 
                      primary={stat.suggested_assignee || t("dashboard.unassigned")} 
                      secondary={`${t("dashboard.stat_total")}: ${stat.total_suggestions} | ${t("dashboard.stat_accepted")}: ${stat.accepted_count} | ${t("dashboard.stat_rejected")}: ${stat.rejected_count}`}
                    />
                    <ListItemSecondaryAction>
                      <Chip 
                        label={stat.total_suggestions > 0 ? Math.round((stat.accepted_count / stat.total_suggestions) * 100) + `% ${t("dashboard.stat_accepted")}` : "0%"} 
                        color="success" 
                        size="small" 
                        variant="outlined"
                      />
                    </ListItemSecondaryAction>
                  </ListItem>
                  {idx < stats.length - 1 && <Divider component="li" />}
                </React.Fragment>
              ))}
              {stats.length === 0 && <Typography variant="body2" color="textSecondary">{t("dashboard.no_statistics_found")}</Typography>}
            </List>
          </Paper>
        </Grid>
      </Grid>

      <Grid container spacing={3}>
        {/* Recent Activity */}
        <Grid item xs={12} md={8}>
          <Paper sx={glassStyle}>
            <Typography
              variant="h6"
              gutterBottom
              display="flex"
              alignItems="center"
            >
              <NotificationsActive sx={{ marginInlineEnd: 1 }} />{" "}
              {t("dashboard.recent_activity")}
            </Typography>
            <Divider sx={{ mb: 2 }} />
            <List>
              {recentActivities.map((activity, idx) => (
                <React.Fragment key={activity.id}>
                  <ListItem disableGutters>
                    <ListItemText
                      primary={activity.text}
                      secondary={activity.time}
                    />
                    <ListItemSecondaryAction>
                      <Chip
                        label={activity.status}
                        size="small"
                        color={
                          activity.status === t("common.success")
                            ? "success"
                            : "warning"
                        }
                        variant="outlined"
                      />
                    </ListItemSecondaryAction>
                  </ListItem>
                  {idx < recentActivities.length - 1 && (
                    <Divider component="li" />
                  )}
                </React.Fragment>
              ))}
            </List>
          </Paper>
        </Grid>

        {/* System Health Summary */}
        <Grid item xs={12} md={4}>
          <Paper sx={{ ...glassStyle, bgcolor: alpha(theme.palette.primary.main, 0.02) }}>
            <Typography variant="h6" gutterBottom>
              {t("dashboard.system_health")}
            </Typography>
            <Divider sx={{ mb: 2 }} />
            <Box sx={{ mb: 2 }}>
              <Typography variant="body2" color="textSecondary">
                {t("dashboard.health_api")}
              </Typography>
              <Typography
                variant="subtitle1"
                color="success.main"
                sx={{ fontWeight: "bold" }}
              >
                {t("dashboard.health_api_status")}
              </Typography>
            </Box>
            <Box sx={{ mb: 2 }}>
              <Typography variant="body2" color="textSecondary">
                {t("dashboard.health_ai")}
              </Typography>
              <Typography
                variant="subtitle1"
                color="primary"
                sx={{ fontWeight: "bold" }}
              >
                {t("dashboard.health_ai_status")}
              </Typography>
            </Box>
            <Box>
              <Typography variant="body2" color="textSecondary">
                {t("dashboard.health_storage")}
              </Typography>
              <Typography
                variant="subtitle1"
                color="warning.main"
                sx={{ fontWeight: "bold" }}
              >
                {t("dashboard.health_storage_status")}
              </Typography>
            </Box>
          </Paper>
        </Grid>
      </Grid>
    </Box>
  );
};

export default DashboardDG;