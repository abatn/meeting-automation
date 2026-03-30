import React, { useEffect } from "react";
import {
  Box,
  Typography,
  Grid,
  CircularProgress,
  Button,
  Stack,
  alpha,
  useTheme,
  IconButton,
  Divider,
  Paper
} from "@mui/material";
import { useTranslation } from "react-i18next";
import { useDispatch, useSelector } from "react-redux";
import { useNavigate } from "react-router-dom";
import { RootState, AppDispatch } from "../../store";
import { fetchManagerDashboardData } from "../../store/dashboardSlice";

// Material UI Icons
import EventIcon from "@mui/icons-material/Event";
import EventAvailableIcon from "@mui/icons-material/EventAvailable";
import AssignmentIcon from "@mui/icons-material/Assignment";
import PeopleIcon from "@mui/icons-material/People";
import CheckCircleIcon from "@mui/icons-material/CheckCircle";
import AddIcon from "@mui/icons-material/Add";

const DashboardManager: React.FC = () => {
  const { t, i18n } = useTranslation();
  const theme = useTheme();
  const navigate = useNavigate();
  const dispatch = useDispatch<AppDispatch>();
  const isRtl = i18n.dir() === 'rtl';
  
  const { data, loading, error } = useSelector(
    (state: RootState) => state.dashboard.managerDashboard,
  );

  useEffect(() => {
    dispatch(fetchManagerDashboardData());
  }, [dispatch]);

  if (loading) {
    return (
      <Box sx={{ display: "flex", justifyContent: "center", alignItems: "center", height: "60vh" }}>
        <CircularProgress size={30} sx={{ color: "#000" }} />
      </Box>
    );
  }

  if (error || !data) {
    return (
      <Box sx={{ p: 4, textAlign: "center" }}>
        <Typography color="error" sx={{ fontSize: 14 }}>{t("dashboard.error_loading_data")} {error}</Typography>
      </Box>
    );
  }

  const glassStyle = {
    borderRadius: "16px",
    background: theme.palette.mode === 'dark' 
      ? alpha(theme.palette.background.paper, 0.05) 
      : alpha(theme.palette.background.paper, 0.8),
    backdropFilter: "blur(12px)",
    border: `1px solid ${theme.palette.mode === 'dark' 
      ? 'rgba(255, 255, 255, 0.08)' 
      : 'rgba(0, 0, 0, 0.05)'}`,
    boxShadow: "none",
    overflow: "hidden"
  };

  const kpis = [
    { title: t("dashboard.total_team_meetings"), value: data.meeting_stats.total, icon: <EventIcon fontSize="small" />, color: "#3B82F6", route: "/meetings" },
    { title: t("dashboard.completed_team_meetings"), value: data.meeting_stats.completed, icon: <EventAvailableIcon fontSize="small" />, color: "#10B981", route: "/reports" },
    { title: t("dashboard.pending_team_actions"), value: data.action_stats.pending, icon: <AssignmentIcon fontSize="small" />, color: "#F59E0B", route: "/actions" },
    { title: t("dashboard.team_members"), value: data.team_members_count, icon: <PeopleIcon fontSize="small" />, color: "#8B5CF6", route: "/team" },
  ];

  const upcomingMeetings = [
    { id: "1", title: "Q3 Strategy Sync", time: "10:00 AM", status: "scheduled" },
    { id: "2", title: "Product Roadmap", time: "1:30 PM", status: "scheduled" },
  ];

  const openActions = [
    { id: "1", title: "Review Q3 Budget", priority: "high" },
    { id: "2", title: "Send ISO Compliance Report", priority: "medium" },
    { id: "3", title: "Update Marketing Assets", priority: "low" },
  ];

  return (
    <Box sx={{ p: { xs: 2, md: 6 }, maxWidth: 1400, mx: "auto", animation: 'fadeIn 0.5s ease-in-out', '@keyframes fadeIn': { from: { opacity: 0 }, to: { opacity: 1 } } }}>
      
      {/* HEADER */}
      <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mb: 6 }}>
        <Typography sx={{ fontSize: 18, fontWeight: 600, color: "text.primary" }}>
          {t("dashboard.manager_title")}
        </Typography>
        <Button 
          variant="contained" 
          disableElevation
          startIcon={<AddIcon />} 
          onClick={() => navigate("/meetings")}
          sx={{ 
            bgcolor: "#000", 
            color: "#FFF", 
            borderRadius: 2, 
            textTransform: "none", 
            fontSize: 14,
            fontWeight: 500, 
            px: 3, 
            py: 1,
            "&:hover": { bgcolor: "#27272A" } 
          }}
        >
          {t("meetings.new_meeting")}
        </Button>
      </Stack>

      {/* KPI GRID */}
      <Grid container spacing={3} sx={{ mb: 6 }}>
        {kpis.map((kpi, idx) => (
          <Grid item xs={12} sm={6} md={3} key={idx}>
            <Paper 
              onClick={() => navigate(kpi.route)}
              sx={{ 
                ...glassStyle,
                p: 3, 
                cursor: "pointer",
                transition: "all 0.2s ease",
                "&:hover": { borderColor: "text.primary", bgcolor: alpha(theme.palette.primary.main, 0.02), transform: "translateY(-2px)" }
              }}
            >
              <Stack spacing={1}>
                <Box sx={{ color: kpi.color, display: "flex", mb: 0.5 }}>
                  {kpi.icon}
                </Box>
                <Typography sx={{ fontSize: 24, fontWeight: 700, color: "text.primary", lineHeight: 1 }}>
                  {kpi.value}
                </Typography>
                <Typography sx={{ fontSize: 14, color: "text.secondary", fontWeight: 500 }}>
                  {kpi.title}
                </Typography>
              </Stack>
            </Paper>
          </Grid>
        ))}
      </Grid>

      {/* CONTENT SPLIT */}
      <Grid container spacing={4}>
        
        {/* Left: Upcoming Meetings */}
        <Grid item xs={12} md={7}>
          <Paper sx={glassStyle}>
            <Box sx={{ px: 3, py: 2, borderBottom: "1px solid", borderColor: "divider", bgcolor: alpha(theme.palette.primary.main, 0.02) }}>
              <Typography sx={{ fontSize: 16, fontWeight: 600 }}>
                {t("dashboard.my_upcoming_meetings")}
              </Typography>
            </Box>
            
            <Box>
              {data.meeting_stats.total === 0 ? (
                <Box sx={{ p: 8, textAlign: "center" }}>
                  <Typography sx={{ fontSize: 14, color: "text.secondary" }}>{t("dashboard.no_meetings_found")}</Typography>
                </Box>
              ) : (
                <Stack divider={<Divider />}>
                  {upcomingMeetings.map((mtg) => (
                    <Box key={mtg.id} sx={{ px: 3, py: 2.5, display: "flex", alignItems: "center", justifyContent: "space-between", transition: 'all 0.2s', "&:hover": { bgcolor: alpha(theme.palette.primary.main, 0.02), transform: isRtl ? 'translateX(-4px)' : 'translateX(4px)' } }}>
                      <Stack direction="row" spacing={3} alignItems="center">
                        <Box sx={{ width: 6, height: 6, borderRadius: "50%", bgcolor: "#3B82F6" }} />
                        <Box>
                          <Typography sx={{ fontSize: 14, fontWeight: 600, color: "text.primary" }}>{mtg.title}</Typography>
                          <Typography sx={{ fontSize: 13, color: "text.secondary" }}>{mtg.time}</Typography>
                        </Box>
                      </Stack>
                      <Button 
                        size="small" 
                        variant="outlined" 
                        sx={{ 
                          borderRadius: 2, 
                          textTransform: "none", 
                          fontSize: 13, 
                          borderColor: "divider", 
                          color: "text.primary",
                          "&:hover": { borderColor: "text.primary", bgcolor: "transparent" }
                        }}
                      >
                        {t("common.join")}
                      </Button>
                    </Box>
                  ))}
                </Stack>
              )}
            </Box>
          </Paper>
        </Grid>

        {/* Right: Open Actions */}
        <Grid item xs={12} md={5}>
          <Paper sx={glassStyle}>
            <Box sx={{ px: 3, py: 2, borderBottom: "1px solid", borderColor: "divider", bgcolor: alpha(theme.palette.primary.main, 0.02) }}>
              <Typography sx={{ fontSize: 16, fontWeight: 600 }}>
                {t("dashboard.my_open_actions")}
              </Typography>
            </Box>
            
            <Box>
              {data.action_stats.pending === 0 ? (
                <Box sx={{ p: 8, textAlign: "center" }}>
                  <Typography sx={{ fontSize: 14, color: "text.secondary" }}>{t("dashboard.no_actions_found")}</Typography>
                </Box>
              ) : (
                <Stack divider={<Divider />}>
                  {openActions.map((act) => (
                    <Box key={act.id} sx={{ px: 3, py: 2.5, display: "flex", alignItems: "center", justifyContent: "space-between", transition: 'all 0.2s', "&:hover": { bgcolor: alpha(theme.palette.primary.main, 0.02), transform: isRtl ? 'translateX(-4px)' : 'translateX(4px)' } }}>
                      <Box>
                        <Typography sx={{ fontSize: 14, fontWeight: 600, color: "text.primary", mb: 0.5 }}>{act.title}</Typography>
                        <Typography sx={{ fontSize: 12, fontWeight: 600, color: act.priority === 'high' ? "#EF4444" : "#F59E0B", textTransform: "uppercase", letterSpacing: "0.05em" }}>
                          {act.priority}
                        </Typography>
                      </Box>
                      <IconButton size="small" sx={{ border: "1px solid", borderColor: "divider", borderRadius: 1.5 }}>
                        <CheckCircleIcon sx={{ fontSize: 18, color: "#D4D4D8" }} />
                      </IconButton>
                    </Box>
                  ))}
                </Stack>
              )}
            </Box>
          </Paper>
        </Grid>

      </Grid>
    </Box>
  );
};

export default DashboardManager;