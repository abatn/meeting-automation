import React, { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import {
  Box,
  Typography,
  Paper,
  Grid,
  Button,
  TextField,
  MenuItem,
  List,
  ListItem,
  ListItemText,
  ListItemIcon,
  ListItemButton,
  Chip,
  Alert,
  Stack,
  Select,
  InputLabel,
  FormControl,
  OutlinedInput,
  Divider,
  Autocomplete,
} from "@mui/material";
import {
  CalendarMonth as CalendarIcon,
  EventNote as EventIcon,
  Add as AddIcon,
  Warning as WarningIcon,
  MeetingRoom as MeetingRoomIcon,
} from "@mui/icons-material";
import { useTranslation } from "react-i18next";
import { useCulturalCalendar } from "../../hooks/useCulturalCalendar";
import { meetingsApi } from "../../services/meetings";
import { teamApi } from "../../services/team";

const MeetingPlanner: React.FC = () => {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { isHoliday, getHolidayName } = useCulturalCalendar();

  const [title, setTitle] = useState("");
  const [meetingDate, setMeetingDate] = useState("2026-03-03");
  const [meetingTime, setMeetingTime] = useState("10:00");
  const [selectedParticipants, setSelectedParticipants] = useState<any[]>([]);
  const [dbResults, setDbResults] = useState<any[]>([]);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [recentMeetings, setRecentMeetings] = useState<any[]>([]);
  const [searchQuery, setSearchQuery] = useState("");

  useEffect(() => {
    const fetchRecentMeetings = async () => {
      try {
        const meetingsData = await meetingsApi.getMeetings();
        // Sort by start_time descending, limit to 10
        const sorted = meetingsData.sort((a: any, b: any) => new Date(b.start_time).getTime() - new Date(a.start_time).getTime());
        setRecentMeetings(sorted.slice(0, 10));
      } catch (err) {
        console.error("Failed to fetch meetings", err);
      }
    };
    fetchRecentMeetings();
  }, []);

  useEffect(() => {
    const timer = setTimeout(async () => {
      if (searchQuery.length >= 2) {
        try {
          const results = await teamApi.searchTeam(searchQuery);
          setDbResults(results);
        } catch (err) {
          console.error("Search failed", err);
        }
      } else {
        setDbResults([]);
      }
    }, 300);
    return () => clearTimeout(timer);
  }, [searchQuery]);

  const holidays = [
    { date: "2026-03-20", name: t("meetings.holiday_independence") },
    { date: "2026-04-09", name: t("meetings.holiday_martyrs") },
  ];

  const holidayWarning = isHoliday(meetingDate)
    ? getHolidayName(meetingDate)
    : null;

  const handleCreate = async () => {
    if (!title || !!holidayWarning) return;
    setIsSubmitting(true);
    try {
      const participants = selectedParticipants.map((p) => {
        if (typeof p === 'string') {
          // Free text email entered by user
          return { email: p, name: p, role: "Guest" };
        }
        // User/TeamMember object from search API
        return { 
          email: p.email, 
          name: p.full_name || p.email, 
          role: p.position || "Participant", 
          user_id: p.source === "user" ? p.id : null 
        };
      });

      // Format start and end times
      const startTime = new Date(`${meetingDate}T${meetingTime}:00`);
      const endTime = new Date(startTime.getTime() + 60 * 60 * 1000); // Add 1 hour

      const meetingData = {
        title,
        description: "Scheduled via UI",
        location: "Virtual",
        status: "planned",
        start_time: startTime.toISOString(),
        end_time: endTime.toISOString(),
        participants,
        agendas: [],
      };

      const newMeeting = await meetingsApi.createMeeting(meetingData);
      // Redirect to the live meeting room
      navigate(`/meetings/live/${newMeeting.id}`);
    } catch (error: any) {
      console.error("Failed to create meeting", error);
      const errorMsg =
        error.response?.data?.detail || error.message || "Unknown error";
      alert(`Error creating meeting: ${errorMsg}`);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <Box sx={{ p: 3 }}>
      <Typography variant="h4" sx={{ mb: 3 }}>
        {t("meetings.planner_title")}
      </Typography>

      <Grid container spacing={3}>
        <Grid item xs={12} md={7}>
          <Paper sx={{ p: 3 }}>
            <Typography variant="h6" gutterBottom>
              {t("meetings.new_meeting")}
            </Typography>
            <Stack spacing={3} sx={{ mt: 2 }}>
              <TextField
                fullWidth
                label={t("meetings.title")}
                placeholder={t("meetings.title_placeholder")}
                value={title}
                onChange={(e) => setTitle(e.target.value)}
              />

              <Box>
                <Grid container spacing={2}>
                  <Grid item xs={12} sm={6}>
                    <TextField
                      fullWidth
                      type="date"
                      label={t("meetings.date")}
                      value={meetingDate}
                      onChange={(e) => setMeetingDate(e.target.value)}
                      InputLabelProps={{ shrink: true }}
                    />
                  </Grid>
                  <Grid item xs={12} sm={6}>
                    <TextField
                      fullWidth
                      type="time"
                      label="Time"
                      value={meetingTime}
                      onChange={(e) => setMeetingTime(e.target.value)}
                      InputLabelProps={{ shrink: true }}
                    />
                  </Grid>
                </Grid>
                {holidayWarning && (
                  <Alert
                    severity="warning"
                    icon={<WarningIcon />}
                    sx={{ mt: 1 }}
                  >
                    {t("meetings.holiday_warning")} {holidayWarning}
                  </Alert>
                )}
              </Box>

              <Autocomplete
                multiple
                freeSolo
                options={dbResults}
                getOptionLabel={(option) => {
                  if (typeof option === 'string') return option;
                  const suffix = option.department ? ` - ${option.department}` : '';
                  return `${option.full_name} (${option.email})${suffix}`;
                }}
                value={selectedParticipants}
                onInputChange={(event, newInputValue) => {
                  setSearchQuery(newInputValue);
                }}
                onChange={(event, newValue) => {
                  setSelectedParticipants(newValue);
                }}
                renderTags={(value, getTagProps) =>
                  value.map((option, index) => (
                    <Chip
                      variant="outlined"
                      color="primary"
                      label={typeof option === 'string' ? option : option.full_name}
                      {...getTagProps({ index })}
                    />
                  ))
                }
                renderInput={(params) => (
                  <TextField
                    {...params}
                    variant="outlined"
                    label={t("meetings.participants")}
                    placeholder={t("common.search")}
                  />
                )}
              />

              <Button
                variant="contained"
                size="large"
                startIcon={<AddIcon />}
                disabled={!!holidayWarning || !title || isSubmitting}
                onClick={handleCreate}
              >
                {t("meetings.create")}
              </Button>
            </Stack>
          </Paper>
        </Grid>

        <Grid item xs={12} md={5}>
          <Paper sx={{ p: 2, mb: 3 }}>
            <Typography variant="subtitle1" gutterBottom sx={{ fontWeight: 'bold' }}>
              <MeetingRoomIcon sx={{ mr: 1, verticalAlign: "middle", color: 'primary.main' }} />
              Recent Meetings
            </Typography>
            <Divider sx={{ mb: 1 }} />
            {recentMeetings.length === 0 ? (
              <Typography variant="body2" color="text.secondary" sx={{ p: 2, textAlign: 'center' }}>
                No recent meetings found. Create one to get started!
              </Typography>
            ) : (
              <List dense>
                {recentMeetings.map((meeting) => (
                  <ListItem disablePadding key={meeting.id}>
                    <ListItemButton onClick={() => navigate(`/meetings/live/${meeting.id}`)} sx={{ borderRadius: 1 }}>
                      <ListItemIcon>
                        <EventIcon color="primary" />
                      </ListItemIcon>
                      <ListItemText 
                        primary={meeting.title} 
                        secondary={new Date(meeting.start_time).toLocaleString()} 
                        primaryTypographyProps={{ fontWeight: '500' }}
                      />
                      <Chip label={meeting.status} size="small" variant="outlined" color={meeting.status === 'completed' ? 'success' : 'default'} />
                    </ListItemButton>
                  </ListItem>
                ))}
              </List>
            )}
          </Paper>

          <Paper sx={{ p: 2, bgcolor: "action.hover" }}>
            <Typography variant="subtitle1" gutterBottom>
              <CalendarIcon sx={{ mr: 1, verticalAlign: "middle" }} />
              {t("meetings.upcoming_holidays")}
            </Typography>
            <List dense>
              {holidays.map((h, i) => (
                <ListItem key={i}>
                  <ListItemIcon>
                    <EventIcon fontSize="small" />
                  </ListItemIcon>
                  <ListItemText primary={h.name} secondary={h.date} />
                  <Chip
                    label={t("meetings.holiday")}
                    size="small"
                    color="error"
                    variant="outlined"
                  />
                </ListItem>
              ))}
            </List>
          </Paper>
        </Grid>
      </Grid>
    </Box>
  );
};

export default MeetingPlanner;
