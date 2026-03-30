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
  Chip,
  Alert,
  Stack,
  Select,
  InputLabel,
  FormControl,
  Autocomplete,
  useTheme,
  alpha
} from "@mui/material";
import {
  EventNote as EventIcon,
  Warning as WarningIcon,
  Edit as EditIcon,
  Room as RoomIcon,
  Groups as GroupsIcon,
  Schedule as ScheduleIcon,
} from "@mui/icons-material";
import { useTranslation } from "react-i18next";
import { DatePicker, TimePicker } from "@mui/x-date-pickers";
import { LocalizationProvider } from "@mui/x-date-pickers/LocalizationProvider";
import { AdapterDayjs } from "@mui/x-date-pickers/AdapterDayjs";
import dayjs from "dayjs";
import "dayjs/locale/ar-tn";
import "dayjs/locale/fr";

import { useCulturalCalendar } from "../../hooks/useCulturalCalendar";
import { meetingsApi } from "../../services/meetings";
import { teamApi } from "../../services/team";
import { roomsApi } from "../../services/rooms";
import api from "../../services/api";

const MeetingPlanner: React.FC = () => {
  const { t, i18n } = useTranslation();
  const theme = useTheme();
  const navigate = useNavigate();
  const { isHoliday, getHolidayName } = useCulturalCalendar();

  // Set dayjs locale based on i18n
  const currentLang = i18n.language.split("-")[0];
  const dayjsLocale = i18n.language === "ar-TN" ? "ar-tn" : currentLang;

  const [title, setTitle] = useState("");
  const [meetingDate, setMeetingDate] = useState<dayjs.Dayjs | null>(dayjs());
  const [meetingTime, setMeetingTime] = useState<dayjs.Dayjs | null>(dayjs().set('hour', 10).set('minute', 0));
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
  const [exportLanguage] = useState<string>(i18n.language.split('-')[0] || "fr");

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
        
        const filtered = meetings.filter((m: any) => {
          const now = new Date();
          const mEndTime = m.end_time ? new Date(m.end_time) : new Date(new Date(m.start_time).getTime() + 60 * 60 * 1000);
          const isExpired = m.status === 'planned' && now > mEndTime;
          return m.status !== 'cancelled' && !isExpired;
        });

        const sorted = filtered.sort((a: any, b: any) => {
          if (a.status === 'in_progress' && b.status !== 'in_progress') return -1;
          if (b.status === 'in_progress' && a.status !== 'in_progress') return 1;
          if (a.status === 'completed' && b.status !== 'completed') return 1;
          if (b.status === 'completed' && a.status !== 'completed') return -1;
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
    const timeoutId = setTimeout(fetchParticipants, 300);
    return () => clearTimeout(timeoutId);
  }, [participantSearch]);

  const handleCreate = async () => {
    if (!title || !meetingDate || !meetingTime || !!holidayWarning) return;
    setIsSubmitting(true);
    try {
      const participants = selectedParticipants.map((p) => {
        if (typeof p === 'string') return { email: p, name: p, role: "Guest" };
        return { email: p.email, name: p.full_name || p.email, role: p.position || "Participant", user_id: p.source === "user" ? p.id : null };
      });

      const meetingLocation: { location?: string; room_id?: string } = {};
      if (typeof location === 'string') meetingLocation.location = location;
      else if (location && location.id) meetingLocation.room_id = location.id;

      const combinedStart = meetingDate.hour(meetingTime.hour()).minute(meetingTime.minute()).second(0);
      const combinedEnd = combinedStart.add(plannedDuration, 'minute');

      const meetingData = {
        title,
        description: "Scheduled via UI",
        status: "planned",
        start_time: combinedStart.toISOString(),
        end_time: combinedEnd.toISOString(),
        participants,
        agendas: [],
        ...meetingLocation
      };

      const newMeeting = await meetingsApi.createMeeting(meetingData);
      const now = dayjs();
      const timeDiffMinutes = combinedStart.diff(now, 'minute');
      
      if (timeDiffMinutes <= 15 && timeDiffMinutes >= -60) {
        navigate(`/meetings/live/${newMeeting.id}`);
      } else {
        alert(t("meetings.created_success"));
        setTitle("");
        setSelectedParticipants([]);
        setLocation(null);
        // Refresh local list
        const meetingsData = await meetingsApi.getMeetings();
        setRecentMeetings(meetingsData.sort((a: any, b: any) => new Date(b.start_time).getTime() - new Date(a.start_time).getTime()).slice(0, 8));
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
        const meetingsData = await meetingsApi.getMeetings();
        setRecentMeetings(meetingsData.slice(0, 8));
      } catch (err) {}
    }
  };

  const holidayWarning = meetingDate && isHoliday(meetingDate.format('YYYY-MM-DD')) 
    ? getHolidayName(meetingDate.format('YYYY-MM-DD')) 
    : null;

  const glassStyle = {
    p: { xs: 2.5, md: 4 },
    borderRadius: "24px",
    background: theme.palette.mode === 'dark' 
      ? alpha(theme.palette.background.paper, 0.05) 
      : alpha(theme.palette.background.paper, 0.8),
    backdropFilter: "blur(16px)",
    border: `1px solid ${theme.palette.mode === 'dark' 
      ? 'rgba(255, 255, 255, 0.08)' 
      : 'rgba(0, 0, 0, 0.05)'}`,
    boxShadow: "none",
  };

  const inputStyles = {
    "& .MuiOutlinedInput-root": {
      borderRadius: '12px',
      bgcolor: theme.palette.mode === 'dark' ? alpha('#FFF', 0.02) : '#FFF',
      transition: 'all 0.2s',
      "&:hover": { bgcolor: theme.palette.mode === 'dark' ? alpha('#FFF', 0.04) : alpha('#000', 0.01) },
      "&.Mui-focused": { bgcolor: theme.palette.mode === 'dark' ? alpha('#FFF', 0.04) : '#FFF' }
    }
  };

  return (
    <LocalizationProvider dateAdapter={AdapterDayjs} adapterLocale={dayjsLocale}>
      <Box sx={{ p: { xs: 2, md: 4 }, maxWidth: 1200, mx: "auto" }}>
        <Typography 
          variant="h4" 
          sx={{ 
            fontWeight: 800, 
            mb: 4, 
            letterSpacing: '-0.02em',
            fontSize: { xs: '1.75rem', md: '2.25rem' }
          }}
        >
          {t("meetings.planner_title")}
        </Typography>

        <Grid container spacing={4}>
          {/* FORM SECTION */}
          <Grid item xs={12} md={7}>
            <Paper sx={glassStyle}>
              <Stack spacing={4}>
                <Box>
                  <Typography variant="h6" sx={{ fontWeight: 800, mb: 0.5 }}>{t("meetings.new_meeting")}</Typography>
                  <Typography variant="body2" color="text.secondary">{t("meetings.subtitle") || "Setup your next discussion"}</Typography>
                </Box>

                <Stack spacing={2.5}>
                  <TextField 
                    fullWidth 
                    label={t("meetings.title")} 
                    placeholder={t("meetings.title_placeholder")}
                    value={title} 
                    onChange={(e) => setTitle(e.target.value)} 
                    sx={inputStyles}
                  />

                  {holidayWarning && (
                    <Alert severity="warning" icon={<WarningIcon />} sx={{ borderRadius: '12px' }}>
                      {t("meetings.holiday_warning")} {holidayWarning}
                    </Alert>
                  )}

                  <Grid container spacing={2}>
                    <Grid item xs={12} sm={6}>
                      <DatePicker
                        label={t("meetings.date")}
                        value={meetingDate}
                        onChange={(val) => setMeetingDate(val)}
                        sx={{ width: '100%', ...inputStyles }}
                        slotProps={{ textField: { fullWidth: true } }}
                      />
                    </Grid>
                    <Grid item xs={12} sm={6}>
                      <TimePicker
                        label={t("meetings.time")}
                        value={meetingTime}
                        onChange={(val) => setMeetingTime(val)}
                        sx={{ width: '100%', ...inputStyles }}
                        slotProps={{ textField: { fullWidth: true } }}
                      />
                    </Grid>
                  </Grid>

                  <FormControl fullWidth sx={inputStyles}>
                    <InputLabel id="duration-label">{t("meetings.duration")}</InputLabel>
                    <Select 
                      labelId="duration-label"
                      value={plannedDuration} 
                      onChange={(e) => setPlannedDuration(Number(e.target.value))} 
                      label={t("meetings.duration")}
                    >
                      <MenuItem value={30}>30 min</MenuItem>
                      <MenuItem value={60}>1 hour</MenuItem>
                      <MenuItem value={90}>1.5 hours</MenuItem>
                      <MenuItem value={120}>2 hours</MenuItem>
                    </Select>
                  </FormControl>

                  <Autocomplete
                    freeSolo
                    options={availableRooms}
                    getOptionLabel={(option) => typeof option === 'string' ? option : option.name}
                    value={location}
                    onChange={(_, val) => setLocation(val)}
                    renderInput={(params) => (
                      <TextField 
                        {...params} 
                        label={t("meetings.location")} 
                        placeholder={t("meetings.location_placeholder")}
                        sx={inputStyles} 
                      />
                    )}
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
                          label={typeof option === 'string' ? option : option.full_name} 
                          {...getTagProps({ index })} 
                          sx={{ borderRadius: '8px', fontWeight: 600 }}
                        />
                      ))
                    }
                    renderInput={(params) => (
                      <TextField 
                        {...params} 
                        label={t("meetings.participants")} 
                        placeholder={t("common.search")} 
                        sx={inputStyles} 
                      />
                    )}
                  />

                  <Button 
                    fullWidth 
                    variant="contained" 
                    disabled={isSubmitting || !title} 
                    onClick={handleCreate} 
                    sx={{ 
                      bgcolor: theme.palette.text.primary, 
                      color: theme.palette.background.paper, 
                      py: 1.8, 
                      borderRadius: '14px', 
                      fontWeight: 800, 
                      fontSize: '1rem',
                      textTransform: 'none',
                      boxShadow: '0 8px 20px rgba(0,0,0,0.1)',
                      "&:hover": { bgcolor: alpha(theme.palette.text.primary, 0.8) } 
                    }}
                  >
                    {t("meetings.create")}
                  </Button>
                </Stack>
              </Stack>
            </Paper>
          </Grid>
          
          {/* RECENT / HOLIDAYS SECTION */}
          <Grid item xs={12} md={5}>
            <Stack spacing={4}>
              <Paper sx={{ ...glassStyle, p: 0, overflow: 'hidden' }}>
                <Box sx={{ px: 3, py: 2.5, borderBottom: "1px solid", borderColor: "divider", bgcolor: alpha(theme.palette.text.primary, 0.02) }}>
                  <Typography variant="subtitle1" sx={{ fontWeight: 800 }}>{t("meetings.recent_meetings")}</Typography>
                </Box>
                
                <List disablePadding>
                  {recentMeetings.length === 0 ? (
                    <Box sx={{ p: 4, textAlign: 'center' }}>
                      <Typography variant="body2" color="text.secondary">{t("meetings.no_recent_meetings")}</Typography>
                    </Box>
                  ) : (
                    recentMeetings.map((meeting) => {
                      const mStart = dayjs(meeting.start_time).locale(dayjsLocale);
                      const mEnd = meeting.end_time ? dayjs(meeting.end_time) : mStart.add(1, 'hour');
                      const now = dayjs();
                      
                      const isUpcoming = now.isBefore(mStart);
                      const isLate = now.isAfter(mStart) && now.isBefore(mEnd);
                      const isExpired = now.isAfter(mEnd);
                      const isJoinableWindow = mStart.diff(now, 'minute') <= 15;
                      
                      let displayStatus = meeting.status;
                      if (meeting.status === 'planned') {
                        if (isExpired) displayStatus = 'expired';
                        else if (isLate) displayStatus = 'late';
                      }

                      return (
                        <ListItem key={meeting.id} divider sx={{ px: 3, py: 2.5, display: 'flex', flexDirection: 'column', alignItems: 'stretch' }}>
                          <Stack direction="row" justifyContent="space-between" alignItems="flex-start" sx={{ mb: 1 }}>
                            <Typography sx={{ fontWeight: 700, fontSize: '0.95rem', textDecoration: isExpired ? "line-through" : "none" }}>{meeting.title}</Typography>
                            <Chip 
                              label={t(`meetings.${displayStatus}`) || displayStatus} 
                              size="small" 
                              variant="outlined" 
                              sx={{ 
                                borderRadius: '6px', 
                                fontSize: '0.65rem', 
                                fontWeight: 800, 
                                textTransform: "uppercase",
                                color: displayStatus === 'late' ? 'error.main' : 'text.secondary'
                              }} 
                            />
                          </Stack>
                          
                          <Stack direction="row" spacing={1.5} alignItems="center" sx={{ mb: 2 }}>
                            <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                              <ScheduleIcon sx={{ fontSize: 14, color: 'text.secondary' }} />
                              <Typography variant="caption" sx={{ color: "text.secondary" }}>{mStart.format('LT')}</Typography>
                            </Box>
                            <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                              <RoomIcon sx={{ fontSize: 14, color: 'text.secondary' }} />
                              <Typography variant="caption" sx={{ color: "text.secondary" }}>{meeting.location || "Office"}</Typography>
                            </Box>
                          </Stack>

                          <Stack direction="row" spacing={1} justifyContent="flex-end">
                            {meeting.status === 'planned' && (
                              <Button 
                                size="small" 
                                variant={isJoinableWindow || isLate ? "contained" : "outlined"}
                                disabled={!isJoinableWindow && !isLate && !isUpcoming}
                                onClick={() => navigate(`/meetings/live/${meeting.id}`)}
                                sx={{ 
                                  borderRadius: '10px', 
                                  fontSize: '0.75rem', 
                                  fontWeight: 700,
                                  textTransform: 'none',
                                  ...(isLate ? { bgcolor: 'error.main' } : isJoinableWindow ? { bgcolor: 'success.main' } : {})
                                }}
                              >
                                {isLate ? t('meetings.join_room') : isJoinableWindow ? t('meetings.join_room') : t('meetings.scheduled')}
                              </Button>
                            )}
                            {pvMap[meeting.id] && (
                              <Button 
                                size="small" 
                                variant="outlined" 
                                startIcon={<EditIcon sx={{ fontSize: 14 }} />} 
                                onClick={() => window.open(`/editor/${pvMap[meeting.id]}`, '_blank')}
                                sx={{ borderRadius: '10px', fontSize: '0.75rem', textTransform: 'none' }}
                              >
                                {t("pv.edit_online")}
                              </Button>
                            )}
                            {meeting.status === 'in_progress' && (
                              <Button 
                                size="small" 
                                variant="contained" 
                                onClick={() => navigate(`/meetings/live/${meeting.id}`)}
                                sx={{ borderRadius: '10px', fontSize: '0.75rem', fontWeight: 700, textTransform: 'none', bgcolor: 'primary.main' }}
                              >
                                {t('meetings.join_room')}
                              </Button>
                            )}
                          </Stack>
                        </ListItem>
                      );
                    })
                  )}
                </List>
              </Paper>

              <Paper sx={{ ...glassStyle, p: 3 }}>
                <Stack direction="row" spacing={1.5} alignItems="center" sx={{ mb: 2 }}>
                  <EventIcon color="primary" />
                  <Typography variant="subtitle1" sx={{ fontWeight: 800 }}>{t("meetings.upcoming_holidays")}</Typography>
                </Stack>
                <Stack spacing={2}>
                  {[
                    { date: "2026-03-20", name: t("meetings.holiday_independence") },
                    { date: "2026-04-09", name: t("meetings.holiday_martyrs") },
                  ].map((h, i) => (
                    <Box key={i} sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', p: 1.5, borderRadius: '12px', bgcolor: alpha(theme.palette.error.main, 0.03), border: `1px solid ${alpha(theme.palette.error.main, 0.1)}` }}>
                      <Box>
                        <Typography sx={{ fontSize: '0.9rem', fontWeight: 700 }}>{h.name}</Typography>
                        <Typography variant="caption" sx={{ color: "text.secondary" }}>{dayjs(h.date).locale(dayjsLocale).format('LL')}</Typography>
                      </Box>
                      <Chip label={t("meetings.holiday")} size="small" color="error" variant="soft" sx={{ fontWeight: 800, fontSize: '0.65rem' }} />
                    </Box>
                  ))}
                </Stack>
              </Paper>
            </Stack>
          </Grid>
        </Grid>
      </Box>
    </LocalizationProvider>
  );
};

export default MeetingPlanner;
