import React, { useState, useEffect, useCallback } from "react";
import {
  Box,
  Typography,
  Paper,
  CircularProgress,
  IconButton,
  Tooltip,
  Divider,
  Chip,
  TextField,
  Avatar,
} from "@mui/material";
import {
  Refresh as RefreshIcon,
  Download as DownloadIcon,
  Edit as EditIcon,
  Check as CheckIcon,
} from "@mui/icons-material";
import { useTranslation } from "react-i18next";
import { meetingsApi } from "../../services/meetings";
import { speakerColor } from "../../utils/speakerUtils";

interface TranscriptionViewerProps {
  meetingId: string;
}

const formatTimestamp = (seconds: number) => {
  const m = Math.floor(seconds / 60)
    .toString()
    .padStart(2, "0");
  const s = Math.floor(seconds % 60)
    .toString()
    .padStart(2, "0");
  return `${m}:${s}`;
};

const TranscriptionViewer: React.FC<TranscriptionViewerProps> = ({
  meetingId,
}) => {
  const { t } = useTranslation();
  const [transcription, setTranscription] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Local speaker mapping
  const [speakerMapping, setSpeakerMapping] = useState<Record<string, string>>(
    {},
  );
  const [editingSpeaker, setEditingSpeaker] = useState<string | null>(null);
  const [editValue, setEditValue] = useState("");

  const fetchTranscription = useCallback(async () => {
    try {
      const data = await meetingsApi.getTranscription(meetingId);
      setTranscription(data);
      setError(null);
    } catch (err: any) {
      if (err.response?.status !== 404) {
        setError(t('meeting_assistant.transcription_load_error'));
      }
    } finally {
      setLoading(false);
    }
  }, [meetingId]);

  useEffect(() => {
    fetchTranscription();

    // Poll for transcription if status is not 'completed' or 'failed'
    let interval: number;
    if (
      transcription &&
      ["pending", "processing"].includes(transcription.status)
    ) {
      interval = window.setInterval(fetchTranscription, 5000);
    }

    return () => {
      if (interval) clearInterval(interval);
    };
  }, [fetchTranscription, transcription?.status]);

  const handleSpeakerRename = (originalSpeaker: string) => {
    if (editValue.trim() !== "") {
      setSpeakerMapping((prev) => ({
        ...prev,
        [originalSpeaker]: editValue.trim(),
      }));
    }
    setEditingSpeaker(null);
    setEditValue("");
  };

  if (loading && !transcription) {
    return (
      <Box display="flex" justifyContent="center" p={4}>
        <CircularProgress />
      </Box>
    );
  }

  if (error) {
    return (
      <Typography color="error" textAlign="center" p={2}>
        {error}
      </Typography>
    );
  }

  if (!transcription) {
    return (
      <Paper sx={{ p: 4, textAlign: "center", bgcolor: "action.hover" }}>
        <Typography variant="body1" color="textSecondary">
          {t('meeting_assistant.no_transcription')}
        </Typography>
      </Paper>
    );
  }

  const hasSegments =
    transcription.segments &&
    Array.isArray(transcription.segments) &&
    transcription.segments.length > 0;

  return (
    <Paper sx={{ height: "100%", display: "flex", flexDirection: "column" }}>
      <Box
        sx={{
          p: 2,
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
        }}
      >
        <Box display="flex" alignItems="center" gap={2}>
          <Typography variant="h6">{t("transcription")}</Typography>
          <Chip
            label={transcription.status.toUpperCase()}
            size="small"
            color={
              transcription.status === "completed"
                ? "success"
                : transcription.status === "failed"
                  ? "error"
                  : "warning"
            }
          />
        </Box>
        <Box>
          <Tooltip title={t('common.refresh_tooltip')}>
            <IconButton onClick={fetchTranscription} disabled={loading}>
              <RefreshIcon fontSize="small" />
            </IconButton>
          </Tooltip>
          <Tooltip title={t('common.download_tooltip')}>
            <IconButton disabled={transcription.status !== "completed"}>
              <DownloadIcon fontSize="small" />
            </IconButton>
          </Tooltip>
        </Box>
      </Box>
      <Divider />
      <Box sx={{ p: 2, flexGrow: 1, overflowY: "auto", maxHeight: 500 }}>
        {transcription.status === "processing" && (
          <Box display="flex" alignItems="center" gap={2} mb={2}>
            <CircularProgress size={20} />
            <Typography variant="body2" color="textSecondary italic">
              {t('meeting_assistant.transcribing')}
            </Typography>
          </Box>
        )}

        {hasSegments ? (
          transcription.segments.map((segment: any, index: number) => {
            const originalSpeaker = segment.speaker || t('meeting_assistant.unknown_speaker');
            const displaySpeaker =
              speakerMapping[originalSpeaker] || originalSpeaker;
            const speakerColorValue = speakerColor(originalSpeaker);
            const isEditing = editingSpeaker === originalSpeaker;

            return (
              <Box key={index} mb={3} display="flex" gap={2}>
                <Avatar
                  sx={{
                    bgcolor: speakerColorValue,
                    width: 40,
                    height: 40,
                    fontSize: "1rem",
                  }}
                >
                  {displaySpeaker.substring(0, 2).toUpperCase()}
                </Avatar>
                <Box flexGrow={1}>
                  <Box display="flex" alignItems="center" gap={1} mb={0.5}>
                    {isEditing ? (
                      <Box display="flex" alignItems="center">
                        <TextField
                          size="small"
                          variant="standard"
                          autoFocus
                          value={editValue}
                          onChange={(e) => setEditValue(e.target.value)}
                          onKeyDown={(e) =>
                            e.key === "Enter" &&
                            handleSpeakerRename(originalSpeaker)
                          }
                        />
                        <IconButton
                          size="small"
                          onClick={() => handleSpeakerRename(originalSpeaker)}
                        >
                          <CheckIcon fontSize="small" color="success" />
                        </IconButton>
                      </Box>
                    ) : (
                      <Typography
                        variant="subtitle2"
                        sx={{
                          color: speakerColorValue,
                          fontWeight: "bold",
                          cursor: "pointer",
                        }}
                        onClick={() => {
                          setEditingSpeaker(originalSpeaker);
                          setEditValue(displaySpeaker);
                        }}
                      >
                        {displaySpeaker}
                      </Typography>
                    )}
                    <Typography variant="caption" color="textSecondary">
                      {formatTimestamp(segment.start)} -{" "}
                      {formatTimestamp(segment.end)}
                    </Typography>
                  </Box>
                  <Typography
                    variant="body1"
                    sx={{ bgcolor: "action.hover", p: 1.5, borderRadius: 2 }}
                  >
                    {segment.text}
                  </Typography>
                </Box>
              </Box>
            );
          })
        ) : transcription.full_text || transcription.content ? (
          <Box>
            <Typography
              variant="body1"
              sx={{ whiteSpace: "pre-wrap", lineHeight: 1.8 }}
            >
              {transcription.full_text || transcription.content}
            </Typography>
          </Box>
        ) : (
          <Typography variant="body2" color="textSecondary">
            {t('meeting_assistant.no_text')}
          </Typography>
        )}
      </Box>
    </Paper>
  );
};

export default TranscriptionViewer;
