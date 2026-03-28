import React, { useState } from "react";
import {
  Box,
  Button,
  Typography,
  Paper,
  IconButton,
  LinearProgress,
  Alert,
  CircularProgress,
} from "@mui/material";
import {
  Mic as MicIcon,
  Stop as StopIcon,
  Pause as PauseIcon,
  PlayArrow as PlayArrowIcon,
} from "@mui/icons-material";
import { useAudioRecorder } from "../../hooks/useAudioRecorder";

interface AudioRecorderProps {
  meetingId: string;
  onUploadSuccess?: (recording: any) => void;
}

const AudioRecorder: React.FC<AudioRecorderProps> = ({
  meetingId,
  onUploadSuccess,
}) => {
  const {
    isRecording,
    isPaused,
    duration,
    startRecording,
    stopRecording,
    pauseRecording,
    resumeRecording,
    error: recorderError,
  } = useAudioRecorder();

  const [isFinishing, setIsFinishing] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);

  const formatDuration = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins.toString().padStart(2, "0")}:${secs.toString().padStart(2, "0")}`;
  };

  const handleStart = async () => {
    setUploadError(null);
    await startRecording(meetingId);
  };

  const handleStop = async () => {
    setIsFinishing(true);
    try {
      const recordingResponse = await stopRecording(meetingId);
      if (recordingResponse && onUploadSuccess) {
        onUploadSuccess(recordingResponse);
      } else if (!recordingResponse) {
        setUploadError("Failed to save the recording.");
      }
    } catch (err: any) {
      setUploadError(
        err.message || "An error occurred while finishing recording.",
      );
    } finally {
      setIsFinishing(false);
    }
  };

  return (
    <Paper sx={{ p: 3, textAlign: "center", bgcolor: "background.default" }}>
      <Typography variant="h6" gutterBottom>
        Live Meeting Assistant
      </Typography>

      {(recorderError || uploadError) && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {recorderError || uploadError}
        </Alert>
      )}

      <Box
        sx={{
          my: 4,
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
        }}
      >
        <Typography variant="h3" sx={{ mb: 2, fontFamily: "monospace" }}>
          {formatDuration(duration)}
        </Typography>

        {isRecording && !isFinishing && (
          <Box sx={{ width: "100%", mb: 2 }}>
            <LinearProgress color="secondary" />
          </Box>
        )}

        {isFinishing && (
          <Box sx={{ width: "100%", mb: 2 }}>
            <Typography variant="body2" sx={{ mb: 1 }}>
              Finalizing Protocol...
            </Typography>
            <LinearProgress color="primary" />
          </Box>
        )}

        <Box sx={{ display: "flex", gap: 2 }}>
          {!isRecording && !isFinishing && (
            <Button
              variant="contained"
              startIcon={<MicIcon />}
              onClick={handleStart}
              size="large"
              sx={{ 
                bgcolor: "#10B981", 
                color: "#FFF", 
                boxShadow: "none", 
                textTransform: "none",
                fontWeight: 600,
                "&:hover": { bgcolor: "#059669", boxShadow: "none" } 
              }}
            >
              Start Meeting
            </Button>
          )}

          {isRecording && !isFinishing && (
            <>
              <IconButton
                color="secondary"
                onClick={isPaused ? resumeRecording : pauseRecording}
                size="large"
                sx={{ border: "1px solid", borderColor: "divider" }}
              >
                {isPaused ? <PlayArrowIcon /> : <PauseIcon />}
              </IconButton>
              <Button
                variant="contained"
                startIcon={<StopIcon />}
                onClick={handleStop}
                size="large"
                sx={{ 
                  bgcolor: "#EF4444", 
                  color: "#FFF", 
                  boxShadow: "none", 
                  textTransform: "none",
                  fontWeight: 600,
                  "&:hover": { bgcolor: "#DC2626", boxShadow: "none" } 
                }}
              >
                Finish Meeting
              </Button>
            </>
          )}
        </Box>
      </Box>

      <Typography variant="caption" color="textSecondary">
        {isFinishing
          ? "Saving recording to server..."
          : isRecording
            ? "Recording in progress (Streaming)..."
            : "Ready to record live"}
      </Typography>
    </Paper>
  );
};

export default AudioRecorder;
