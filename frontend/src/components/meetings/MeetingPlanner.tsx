import React, { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { useSelector } from "react-redux";
import { RootState } from "../../store";
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
  const currentUser = useSelector((state: RootState) => state.auth.user);

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

  // --- VALIDATION LOGIC ---
  const getCombinedStart = () => {
    if (!meetingDate || !meetingTime) return null;
    return meetingDate.hour(meetingTime.hour()).minute(meetingTime.minute()).second(0).millisecond(0);
  };

  const isPastTime = () => {
    const combined = getCombinedStart();
    if (!combined) return false;
    return combined.isBefore(dayjs().add(1, 'minute'));
  };

  const isFormInvalid = () => {
    return (!title.trim() || !meetingDate || !meetingTime || !location || selectedParticipants.length === 0 || isPastTime());
  };

  const fetchMeetings = async () => {
    try {
      const meetings = await meetingsApi.getMeetings();
      console.log("DEBUG: fetchMeetings() - All meetings from API:", meetings);
      console.log("DEBUG: currentUser from Redux:", currentUser);
      
      const nowTs = dayjs().valueOf();
      
      // 1. Define what is "Active" vs "History/Past"
      const processed = meetings.map((m: any) => {
        const mStart = dayjs(m.start_time).valueOf();
        const mEnd = m.end_time ? dayjs(m.end_time).valueOf() : mStart + (3600 * 1000);
        const result = { ...m, isExpired: nowTs > mEnd && m.status === 'planned' };
        const isCreatorCheck = currentUser?.id && m.creator_id && String(currentUser.id) === String(m.creator_id);
        console.log(`DEBUG: Meeting "${m.title}" - creator_id: "${m.creator_id}" (type: ${typeof m.creator_id}), currentUser.id: "${currentUser?.id}" (type: ${typeof currentUser?.id}), isCreator: ${isCreatorCheck}`);
        return result;
      });

      const activeMeetings = processed.filter((m: any) => 
        m.status === 'in_progress' || (m.status === 'planned' && !m.isExpired)
      );

      const historyMeetings = processed
        .filter((m: any) => m.status === 'cancelled' || m.isExpired)
        .sort((a: any, b: any) => new Date(b.start_time).getTime() - new Date(a.start_time).getTime());
      
      // 2. Combine all active + the single latest from history (cancelled or expired)
      const filtered = [...activeMeetings];
      if (historyMeetings.length > 0) {
        filtered.push(historyMeetings[0]);
      }

      const sorted = filtered
        .sort((a: any, b: any) => {
          const startA = dayjs(a.start_time).valueOf();
          const startB = dayjs(b.start_time).valueOf();

          const getStatusScore = (m: any) => {
            if (m.status === 'in_progress') return 0;
            if (m.status === 'planned' && !m.isExpired) return 1;
            return 2; // Cancelled or Expired
          };

          const scoreA = getStatusScore(a);
          const scoreB = getStatusScore(b);
          if (scoreA !== scoreB) return scoreA - scoreB;
          return startA - startB;
        })
        .slice(0, 10);
      setRecentMeetings(sorted);

      const pvs: { [key: string]: string } = {};
      for (const m of sorted) {
        if (m.status === 'completed') {
          try {
            const pvRes = await api.get(`/pv/meeting/${m.id}`);
            if (pvRes.data) pvs[m.id] = pvRes.data.id;
          } catch (e) {
            // Ignore error if PV not found
          }
        }
      }
      setPvMap(pvs);
    } catch (e) { 
      console.error(e); 
    }
  };

  useEffect(() => {
    roomsApi.getRooms().then(setAvailableRooms);
    fetchMeetings();
    const interval = setInterval(fetchMeetings, 30000); // Auto-refresh every 30s
    return () => clearInterval(interval);
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
    if (isFormInvalid()) return;
    setIsSubmitting(true);
    try {
      const start = meetingDate!.hour(meetingTime!.hour()).minute(meetingTime!.minute()).second(0);
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
    } catch (e) { 
      console.error(e); 
    } finally { setIsSubmitting(false); }
  };

  const handleAction = async (id: string, action: 'cancel' | 'delete') => {
    const msg = action === 'cancel' ? t("common.confirm_cancel") : t("common.confirm_delete");
    if (!window.confirm(msg || "Confirm?")) return;
    try {
      if (action === 'cancel') await api.patch(`/meetings/${id}/cancel`);
      else await api.delete(`/meetings/${id}`);
      await fetchMeetings();
    } catch (e) { 
      console.error(e); 
    }
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
          <Grid item xs={12} md={7}>
            <Paper sx={glassStyle}>
              <Stack spacing={3}>
                <Typography variant="h6" sx={{ fontWeight: 800 }}>{t("meetings.new_meeting")}</Typography>
                <TextField fullWidth label={t("meetings.title")} value={title} onChange={(e) => setTitle(e.target.value)} />
                {holidayWarning && <Alert severity="warning">{t("meetings.holiday_warning")} {holidayWarning}</Alert>}
                <Stack direction="row" spacing={2}>
                  <DatePicker label={t("meetings.date")} value={meetingDate} onChange={setMeetingDate} minDate={dayjs()} sx={{ flex: 1 }} />
                  <TimePicker label={t("meetings.time")} value={meetingTime} onChange={setMeetingTime} ampm={false} sx={{ flex: 1 }} />
                </Stack>
                <FormControl fullWidth>
                  <InputLabel id="dur-lbl">{t("meetings.duration")}</InputLabel>
                  <Select labelId="dur-lbl" value={plannedDuration} onChange={(e) => setPlannedDuration(Number(e.target.value))} label={t("meetings.duration")}>
                    <MenuItem value={30}>{t('meetings.duration_options.30min')}</MenuItem>
                    <MenuItem value={60}>{t('meetings.duration_options.1hour')}</MenuItem>
                    <MenuItem value={90}>{t('meetings.duration_options.1_5hours')}</MenuItem>
                    <MenuItem value={120}>{t('meetings.duration_options.2hours')}</MenuItem>
                  </Select>
                </FormControl>
                <Autocomplete freeSolo options={availableRooms} getOptionLabel={(o) => typeof o === 'string' ? o : o.name} value={location} onChange={(_, v) => setLocation(v)} renderInput={(p) => <TextField {...p} label={t("meetings.location")} />} />
                <Autocomplete multiple freeSolo options={participantResults} getOptionLabel={(o) => typeof o === 'string' ? o : o.full_name} value={selectedParticipants} onInputChange={(_, v) => setParticipantSearch(v)} onChange={(_, v) => setSelectedParticipants(v)} renderInput={(p) => <TextField {...p} label={t("meetings.participants")} />} />
                <Button 
                  fullWidth variant="contained" disabled={isSubmitting || isFormInvalid()} onClick={handleCreate} 
                  sx={{ py: 1.5, borderRadius: '12px', fontWeight: 800, bgcolor: '#000', color: '#fff', '&:hover': { bgcolor: '#333' }, "&.Mui-disabled": { bgcolor: alpha('#000', 0.1) } }}
                >
                  {isPastTime() && !isSubmitting ? t("meetings.error_past_date", "Invalid Time") : t("meetings.create")}
                </Button>
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
                    const now = dayjs();
                    const mStart = dayjs(m.start_time);
                    const mEnd = m.end_time ? dayjs(m.end_time) : mStart.add(1, 'hour');
                    
                     const isLate = now.isAfter(mStart) && now.isBefore(mEnd);
                     const isExpired = now.isAfter(mEnd) && m.status === 'planned';
                     const isSoon = mStart.diff(now, 'minute') <= 15 && mStart.diff(now, 'minute') >= 0;
                     const isCreator = currentUser?.id && m.creator_id && String(currentUser.id) === String(m.creator_id);
                     console.log(`DEBUG: Rendering meeting "${m.title}" - currentUser?.id: "${currentUser?.id}" (type: ${typeof currentUser?.id}) vs m.creator_id: "${m.creator_id}" (type: ${typeof m.creator_id}), isCreator: ${isCreator}`);

                   return (
                    <ListItem key={m.id} divider sx={{ px: 3, py: 2, display: 'flex', flexDirection: 'column', alignItems: 'stretch' }}>
                      <Stack direction="row" justifyContent="space-between" sx={{ mb: 1 }}>
                        <Typography sx={{ fontWeight: 700, textDecoration: isExpired ? 'line-through' : 'none', color: isExpired ? 'text.secondary' : 'text.primary' }}>{m.title}</Typography>
                        <Chip label={t(`meetings.${isExpired ? 'expired' : isLate ? 'late' : m.status}`)} size="small" variant="outlined" sx={{ borderRadius: '6px', fontSize: '10px', fontWeight: 800, color: isLate ? 'error.main' : 'text.secondary', borderColor: isLate ? 'error.main' : 'divider' }} />
                      </Stack>
                      <Stack direction="row" spacing={2} sx={{ mb: 2 }}>
                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}><ScheduleIcon sx={{ fontSize: 14 }} /><Typography variant="caption">{mStart.format('HH:mm')}</Typography></Box>
                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}><RoomIcon sx={{ fontSize: 14 }} /><Typography variant="caption">{m.location || t('meetings.default_location')}</Typography></Box>
                      </Stack>
                        <Stack direction="row" spacing={1} justifyContent="flex-end">
                           {m.status?.toLowerCase() === 'planned' && !isExpired && (
                             <>
                               {isCreator && (
                                 <Button size="small" variant="outlined" color="error" startIcon={<CancelIcon sx={{ fontSize: 14 }} />} onClick={() => handleAction(m.id, 'cancel')} sx={{ borderRadius: '8px', textTransform: 'none', fontWeight: 700 }}>{t('common.cancel', 'Cancel')}</Button>
                               )}
                               {isCreator ? (
                                 <Button 
                                   size="small" variant="contained" onClick={() => navigate(`/meetings/live/${m.id}`)}
                                   startIcon={<PlayArrowIcon sx={{ fontSize: 14 }} />}
                                   sx={{ 
                                     borderRadius: '8px', fontWeight: 800, textTransform: 'none',
                                     bgcolor: (isSoon || isLate) ? 'success.main' : 'primary.main',
                                     color: '#fff', animation: isSoon ? 'pulse 2s infinite' : 'none',
                                     '&:hover': { bgcolor: (isSoon || isLate) ? 'success.dark' : 'primary.dark' }
                                   }}
                                 >
                                   {isSoon || isLate ? t('meetings.join_room', 'Join') : t('meetings.start_now', 'Start Now')}
                                 </Button>
                               ) : (
                                 <>
                                   {(isSoon || isLate) && (
                                     <Button 
                                       size="small" variant="contained" onClick={() => navigate(`/meetings/live/${m.id}`)}
                                       startIcon={<PlayArrowIcon sx={{ fontSize: 14 }} />}
                                       sx={{ 
                                         borderRadius: '8px', fontWeight: 800, textTransform: 'none',
                                         bgcolor: 'success.main',
                                         color: '#fff', animation: 'pulse 2s infinite',
                                         '&:hover': { bgcolor: 'success.dark' }
                                       }}
                                     >
                                       {t('meetings.join_room', 'Join')}
                                     </Button>
                                   )}
                                   {!(isSoon || isLate) && (
                                     <Button 
                                       size="small" variant="outlined" onClick={() => navigate(`/meetings/live/${m.id}`)}
                                       startIcon={<PlayArrowIcon sx={{ fontSize: 14 }} />}
                                       sx={{ borderRadius: '8px', textTransform: 'none', fontWeight: 700 }}
                                     >
                                       {t('meetings.view_details', 'View Details')}
                                     </Button>
                                   )}
                                 </>
                               )}
                             </>
                           )}
                          {isExpired && isCreator && <Button size="small" color="error" startIcon={<DeleteIcon sx={{ fontSize: 14 }} />} onClick={() => handleAction(m.id, 'delete')} sx={{ textTransform: 'none', fontWeight: 700 }}>{t('common.delete', 'Delete')}</Button>}
                           {m.status?.toLowerCase() === 'in_progress' && <Button size="small" variant="contained" color="primary" onClick={() => navigate(`/meetings/live/${m.id}`)} sx={{ borderRadius: '8px', fontWeight: 800, textTransform: 'none' }}>{t('meetings.join_room', 'Join Room')}</Button>}
                          {m.status === 'completed' && pvMap[m.id] && <Button size="small" variant="outlined" startIcon={<EditIcon sx={{ fontSize: 14 }} />} onClick={() => window.open(`/editor/${pvMap[m.id]}`, '_blank')} sx={{ borderRadius: '8px', textTransform: 'none', fontWeight: 700 }}>{t("pv.edit_online", "Edit PV")}</Button>}
                        </Stack>
                    </ListItem>
                  );
                })}
              </List>
            </Paper>

            <Paper sx={{ ...glassStyle, p: 3, mt: 4 }}>
              <Stack direction="row" spacing={1.5} alignItems="center" sx={{ mb: 2 }}><EventIcon color="primary" /><Typography variant="subtitle1" sx={{ fontWeight: 800 }}>{t("meetings.upcoming_holidays")}</Typography></Stack>
              <Stack spacing={2}>
                {[ { date: "2026-03-20", name: t("meetings.holiday_independence") }, { date: "2026-04-09", name: t("meetings.holiday_martyrs") } ].map((h, i) => (
                  <Box key={i} sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', p: 1.5, borderRadius: '12px', bgcolor: alpha(theme.palette.error.main, 0.03), border: `1px solid ${alpha(theme.palette.error.main, 0.1)}` }}>
                    <Box><Typography sx={{ fontSize: '0.9rem', fontWeight: 700 }}>{h.name}</Typography><Typography variant="caption" sx={{ color: "text.secondary" }}>{dayjs(h.date).locale(dayjsLocale).format('LL')}</Typography></Box>
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