import React, { useState, useEffect } from "react";
import { useParams } from "react-router-dom";
import {
  Box,
  Grid,
  Typography,
  Paper,
  Divider,
  Tab,
  Tabs,
  Badge,
  Stack,
  Button,
  IconButton,
  Tooltip,
  CircularProgress,
  alpha,
} from "@mui/material";
import {
  AutoFixHigh as SuggestionIcon,
  AddCircleOutline as AddIcon,
  HighlightOff as RejectIcon,
} from "@mui/icons-material";
import AudioRecorder from "./AudioRecorder";
import TranscriptionViewer from "./TranscriptionViewer";
import PVValidator from "./PVValidator";
import { useTranslation } from "react-i18next";
import api from "../../services/api";

interface ActionSuggestion {
  id: string;
  title: string;
  description: string;
  suggested_assignee: string | null;
  status: "suggested" | "accepted" | "rejected";
}

const MeetingRoom: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const { t, i18n } = useTranslation();
  const [activeTab, setActiveTab] = useState(0);
  const [suggestions, setSuggestions] = useState<ActionSuggestion[]>([]);
  const [exportLanguage, setExportLanguage] = useState<string>(i18n.language.split('-')[0] || "fr");
  const [translating, setTranslating] = useState(false);

  useEffect(() => {
    if (!id) return;
    
    const fetchSuggestions = async () => {
      try {
        const lang = i18n.language.split('-')[0] || "fr";
        const suggestionsRes = await api.get(`/actions/suggestions/${id}?lang=${lang}`);
        if (suggestionsRes.data) {
          setSuggestions(suggestionsRes.data.filter((s: ActionSuggestion) => s.status.toLowerCase() === "suggested"));
        }
      } catch (err) {
        console.error("Failed to fetch action suggestions", err);
      }
    };

    fetchSuggestions();
    const interval = setInterval(fetchSuggestions, 30000); // Polling suggestions less frequently

    return () => clearInterval(interval);
  }, [id, i18n.language]);

  const handleSuggestionFeedback = async (suggestionId: string, action: "accept" | "reject") => {
    try {
      await api.post("/actions/suggestions/learn", {
        suggestion_id: suggestionId,
        action: action
      });
      setSuggestions(prev => prev.filter(s => s.id !== suggestionId));
    } catch (err) {
      console.error(`Failed to ${action} suggestion`, err);
    }
  };

  const handleTabChange = (event: React.SyntheticEvent, newValue: number) => {
    setActiveTab(newValue);
  };

  return (
    <Box sx={{ p: { xs: 2, md: 6 }, maxWidth: 1600, mx: "auto" }}>
      
      {/* HEADER */}
      <Stack direction="row" alignItems="center" spacing={2} sx={{ mb: 4 }}>
        <Box sx={{ width: 8, height: 8, borderRadius: "50%", bgcolor: "#3B82F6", animation: "pulse 2s infinite" }} />
        <Typography sx={{ fontSize: 18, fontWeight: 600, color: "text.primary" }}>
          Meeting Room: {id}
        </Typography>
        <style>
          {`@keyframes pulse { 0% { opacity: 1; } 50% { opacity: 0.4; } 100% { opacity: 1; } }`}
        </style>
      </Stack>

      <Grid container spacing={4}>
        {/* Left Column: Live Recording Controls & Meeting Info */}
        <Grid item xs={12} md={4}>
          <Stack spacing={3}>
            <Box>
              <AudioRecorder
                meetingId={id!}
                onUploadSuccess={() => setActiveTab(1)}
              />
            </Box>

            <Box sx={{ p: 3, borderRadius: 3, border: "1px solid", borderColor: "divider" }}>
              <Typography sx={{ fontSize: 15, fontWeight: 600, mb: 2 }}>
                Meeting Info
              </Typography>
              <Stack spacing={1}>
                <Typography sx={{ fontSize: 13, color: "text.secondary", display: 'flex', justifyContent: 'space-between' }}>
                  <span>ID:</span> <strong style={{ color: '#000' }}>{id}</strong>
                </Typography>
                <Typography sx={{ fontSize: 13, color: "text.secondary", display: 'flex', justifyContent: 'space-between' }}>
                  <span>Status:</span> <strong style={{ color: '#3B82F6' }}>Live</strong>
                </Typography>
              </Stack>
            </Box>

            {/* AI Recommendations under Meeting Info */}
            <Box 
              sx={{ 
                p: 3, 
                borderRadius: 3, 
                border: "1px solid",
                borderColor: "divider",
                bgcolor: alpha("#000", 0.01),
                minHeight: '300px',
                display: 'flex',
                flexDirection: 'column',
                position: 'relative'
              }}
            >
              {translating && (
                <Box sx={{ position: 'absolute', top: 0, left: 0, right: 0, bottom: 0, bgcolor: 'rgba(255,255,255,0.7)', zIndex: 1, display: 'flex', justifyContent: 'center', alignItems: 'center', borderRadius: 3 }}>
                  <CircularProgress size={24} sx={{ color: "#000" }} />
                </Box>
              )}
              <Stack direction="row" alignItems="center" justifyContent="space-between" sx={{ mb: 2.5 }}>
                <Typography sx={{ display: 'flex', alignItems: 'center', gap: 1, fontSize: 15, fontWeight: 600, color: "text.primary" }}>
                  <SuggestionIcon sx={{ fontSize: 20 }} /> AI Recommendations
                </Typography>
                <Badge 
                  badgeContent={suggestions.length} 
                  sx={{ 
                    "& .MuiBadge-badge": { bgcolor: "#000", color: "#FFF", fontSize: 10, fontWeight: 700 } 
                  }} 
                />
              </Stack>
              
              {suggestions.length === 0 ? (
                <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', flexGrow: 1, color: 'text.secondary', textAlign: 'center', p: 4 }}>
                  <Typography sx={{ fontSize: 13 }}>
                    No suggestions yet. Once the meeting is processed, AI will recommend tasks here.
                  </Typography>
                </Box>
              ) : (
                <Stack spacing={2} sx={{ maxHeight: "600px", overflowY: "auto", pr: 1 }}>
                  {suggestions.map((suggestion) => (
                    <Box key={suggestion.id} sx={{ p: 2, bgcolor: "#FFF", borderRadius: 2, border: '1px solid', borderColor: 'divider' }}>
                      <Typography sx={{ fontSize: 14, fontWeight: 600, color: "text.primary", mb: 0.5 }}>{suggestion.title}</Typography>
                      <Typography sx={{ fontSize: 12, color: "text.secondary", mb: 2, display: 'block', lineHeight: 1.5 }}>{suggestion.description}</Typography>
                      {suggestion.suggested_assignee && (
                        <Typography sx={{ display: 'inline-block', bgcolor: alpha("#000", 0.04), px: 1, py: 0.5, borderRadius: 1, fontSize: 11, fontWeight: 500, mb: 2 }}>
                          👤 For: <strong>{suggestion.suggested_assignee}</strong>
                        </Typography>
                      )}
                      <Stack direction="row" spacing={1}>
                        <Button 
                          size="small" 
                          variant="contained" 
                          disableElevation
                          onClick={() => handleSuggestionFeedback(suggestion.id, "accept")}
                          sx={{ 
                            flexGrow: 1, bgcolor: "#000", color: "#FFF", borderRadius: 1.5, textTransform: "none", fontSize: 12, fontWeight: 600, py: 0.8,
                            "&:hover": { bgcolor: "#27272A" }
                          }}
                        >
                          Accept
                        </Button>
                        <Button 
                          size="small" 
                          variant="outlined" 
                          onClick={() => handleSuggestionFeedback(suggestion.id, "reject")}
                          sx={{ 
                            borderRadius: 1.5, textTransform: "none", fontSize: 12, fontWeight: 600, py: 0.8, borderColor: "divider", color: "text.primary",
                            "&:hover": { borderColor: "text.primary", bgcolor: "transparent" }
                          }}
                        >
                          Reject
                        </Button>
                      </Stack>
                    </Box>
                  ))}
                </Stack>
              )}
            </Box>
          </Stack>
        </Grid>

        {/* Right Column: Dynamic Content (Transcription / PV) */}
        <Grid item xs={12} md={8}>
          <Box sx={{ width: "100%", mb: 4, borderBottom: 1, borderColor: "divider" }}>
            <Tabs 
              value={activeTab} 
              onChange={handleTabChange}
              sx={{
                "& .MuiTabs-indicator": { bgcolor: "#000", height: 2 },
                "& .MuiTab-root": { textTransform: "none", fontSize: 14, fontWeight: 600, color: "text.secondary", py: 2 },
                "& .Mui-selected": { color: "#000 !important" }
              }}
            >
              <Tab label={t("meetings.live_transcription")} />
              <Tab label={t("meetings.protocol_pv")} />
            </Tabs>
          </Box>

          <Box sx={{ minHeight: '70vh' }}>
            {activeTab === 0 && <TranscriptionViewer meetingId={id!} />}

            {activeTab === 1 && (
              <PVValidator 
                exportLanguage={exportLanguage} 
                onLanguageChange={setExportLanguage} 
              />
            )}
          </Box>
        </Grid>
      </Grid>
    </Box>
  );
};

export default MeetingRoom;
