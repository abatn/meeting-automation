import React, { useEffect } from "react";
import {
  Box,
  Typography,
  Paper,
  Grid,
  CircularProgress,
  Alert,
  List,
  ListItem,
  ListItemText,
  ListItemIcon,
  ListItemButton,
  Chip,
  Stack,
  useTheme,
  alpha,
} from "@mui/material";
import { useTranslation } from "react-i18next";
import { useDispatch, useSelector } from "react-redux";
import { useNavigate } from "react-router-dom";
import { RootState, AppDispatch } from "../../store";
import { fetchParticipantDashboardData } from "../../store/dashboardSlice";
import KPICard from "../common/KPICard";
import EventIcon from "@mui/icons-material/Event";
import TaskAltIcon from "@mui/icons-material/TaskAlt";

const DashboardParticipant: React.FC = () => {
  const { t, i18n } = useTranslation();
  const theme = useTheme();
  const dispatch = useDispatch<AppDispatch>();
  const navigate = useNavigate();
  const isRtl = i18n.dir() === 'rtl';
  
  const { data, loading, error } = useSelector(
    (state: RootState) => state.dashboard.participantDashboard,
  );

  useEffect(() => {
    dispatch(fetchParticipantDashboardData());
  }, [dispatch]);

  if (loading) {
    return (
      <Box sx={{ display: "flex", justifyContent: "center", alignItems: "center", minHeight: '400px' }}>
        <CircularProgress />
      </Box>
    );
  }

  if (error) {
    return (
      <Box sx={{ p: { xs: 2, md: 3 } }}>
        <Alert severity="error">
          {t("dashboard.error_loading_data")} {error}
        </Alert>
      </Box>
    );
  }

  if (!data) {
    return (
      <Box sx={{ p: { xs: 2, md: 3 } }}>
        <Alert severity="info">{t("dashboard.no_data_available")}</Alert>
      </Box>
    );
  }

  const glassStyle = {
    p: { xs: 2, md: 3 },
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

  return (
    <Box 
      sx={{ 
        p: { xs: 2, md: 4 },
        animation: 'fadeIn 0.5s ease-in-out',
        '@keyframes fadeIn': {
          from: { opacity: 0 },
          to: { opacity: 1 }
        }
      }}
    >
      {/* HEADER SECTION */}
      <Stack 
        direction={{ xs: 'column', sm: 'row' }} 
        justifyContent="space-between" 
        alignItems={{ xs: 'stretch', sm: 'center' }} 
        spacing={3} 
        sx={{ mb: 4 }}
      >
        <Box>
          <Typography 
            variant="h4" 
            sx={{ 
              fontWeight: 800, 
              fontSize: { xs: '1.75rem', sm: '2.125rem' },
              letterSpacing: '-0.02em',
              mb: 0.5
            }}
          >
            {t("dashboard.participant_title")}
          </Typography>
          <Typography variant="body2" color="text.secondary">
            {new Date().toLocaleDateString(i18n.language, { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' })}
          </Typography>
        </Box>
      </Stack>

      <Grid container spacing={{ xs: 2, md: 3 }}>
        {/* KPI CARDS */}
        <Grid item xs={6} md={4}>
          <KPICard
            title={t("dashboard.my_upcoming_meetings")}
            value={data.my_upcoming_meetings}
            icon={<EventIcon />}
          />
        </Grid>
        <Grid item xs={6} md={4}>
          <KPICard
            title={t("dashboard.my_open_actions")}
            value={data.my_open_actions}
            icon={<TaskAltIcon />}
          />
        </Grid>

        {/* LIST SECTION - ACTIONS */}
        <Grid item xs={12} md={6}>
          <Paper sx={glassStyle}>
            <Stack direction="row" alignItems="center" spacing={1.5} sx={{ mb: 3 }}>
              <TaskAltIcon color="primary" />
              <Typography variant="h6" sx={{ fontWeight: 800, letterSpacing: '-0.01em' }}>
                {t("dashboard.my_actions")}
              </Typography>
            </Stack>

            <Box sx={{ 
              minHeight: 250, 
              maxHeight: { xs: 450, md: 500 }, 
              overflowY: "auto",
              paddingInlineEnd: 1
            }}>
              {data.open_actions_list?.length === 0 ? (
                <Box sx={{ py: 4, textAlign: 'center', bgcolor: alpha(theme.palette.text.disabled, 0.05), borderRadius: '12px' }}>
                  <Typography variant="body2" color="text.secondary">
                    {t("dashboard.no_actions_found")}
                  </Typography>
                </Box>
              ) : (
                <List sx={{ display: 'flex', flexDirection: 'column', gap: 1.5, p: 0 }}>
                  {data.open_actions_list?.map((action) => (
                    <ListItem key={action.id} disablePadding>
                      <ListItemButton 
                        onClick={() => navigate("/actions")}
                        sx={{ 
                          borderRadius: '12px',
                          p: 2,
                          gap: 2,
                          bgcolor: alpha(theme.palette.background.paper, 0.4),
                          border: `1px solid ${alpha(theme.palette.divider, 0.05)}`,
                          transition: 'all 0.2s',
                          "&:hover": { 
                            bgcolor: alpha(theme.palette.primary.main, 0.04),
                            borderColor: alpha(theme.palette.primary.main, 0.1),
                            transform: isRtl ? 'translateX(-4px)' : 'translateX(4px)'
                          }
                        }}
                      >
                        <ListItemIcon sx={{ minWidth: '40px', display: 'flex', justifyContent: 'center' }}>
                          <TaskAltIcon color={action.priority === 'high' ? 'error' : 'primary'} />
                        </ListItemIcon>
                        <ListItemText
                          primary={action.title}
                          secondary={`${t("dashboard.due")}: ${action.due_date ? new Date(action.due_date).toLocaleDateString(i18n.language) : 'N/A'}`}
                          primaryTypographyProps={{ fontWeight: 700, fontSize: '0.95rem', mb: 0.5, lineHeight: 1.6 }}
                          secondaryTypographyProps={{ color: 'text.secondary', fontSize: '0.85rem' }}
                        />
                        <Chip 
                          label={action.priority} 
                          size="small" 
                          color={action.priority === 'high' ? 'error' : 'primary'}
                          variant="outlined"
                          sx={{ 
                            borderRadius: '8px', 
                            fontWeight: 800, 
                            fontSize: '0.7rem',
                            textTransform: 'uppercase',
                            minWidth: 70
                          }} 
                        />
                      </ListItemButton>
                    </ListItem>
                  ))}
                </List>
              )}
            </Box>
          </Paper>
        </Grid>

        {/* LIST SECTION - MEETINGS */}
        <Grid item xs={12} md={6}>
          <Paper sx={glassStyle}>
            <Stack direction="row" alignItems="center" spacing={1.5} sx={{ mb: 3 }}>
              <EventIcon color="primary" />
              <Typography variant="h6" sx={{ fontWeight: 800, letterSpacing: '-0.01em' }}>
                {t("dashboard.my_meetings")}
              </Typography>
            </Stack>

            <Box sx={{ 
              minHeight: 250, 
              maxHeight: { xs: 450, md: 500 }, 
              overflowY: "auto",
              paddingInlineEnd: 1
            }}>
              {data.upcoming_meetings_list?.length === 0 ? (
                <Box sx={{ py: 4, textAlign: 'center', bgcolor: alpha(theme.palette.text.disabled, 0.05), borderRadius: '12px' }}>
                  <Typography variant="body2" color="text.secondary">
                    {t("dashboard.no_meetings_found")}
                  </Typography>
                </Box>
              ) : (
                <List sx={{ display: 'flex', flexDirection: 'column', gap: 1.5, p: 0 }}>
                  {data.upcoming_meetings_list?.map((meeting) => (
                    <ListItem key={meeting.id} disablePadding>
                      <ListItemButton 
                        onClick={() => navigate(`/meetings/live/${meeting.id}`)}
                        sx={{ 
                          borderRadius: '12px',
                          p: 2,
                          bgcolor: alpha(theme.palette.background.paper, 0.4),
                          border: `1px solid ${alpha(theme.palette.divider, 0.05)}`,
                          transition: 'all 0.2s',
                          "&:hover": { 
                            bgcolor: alpha(theme.palette.primary.main, 0.04),
                            borderColor: alpha(theme.palette.primary.main, 0.1),
                            transform: isRtl ? 'translateX(-4px)' : 'translateX(4px)'
                          }
                        }}
                      >
                        <ListItemIcon sx={{ minWidth: '40px', display: 'flex', justifyContent: 'center' }}>
                          <EventIcon color="primary" />
                        </ListItemIcon>
                        <ListItemText
                          primary={meeting.title}
                          secondary={new Date(meeting.start_time).toLocaleString(i18n.language)}
                          primaryTypographyProps={{ fontWeight: 700, fontSize: '0.95rem', mb: 0.5, lineHeight: 1.6 }}
                          secondaryTypographyProps={{ color: 'text.secondary', fontSize: '0.85rem' }}
                        />
                        <Chip 
                          label={meeting.status} 
                          size="small" 
                          variant="outlined"
                          sx={{ 
                            borderRadius: '8px', 
                            fontWeight: 800, 
                            fontSize: '0.7rem',
                            textTransform: 'uppercase',
                            minWidth: 80
                          }} 
                        />
                      </ListItemButton>
                    </ListItem>
                  ))}
                </List>
              )}
            </Box>
          </Paper>
        </Grid>
      </Grid>
    </Box>
  );
};

export default DashboardParticipant;
