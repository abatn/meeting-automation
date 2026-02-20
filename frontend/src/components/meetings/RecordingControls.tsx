import React, { useState } from 'react';
import { Button, Box } from '@mui/material';
import { Mic, MicOff, Stop } from '@mui/icons-material';
import { useTranslation } from 'react-i18next';

const RecordingControls: React.FC = () => {
  const { t } = useTranslation();
  const [isRecording, setIsRecording] = useState(false);

  const handleToggleRecording = () => {
    // TODO: Handle recording logic
    setIsRecording(!isRecording);
  };

  return (
    <Box>
      <Button
        variant="contained"
        startIcon={isRecording ? <MicOff /> : <Mic />}
        onClick={handleToggleRecording}
      >
        {isRecording ? t('stopRecording') : t('startRecording')}
      </Button>
    </Box>
  );
};

export default RecordingControls;