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
  SelectChangeEvent,
  IconButton,
  alpha
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
      const participants = selectedParticipants.map((p) => {
        if (typeof p === 'string') return { email: p, name: p, role: "Guest" };
        return { email: p.email, name: p.full_name || p.email, role: p.position || "Participant", user_id: p.source === "user" ? p.id : null };
      });

      const meetingLocation: { location?: string; room_id?: string } = {};
      if (typeof location === 'string') {
        meetingLocation.location = location;
      } else if (location && location.id) {
        meetingLocation.room_id = location.id;
      }

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
      
      // Smart Navigation Logic
      const now = new Date();
      const timeDiffMinutes = (startTime.getTime() - now.getTime()) / (1000 * 60);
      
      if (timeDiffMinutes <= 15) {
        // Meeting is happening now or very soon -> jump to live room
        navigate(`/meetings/live/${newMeeting.id}`);
      } else {
        // Meeting is in the future -> stay on page, reset form, show success
        alert(t("meetings.created_success") || "Meeting successfully scheduled for the future.");
        setTitle("");
        setSelectedParticipants([]);
        setLocation(null);
        // Refresh the list
        const meetingsData = await meetingsApi.getMeetings();
        setRecentMeetings(meetingsData.sort((a: any, b: any) => new Date(b.start_time).getTime() - new Date(a.start_time).getTime()).slice(0, 10));
      }
    } catch (error: any) {
      console.error("Failed to create meeting", error);
      alert(`Error creating meeting: ${error.response?.data?.detail || error.message || "Unknown error"}`);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleCancelMeeting = async (e: React.MouseEvent, id: string) => {
    e.preventDefault();
    e.stopPropagation();
    if (window.confirm("Are you sure you want to cancel this meeting?")) {
      try {
        await api.patch(`/meetings/${id}/cancel`);
        alert("Meeting successfully cancelled.");
        const meetingsData = await meetingsApi.getMeetings();
        setRecentMeetings(meetingsData.sort((a: any, b: any) => new Date(b.start_time).getTime() - new Date(a.start_time).getTime()).slice(0, 10));
      } catch (err: any) {
        console.error("Failed to cancel", err);
        alert(err.response?.data?.detail || "Failed to cancel meeting.");
      }
    }
  };

  return (
    <Box sx={{ p: { xs: 2, md: 6 }, maxWidth: 1400, mx: "auto" }}>
      
      {/* HEADER */}
      <Typography sx={{ fontSize: 18, fontWeight: 600, color: "text.primary", mb: 4 }}>
        {t("meetings.planner_title")}
      </Typography>

      <Grid container spacing={4}>
        
        {/* LEFT: SCHEDULE FORM */}
        <Grid item xs={12} md={7}>
          <Paper variant="outlined" sx={{ p: 3, borderRadius: 3, borderColor: "divider" }}>
            <Stack spacing={4}>
              <Typography sx={{ fontSize: 16, fontWeight: 600, color: "text.primary" }}>
                {t("meetings.new_meeting")}
              </Typography>

              <Stack spacing={3}>
                <TextField 
                  fullWidth 
                  label={t("meetings.title")} 
                  variant="outlined"
                  value={title} 
                  onChange={(e) => setTitle(e.target.value)}
                  InputProps={{ sx: { borderRadius: 2 } }}
                  InputLabelProps={{ sx: { fontSize: 14 } }}
                />

                <Box>
                  <Grid container spacing={2}>
                    <Grid item xs={12} sm={4}>
                      <TextField 
                        fullWidth 
                        type="date" 
                        label={t("meetings.date")} 
                        value={meetingDate} 
                        onChange={(e) => setMeetingDate(e.target.value)} 
                        InputLabelProps={{ shrink: true, sx: { fontSize: 14 } }}
                        InputProps={{ sx: { borderRadius: 2 } }}
                      />
                    </Grid>
                    <Grid item xs={12} sm={4}>
                      <TextField 
                        fullWidth 
                        type="time" 
                        label={t("meetings.time")} 
                        value={meetingTime} 
                        onChange={(e) => setMeetingTime(e.target.value)} 
                        InputLabelProps={{ shrink: true, sx: { fontSize: 14 } }}
                        InputProps={{ sx: { borderRadius: 2 } }}
                      />
                    </Grid>
                    <Grid item xs={12} sm={4}>
                      <FormControl fullWidth>
                        <InputLabel id="duration-label" sx={{ fontSize: 14 }}>{t("meetings.duration")}</InputLabel>
                        <Select
                          labelId="duration-label"
                          value={plannedDuration}
                          label={t("meetings.duration")}
                          onChange={(e: SelectChangeEvent<number>) => setPlannedDuration(e.target.value as number)}
                          sx={{ borderRadius: 2 }}
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
                    <Alert severity="warning" icon={<WarningIcon />} sx={{ mt: 2, borderRadius: 2, fontSize: 13 }}>
                      {t("meetings.holiday_warning")} {holidayWarning}
                    </Alert>
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
                      InputLabelProps={{ sx: { fontSize: 14 } }}
                      InputProps={{ ...params.InputProps, sx: { borderRadius: 2 } }}
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
                      <Chip 
                        variant="outlined" 
                        label={typeof option === 'string' ? option : option.full_name} 
                        {...getTagProps({ index })} 
                        sx={{ borderRadius: 1, fontSize: 12, fontWeight: 500 }}
                      />
                    ))
                  }
                  renderInput={(params) => (
                    <TextField 
                      {...params} 
                      label={t("meetings.participants")} 
                      placeholder={t("common.search")} 
                      InputLabelProps={{ sx: { fontSize: 14 } }}
                      InputProps={{ ...params.InputProps, sx: { borderRadius: 2 } }}
                    />
                  )}
                />

                <Button
                  variant="contained"
                  disableElevation
                  fullWidth
                  disabled={!!holidayWarning || !title || isSubmitting}
                  onClick={handleCreate}
                  sx={{ 
                    bgcolor: "#000", 
                    color: "#FFF", 
                    py: 1.5, 
                    borderRadius: 2, 
                    textTransform: "none",
                    fontSize: 14,
                    fontWeight: 600,
                    "&:hover": { bgcolor: "#27272A" }
                  }}
                >
                  {t("meetings.create")}
                </Button>
              </Stack>
            </Stack>
          </Paper>
        </Grid>
        
        {/* RIGHT: SIDEBAR */}
        <Grid item xs={12} md={5}>
          <Stack spacing={4}>
            
            {/* Recent Meetings */}
            <Paper variant="outlined" sx={{ borderRadius: 3, overflow: "hidden", borderColor: "divider" }}>
              <Box sx={{ px: 3, py: 2, borderBottom: "1px solid", borderColor: "divider", display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <Typography sx={{ fontSize: 15, fontWeight: 600 }}>
                  {t("meetings.recent_meetings")}
                </Typography>
                
                <FormControl size="small" variant="standard">
                  <Select
                    value={exportLanguage}
                    onChange={(e) => setExportLanguage(e.target.value)}
                    sx={{ fontSize: '12px', fontWeight: 600 }}
                  >
                    <MenuItem value="ar">AR</MenuItem>
                    <MenuItem value="fr">FR</MenuItem>
                    <MenuItem value="en">EN</MenuItem>
                  </Select>
                </FormControl>
              </Box>
              
              <Box>
                {recentMeetings.length === 0 ? (
                  <Box sx={{ p: 4, textAlign: 'center' }}>
                    <Typography sx={{ fontSize: 13, color: "text.secondary" }}>
                      {t("meetings.no_recent_meetings")}
                    </Typography>
                  </Box>
                ) : (
                  <List disablePadding>
                    {recentMeetings.map((meeting) => {
                      const now = new Date();
                      const mStartTime = new Date(meeting.start_time);
                      const mEndTime = meeting.end_time ? new Date(meeting.end_time) : new Date(mStartTime.getTime() + 60 * 60 * 1000); // Default 1h if no end_time
                      
                      const timeDiffMins = (mStartTime.getTime() - now.getTime()) / (1000 * 60);
                      const isJoinable = meeting.status === 'planned' && timeDiffMins <= 15 && now < mEndTime;
                      const isExpired = meeting.status === 'planned' && now > mEndTime;
                      
                      // Derive display status
                      let displayStatus = meeting.status;
                      if (isExpired) displayStatus = 'expired';

                      return (
                        <ListItem 
                          key={meeting.id}
                          divider
                          sx={{ 
                            px: 3, py: 2.5, 
                            display: 'flex', 
                            flexDirection: 'column', 
                            alignItems: 'stretch',
                            "&:hover": { bgcolor: alpha("#000", 0.01) } 
                          }}
                        >
                          {/* Top Row: Title & Status */}
                          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', mb: 0.5 }}>
                            <Typography sx={{ fontSize: 14, fontWeight: 600, color: isExpired ? "text.secondary" : "#000", textDecoration: isExpired ? "line-through" : "none" }}>
                              {meeting.title}
                            </Typography>
                            <Chip 
                              label={displayStatus} 
                              size="small" 
                              variant="outlined" 
                              sx={{ 
                                height: 20, 
                                fontSize: 10, 
                                fontWeight: 700, 
                                textTransform: "uppercase",
                                borderColor: displayStatus === 'completed' ? alpha("#10B981", 0.3) : displayStatus === 'planned' ? alpha("#F59E0B", 0.3) : displayStatus === 'expired' ? alpha("#EF4444", 0.3) : "divider",
                                color: displayStatus === 'completed' ? "#10B981" : displayStatus === 'planned' ? "#F59E0B" : displayStatus === 'expired' ? "#EF4444" : "text.secondary"
                              }} 
                            />
                          </Box>

                          {/* Sub Row: Date */}
                          <Typography sx={{ fontSize: 12, color: "#71717A", mb: 2 }}>
                            {mStartTime.toLocaleString(undefined, { dateStyle: 'short', timeStyle: 'short' })}
                          </Typography>

                          {/* Bottom Row: Actions */}
                          <Stack direction="row" spacing={1} justifyContent="flex-end">
                            {meeting.status === 'planned' && (
                              <>
                                <Button 
                                  size="small" 
                                  variant="text" 
                                  color="error"
                                  onClick={(e) => handleCancelMeeting(e, meeting.id)}
                                  sx={{ textTransform: 'none', fontSize: 12, fontWeight: 500, minWidth: 0, px: 1 }}
                                >
                                  {isExpired ? t('common.delete', 'Delete') : t('common.cancel', 'Cancel')}
                                </Button>
                                
                                {!isExpired && (
                                  <>
                                    {/* Force Start Button (Always available for planned meetings) */}
                                    <Button 
                                      size="small" 
                                      variant="outlined"
                                      onClick={(e) => { e.preventDefault(); e.stopPropagation(); navigate(`/meetings/live/${meeting.id}`); }}
                                      sx={{ 
                                        textTransform: 'none', borderRadius: 1.5, fontSize: 12, fontWeight: 600, px: 2,
                                        borderColor: "divider", color: "text.primary",
                                        "&:hover": { bgcolor: alpha("#000", 0.05) }
                                      }}
                                    >
                                      {t('meetings.start_now', 'Start Now')}
                                    </Button>

                                    {/* Conditional Join Button (Green when time is close) */}
                                    <Button 
                                      size="small" 
                                      variant={isJoinable ? "contained" : "outlined"}
                                      disabled={!isJoinable}
                                      onClick={(e) => { e.preventDefault(); e.stopPropagation(); navigate(`/meetings/live/${meeting.id}`); }}
                                      sx={{ 
                                        textTransform: 'none', borderRadius: 1.5, fontSize: 12, fontWeight: 600, px: 2,
                                        ...(isJoinable ? { bgcolor: "#10B981", color: "#FFF", "&:hover": { bgcolor: "#059669" }, boxShadow: "none" } : { borderColor: "divider", color: "#A1A1AA" })
                                      }}
                                    >
                                      {isJoinable ? t('meetings.join_room', 'Join Room') : t('meetings.scheduled', 'Scheduled')}
                                    </Button>
                                  </>
                                )}
                              </>
                            )}

                            {pvMap[meeting.id] && (
                              <>
                                <Button
                                  size="small"
                                  variant="outlined"
                                  startIcon={<EditIcon sx={{ fontSize: 14 }} />}
                                  onClick={() => window.open(`/editor/${pvMap[meeting.id]}?lang=${exportLanguage}`, '_blank')}
                                  sx={{ textTransform: 'none', borderRadius: 1.5, fontSize: 12, fontWeight: 500, borderColor: 'divider', color: '#000' }}
                                >
                                  {t("pv.edit_online")}
                                </Button>
                                <DocumentExportMenu 
                                  pvId={pvMap[meeting.id]} 
                                  language={exportLanguage} 
                                  variant="text" 
                                  showDocx={false}
                                />
                              </>
                            )}

                            {meeting.status === 'in_progress' && (
                              <Button 
                                size="small" 
                                variant="contained" 
                                color="primary"
                                onClick={() => navigate(`/meetings/live/${meeting.id}`)}
                                sx={{ textTransform: 'none', borderRadius: 1.5, fontSize: 12, fontWeight: 600, bgcolor: "#3B82F6" }}
                              >
                                {t('meetings.join_room', 'Join Live')}
                              </Button>
                            )}
                          </Stack>
                        </ListItem>
                      );
                    })}
                  </List>
                )}
              </Box>
            </Paper>

            {/* Cultural Calendar */}
            <Paper variant="outlined" sx={{ p: 3, borderRadius: 3, borderColor: "divider" }}>
              <Typography sx={{ fontSize: 15, fontWeight: 600, mb: 2 }}>
                {t("meetings.upcoming_holidays")}
              </Typography>
              <Stack spacing={2}>
                {holidays.map((h, i) => (
                  <Box key={i} sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <Box>
                      <Typography sx={{ fontSize: 14, fontWeight: 500 }}>{h.name}</Typography>
                      <Typography sx={{ fontSize: 12, color: "text.secondary" }}>{h.date}</Typography>
                    </Box>
                    <Chip
                      label={t("meetings.holiday")}
                      size="small"
                      variant="outlined"
                      sx={{ 
                        height: 20, 
                        fontSize: 10, 
                        fontWeight: 700, 
                        color: "#EF4444", 
                        borderColor: alpha("#EF4444", 0.3),
                        textTransform: "uppercase" 
                      }}
                    />
                  </Box>
                ))}
              </Stack>
            </Paper>
          </Stack>
        </Grid>
      </Grid>
    </Box>
  );
};

export default MeetingPlanner;

