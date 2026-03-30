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
  alpha,
} from "@mui/material";
import {
  EventNote as EventIcon,
  Warning as WarningIcon,
  Edit as EditIcon,
  Room as RoomIcon,
  Schedule as ScheduleIcon,
  Delete as DeleteIcon,
  Cancel as CancelIcon,
  PlayArrow as PlayArrowIcon,
} from "@mui/icons-material";
import { useTranslation } from "react-i18next";
import { DatePicker, TimePicker } from "@mui/x-date-pickers";
import { LocalizationProvider } from "@mui/x-date-pickers/LocalizationProvider";
import { AdapterDayjs } from "@mui/x-date-pickers/AdapterDayjs";
import dayjs from "dayjs";
import utc from "dayjs/plugin/utc";
import timezone from "dayjs/plugin/timezone";
import "dayjs/locale/ar-tn";
import "dayjs/locale/fr";

dayjs.extend(utc);
dayjs.extend(timezone);

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

  const dayjsLocale = i18n.language === "ar-TN" ? "ar-tn" : i18n.language.split("-")[0];

  const [title, setTitle] = useState("");
  const [meetingDate, setMeetingDate] = useState<dayjs.Dayjs | null>(dayjs());
  const [meetingTime, setMeetingTime] = useState<dayjs.Dayjs | null>(dayjs());
  const [plannedDuration, setPlannedDuration] = useState(60);
  const [location, setLocation] = useState<any>(null);
  const [selectedParticipants, setSelectedParticipants] = useState<any[]>([]);
  const [participantSearch, setParticipantSearch] = useState("");
  const [participantResults, setParticipantResults] = useState<any[]>([]);
  const [availableRooms, setAvailableRooms] = useState<any[]>([]);
  const [recentMeetings, setRecentMeetings] = useState<any[]>([]);
  const [pvMap, setPvMap] = useState<{ [key: string]: string }>({});
  const [isSubmitting, setIsSubmitting] = useState(false);

  const fetchMeetings = async () => {
    try {
      const meetings = await meetingsApi.getMeetings();
      const now = dayjs();
      
      const sorted = meetings
        .filter((m: any) => m.status !== 'cancelled')
        .sort((a: any, b: any) => {
          const mStartA = dayjs(a.start_time);
          const mEndA = a.end_time ? dayjs(a.end_time) : mStartA.add(1, 'hour');
          const mStartB = dayjs(b.start_time);
          const mEndB = b.end_time ? dayjs(b.end_time) : mStartB.add(1, 'hour');

          const getStatusScore = (m: any, end: dayjs.Dayjs) => {
            if (m.status === 'in_progress') return 0;
            if (m.status === 'planned') return now.isAfter(end) ? 3 : 1;
            return 2;
          };

          const scoreA = getStatusScore(a, mEndA);
          const scoreB = getStatusScore(b, mEndB);
          if (scoreA !== scoreB) return scoreA - scoreB;
          return mStartA.valueOf() - mStartB.valueOf();
        })
        .slice(0, 10);
      setRecentMeetings(sorted);

      const pvs: { [key: string]: string } = {};
      for (const m of sorted) {
        if (m.status === 'completed') {
          try {
            const pvRes = await api.get(`/pv/meeting/${m.id}`);
            if (pvRes.data) pvs[m.id] = pvRes.data.id;
          } catch (e) {}
        }
      }
      setPvMap(pvs);
    } catch (e) { console.error(e); }
  };

  useEffect(() => {
    roomsApi.getRooms().then(setAvailableRooms);
    fetchMeetings();
  }, []);

  useEffect(() => {
    const search = async () => {
      if (participantSearch.length > 1) {
        const res = await teamApi.searchTeam(participantSearch);
        setParticipantResults(res);
      }
    };
    const timer = setTimeout(search, 300);
    return () => clearTimeout(timer);
  }, [participantSearch]);

  const handleCreate = async () => {
    if (!title || !meetingDate || !meetingTime) return;
    setIsSubmitting(true);
    try {
      const start = meetingDate.hour(meetingTime.hour()).minute(meetingTime.minute()).second(0);
      const data = {
        title,
        status: "planned",
        start_time: start.toISOString(),
        end_time: start.add(plannedDuration, 'minute').toISOString(),
        participants: selectedParticipants.map(p => typeof p === 'string' ? { email: p, name: p } : { email: p.email, name: p.full_name, user_id: p.id }),
        location: typeof location === 'string' ? location : location?.name,
        room_id: location?.id
      };
      await meetingsApi.createMeeting(data);
      setTitle(""); setSelectedParticipants([]); setLocation(null);
      await fetchMeetings();
      alert(t("meetings.created_success"));
    } catch (e) { console.error(e); } finally { setIsSubmitting(false); }
  };

  const handleAction = async (id: string, action: 'cancel' | 'delete') => {
    const confirmMsg = action === 'cancel' 
      ? (t("common.confirm_cancel") || "Are you sure you want to cancel?") 
      : (t("common.confirm_delete") || "Are you sure you want to delete?");
    if (!window.confirm(confirmMsg)) return;
    try {
      if (action === 'cancel') await api.patch(`/meetings/${id}/cancel`);
      else await api.delete(`/meetings/${id}`);
      await fetchMeetings();
    } catch (e) { console.error(e); }
  };

  const glassStyle = {
    p: { xs: 2.5, md: 4 },
    borderRadius: "24px",
    background: alpha(theme.palette.background.paper, 0.8),
    backdropFilter: "blur(16px)",
    border: `1px solid rgba(0,0,0,0.05)`,
  };

  const holidayWarning = meetingDate && isHoliday(meetingDate.format('YYYY-MM-DD')) ? getHolidayName(meetingDate.format('YYYY-MM-DD')) : null;

  return (
    <LocalizationProvider dateAdapter={AdapterDayjs} adapterLocale={dayjsLocale}>
      <Box sx={{ p: { xs: 2, md: 4 }, maxWidth: 1200, mx: "auto" }}>
        <Typography variant="h4" sx={{ fontWeight: 800, mb: 4, letterSpacing: '-0.02em' }}>{t("meetings.planner_title")}</Typography>
        <Grid container spacing={4}>
          {/* FORM SECTION */}
          <Grid item xs={12} md={7}>
            <Paper sx={glassStyle}>
              <Stack spacing={3}>
                <Typography variant="h6" sx={{ fontWeight: 800 }}>{t("meetings.new_meeting")}</Typography>
                <TextField fullWidth label={t("meetings.title")} value={title} onChange={(e) => setTitle(e.target.value)} />
                {holidayWarning && <Alert severity="warning">{t("meetings.holiday_warning")} {holidayWarning}</Alert>}
                <Stack direction="row" spacing={2}>
                  <DatePicker label={t("meetings.date")} value={meetingDate} onChange={setMeetingDate} sx={{ flex: 1 }} />
                  <TimePicker label={t("meetings.time")} value={meetingTime} onChange={setMeetingTime} ampm={false} sx={{ flex: 1 }} />
                </Stack>
                <FormControl fullWidth>
                  <InputLabel id="dur-lbl">{t("meetings.duration")}</InputLabel>
                  <Select labelId="dur-lbl" value={plannedDuration} onChange={(e) => setPlannedDuration(Number(e.target.value))} label={t("meetings.duration")}>
                    <MenuItem value={30}>30 min</MenuItem>
                    <MenuItem value={60}>1 hour</MenuItem>
                    <MenuItem value={90}>1.5 hours</MenuItem>
                    <MenuItem value={120}>2 hours</MenuItem>
                  </Select>
                </FormControl>
                <Autocomplete freeSolo options={availableRooms} getOptionLabel={(o) => typeof o === 'string' ? o : o.name} value={location} onChange={(_, v) => setLocation(v)} renderInput={(p) => <TextField {...p} label={t("meetings.location")} />} />
                <Autocomplete multiple freeSolo options={participantResults} getOptionLabel={(o) => typeof o === 'string' ? o : o.full_name} value={selectedParticipants} onInputChange={(_, v) => setParticipantSearch(v)} onChange={(_, v) => setSelectedParticipants(v)} renderInput={(p) => <TextField {...p} label={t("meetings.participants")} />} />
                <Button fullWidth variant="contained" disabled={isSubmitting || !title} onClick={handleCreate} sx={{ py: 1.5, borderRadius: '12px', fontWeight: 800, bgcolor: '#000', color: '#fff', '&:hover': { bgcolor: '#333' } }}>{t("meetings.create")}</Button>
              </Stack>
            </Paper>
          </Grid>

          <Grid item xs={12} md={5}>
            <Paper sx={{ ...glassStyle, p: 0, overflow: 'hidden' }}>
              <Box sx={{ px: 3, py: 2, borderBottom: "1px solid", borderColor: "divider", bgcolor: alpha('#000', 0.02) }}>
                <Typography variant="subtitle1" sx={{ fontWeight: 800 }}>{t("meetings.recent_meetings")}</Typography>
              </Box>
              <List disablePadding>
                {recentMeetings.map((m) => {
                  const mStart = dayjs(m.start_time);
                  const mEnd = m.end_time ? dayjs(m.end_time) : mStart.add(1, 'hour');
                  const now = dayjs();
                  
                  const isLate = now.isAfter(mStart) && now.isBefore(mEnd);
                  const isExpired = now.isAfter(mEnd) && m.status === 'planned';
                  const isSoon = mStart.diff(now, 'minute') <= 15 && mStart.diff(now, 'minute') >= 0;

                  return (
                    <ListItem key={m.id} divider sx={{ px: 3, py: 2, display: 'flex', flexDirection: 'column', alignItems: 'stretch' }}>
                      <Stack direction="row" justifyContent="space-between" sx={{ mb: 1 }}>
                        <Typography sx={{ fontWeight: 700, textDecoration: isExpired ? 'line-through' : 'none', color: isExpired ? 'text.secondary' : 'text.primary' }}>{m.title}</Typography>
                        <Chip label={t(`meetings.${isExpired ? 'expired' : isLate ? 'late' : m.status}`)} size="small" variant="outlined" sx={{ borderRadius: '6px', fontSize: '10px', fontWeight: 800, color: isLate ? 'error.main' : 'text.secondary', borderColor: isLate ? 'error.main' : 'divider' }} />
                      </Stack>
                      <Stack direction="row" spacing={2} sx={{ mb: 2 }}>
                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}><ScheduleIcon sx={{ fontSize: 14 }} /><Typography variant="caption">{mStart.format('HH:mm')}</Typography></Box>
                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}><RoomIcon sx={{ fontSize: 14 }} /><Typography variant="caption">{m.location || "Office"}</Typography></Box>
                      </Stack>
                      
                      <Stack direction="row" spacing={1} justifyContent="flex-end">
                        {/* PLANNED LOGIC - START BUTTON ALWAYS SAYS "START" TO AVOID CONFUSION */}
                        {m.status === 'planned' && !isExpired && (
                          <>
                            <Button 
                              size="small" 
                              variant="outlined" 
                              color="error" 
                              startIcon={<CancelIcon sx={{ fontSize: 14 }} />} 
                              onClick={() => handleAction(m.id, 'cancel')} 
                              sx={{ borderRadius: '8px', textTransform: 'none', fontWeight: 700 }}
                            >
                              {t('common.cancel', 'Cancel')}
                            </Button>
                            <Button 
                              size="small" 
                              variant="contained"
                              onClick={() => navigate(`/meetings/live/${m.id}`)}
                              startIcon={<PlayArrowIcon sx={{ fontSize: 14 }} />}
                              sx={{ 
                                borderRadius: '8px', fontWeight: 800, textTransform: 'none',
                                bgcolor: isSoon ? 'success.main' : isLate ? 'error.main' : 'primary.main',
                                color: '#fff',
                                animation: isSoon ? 'pulse 2s infinite' : 'none',
                                '&:hover': {
                                  bgcolor: isSoon ? 'success.dark' : isLate ? 'error.dark' : 'primary.dark',
                                }
                              }}
                            >
                              {t('meetings.start_now', 'Start Now')}
                            </Button>
                          </>
                        )}

                        {isExpired && (
                          <Button size="small" color="error" startIcon={<DeleteIcon sx={{ fontSize: 14 }} />} onClick={() => handleAction(m.id, 'delete')} sx={{ textTransform: 'none', fontWeight: 700 }}>
                            {t('common.delete', 'Delete')}
                          </Button>
                        )}

                        {m.status === 'in_progress' && (
                          <Button size="small" variant="contained" color="primary" onClick={() => navigate(`/meetings/live/${m.id}`)} sx={{ borderRadius: '8px', fontWeight: 800, textTransform: 'none' }}>
                            {t('meetings.join_room', 'Join Room')}
                          </Button>
                        )}

                        {m.status === 'completed' && pvMap[m.id] && (
                          <Button size="small" variant="outlined" startIcon={<EditIcon sx={{ fontSize: 14 }} />} onClick={() => window.open(`/editor/${pvMap[m.id]}`, '_blank')} sx={{ borderRadius: '8px', textTransform: 'none', fontWeight: 700 }}>
                            {t("pv.edit_online", "Edit PV")}
                          </Button>
                        )}
                      </Stack>
                    </ListItem>
                  );
                })}
              </List>
            </Paper>

            {/* TUNISIAN CULTURAL CALENDAR */}
            <Paper sx={{ ...glassStyle, p: 3, mt: 4 }}>
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
                    <Chip label={t("meetings.holiday")} size="small" color="error" variant="filled" sx={{ fontWeight: 800, fontSize: '0.65rem' }} />
                  </Box>
                ))}
              </Stack>
            </Paper>
          </Grid>
        </Grid>
      </Box>
      <style>{`@keyframes pulse { 0% { box-shadow: 0 0 0 0 rgba(16, 185, 129, 0.4); } 70% { box-shadow: 0 0 0 10px rgba(16, 185, 129, 0); } 100% { box-shadow: 0 0 0 0 rgba(16, 185, 129, 0); } }`}</style>
    </LocalizationProvider>
  );
};

export default MeetingPlanner;