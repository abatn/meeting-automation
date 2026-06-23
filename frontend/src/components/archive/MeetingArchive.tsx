import React, { useState, useEffect, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import {
  Box,
  Typography,
  Grid,
  Paper,
  TextField,
  InputAdornment,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Button,
  Stack,
  MenuItem,
  Select,
  FormControl,
  InputLabel,
  CircularProgress,
  alpha,
  Tooltip,
  Chip,
  useTheme,
} from "@mui/material";
import { DatePicker } from "@mui/x-date-pickers/DatePicker";
import { LocalizationProvider } from "@mui/x-date-pickers/LocalizationProvider";
import { AdapterDayjs } from "@mui/x-date-pickers/AdapterDayjs";
import {
  Search as SearchIcon,
  FilterList as FilterIcon,
  Visibility as ViewIcon,
  MeetingRoom as RoomIcon,
} from "@mui/icons-material";
import { useTranslation } from "react-i18next";
import dayjs from "dayjs";
import "dayjs/locale/ar-tn";
import "dayjs/locale/fr";
import { meetingsApi } from "../../services/meetings";
import { roomsApi } from "../../services/rooms";

const MeetingArchive: React.FC = () => {
  const { t, i18n } = useTranslation();
  const theme = useTheme();
  const navigate = useNavigate();

  // Set dayjs locale based on i18n
  const currentLang = i18n.language.split("-")[0];
  const dayjsLocale = i18n.language === "ar-TN" ? "ar-tn" : currentLang;

  const [meetings, setMeetings] = useState<any[]>([]);
  const [rooms, setRooms] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  // Filter States
  const [searchQuery, setSearchQuery] = useState("");
  const [topicQuery, setTopicQuery] = useState("");
  const [selectedRoom, setSelectedRoom] = useState("all");
  const [dateFrom, setDateFrom] = useState<any>(null);
  const [dateTo, setDateTo] = useState<any>(null);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [meetingsData, roomsData] = await Promise.all([
          meetingsApi.getMeetings(),
          roomsApi.getRooms(),
        ]);
        // Show meetings that are completed OR already have a PV
        setMeetings(
          meetingsData.filter((m: any) => m.pv || m.status === "COMPLETED")
        );
        setRooms(roomsData);
      } catch (error) {
        console.error("Failed to fetch archive data", error);
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, []);

  const filteredMeetings = useMemo(() => {
    return meetings.filter((m) => {
      const matchesSearch = m.title
        .toLowerCase()
        .includes(searchQuery.toLowerCase());
      const matchesTopic =
        !topicQuery ||
        (m.pv?.tags && m.pv.tags.toLowerCase().includes(topicQuery.toLowerCase()));
      const matchesRoom =
        selectedRoom === "all" ||
        m.room_id === selectedRoom ||
        m.location === selectedRoom;

      const mDate = dayjs(m.start_time);
      const matchesDateFrom = !dateFrom || mDate.isSame(dateFrom, 'day') || mDate.isAfter(dateFrom, 'day');
      const matchesDateTo = !dateTo || mDate.isSame(dateTo, 'day') || mDate.isBefore(dateTo, 'day');

      return matchesSearch && matchesTopic && matchesRoom && matchesDateFrom && matchesDateTo;
    });
  }, [meetings, searchQuery, topicQuery, selectedRoom, dateFrom, dateTo]);

  if (loading) {
    return (
      <Box
        sx={{
          display: "flex",
          justifyContent: "center",
          alignItems: "center",
          height: "60vh",
        }}
      >
        <CircularProgress size={40} sx={{ color: "#000" }} />
      </Box>
    );
  }

  return (
    <Box sx={{ p: { xs: 2, md: 4 }, maxWidth: 1400, mx: "auto" }}>
      {/* HEADER */}
      <Box sx={{ mb: 4 }}>
        <Typography
          variant="h4"
          fontWeight="800"
          sx={{ letterSpacing: "-0.5px", fontSize: "28px", mb: 1 }}
        >
          {t("sidebar.archive")}
        </Typography>
        <Typography variant="body2" color="text.secondary">
          {t("archive.subtitle")}
        </Typography>
      </Box>

      {/* FILTER TOOLBAR */}
      <Paper
        variant="outlined"
        sx={{
          p: 2,
          mb: 4,
          borderRadius: 3,
          bgcolor: "rgba(0,0,0,0.01)",
          borderColor: "divider",
        }}
      >
        <Grid container spacing={2} alignItems="center">
          <Grid item xs={12} md={3}>
            <TextField
              fullWidth
              size="small"
              label={t("common.search")}
              placeholder={t("archive.search_placeholder")}
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              InputProps={{
                startAdornment: (
                  <InputAdornment position="start">
                    <SearchIcon fontSize="small" sx={{ color: "text.secondary" }} />
                  </InputAdornment>
                ),
                sx: { borderRadius: 2, bgcolor: theme.palette.mode === 'dark' ? 'rgba(0,0,0,0.2)' : '#FFF' },
              }}
            />
          </Grid>

          <Grid item xs={12} md={2}>
            <TextField
              fullWidth
              size="small"
              label={t("archive.filter_topic")}
              placeholder={t("archive.filter_topic")}
              value={topicQuery}
              onChange={(e) => setTopicQuery(e.target.value)}
              InputProps={{
                startAdornment: (
                  <InputAdornment position="start">
                    <FilterIcon fontSize="small" sx={{ color: "text.secondary" }} />
                  </InputAdornment>
                ),
                sx: { borderRadius: 2, bgcolor: theme.palette.mode === 'dark' ? 'rgba(0,0,0,0.2)' : '#FFF' },
              }}
            />
          </Grid>

          <Grid item xs={12} md={2.3}>
            <FormControl fullWidth size="small">
              <InputLabel sx={{ fontSize: 14 }}>{t("meetings.location")}</InputLabel>
              <Select
                value={selectedRoom}
                label={t("meetings.location")}
                onChange={(e) => setSelectedRoom(e.target.value)}
                sx={{ borderRadius: 2, bgcolor: theme.palette.mode === 'dark' ? 'rgba(0,0,0,0.2)' : '#FFF', fontSize: 14 }}
              >
                <MenuItem value="all">{t("common.all")}</MenuItem>
                {rooms.map((r) => (
                  <MenuItem key={r.id} value={r.id}>
                    {r.name}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
          </Grid>

          <Grid item xs={12} sm={6} md={2.3}>
            <LocalizationProvider dateAdapter={AdapterDayjs} adapterLocale={dayjsLocale}>
              <DatePicker
                label={t("archive.date_from")}
                value={dateFrom}
                onChange={(newValue) => setDateFrom(newValue)}
                format={t("common.date_placeholder")}
                slotProps={{
                  textField: {
                    size: "small",
                    fullWidth: true,
                    InputLabelProps: { shrink: true, sx: { fontSize: 14 } },
                    InputProps: { sx: { borderRadius: 2, bgcolor: theme.palette.mode === 'dark' ? 'rgba(0,0,0,0.2)' : '#FFF', fontSize: 14 } },
                  },
                }}
              />
            </LocalizationProvider>
          </Grid>

          <Grid item xs={12} sm={6} md={2.3}>
            <LocalizationProvider dateAdapter={AdapterDayjs} adapterLocale={dayjsLocale}>
              <DatePicker
                label={t("archive.date_to")}
                value={dateTo}
                onChange={(newValue) => setDateTo(newValue)}
                format={t("common.date_placeholder")}
                slotProps={{
                  textField: {
                    size: "small",
                    fullWidth: true,
                    InputLabelProps: { shrink: true, sx: { fontSize: 14 } },
                    InputProps: { sx: { borderRadius: 2, bgcolor: theme.palette.mode === 'dark' ? 'rgba(0,0,0,0.2)' : '#FFF', fontSize: 14 } },
                  },
                }}
              />
            </LocalizationProvider>
          </Grid>
        </Grid>
      </Paper>

      {/* ARCHIVE TABLE */}
      <TableContainer
        component={Paper}
        variant="outlined"
        sx={{
          borderRadius: 3,
          overflowX: "auto",
          width: "100%",
          borderColor: "divider",
          boxShadow: "none",
          "&::-webkit-scrollbar": {
            height: "6px",
          },
          "&::-webkit-scrollbar-thumb": {
            backgroundColor: "rgba(0,0,0,0.1)",
            borderRadius: "3px",
          },
        }}
      >
        <Table stickyHeader sx={{ minWidth: 800 }}>
          <TableHead>
            <TableRow sx={{ bgcolor: alpha("#000", 0.02) }}>
              <TableCell
                sx={{
                  fontWeight: 700,
                  fontSize: 11,
                  textTransform: "uppercase",
                  letterSpacing: "0.05em",
                  color: "#71717A",
                  minWidth: 100
                }}
              >
                {t("meetings.date")}
              </TableCell>
              <TableCell
                sx={{
                  fontWeight: 700,
                  fontSize: 11,
                  textTransform: "uppercase",
                  letterSpacing: "0.05em",
                  color: "#71717A",
                  minWidth: 150
                }}
              >
                {t("meetings.title")}
              </TableCell>
              <TableCell
                sx={{
                  fontWeight: 700,
                  fontSize: 11,
                  textTransform: "uppercase",
                  letterSpacing: "0.05em",
                  color: "#71717A",
                  minWidth: 150
                }}
              >
                {t("archive.topics")}
              </TableCell>
              <TableCell
                sx={{
                  fontWeight: 700,
                  fontSize: 11,
                  textTransform: "uppercase",
                  letterSpacing: "0.05em",
                  color: "#71717A",
                  minWidth: 120
                }}
              >
                {t("meetings.location")}
              </TableCell>
              <TableCell
                sx={{
                  fontWeight: 700,
                  fontSize: 11,
                  textTransform: "uppercase",
                  letterSpacing: "0.05em",
                  color: "#71717A",
                }}
                align="center"
              >
                {t("meetings.participants")}
              </TableCell>
              <TableCell
                sx={{
                  fontWeight: 700,
                  fontSize: 11,
                  textTransform: "uppercase",
                  letterSpacing: "0.05em",
                  color: "#71717A",
                  minWidth: 120
                }}
                align="right"
              >
                {t("common.actions")}
              </TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {filteredMeetings.length === 0 ? (
              <TableRow>
                <TableCell colSpan={6} align="center" sx={{ py: 8 }}>
                  <Typography variant="body2" color="text.secondary">
                    {t("archive.no_results")}
                  </Typography>
                </TableCell>
              </TableRow>
            ) : (
              filteredMeetings.map((m) => (
                <TableRow
                  key={m.id}
                  hover
                  sx={{ "&:last-child td, &:last-child th": { border: 0 } }}
                >
                  <TableCell sx={{ fontSize: 13, fontWeight: 500 }}>
                    {dayjs(m.start_time)
                      .locale(dayjsLocale)
                      .format(t("common.date_format"))}
                  </TableCell>
                  <TableCell sx={{ fontSize: 13, fontWeight: 600, color: "#000" }}>
                    {m.title}
                  </TableCell>
                  <TableCell sx={{ fontSize: 13 }}>
                    <Stack direction="row" spacing={0.5} flexWrap="wrap">
                      {m.pv?.tags ? (
                        m.pv.tags.split(",").map((tag: string, idx: number) => (
                          <Chip
                            key={idx}
                            label={tag.trim()}
                            size="small"
                            sx={{
                              fontSize: 10,
                              height: 18,
                              bgcolor: alpha(theme.palette.primary.main, 0.05),
                              color: theme.palette.primary.main,
                              fontWeight: 700,
                              borderRadius: 1,
                              m: 0.2,
                            }}
                          />
                        ))
                      ) : (
                        <Typography variant="caption" color="text.disabled">
                          No tags
                        </Typography>
                      )}
                    </Stack>
                  </TableCell>
                  <TableCell sx={{ fontSize: 13, color: "#52525B" }}>
                    <Stack direction="row" spacing={1} alignItems="center">
                      <RoomIcon fontSize="inherit" sx={{ opacity: 0.5, fontSize: 16 }} />
                      <Typography variant="inherit">
                        {rooms.find((r) => r.id === m.room_id)?.name ||
                          m.location ||
                          "Online"}
                      </Typography>
                    </Stack>
                  </TableCell>
                  <TableCell align="center">
                    <Tooltip
                      title={m.participants
                        ?.map((p: any) => p.name || p.email)
                        .join(", ")}
                    >
                      <Chip
                        label={m.participants?.length || 0}
                        size="small"
                        sx={{
                          fontWeight: 600,
                          borderRadius: 1,
                          bgcolor: alpha("#000", 0.05),
                          fontSize: 11,
                        }}
                      />
                    </Tooltip>
                  </TableCell>
                  <TableCell align="right">
                    <Stack direction="row" spacing={1} justifyContent="flex-end">
                      <Button
                        size="small"
                        variant="outlined"
                        startIcon={<ViewIcon sx={{ fontSize: 14 }} />}
                        onClick={() => navigate(`/meetings/live/${m.id}`)}
                        sx={{
                          textTransform: "none",
                          borderRadius: 1.5,
                          fontSize: 12,
                          fontWeight: 600,
                          borderColor: "divider",
                          color: "#000",
                          px: 2,
                        }}
                      >
                        {t("common.view")}
                      </Button>
                    </Stack>
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </TableContainer>
    </Box>
  );
};

export default MeetingArchive;
