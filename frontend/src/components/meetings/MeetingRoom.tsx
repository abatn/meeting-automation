import React, { useState } from 'react';
import { useParams } from 'react-router-dom';
import { Box, Grid, Typography, Paper, Divider, Tab, Tabs } from '@mui/material';
import AudioRecorder from './AudioRecorder';
import TranscriptionViewer from './TranscriptionViewer';
import PVValidator from './PVValidator';
import { useTranslation } from 'react-i18next';

const MeetingRoom: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const { t } = useTranslation();
  const [activeTab, setActiveTab] = useState(0);

  const handleTabChange = (event: React.SyntheticEvent, newValue: number) => {
    setActiveTab(newValue);
  };

  return (
    <Box sx={{ flexGrow: 1 }}>
      <Typography variant="h4" gutterBottom>
        Meeting Room: {id}
      </Typography>
      
      <Grid container spacing={3}>
        {/* Left Column: Live Recording Controls */}
        <Grid item xs={12} md={4}>
          <Box sx={{ mb: 3 }}>
            <AudioRecorder meetingId={id!} onUploadSuccess={() => setActiveTab(1)} />
          </Box>
          <Paper sx={{ p: 2 }}>
            <Typography variant="h6" gutterBottom>Meeting Info</Typography>
            <Divider sx={{ mb: 2 }} />
            <Typography variant="body2"><strong>ID:</strong> {id}</Typography>
            <Typography variant="body2"><strong>Status:</strong> Live</Typography>
          </Paper>
        </Grid>

        {/* Right Column: Dynamic Content (Transcription / PV) */}
        <Grid item xs={12} md={8}>
          <Paper sx={{ width: '100%', mb: 2 }}>
            <Tabs value={activeTab} onChange={handleTabChange} centered>
              <Tab label={t('meetings.live_transcription')} />
              <Tab label={t('meetings.protocol_pv')} />
            </Tabs>
          </Paper>

          {activeTab === 0 && (
            <TranscriptionViewer meetingId={id!} />
          )}

          {activeTab === 1 && (
            <PVValidator />
          )}
        </Grid>
      </Grid>
    </Box>
  );
};

export default MeetingRoom;