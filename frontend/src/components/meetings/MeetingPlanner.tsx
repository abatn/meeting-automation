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
  Chip,
  Alert,
  Stack,
  Select,
  InputLabel,
  FormControl,
  Divider,
  Autocomplete,
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
  const { t, i18n } = useTranslation();
  const navigate = useNavigate();
  const { isHoliday, getHolidayName } = useCulturalCalendar();

  const [title, setTitle] = useState("");
  const [meetingDate, setMeetingDate] = useState(new Date().toISOString().split('T')[0]);
  const [meetingTime, setMeetingTime] = useState("10:00");
  const [plannedDuration, setPlannedDuration] = useState(60);
  const [location, setLocation] = useState<any>(null);
  const [selectedParticipants, setSelectedParticipants] = useState<any[]>([]);

  const [participantSearch, setParticipantSearch] = useState("");
  const [participantResults, setParticipantResults] = useState<any[]>([]);

  const [availableUsers, setAvailableUsers] = useState<any[]>([]);
  const [availableRooms, setAvailableRooms] = useState<any[]>([]);
  const [recentMeetings, setRecentMeetings] = useState<any[]>([]);
  const [pvMap, setPvMap] = useState<{ [key: string]: string }>({});
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [exportLanguage, setExportLanguage] = useState<string>(i18n.language.split('-')[0] || "fr");

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [users, rooms, meetings] = await Promise.all([
          meetingsApi.getUsers(),
          roomsApi.getRooms(),
          meetingsApi.getMeetings(),
        ]);
        setAvailableUsers(users);
        setAvailableRooms(rooms);
        
        // Professional Filtering & Sorting Logic
        const filtered = meetings.filter((m: any) => {
          const now = new Date();
          const mEndTime = m.end_time ? new Date(m.end_time) : new Date(new Date(m.start_time).getTime() + 60 * 60 * 1000);
          const isExpired = m.status === 'planned' && now > mEndTime;
          
          // Only show what's relevant for daily operations
          return m.status !== 'cancelled' && !isExpired;
        });

        const sorted = filtered.sort((a: any, b: any) => {
          // 1. Live meetings always at the very top
          if (a.status === 'in_progress' && b.status !== 'in_progress') return -1;
          if (b.status === 'in_progress' && a.status !== 'in_progress') return 1;
          
          // 2. Completed meetings always at the bottom
          if (a.status === 'completed' && b.status !== 'completed') return 1;
          if (b.status === 'completed' && a.status !== 'completed') return -1;
          
          // 3. Planned meetings: Show the NEXT meeting first (Ascending start_time)
          return new Date(a.start_time).getTime() - new Date(b.start_time).getTime();
        }).slice(0, 8); 

        setRecentMeetings(sorted);

        const pvs: { [key: string]: string } = {};
        await Promise.all(sorted.map(async (m: any) => {
          if (m.status === 'completed') {
            try {
              const pvRes = await api.get(`/pv/meeting/${m.id}`);
              if (pvRes.data) pvs[m.id] = pvRes.data.id;
            } catch (e) {}
          }
        }));
        setPvMap(pvs);
      } catch (error) {
        console.error("Initialization error", error);
      }
    };
    fetchData();
  }, []);

  
  // Live Search for Team Directory
  useEffect(() => {
    const fetchParticipants = async () => {
      if (participantSearch.length > 1) {
        try {
          const results = await teamApi.searchTeam(participantSearch);
          setParticipantResults(results);
        } catch (error) {
          console.error("Search error", error);
        }
      } else {
        setParticipantResults([]);
      }
    };
    
    const timeoutId = setTimeout(() => {
      fetchParticipants();
    }, 300); // Debounce
    
    return () => clearTimeout(timeoutId);
  }, [participantSearch]);

  const handleCreate = async () => {
    if (!title || !!holidayWarning) return;
    setIsSubmitting(true);
    try {
      const participants = selectedParticipants.map((p) => {
        if (typeof p === 'string') return { email: p, name: p, role: "Guest" };
        return { email: p.email, name: p.full_name || p.email, role: p.position || "Participant", user_id: p.source === "user" ? p.id : null };
      });

      const meetingLocation: { location?: string; room_id?: string } = {};
      if (typeof location === 'string') meetingLocation.location = location;
      else if (location && location.id) meetingLocation.room_id = location.id;

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
      
      const now = new Date();
      const timeDiffMinutes = (startTime.getTime() - now.getTime()) / (1000 * 60);
      
      if (timeDiffMinutes <= 15) {
        navigate(`/meetings/live/${newMeeting.id}`);
      } else {
        alert(t("meetings.created_success"));
        setTitle("");
        setSelectedParticipants([]);
        setLocation(null);
        const meetingsData = await meetingsApi.getMeetings();
        setRecentMeetings(meetingsData.sort((a: any, b: any) => new Date(b.start_time).getTime() - new Date(a.start_time).getTime()).slice(0, 10));
      }
    } catch (error: any) {
      console.error("Create error", error);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleCancelMeeting = async (e: React.MouseEvent, id: string) => {
    e.preventDefault(); e.stopPropagation();
    if (window.confirm("Are you sure?")) {
      try {
        await api.patch(`/meetings/${id}/cancel`);
        alert("Meeting cancelled.");
        const meetingsData = await meetingsApi.getMeetings();
        setRecentMeetings(meetingsData.sort((a: any, b: any) => new Date(b.start_time).getTime() - new Date(a.start_time).getTime()).slice(0, 10));
      } catch (err) {}
    }
  };

  
  const holidays = [
    { date: "2026-03-20", name: t("meetings.holiday_independence") },
    { date: "2026-04-09", name: t("meetings.holiday_martyrs") },
  ];

  const holidayWarning = isHoliday(meetingDate) ? getHolidayName(meetingDate) : null;


  return (
    <Box sx={{ p: { xs: 2, md: 6 }, maxWidth: 1400, mx: "auto" }}>
      <Typography sx={{ fontSize: 18, fontWeight: 600, color: "text.primary", mb: 4 }}>
        {t("meetings.planner_title")}
      </Typography>

      <Grid container spacing={4}>
        <Grid item xs={12} md={7}>
          <Paper variant="outlined" sx={{ p: 3, borderRadius: 3, borderColor: "divider" }}>
            <Stack spacing={4}>
              <Typography sx={{ fontSize: 16, fontWeight: 600 }}>{t("meetings.new_meeting")}</Typography>
              <Stack spacing={3}>
                <TextField fullWidth label={t("meetings.title")} value={title} onChange={(e) => setTitle(e.target.value)} InputProps={{ sx: { borderRadius: 2 } }} />
                {holidayWarning && (
                  <Alert severity="warning" icon={<WarningIcon />} sx={{ mt: 1, borderRadius: 2 }}>
                    {t("meetings.holiday_warning")} {holidayWarning}
                  </Alert>
                )}

                <Grid container spacing={2}>
                  <Grid item xs={12} sm={4}>
                    <TextField fullWidth type="date" label={t("meetings.date")} value={meetingDate} onChange={(e) => setMeetingDate(e.target.value)} InputLabelProps={{ shrink: true }} InputProps={{ sx: { borderRadius: 2 } }} />
                  </Grid>
                  <Grid item xs={12} sm={4}>
                    <TextField fullWidth type="time" label={t("meetings.time")} value={meetingTime} onChange={(e) => setMeetingTime(e.target.value)} InputLabelProps={{ shrink: true }} InputProps={{ sx: { borderRadius: 2 } }} />
                  </Grid>
                  <Grid item xs={12} sm={4}>
                    <FormControl fullWidth>
                      <InputLabel shrink>{t("meetings.duration")}</InputLabel>
                      <Select value={plannedDuration} onChange={(e) => setPlannedDuration(Number(e.target.value))} label={t("meetings.duration")} sx={{ borderRadius: 2 }}>
                        <MenuItem value={30}>30 min</MenuItem>
                        <MenuItem value={60}>1 hour</MenuItem>
                        <MenuItem value={90}>1.5 hours</MenuItem>
                        <MenuItem value={120}>2 hours</MenuItem>
                      </Select>
                    </FormControl>
                  </Grid>
                </Grid>

                <Autocomplete
                  freeSolo
                  options={availableRooms}
                  getOptionLabel={(option) => typeof option === 'string' ? option : option.name}
                  value={location}
                  onChange={(_, val) => setLocation(val)}
                  renderInput={(params) => <TextField {...params} label={t("meetings.location")} InputProps={{ ...params.InputProps, sx: { borderRadius: 2 } }} />}
                />

                <Autocomplete
                  multiple
                  freeSolo
                  options={participantResults}
                  getOptionLabel={(option) => (typeof option === 'string' ? option : `${option.full_name} (${option.email})`)}
                  value={selectedParticipants}
                  onInputChange={(_, newInputValue) => setParticipantSearch(newInputValue)}
                  onChange={(_, newValue) => setSelectedParticipants(newValue)}
                  renderTags={(value, getTagProps) =>
                    value.map((option, index) => (
                      <Chip 
                        size="small"
                        variant="outlined" 
                        label={typeof option === 'string' ? option : option.full_name} 
                        {...getTagProps({ index })} 
                        sx={{ borderRadius: 1.5, fontWeight: 600, bgcolor: "background.paper" }}
                      />
                    ))
                  }
                  renderInput={(params) => (
                    <TextField {...params} label={t("meetings.participants")} placeholder={t("common.search")} InputProps={{ ...params.InputProps, sx: { borderRadius: 2 } }} />
                  )}
                />

                <Button fullWidth variant="contained" disabled={isSubmitting || !title} onClick={handleCreate} sx={{ bgcolor: "#000", color: "#FFF", py: 1.5, borderRadius: 2, fontWeight: 600, "&:hover": { bgcolor: "#27272A" } }}>
                  {t("meetings.create")}
                </Button>
              </Stack>
            </Stack>
          </Paper>
        </Grid>
        
        <Grid item xs={12} md={5}>
          <Stack spacing={4}>
            <Paper variant="outlined" sx={{ borderRadius: 3, overflow: "hidden" }}>
              <Box sx={{ px: 3, py: 2, borderBottom: "1px solid", borderColor: "divider", display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <Typography sx={{ fontSize: 15, fontWeight: 600 }}>{t("meetings.recent_meetings")}</Typography>
              </Box>
              
              <List disablePadding>
                {recentMeetings.map((meeting) => {
                  const now = new Date();
                  const mStartTime = new Date(meeting.start_time);
                  const mEndTime = meeting.end_time ? new Date(meeting.end_time) : new Date(mStartTime.getTime() + 60 * 60 * 1000);
                  
                  const isUpcoming = now < mStartTime;
                  const isLate = now >= mStartTime && now < mEndTime;
                  const isExpired = now >= mEndTime;
                  
                  const isJoinableWindow = (mStartTime.getTime() - now.getTime()) / 60000 <= 15;
                  
                  let displayStatus = meeting.status;
                  if (meeting.status === 'planned') {
                    if (isExpired) displayStatus = 'expired';
                    else if (isLate) displayStatus = 'late';
                  }

                  return (
                    <ListItem key={meeting.id} divider sx={{ px: 3, py: 2, display: 'flex', flexDirection: 'column', alignItems: 'stretch' }}>
                      <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 0.5 }}>
                        <Typography sx={{ fontSize: 14, fontWeight: 600, textDecoration: isExpired ? "line-through" : "none" }}>{meeting.title}</Typography>
                        <Chip label={t(`meetings.${displayStatus}`) || displayStatus} size="small" variant="outlined" sx={{ height: 20, fontSize: 10, fontWeight: 700, textTransform: "uppercase" }} />
                      </Box>
                      <Typography sx={{ fontSize: 12, color: "#71717A", mb: 2 }}>{mStartTime.toLocaleString(undefined, { dateStyle: 'short', timeStyle: 'short' })}</Typography>

                      <Stack direction="row" spacing={1} justifyContent="flex-end">
                        {meeting.status === 'planned' && (
                          <>
                            <Button size="small" variant="text" color="error" onClick={(e) => handleCancelMeeting(e, meeting.id)} sx={{ textTransform: 'none', fontSize: 12 }}>
                              {isExpired ? t('common.delete') : t('common.cancel')}
                            </Button>
                            
                            {isUpcoming && (
                              <Button size="small" variant="outlined" onClick={() => navigate(`/meetings/live/${meeting.id}`)} sx={{ textTransform: 'none', borderRadius: 1.5, fontSize: 12, fontWeight: 600 }}>
                                {t('meetings.start_now')}
                              </Button>
                            )}

                            {!isExpired && (
                              <Button 
                                size="small" 
                                variant={(isJoinableWindow || isLate) ? "contained" : "outlined"}
                                disabled={!isJoinableWindow && !isLate}
                                onClick={() => navigate(`/meetings/live/${meeting.id}`)}
                                sx={{ 
                                  textTransform: 'none', borderRadius: 1.5, fontSize: 12, fontWeight: 600,
                                  ...((isJoinableWindow || isLate) ? { bgcolor: isLate ? "#F44336" : "#10B981", color: "#FFF" } : {})
                                }}
                              >
                                {isLate ? t('meetings.join_room') : isJoinableWindow ? t('meetings.join_room') : t('meetings.scheduled')}
                              </Button>
                            )}
                          </>
                        )}
                        {pvMap[meeting.id] && (
                          <Button size="small" variant="outlined" startIcon={<EditIcon sx={{ fontSize: 14 }} />} onClick={() => window.open(`/editor/${pvMap[meeting.id]}?lang=${exportLanguage}`, '_blank')} sx={{ textTransform: 'none', borderRadius: 1.5, fontSize: 12 }}>
                            {t("pv.edit_online")}
                          </Button>
                        )}
                        {meeting.status === 'in_progress' && (
                          <Button size="small" variant="contained" color="primary" onClick={() => navigate(`/meetings/live/${meeting.id}`)} sx={{ textTransform: 'none', borderRadius: 1.5, fontSize: 12, fontWeight: 600, bgcolor: "#3B82F6" }}>
                            {t('meetings.join_room')}
                          </Button>
                        )}
                      </Stack>
                    </ListItem>
                  );
                })}
              </List>
            </Paper>

            <Paper variant="outlined" sx={{ p: 3, borderRadius: 3 }}>
              <Typography sx={{ fontSize: 15, fontWeight: 600, mb: 2 }}>{t("meetings.upcoming_holidays")}</Typography>
              <Stack spacing={2}>
                {holidays.map((h, i) => (
                  <Box key={i} sx={{ display: 'flex', justifyContent: 'space-between' }}>
                    <Box><Typography sx={{ fontSize: 14, fontWeight: 500 }}>{h.name}</Typography><Typography sx={{ fontSize: 12, color: "#71717A" }}>{h.date}</Typography></Box>
                    <Chip label={t("meetings.holiday")} size="small" variant="outlined" sx={{ color: "#EF4444", borderColor: alpha("#EF4444", 0.3) }} />
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
