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
  const { t } = useTranslation();
  const [activeTab, setActiveTab] = useState(0);
  const [suggestions, setSuggestions] = useState<ActionSuggestion[]>([]);
  const [exportLanguage, setExportLanguage] = useState<string>("fr");
  const [translating, setTranslating] = useState(false);

  useEffect(() => {
    if (!id) return;
    
    const fetchSuggestions = async () => {
      try {
        const suggestionsRes = await api.get(`/actions/suggestions/${id}`);
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
  }, [id]);

  // Auto-translate suggestions when export language changes
  useEffect(() => {
    const translateSidebar = async () => {
      if (suggestions.length === 0 || translating) return;
      
      setTranslating(true);
      try {
        const res = await api.post("/actions/suggestions/translate", {
          suggestions: suggestions.map(s => ({ id: s.id, title: s.title, description: s.description })),
          target_language: exportLanguage
        });
        if (Array.isArray(res.data)) {
          // Merge translated content back into suggestions
          setSuggestions(prev => prev.map(s => {
            const trans = res.data.find((t: any) => t.id === s.id);
            return trans ? { ...s, title: trans.title, description: trans.description } : s;
          }));
        }
      } catch (err) {
        console.error("Failed to translate sidebar suggestions", err);
      } finally {
        setTranslating(false);
      }
    };

    translateSidebar();
  }, [exportLanguage, id]);

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
    <Box sx={{ flexGrow: 1 }}>
      <Typography variant="h4" gutterBottom>
        Meeting Room: {id}
      </Typography>

      <Grid container spacing={3}>
        {/* Left Column: Live Recording Controls & Meeting Info */}
        <Grid item xs={12} md={4}>
          <Box sx={{ mb: 3 }}>
            <AudioRecorder
              meetingId={id!}
              onUploadSuccess={() => setActiveTab(1)}
            />
          </Box>
          <Paper sx={{ p: 2, mb: 3 }}>
            <Typography variant="h6" gutterBottom>
              Meeting Info
            </Typography>
            <Divider sx={{ mb: 2 }} />
            <Typography variant="body2">
              <strong>ID:</strong> {id}
            </Typography>
            <Typography variant="body2">
              <strong>Status:</strong> Live
            </Typography>
          </Paper>

          {/* AI Recommendations under Meeting Info */}
          <Paper 
            sx={{ 
              p: 2, 
              bgcolor: "#fff9f0", 
              borderColor: "#ffe0b2", 
              border: "1px solid",
              minHeight: '200px',
              display: 'flex',
              flexDirection: 'column',
              position: 'relative'
            }}
          >
            {translating && (
              <Box sx={{ position: 'absolute', top: 0, left: 0, right: 0, bottom: 0, bgcolor: 'rgba(255,255,255,0.5)', zIndex: 1, display: 'flex', justifyContent: 'center', alignItems: 'center' }}>
                <CircularProgress size={24} color="secondary" />
              </Box>
            )}
            <Typography variant="subtitle1" gutterBottom sx={{ display: 'flex', alignItems: 'center', gap: 1, fontWeight: 'bold', color: 'secondary.main' }}>
              <SuggestionIcon /> AI Recommendations
              <Badge badgeContent={suggestions.length} color="error" sx={{ ml: 1 }} />
            </Typography>
            <Divider sx={{ mb: 2 }} />
            
            {suggestions.length === 0 ? (
              <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', flexGrow: 1, color: 'text.secondary', textAlign: 'center' }}>
                <Typography variant="body2">
                  No suggestions yet. Once the meeting is processed, AI will recommend tasks here.
                </Typography>
              </Box>
            ) : (
              <Stack spacing={2} sx={{ maxHeight: "500px", overflowY: "auto", pr: 1 }}>
                {suggestions.map((suggestion) => (
                  <Box key={suggestion.id} sx={{ p: 1.5, bgcolor: "white", borderRadius: 1, boxShadow: 1, border: '1px solid #eee' }}>
                    <Typography variant="subtitle2" sx={{ fontWeight: "bold" }}>{suggestion.title}</Typography>
                    <Typography variant="caption" color="textSecondary" sx={{ display: 'block', mb: 1 }}>{suggestion.description}</Typography>
                    {suggestion.suggested_assignee && (
                      <Typography variant="caption" sx={{ display: 'inline-block', bgcolor: '#f5f5f5', px: 1, py: 0.5, borderRadius: 1, mb: 1 }}>
                        👤 For: <strong>{suggestion.suggested_assignee}</strong>
                      </Typography>
                    )}
                    <Stack direction="row" spacing={1} justifyContent="flex-end">
                      <Button 
                        size="small" 
                        color="success" 
                        variant="contained" 
                        startIcon={<AddIcon />}
                        onClick={() => handleSuggestionFeedback(suggestion.id, "accept")}
                      >
                        Accept
                      </Button>
                      <Button 
                        size="small" 
                        color="error" 
                        variant="outlined" 
                        startIcon={<RejectIcon />}
                        onClick={() => handleSuggestionFeedback(suggestion.id, "reject")}
                      >
                        Reject
                      </Button>
                    </Stack>
                  </Box>
                ))}
              </Stack>
            )}
          </Paper>
        </Grid>

        {/* Right Column: Dynamic Content (Transcription / PV) */}
        <Grid item xs={12} md={8}>
          <Paper sx={{ width: "100%", mb: 2 }}>
            <Tabs value={activeTab} onChange={handleTabChange} centered>
              <Tab label={t("meetings.live_transcription")} />
              <Tab label={t("meetings.protocol_pv")} />
            </Tabs>
          </Paper>

          {activeTab === 0 && <TranscriptionViewer meetingId={id!} />}

          {activeTab === 1 && (
            <PVValidator 
              exportLanguage={exportLanguage} 
              onLanguageChange={setExportLanguage} 
            />
          )}
        </Grid>
      </Grid>
    </Box>
  );
};

export default MeetingRoom;
