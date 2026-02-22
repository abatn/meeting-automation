import React, { useState, useEffect } from 'react';
import { 
  Box, 
  Button, 
  Typography, 
  Paper, 
  IconButton, 
  LinearProgress,
  Alert,
  CircularProgress
} from '@mui/material';
import {
  Mic as MicIcon,
  Stop as StopIcon,
  Pause as PauseIcon,
  PlayArrow as PlayArrowIcon,
  CloudUpload as UploadIcon,
  Delete as DeleteIcon
} from '@mui/icons-material';
import { useAudioRecorder } from '../../hooks/useAudioRecorder';
import { meetingsApi } from '../../services/meetings';

interface AudioRecorderProps {
  meetingId: string;
  onUploadSuccess?: (recording: any) => void;
}

const AudioRecorder: React.FC<AudioRecorderProps> = ({ meetingId, onUploadSuccess }) => {
  const {
    isRecording,
    isPaused,
    duration,
    startRecording,
    stopRecording,
    pauseRecording,
    resumeRecording,
    error: recorderError
  } = useAudioRecorder();

  const [audioBlob, setAudioBlob] = useState<Blob | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);

  const formatDuration = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  };

  const handleStop = async () => {
    const blob = await stopRecording();
    if (blob) {
      setAudioBlob(blob);
    }
  };

  const handleUpload = async () => {
    if (!audioBlob) return;

    setIsUploading(true);
    setUploadError(null);
    try {
      const file = new File([audioBlob], `recording-${meetingId}.wav`, { type: 'audio/wav' });
      const response = await meetingsApi.uploadRecording(meetingId, file);
      if (onUploadSuccess) {
        onUploadSuccess(response.data);
      }
      setAudioBlob(null);
    } catch (err: any) {
      setUploadError(err.response?.data?.detail || 'Failed to upload recording');
    } finally {
      setIsUploading(false);
    }
  };

  const handleDiscard = () => {
    setAudioBlob(null);
    setUploadError(null);
  };

  return (
    <Paper sx={{ p: 3, textAlign: 'center', bgcolor: 'background.default' }}>
      <Typography variant="h6" gutterBottom>
        Meeting Recording
      </Typography>

      {(recorderError || uploadError) && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {recorderError || uploadError}
        </Alert>
      )}

      <Box sx={{ my: 4, display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
        <Typography variant="h3" sx={{ mb: 2, fontFamily: 'monospace' }}>
          {formatDuration(duration)}
        </Typography>
        
        {isRecording && (
          <Box sx={{ width: '100%', mb: 2 }}>
            <LinearProgress color="secondary" />
          </Box>
        )}

        <Box sx={{ display: 'flex', gap: 2 }}>
          {!isRecording && !audioBlob && (
            <Button
              variant="contained"
              color="primary"
              startIcon={<MicIcon />}
              onClick={startRecording}
              size="large"
            >
              Start Recording
            </Button>
          )}

          {isRecording && (
            <>
              <IconButton 
                color="secondary" 
                onClick={isPaused ? resumeRecording : pauseRecording}
                size="large"
              >
                {isPaused ? <PlayArrowIcon /> : <PauseIcon />}
              </IconButton>
              <IconButton 
                color="error" 
                onClick={handleStop}
                size="large"
              >
                <StopIcon />
              </IconButton>
            </>
          )}

          {audioBlob && !isUploading && (
            <>
              <Button
                variant="contained"
                color="success"
                startIcon={<UploadIcon />}
                onClick={handleUpload}
              >
                Upload & Process
              </Button>
              <Button
                variant="outlined"
                color="error"
                startIcon={<DeleteIcon />}
                onClick={handleDiscard}
              >
                Discard
              </Button>
            </>
          )}

          {isUploading && <CircularProgress />}
        </Box>
      </Box>

      <Typography variant="caption" color="textSecondary">
        {isRecording ? 'Recording in progress...' : audioBlob ? 'Recording captured' : 'Ready to record'}
      </Typography>
    </Paper>
  );
};

export default AudioRecorder;