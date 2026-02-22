import React, { useState, useEffect, useCallback } from 'react';
import { 
  Box, 
  Typography, 
  Paper, 
  CircularProgress, 
  IconButton, 
  Tooltip,
  Divider,
  Chip
} from '@mui/material';
import { Refresh as RefreshIcon, Download as DownloadIcon } from '@mui/icons-material';
import { useTranslation } from 'react-i18next';
import { meetingsApi } from '../../services/meetings';

interface TranscriptionViewerProps {
  meetingId: string;
}

const TranscriptionViewer: React.FC<TranscriptionViewerProps> = ({ meetingId }) => {
  const { t } = useTranslation();
  const [transcription, setTranscription] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchTranscription = useCallback(async () => {
    try {
      const data = await meetingsApi.getTranscription(meetingId);
      setTranscription(data);
      setError(null);
    } catch (err: any) {
      if (err.response?.status !== 404) {
        setError('Failed to load transcription');
      }
    } finally {
      setLoading(false);
    }
  }, [meetingId]);

  useEffect(() => {
    fetchTranscription();
    
    // Poll for transcription if status is not 'completed' or 'failed'
    let interval: number;
    if (transcription && ['pending', 'processing'].includes(transcription.status)) {
      interval = window.setInterval(fetchTranscription, 5000);
    }

    return () => {
      if (interval) clearInterval(interval);
    };
  }, [fetchTranscription, transcription?.status]);

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
      <Paper sx={{ p: 4, textAlign: 'center', bgcolor: 'action.hover' }}>
        <Typography variant="body1" color="textSecondary">
          No transcription available yet. Start recording to generate one.
        </Typography>
      </Paper>
    );
  }

  return (
    <Paper sx={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      <Box sx={{ p: 2, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <Box display="flex" alignItems="center" gap={2}>
          <Typography variant="h6">{t('transcription')}</Typography>
          <Chip 
            label={transcription.status.toUpperCase()} 
            size="small" 
            color={
              transcription.status === 'completed' ? 'success' : 
              transcription.status === 'failed' ? 'error' : 'warning'
            } 
          />
        </Box>
        <Box>
          <Tooltip title="Refresh">
            <IconButton onClick={fetchTranscription} disabled={loading}>
              <RefreshIcon fontSize="small" />
            </IconButton>
          </Tooltip>
          <Tooltip title="Download">
            <IconButton disabled={transcription.status !== 'completed'}>
              <DownloadIcon fontSize="small" />
            </IconButton>
          </Tooltip>
        </Box>
      </Box>
      <Divider />
      <Box sx={{ p: 2, flexGrow: 1, overflowY: 'auto', maxHeight: 500 }}>
        {transcription.status === 'processing' && (
          <Box display="flex" alignItems="center" gap={2} mb={2}>
            <CircularProgress size={20} />
            <Typography variant="body2" color="textSecondary italic">
              AI is currently transcribing the meeting...
            </Typography>
          </Box>
        )}
        
        {transcription.content ? (
          <Box>
            <Typography variant="body1" sx={{ whiteSpace: 'pre-wrap', lineHeight: 1.8 }}>
              {transcription.content}
            </Typography>
          </Box>
        ) : (
          transcription.segments?.map((segment: any, index: number) => (
            <Box key={index} mb={2}>
              <Box display="flex" justifyContent="space-between" mb={0.5}>
                <Typography variant="subtitle2" color="primary">
                  {segment.speaker || 'Unknown Speaker'}
                </Typography>
                <Typography variant="caption" color="textSecondary">
                  {segment.timestamp}
                </Typography>
              </Box>
              <Typography variant="body1">{segment.text}</Typography>
            </Box>
          ))
        )}
      </Box>
    </Paper>
  );
};

export default TranscriptionViewer;