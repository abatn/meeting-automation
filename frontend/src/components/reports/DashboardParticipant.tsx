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
} from "@mui/material";
import { useTranslation } from "react-i18next";
import { useDispatch, useSelector } from "react-redux";
import { useNavigate } from "react-router-dom";
import { RootState, AppDispatch } from "../../store";
import { fetchParticipantDashboardData } from "../../store/dashboardSlice";
import KPICard from "../common/KPICard";
import EventIcon from "@mui/icons-material/Event";
import TaskAltIcon from "@mui/icons-material/TaskAlt";
import UsageProgressBar from "../common/UsageProgressBar";

// Interfaces from dashboardSlice.ts for type safety
interface UsageInfo {
  period: string;
  minutes_used: number;
  minutes_included: number;
  remaining: number;
}

interface ParticipantDashboardData {
  my_upcoming_meetings: number;
  my_open_actions: number;
  upcoming_meetings_list: any[];
  open_actions_list: any[];
  client_usage: UsageInfo;
}

const DashboardParticipant: React.FC = () => {
  const { t } = useTranslation();
  const dispatch = useDispatch<AppDispatch>();
  const navigate = useNavigate();
  const { data, loading, error } = useSelector(
    (state: RootState) => state.dashboard.participantDashboard,
  );

  useEffect(() => {
    dispatch(fetchParticipantDashboardData());
  }, [dispatch]);

  if (loading) {
    return (
      <Box sx={{ display: "flex", justifyContent: "center", mt: 4 }}>
        <CircularProgress />
      </Box>
    );
  }

  if (error) {
    return (
      <Box sx={{ p: 3 }}>
        <Alert severity="error">
          {t("dashboard.error_loading_data")} {error}
        </Alert>
      </Box>
    );
  }

  if (!data) {
    return (
      <Box sx={{ p: 3 }}>
        <Alert severity="info">{t("dashboard.no_data_available")}</Alert>
      </Box>
    );
  }

  return (
    <Box sx={{ p: 3 }}>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1 }}>
        <Typography variant="h4">
          {t("dashboard.participant_title")}
        </Typography>
        {data.client_usage && (
          <Box sx={{ width: 300 }}>
            <UsageProgressBar 
              used={data.client_usage.minutes_used} 
              total={data.client_usage.minutes_included} 
            />
          </Box>
        )}
      </Box>

      <Grid container spacing={3} sx={{ mt: 2 }}>
        {/* KPI Cards */}
        <Grid item xs={12} sm={6} md={4}>
          <KPICard
            title={t("dashboard.my_upcoming_meetings")}
            value={data.my_upcoming_meetings}
            icon={<EventIcon />}
          />
        </Grid>
        <Grid item xs={12} sm={6} md={4}>
          <KPICard
            title={t("dashboard.my_open_actions")}
            value={data.my_open_actions}
            icon={<TaskAltIcon />}
          />
        </Grid>

        {/* Real Action Items List */}
        <Grid item xs={12} md={6}>
          <Paper sx={{ p: 2 }}>
            <Typography variant="h6" gutterBottom>
              {t("dashboard.my_actions")}
            </Typography>
            <Box sx={{ height: 300, overflow: "auto" }}>
              {data.open_actions_list?.length === 0 ? (
                <Typography variant="body2" color="text.secondary" sx={{ p: 2 }}>{t("dashboard.no_actions_found") || "No open actions found."}</Typography>
              ) : (
                <List>
                  {data.open_actions_list?.map((action) => (
                    <ListItem key={action.id} disablePadding>
                      <ListItemButton onClick={() => navigate("/actions")}>
                        <ListItemIcon>
                          <TaskAltIcon color={action.priority === 'high' ? 'error' : 'primary'} />
                        </ListItemIcon>
                        <ListItemText
                          primary={action.title}
                          secondary={`Due: ${action.due_date ? new Date(action.due_date).toLocaleDateString() : 'N/A'}`}
                        />
                        <Chip label={action.priority} size="small" variant="outlined" />
                      </ListItemButton>
                    </ListItem>
                  ))}
                </List>
              )}
            </Box>
          </Paper>
        </Grid>

        {/* Real Upcoming Meetings List */}
        <Grid item xs={12} md={6}>
          <Paper sx={{ p: 2 }}>
            <Typography variant="h6" gutterBottom>
              {t("dashboard.my_meetings")}
            </Typography>
            <Box sx={{ height: 300, overflow: "auto" }}>
              {data.upcoming_meetings_list?.length === 0 ? (
                <Typography variant="body2" color="text.secondary" sx={{ p: 2 }}>{t("dashboard.no_meetings_found") || "No upcoming meetings found."}</Typography>
              ) : (
                <List>
                  {data.upcoming_meetings_list?.map((meeting) => (
                    <ListItem key={meeting.id} disablePadding>
                      <ListItemButton onClick={() => navigate(`/meetings/live/${meeting.id}`)}>
                        <ListItemIcon>
                          <EventIcon color="primary" />
                        </ListItemIcon>
                        <ListItemText
                          primary={meeting.title}
                          secondary={new Date(meeting.start_time).toLocaleString()}
                        />
                        <Chip label={meeting.status} size="small" variant="outlined" />
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
