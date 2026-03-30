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
  Paper,
  Chip
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
import AccessTimeIcon from "@mui/icons-material/AccessTime";

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

  // Logic for phased buttons (Part 42)
  const getMeetingButton = (meeting: any) => {
    const startTime = new Date(meeting.start_time);
    const now = new Date();
    const diffMs = startTime.getTime() - now.getTime();
    const diffMins = Math.floor(diffMs / 60000);

    if (meeting.status === "in_progress") {
      return (
        <Button 
          size="small" 
          variant="contained" 
          onClick={() => navigate(`/meetings/live/${meeting.id}`)}
          sx={{ 
            borderRadius: 2, 
            textTransform: "none", 
            fontSize: 13, 
            bgcolor: "#10B981",
            color: "#FFF",
            "&:hover": { bgcolor: "#059669" }
          }}
        >
          {t("meetings.join_room", "Join Room")}
        </Button>
      );
    }

    if (diffMins <= 15 && diffMins >= -60) {
      return (
        <Button 
          size="small" 
          variant="contained" 
          onClick={() => navigate(`/meetings/live/${meeting.id}`)}
          sx={{ 
            borderRadius: 2, 
            textTransform: "none", 
            fontSize: 13, 
            bgcolor: "#10B981",
            color: "#FFF",
            "&:hover": { bgcolor: "#059669" },
            animation: 'pulse 2s infinite',
            '@keyframes pulse': {
              '0%': { boxShadow: '0 0 0 0 rgba(16, 185, 129, 0.4)' },
              '70%': { boxShadow: '0 0 0 10px rgba(16, 185, 129, 0)' },
              '100%': { boxShadow: '0 0 0 0 rgba(16, 185, 129, 0)' }
            }
          }}
        >
          {t("meetings.join_room", "Join Room")}
        </Button>
      );
    }

    return (
      <Stack direction="row" spacing={1}>
        <Button 
          size="small" 
          variant="outlined" 
          onClick={() => navigate(`/meetings`)}
          sx={{ 
            borderRadius: 2, 
            textTransform: "none", 
            fontSize: 12, 
            borderColor: "divider", 
            color: "text.primary"
          }}
        >
          {t("meetings.start_now", "Start Now")}
        </Button>
        <Button 
          size="small" 
          variant="text" 
          color="error"
          sx={{ borderRadius: 2, textTransform: "none", fontSize: 12 }}
        >
          {t("common.cancel")}
        </Button>
      </Stack>
    );
  };

  const isLate = (startTimeStr: string) => {
    const startTime = new Date(startTimeStr);
    const now = new Date();
    return now > startTime;
  };

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
              onClick={() => {
                // Logic for AI tagging navigation (Part 42)
                if (kpi.route === "/reports") {
                  navigate("/archive"); // Direct to archive for AI Topics
                } else {
                  navigate(kpi.route);
                }
              }}
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
              {!data.upcoming_meetings_list || data.upcoming_meetings_list.length === 0 ? (
                <Box sx={{ p: 8, textAlign: "center" }}>
                  <Typography sx={{ fontSize: 14, color: "text.secondary" }}>{t("dashboard.no_meetings_found")}</Typography>
                </Box>
              ) : (
                <Stack divider={<Divider />}>
                  {data.upcoming_meetings_list.map((mtg: any) => (
                    <Box key={mtg.id} sx={{ px: 3, py: 2.5, display: "flex", alignItems: "center", justifyContent: "space-between", transition: 'all 0.2s', "&:hover": { bgcolor: alpha(theme.palette.primary.main, 0.02), transform: isRtl ? 'translateX(-4px)' : 'translateX(4px)' } }}>
                      <Stack direction="row" spacing={3} alignItems="center">
                        <Box sx={{ width: 6, height: 6, borderRadius: "50%", bgcolor: mtg.status === "in_progress" ? "#10B981" : "#3B82F6" }} />
                        <Box>
                          <Stack direction="row" spacing={1} alignItems="center">
                            <Typography sx={{ fontSize: 14, fontWeight: 600, color: "text.primary" }}>{mtg.title}</Typography>
                            {isLate(mtg.start_time) && mtg.status === "scheduled" && (
                              <Chip label={t("meetings.late", "late")} size="small" color="error" variant="outlined" sx={{ height: 18, fontSize: 10, fontWeight: 700, textTransform: "uppercase" }} />
                            )}
                          </Stack>
                          <Typography sx={{ fontSize: 13, color: "text.secondary", display: 'flex', alignItems: 'center', mt: 0.5 }}>
                            <AccessTimeIcon sx={{ fontSize: 14, mr: 0.5 }} />
                            {new Date(mtg.start_time).toLocaleString(i18n.language, { hour: '2-digit', minute: '2-digit', day: '2-digit', month: 'short' })}
                          </Typography>
                        </Box>
                      </Stack>
                      {getMeetingButton(mtg)}
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
              {!data.open_actions_list || data.open_actions_list.length === 0 ? (
                <Box sx={{ p: 8, textAlign: "center" }}>
                  <Typography sx={{ fontSize: 14, color: "text.secondary" }}>{t("dashboard.no_actions_found")}</Typography>
                </Box>
              ) : (
                <Stack divider={<Divider />}>
                  {data.open_actions_list.map((act: any) => (
                    <Box key={act.id} sx={{ px: 3, py: 2.5, display: "flex", alignItems: "center", justifyContent: "space-between", transition: 'all 0.2s', "&:hover": { bgcolor: alpha(theme.palette.primary.main, 0.02), transform: isRtl ? 'translateX(-4px)' : 'translateX(4px)' } }}>
                      <Box>
                        <Typography sx={{ fontSize: 14, fontWeight: 600, color: "text.primary", mb: 0.5 }}>{act.title}</Typography>
                        <Stack direction="row" spacing={1} alignItems="center">
                          <Typography sx={{ fontSize: 12, fontWeight: 700, color: act.priority === 'high' ? "#EF4444" : act.priority === 'medium' ? "#F59E0B" : "#3B82F6", textTransform: "uppercase", letterSpacing: "0.05em" }}>
                            {t(`common.priority_${act.priority}`, act.priority) as string}
                          </Typography>
                          <Typography sx={{ fontSize: 11, color: "text.secondary" }}>
                            • {act.due_date ? new Date(act.due_date).toLocaleDateString(i18n.language) : "No date"}
                          </Typography>
                        </Stack>
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