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
} from "@mui/material";
import { useTranslation } from "react-i18next";
import { useDispatch, useSelector } from "react-redux";
import { RootState, AppDispatch } from "../../store";
import { fetchParticipantDashboardData } from "../../store/dashboardSlice";
import KPICard from "../common/KPICard"; // Annahme: Existiert oder muss erstellt werden
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
  client_usage: UsageInfo;
}

const DashboardParticipant: React.FC = () => {
  const { t } = useTranslation();
  const dispatch = useDispatch<AppDispatch>();
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

        {/* TODO: Implement Personal Action Items List with Virtualization */}
        <Grid item xs={12} md={6}>
          <Paper sx={{ p: 2 }}>
            <Typography variant="h6" gutterBottom>
              {t("dashboard.my_actions")}
            </Typography>
            <Box sx={{ height: 300, overflow: "auto" }}>
              <Typography>{t("dashboard.my_actions_placeholder")}</Typography>
              {/* Hier würde die Virtualisierung für die Aufgabenliste implementiert */}
              <List>
                {/* Beispiel für Listeneinträge, die dynamisch geladen werden würden */}
                <ListItem>
                  <ListItemIcon>
                    <TaskAltIcon />
                  </ListItemIcon>
                  <ListItemText
                    primary="Action 1"
                    secondary="Due: 28.02.2026"
                  />
                </ListItem>
                <ListItem>
                  <ListItemIcon>
                    <TaskAltIcon />
                  </ListItemIcon>
                  <ListItemText
                    primary="Action 2"
                    secondary="Due: 01.03.2026"
                  />
                </ListItem>
              </List>
            </Box>
          </Paper>
        </Grid>

        {/* TODO: Implement My Upcoming Meetings List with Virtualization */}
        <Grid item xs={12} md={6}>
          <Paper sx={{ p: 2 }}>
            <Typography variant="h6" gutterBottom>
              {t("dashboard.my_meetings")}
            </Typography>
            <Box sx={{ height: 300, overflow: "auto" }}>
              <Typography>{t("dashboard.my_meetings_placeholder")}</Typography>
              {/* Hier würde die Virtualisierung für die Meeting-Liste implementiert */}
              <List>
                {/* Beispiel für Listeneinträge */}
                <ListItem>
                  <ListItemIcon>
                    <EventIcon />
                  </ListItemIcon>
                  <ListItemText
                    primary="Team Standup"
                    secondary="Today 10:00 AM"
                  />
                </ListItem>
                <ListItem>
                  <ListItemIcon>
                    <EventIcon />
                  </ListItemIcon>
                  <ListItemText
                    primary="Project Sync"
                    secondary="Tomorrow 02:00 PM"
                  />
                </ListItem>
              </List>
            </Box>
          </Paper>
        </Grid>
      </Grid>
    </Box>
  );
};

export default DashboardParticipant;
