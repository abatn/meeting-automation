import React from 'react';
import { Box, Typography, Paper } from '@mui/material';
import { useTranslation } from 'react-i18next';

interface TranscriptionSegment {
  speaker: string;
  timestamp: string;
  text: string;
}

interface TranscriptionViewerProps {
  segments: TranscriptionSegment[];
}

const TranscriptionViewer: React.FC<TranscriptionViewerProps> = ({ segments }) => {
  const { t } = useTranslation();

  return (
    <Paper style={{ padding: 16, maxHeight: 400, overflow: 'auto' }}>
      <Typography variant="h6">{t('transcription')}</Typography>
      {segments.map((segment, index) => (
        <Box key={index} my={1}>
          <Typography variant="body2" color="textSecondary">
            {segment.speaker} - {segment.timestamp}
          </Typography>
          <Typography variant="body1">{segment.text}</Typography>
        </Box>
      ))}
    </Paper>
  );
};

export default TranscriptionViewer;