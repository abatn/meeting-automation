import React, { useState, useEffect } from "react";
import { useParams } from "react-router-dom";
import {
  Box,
  Grid,
  Paper,
  Typography,
  TextField,
  Button,
  Stack,
  IconButton,
  Tooltip,
  CircularProgress,
  Alert,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
  Dialog,
} from "@mui/material";
import {
  CheckCircle as ApproveIcon,
  Edit as EditIcon,
  History as HistoryIcon,
  Save as SaveIcon,
  Language as LanguageIcon,
} from "@mui/icons-material";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import DocumentExportMenu from "./DocumentExportMenu";
import api from "../../services/api";

interface PVValidatorProps {
  exportLanguage: string;
  onLanguageChange: (lang: string) => void;
}

const PVValidator: React.FC<PVValidatorProps> = ({ exportLanguage, onLanguageChange }) => {
  const { id: meetingId } = useParams<{ id: string }>();
  const { t } = useTranslation();
  const [pvContent, setPvContent] = useState("");
  const [originalTranscript, setOriginalTranscript] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [pvId, setPvId] = useState<string | null>(null);


  useEffect(() => {
    const fetchData = async () => {
      if (!meetingId) return;

      // 1. Fetch transcription independently
      try {
        const transcriptRes = await api.get(
          `/transcriptions/meeting/${meetingId}`,
        );
        if (transcriptRes.data) {
          setOriginalTranscript(
            transcriptRes.data.full_text || transcriptRes.data.content || "",
          );
        }
      } catch (err) {
        console.warn("Transcription not yet available");
      }

      // 2. Fetch PV independently
      try {
        const pvRes = await api.get(`/pv/meeting/${meetingId}`);
        if (pvRes.data) {
          setPvContent(pvRes.data.content_html || pvRes.data.content || "");
          setPvId(pvRes.data.id);
          setError(null);
        }
      } catch (err: any) {
        console.error("Error fetching PV data:", err);
        if (err.response?.status === 404) {
          setError(
            "AI is still processing your meeting. Please wait a few seconds...",
          );
        } else {
          setError("Failed to load real-time AI results.");
        }
      } finally {
        setLoading(false);
      }
    };

    fetchData();
    const interval = setInterval(fetchData, 10000);

    return () => clearInterval(interval);
  }, [meetingId]);

  const handleApprove = async () => {
    if (!pvId) return;
    try {
      await api.post(`/pv/${pvId}/approve`);
      // You can add a success notification here
    } catch (err) {
      console.error("Failed to approve PV", err);
    }
  };

  if (loading && !pvContent && !originalTranscript) {
    return (
      <Box
        sx={{
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          height: "300px",
        }}
      >
        <CircularProgress sx={{ mb: 2 }} />
        <Typography variant="body1">
          Connecting to AI Engine...
        </Typography>
      </Box>
    );
  }

  return (
    <Box sx={{ p: 3, height: "calc(100vh - 100px)" }}>
      {error && !pvContent && (
        <Alert severity="info" sx={{ mb: 2 }}>
          {error}
        </Alert>
      )}

      <Box sx={{ display: "flex", justifyContent: "space-between", mb: 2, alignItems: "center" }}>
        <Typography variant="h5" fontWeight="bold">{t("pv.validator_title")}</Typography>
        <Stack direction="row" spacing={2} alignItems="center">
          <FormControl size="small" sx={{ minWidth: 120 }}>
            <InputLabel id="export-lang-label">{t("common.language") || "Language"}</InputLabel>
            <Select
              labelId="export-lang-label"
              value={exportLanguage}
              label={t("common.language") || "Language"}
              onChange={(e) => onLanguageChange(e.target.value as string)}
              startIcon={<LanguageIcon fontSize="small" />}
            >
              <MenuItem value="ar">العربية</MenuItem>
              <MenuItem value="fr">Français</MenuItem>
              <MenuItem value="en">English</MenuItem>
            </Select>
          </FormControl>

          <Button variant="outlined" startIcon={<HistoryIcon />}>
            {t("pv.versions")}
          </Button>

          <Button 
            href={`/editor/${pvId}?lang=${exportLanguage}`}
            target="_blank"
            rel="noopener noreferrer"
            onClick={(e) => {
              e.preventDefault();
              e.stopPropagation();
              window.open(`/editor/${pvId}?lang=${exportLanguage}`, '_blank');
            }}
            variant="contained" 
            color="primary" 
            startIcon={<EditIcon />}
            disabled={!pvId}
          >
            {t("pv.edit_online") || "Edit Online"}
          </Button>
          
          {pvId && (
            <DocumentExportMenu 
              pvId={pvId} 
              language={exportLanguage} 
              variant="outlined" 
              showDocx={false}
            />
          )}

          <Button
            variant="contained"
            color="success"
            startIcon={<ApproveIcon />}
            onClick={handleApprove}
          >
            {t("pv.approve")}
          </Button>
        </Stack>
      </Box>

      <Grid container spacing={2} sx={{ height: "90%" }}>
        {/* Left: Original Transcript */}
        <Grid item xs={12} md={5} sx={{ height: "100%" }}>
          <Paper
            sx={{ p: 2, height: "100%", overflowY: "auto", bgcolor: "#f8f9fa" }}
          >
            <Typography variant="subtitle2" gutterBottom color="textSecondary">
              {t("pv.original_transcript")}
            </Typography>
            <Typography
              variant="body2"
              sx={{ whiteSpace: "pre-wrap", fontFamily: "monospace" }}
            >
              {originalTranscript || "No transcription available yet."}
            </Typography>
          </Paper>
        </Grid>

        {/* Right: AI Generated PV (Editable) */}
        <Grid item xs={12} md={7} sx={{ height: "100%" }}>
          <Paper
            sx={{
              p: 2,
              height: "100%",
              display: "flex",
              flexDirection: "column",
            }}
          >
            <Box
              sx={{ display: "flex", justifyContent: "space-between", mb: 1 }}
            >
              <Typography variant="subtitle2" color="primary">
                {t("pv.ai_draft")}
              </Typography>
              <Tooltip title="Save Draft">
                <IconButton size="small">
                  <SaveIcon fontSize="small" />
                </IconButton>
              </Tooltip>
            </Box>
            <TextField
              multiline
              fullWidth
              value={pvContent}
              onChange={(e) => setPvContent(e.target.value)}
              variant="outlined"
              sx={{
                flexGrow: 1,
                "& .MuiInputBase-root": {
                  height: "100%",
                  alignItems: "flex-start",
                },
                "& textarea": {
                  height: "100% !important",
                  fontFamily: "serif",
                  fontSize: "1.1rem",
                },
              }}
              placeholder="Waiting for Mistral to generate the draft..."
            />
            <Box
              sx={{
                mt: 2,
                p: 2,
                border: "1px dashed #ccc",
                borderRadius: 1,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
              }}
            >
              <Typography
                variant="caption"
                sx={{ display: "flex", alignItems: "center", gap: 1 }}
              >
                <EditIcon fontSize="small" /> {t("pv.signature_placeholder")}
              </Typography>
            </Box>
          </Paper>
        </Grid>
      </Grid>
    </Box>
  );
};

export default PVValidator;
