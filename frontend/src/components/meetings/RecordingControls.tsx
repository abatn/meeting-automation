import React, { useState, useEffect } from 'react';
import { 
  Box, 
  Paper, 
  Typography, 
  IconButton, 
  Button, 
  LinearProgress, 
  Stack,
  Alert
} from '@mui/material';
import { 
  Mic as MicIcon, 
  Stop as StopIcon, 
  Pause as PauseIcon, 
  PlayArrow as PlayIcon,
  CloudUpload as UploadIcon,
  GraphicEq as WaveIcon
} from '@mui/icons-material';
import { useTranslation } from 'react-i18next';
import TranscriptionProgress from './TranscriptionProgress';

const RecordingControls: React.FC = () => {
  const { t } = useTranslation();
  const [isRecording, setIsRecording] = useState(false);
  const [isPaused, setIsPaused] = useState(false);
  const [duration, setDuration] = useState(0);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [recordingId, setRecordingId] = useState<string | null>(null);

  useEffect(() => {
    let interval: any;
    if (isRecording && !isPaused) {
      interval = setInterval(() => {
        setDuration((prev) => prev + 1);
      }, 1000);
    }
    return () => clearInterval(interval);
  }, [isRecording, isPaused]);

  const formatTime = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  };

  const handleStart = () => {
    setIsRecording(true);
    setIsPaused(false);
  };

  const handleStop = () => {
    setIsRecording(false);
    // Simulate upload
    setUploadProgress(10);
    const interval = setInterval(() => {
      setUploadProgress((prev) => {
        if (prev >= 100) {
          clearInterval(interval);
          // Set a mock recordingId to start WebSocket connection
          setRecordingId("mock-rec-1234");
          return 100;
        }
        return prev + 20;
      });
    }, 500);
  };

  return (
    <Paper sx={{ p: 3, textAlign: 'center' }}>
      <Typography variant="h6" gutterBottom>{t('meetings.recording_session')}</Typography>
      
      <Box sx={{ my: 4, display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
        <Typography variant="h2" sx={{ fontFamily: 'monospace', mb: 2, color: isRecording ? 'error.main' : 'text.primary' }}>
          {formatTime(duration)}
        </Typography>
        
        {isRecording && (
           <Box sx={{ display: 'flex', gap: 1, mb: 2, color: 'error.main' }}>
              <WaveIcon className="animate-pulse" />
              <Typography variant="caption">{t('meetings.live_recording')}</Typography>
           </Box>
        )}

        <Stack direction="row" spacing={3}>
          {!isRecording ? (
            <Button 
              variant="contained" 
              color="error" 
              size="large" 
              startIcon={<MicIcon />}
              onClick={handleStart}
              sx={{ borderRadius: 10, px: 4 }}
            >
              {t('meetings.start_recording')}
            </Button>
          ) : (
            <>
              <IconButton 
                size="large" 
                color="primary" 
                onClick={() => setIsPaused(!isPaused)}
                sx={{ border: '2px solid' }}
              >
                {isPaused ? <PlayIcon fontSize="large" /> : <PauseIcon fontSize="large" />}
              </IconButton>
              <IconButton 
                size="large" 
                color="error" 
                onClick={handleStop}
                sx={{ border: '2px solid' }}
              >
                <StopIcon fontSize="large" />
              </IconButton>
            </>
          )}
        </Stack>
      </Box>

      {uploadProgress > 0 && uploadProgress < 100 && (
        <Box sx={{ mt: 3 }}>
          <Typography variant="body2" color="textSecondary" gutterBottom>
            {t('meetings.uploading')}
          </Typography>
          <LinearProgress variant="determinate" value={uploadProgress} sx={{ height: 10, borderRadius: 5 }} />
        </Box>
      )}

      {uploadProgress === 100 && (
        <Box sx={{ mt: 3 }}>
          <Alert severity="success" sx={{ mb: 2 }}>
            {t('meetings.transcription_started')}
          </Alert>
          {recordingId && (
            <TranscriptionProgress recordingId={recordingId} />
          )}
        </Box>
      )}

      <Box sx={{ mt: 4, pt: 2, borderTop: '1px solid #eee' }}>
        <Button startIcon={<UploadIcon />} variant="outlined">
          {t('meetings.upload_file')}
        </Button>
      </Box>
    </Paper>
  );
};

export default RecordingControls;