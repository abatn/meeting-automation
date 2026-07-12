import React from 'react';
import { Container, Typography, Box } from '@mui/material';
import { useTranslation } from 'react-i18next';

export default function PrivacyPolicy() {
  const { t } = useTranslation();

  return (
    <Container maxWidth="md" sx={{ py: 4 }}>
      <Typography variant="h4" gutterBottom>{t('consent.title')}</Typography>

      <Typography variant="h6" gutterBottom>{t('consent.audio_recording.short')}</Typography>
      <Typography variant="body1" paragraph>{t('consent.audio_recording.text')}</Typography>

      <Typography variant="h6" gutterBottom>{t('consent.voice_profiling.short')}</Typography>
      <Typography variant="body1" paragraph>{t('consent.voice_profiling.text')}</Typography>

      <Typography variant="h6" gutterBottom>{t('consent.third_party_sharing.short')}</Typography>
      <Typography variant="body1" paragraph>{t('consent.third_party_sharing.text')}</Typography>

      <Typography variant="h6" gutterBottom>{t('consent.transcript_storage.short')}</Typography>
      <Typography variant="body1" paragraph>{t('consent.transcript_storage.text')}</Typography>

      <Box sx={{ mt: 4 }}>
        <Typography variant="body2" color="text.secondary">
          Contact: privacy@meeting-automation.com
        </Typography>
      </Box>
    </Container>
  );
}
