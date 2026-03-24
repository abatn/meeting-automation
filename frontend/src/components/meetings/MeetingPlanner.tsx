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
  Divider,
  Autocomplete,
  SelectChangeEvent
} from "@mui/material";
import {
  CalendarMonth as CalendarIcon,
  EventNote as EventIcon,
  Add as AddIcon,
  Warning as WarningIcon,
  MeetingRoom as MeetingRoomIcon,
  Edit as EditIcon,
} from "@mui/icons-material";
import { useTranslation } from "react-i18next";
import { Link, useNavigate } from "react-router-dom";
import { useCulturalCalendar } from "../../hooks/useCulturalCalendar";
import { meetingsApi } from "../../services/meetings";
import { teamApi } from "../../services/team";
import { roomsApi } from "../../services/rooms";
import DocumentExportMenu from "./DocumentExportMenu";
import api from "../../services/api";

const MeetingPlanner: React.FC = () => {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { isHoliday, getHolidayName } = useCulturalCalendar();

  // State for form fields
  const [title, setTitle] = useState("");
  const [meetingDate, setMeetingDate] = useState("2026-03-03");
  const [meetingTime, setMeetingTime] = useState("10:00");
  const [plannedDuration, setPlannedDuration] = useState(60);
  const [location, setLocation] = useState<any>(null); // Can be a room object or a string

  // State for participants
  const [selectedParticipants, setSelectedParticipants] = useState<any[]>([]);
  const [participantSearch, setParticipantSearch] = useState("");
  const [participantResults, setParticipantResults] = useState<any[]>([]);

  // State for rooms
  const [availableRooms, setAvailableRooms] = useState<any[]>([]);
  
  // General UI state
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [recentMeetings, setRecentMeetings] = useState<any[]>([]);
  const [pvMap, setPvMap] = useState<Record<string, string>>({}); // mapping meetingId -> pvId
  const [exportLanguage, setExportLanguage] = useState("fr");
  
  // Fetch initial data (recent meetings and available rooms)
  useEffect(() => {
    const fetchInitialData = async () => {
      try {
        const [meetingsData, roomsData] = await Promise.all([
          meetingsApi.getMeetings(),
          roomsApi.getRooms(),
        ]);
        
        const sorted = meetingsData.sort((a: any, b: any) => new Date(b.start_time).getTime() - new Date(a.start_time).getTime());
        const limited = sorted.slice(0, 10);
        setRecentMeetings(limited);
        setAvailableRooms(roomsData);

        // Check for PVs for completed meetings to enable smart export
        const completedMeetings = limited.filter((m: any) => m.status === 'completed');
        if (completedMeetings.length > 0) {
          const pvs: Record<string, string> = {};
          await Promise.all(completedMeetings.map(async (m: any) => {
            try {
              const res = await api.get(`/pv/meeting/${m.id}`);
              if (res.data && res.data.id) {
                pvs[m.id] = res.data.id;
              }
            } catch (e) {
              // No PV yet
            }
          }));
          setPvMap(pvs);
        }
      } catch (err) {
        console.error("Failed to fetch initial data", err);
      }
    };
    fetchInitialData();
  }, []);

  // Set default end_time to start_time + 60 mins
  useEffect(() => {
    // This effect is not strictly needed if handleCreate handles it, but let's ensure consistency
  }, []);

  // Debounced search for participants
  useEffect(() => {
    const timer = setTimeout(async () => {
      if (participantSearch.length >= 2) {
        try {
          const results = await teamApi.searchTeam(participantSearch);
          setParticipantResults(results);
        } catch (err) {
          console.error("Participant search failed", err);
        }
      } else {
        setParticipantResults([]);
      }
    }, 300);
    return () => clearTimeout(timer);
  }, [participantSearch]);

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
      // Prepare participants payload
      const participants = selectedParticipants.map((p) => {
        if (typeof p === 'string') return { email: p, name: p, role: "Guest" };
        return { email: p.email, name: p.full_name || p.email, role: p.position || "Participant", user_id: p.source === "user" ? p.id : null };
      });

      // Prepare location payload
      const meetingLocation: { location?: string; room_id?: string } = {};
      if (typeof location === 'string') {
        meetingLocation.location = location;
      } else if (location && location.id) {
        meetingLocation.room_id = location.id;
      }

      // Format start and end times
      const startTime = new Date(`${meetingDate}T${meetingTime}:00`);
      const endTime = new Date(startTime.getTime() + plannedDuration * 60 * 1000);

      const meetingData = {
        title,
        description: "Scheduled via UI",
        status: "planned",
        start_time: startTime.toISOString(),
        end_time: endTime.toISOString(),
        participants,
        agendas: [],
        ...meetingLocation
      };

      const newMeeting = await meetingsApi.createMeeting(meetingData);
      navigate(`/meetings/live/${newMeeting.id}`);
    } catch (error: any) {
      console.error("Failed to create meeting", error);
      const errorMsg = error.response?.data?.detail || error.message || "Unknown error";
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
              <TextField fullWidth label={t("meetings.title")} value={title} onChange={(e) => setTitle(e.target.value)} />

              <Box>
                <Grid container spacing={2}>
                  <Grid item xs={12} sm={4}>
                    <TextField fullWidth type="date" label={t("meetings.date")} value={meetingDate} onChange={(e) => setMeetingDate(e.target.value)} InputLabelProps={{ shrink: true }} />
                  </Grid>
                  <Grid item xs={12} sm={4}>
                    <TextField fullWidth type="time" label={t("meetings.time")} value={meetingTime} onChange={(e) => setMeetingTime(e.target.value)} InputLabelProps={{ shrink: true }} />
                  </Grid>
                  <Grid item xs={12} sm={4}>
                    <FormControl fullWidth>
                      <InputLabel id="duration-label">{t("meetings.duration")}</InputLabel>
                      <Select
                        labelId="duration-label"
                        value={plannedDuration}
                        label={t("meetings.duration")}
                        onChange={(e: SelectChangeEvent<number>) => setPlannedDuration(e.target.value as number)}
                      >
                        <MenuItem value={30}>30 min</MenuItem>
                        <MenuItem value={60}>60 min</MenuItem>
                        <MenuItem value={90}>90 min</MenuItem>
                        <MenuItem value={120}>120 min</MenuItem>
                      </Select>
                    </FormControl>
                  </Grid>
                </Grid>
                {holidayWarning && (
                  <Alert severity="warning" icon={<WarningIcon />} sx={{ mt: 1 }}>{t("meetings.holiday_warning")} {holidayWarning}</Alert>
                )}
              </Box>

              <Autocomplete
                freeSolo
                options={availableRooms}
                getOptionLabel={(option) => (typeof option === 'string' ? option : option.name)}
                value={location}
                onChange={(event, newValue) => setLocation(newValue)}
                renderInput={(params) => (
                  <TextField
                    {...params}
                    label={t("meetings.location")}
                    placeholder={t("meetings.location_placeholder")}
                  />
                )}
              />

              <Autocomplete
                multiple
                freeSolo
                options={participantResults}
                getOptionLabel={(option) => (typeof option === 'string' ? option : `${option.full_name} (${option.email})`)}
                value={selectedParticipants}
                onInputChange={(event, newInputValue) => setParticipantSearch(newInputValue)}
                onChange={(event, newValue) => setSelectedParticipants(newValue)}
                renderTags={(value, getTagProps) =>
                  value.map((option, index) => (
                    <Chip variant="outlined" color="primary" label={typeof option === 'string' ? option : option.full_name} {...getTagProps({ index })} />
                  ))
                }
                renderInput={(params) => (
                  <TextField {...params} label={t("meetings.participants")} placeholder={t("common.search")} />
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
            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1 }}>
              <Typography variant="subtitle1" sx={{ fontWeight: 'bold', display: 'flex', alignItems: 'center' }}>
                <MeetingRoomIcon sx={{ mr: 1, color: 'primary.main' }} />
                {t("meetings.recent_meetings")}
              </Typography>
              
              <FormControl size="small" sx={{ minWidth: 100 }}>
                <Select
                  value={exportLanguage}
                  onChange={(e) => setExportLanguage(e.target.value)}
                  variant="standard"
                  sx={{ fontSize: '0.8rem' }}
                >
                  <MenuItem value="ar">العربية</MenuItem>
                  <MenuItem value="fr">Français</MenuItem>
                  <MenuItem value="en">English</MenuItem>
                </Select>
              </FormControl>
            </Box>
            
            <Divider sx={{ mb: 1 }} />
            {recentMeetings.length === 0 ? (
              <Typography variant="body2" color="text.secondary" sx={{ p: 2, textAlign: 'center' }}>
                {t("meetings.no_recent_meetings")}
              </Typography>
            ) : (
              <List dense>
                {recentMeetings.map((meeting) => (
                  <ListItem 
                    disablePadding 
                    key={meeting.id}
                    secondaryAction={
                      pvMap[meeting.id] && (
                        <Stack direction="row" spacing={1}>
                          <IconButton 
                            size="small" 
                            color="primary" 
                            component={Link}
                            to={`/editor/${pvMap[meeting.id]}?lang=${exportLanguage}`}
                            target="_blank"
                            title={t("pv.edit_online")}
                          >
                            <EditIcon fontSize="small" />
                          </IconButton>
                          <DocumentExportMenu 
                            pvId={pvMap[meeting.id]} 
                            language={exportLanguage} 
                            variant="text" 
                            showDocx={false}
                          />
                        </Stack>
                      )
                    }
                  >
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

