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
  alpha,
} from "@mui/material";
import {
  CheckCircle as ApproveIcon,
  Check as CheckIcon,
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
  const [isValidated, setIsValidated] = useState(false);
  const [isApproving, setIsApproving] = useState(false);


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
          setIsValidated(pvRes.data.status === 'published' || pvRes.data.is_validated === true);
          setError(null);
        }
      } catch (err: any) {
        console.error("Error fetching PV data:", err);
        if (err.response?.status === 404) {
          setError(t("pv.processing"));
        } else {
          setError(t("pv.load_error"));
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
    if (!pvId || isValidated || isApproving) return;
    setIsApproving(true);
    try {
      await api.post(`/pv/${pvId}/validate`);
      setIsValidated(true);
      alert(t("pv.approved_success") || "Protocol successfully validated! Action items have been assigned.");
    } catch (err) {
      console.error("Failed to approve PV", err);
      alert(t("pv.approved_error") || "Error validating the protocol.");
    } finally {
      setIsApproving(false);
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
          {t('meeting_assistant.connecting')}
        </Typography>
      </Box>
    );
  }

  return (
    <Box sx={{ p: 3, height: "calc(100vh - 100px)", display: "flex", flexDirection: "column" }}>
      {error && !pvContent && (
        <Alert severity="info" sx={{ mb: 2 }}>
          {error}
        </Alert>
      )}

      {/* Header with Tools */}
      <Box sx={{ display: "flex", justifyContent: "space-between", mb: 3, alignItems: "center", flexWrap: "wrap", gap: 2 }}>
        <Typography sx={{ fontSize: 18, fontWeight: 600, color: "text.primary" }}>
          {t("pv.validator_title")}
        </Typography>
        
        <Stack direction="row" spacing={1.5} alignItems="center">
          <FormControl size="small" sx={{ minWidth: 140 }}>
            <InputLabel id="export-lang-label" sx={{ fontSize: 14 }}>{t("common.language") || "Language"}</InputLabel>
            <Select
              labelId="export-lang-label"
              value={exportLanguage}
              label={t("common.language") || "Language"}
              onChange={(e) => onLanguageChange(e.target.value as string)}
              sx={{ borderRadius: 2, bgcolor: "background.paper" }}
            >
              <MenuItem value="ar">العربية</MenuItem>
              <MenuItem value="fr">Français</MenuItem>
              <MenuItem value="en">English</MenuItem>
            </Select>
          </FormControl>
          
          <Button 
            variant="outlined" 
            size="medium" 
            startIcon={<EditIcon />} 
            disabled={!pvId || !originalTranscript}
            sx={{ borderRadius: 2, textTransform: "none", color: "text.primary", borderColor: "divider", bgcolor: "background.paper", "&:hover": { bgcolor: "action.hover" } }}
            onClick={() => {
              if (pvId) window.open(`/editor/${pvId}?lang=${exportLanguage}`, '_blank');
            }}
          >
            {t("pv.edit_online")}
          </Button>

          <DocumentExportMenu 
            pvId={pvId || ""} 
            language={exportLanguage} 
            disabled={!pvId || !originalTranscript}
            variant="outlined"
          />
        </Stack>
      </Box>

      <Grid container spacing={3} sx={{ flexGrow: 1, overflow: 'hidden', mb: 3 }}>
        {/* Left: Original Transcript */}
        <Grid item xs={12} md={5} sx={{ height: "100%" }}>
          <Paper
            variant="outlined"
            sx={{ p: 3, height: "100%", overflowY: "auto", borderRadius: 3, borderColor: "divider", bgcolor: alpha("#000", 0.01) }}
          >
            <Typography sx={{ fontSize: 14, fontWeight: 600, color: "text.secondary", mb: 2 }}>
              {t("pv.original_transcript")}
            </Typography>
            <Typography
              variant="body2"
              sx={{ whiteSpace: "pre-wrap", fontFamily: "monospace", fontSize: 13, lineHeight: 1.6 }}
            >
              {originalTranscript || t("pv.no_transcript")}
            </Typography>
          </Paper>
        </Grid>

        {/* Right: AI Generated PV (Editable) */}
        <Grid item xs={12} md={7} sx={{ height: "100%" }}>
          <Paper
            variant="outlined"
            sx={{
              p: 3,
              height: "100%",
              display: "flex",
              flexDirection: "column",
              borderRadius: 3,
              borderColor: "divider"
            }}
          >
            <Box
              sx={{ display: "flex", justifyContent: "space-between", mb: 2 }}
            >
              <Typography sx={{ fontSize: 14, fontWeight: 600, color: "primary.main" }}>
                {t("pv.ai_draft")}
              </Typography>
              <Tooltip title={t('meeting_assistant.save_draft_tooltip')}>
                <IconButton size="small" sx={{ border: "1px solid", borderColor: "divider", borderRadius: 1.5 }}>
                  <SaveIcon sx={{ fontSize: 18, color: "text.secondary" }} />
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
                  borderRadius: 2,
                  bgcolor: "transparent"
                },
                "& textarea": {
                  height: "100% !important",
                  fontFamily: "serif",
                  fontSize: "1.1rem",
                  lineHeight: 1.6
                },
              }}
              placeholder={t("pv.waiting_for_draft")}
            />
            <Box
              sx={{
                mt: 2,
                p: 2,
                border: "1px dashed",
                borderColor: "divider",
                borderRadius: 2,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                bgcolor: alpha("#000", 0.01)
              }}
            >
              <Typography
                sx={{ display: "flex", alignItems: "center", gap: 1, fontSize: 12, color: "text.secondary" }}
              >
                <EditIcon sx={{ fontSize: 16 }} /> {t("pv.signature_placeholder")}
              </Typography>
            </Box>
          </Paper>
        </Grid>
      </Grid>

      {/* BOTTOM ACTION BAR */}
      <Box 
        sx={{ 
          pt: 3, 
          borderTop: "1px solid", 
          borderColor: "divider",
          display: "flex",
          justifyContent: "flex-end"
        }}
      >
        <Button
          variant="contained"
          disableElevation
          startIcon={isApproving ? <CircularProgress size={16} color="inherit" /> : isValidated ? <CheckIcon /> : <ApproveIcon />}
          onClick={handleApprove}
          disabled={!pvId || !originalTranscript || isValidated || isApproving}
          sx={{ 
            bgcolor: isValidated ? "#10B981" : "#3B82F6", 
            color: "#FFF", 
            borderRadius: 2, 
            textTransform: "none", 
            fontWeight: 600, 
            fontSize: 14, 
            px: 4,
            "&:hover": { bgcolor: isValidated ? "#059669" : "#2563EB" },
            "&.Mui-disabled": { bgcolor: isValidated ? alpha("#10B981", 0.6) : undefined, color: isValidated ? "#FFF" : undefined }
          }}
        >
          {isValidated ? (t("pv.validated") || "Validated") : (t("pv.approve") || "Approve & Sign")}
        </Button>
      </Box>
    </Box>
  );
};

export default PVValidator;
