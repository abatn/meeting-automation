import React, { useState } from 'react';
import {
  Dialog, DialogTitle, DialogContent, DialogActions,
  Button, Checkbox, FormControlLabel, Typography, Box,
  Stepper, Step, StepLabel, Alert
} from '@mui/material';
import { useTranslation } from 'react-i18next';

interface ConsentItem {
  type: string;
  required: boolean;
  translationKey: string;
}

interface ConsentDialogProps {
  open: boolean;
  onClose: () => void;
  onConfirm: (consents: { consent_type: string; consented: boolean; consent_version: string }[]) => void;
}

const CONSENTS: ConsentItem[] = [
  { type: 'audio_recording', required: true, translationKey: 'consent.audio_recording' },
  { type: 'voice_profiling', required: false, translationKey: 'consent.voice_profiling' },
  { type: 'third_party_sharing', required: true, translationKey: 'consent.third_party_sharing' },
  { type: 'transcript_storage', required: true, translationKey: 'consent.transcript_storage' },
];

export default function ConsentDialog({ open, onClose, onConfirm }: ConsentDialogProps) {
  const { t } = useTranslation();
  const [activeStep, setActiveStep] = useState(0);
  const [checked, setChecked] = useState<Record<string, boolean>>({
    audio_recording: false,
    voice_profiling: false,
    third_party_sharing: false,
    transcript_storage: false,
  });

  const allRequired = CONSENTS.filter(c => c.required).every(c => checked[c.type]);
  const current = CONSENTS[activeStep];

  const handleToggle = (type: string) => {
    setChecked(prev => ({ ...prev, [type]: !prev[type] }));
  };

  const handleNext = () => {
    if (activeStep < CONSENTS.length - 1) setActiveStep(prev => prev + 1);
  };

  const handleBack = () => {
    if (activeStep > 0) setActiveStep(prev => prev - 1);
  };

  const handleConfirm = () => {
    onConfirm(CONSENTS.map(c => ({
      consent_type: c.type,
      consented: checked[c.type],
      consent_version: '1.0',
    })));
  };

  return (
    <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
      <DialogTitle>{t('consent.title')}</DialogTitle>
      <DialogContent>
        <Stepper activeStep={activeStep} sx={{ mb: 3 }}>
          {CONSENTS.map((c) => (
            <Step key={c.type}>
              <StepLabel>{t(`${c.translationKey}.short`)}</StepLabel>
            </Step>
          ))}
        </Stepper>

        <Alert severity="info" sx={{ mb: 2 }}>
          {current.required ? t('consent.required_notice') : t('consent.optional_notice')}
        </Alert>

        <Typography variant="body1" sx={{ mb: 2 }}>
          {t(`${current.translationKey}.text`)}
        </Typography>

        <FormControlLabel
          control={
            <Checkbox
              checked={checked[current.type]}
              onChange={() => handleToggle(current.type)}
            />
          }
          label={t(`${current.translationKey}.checkbox`)}
        />
      </DialogContent>

      <DialogActions>
        <Button onClick={handleBack} disabled={activeStep === 0}>{t('common.back')}</Button>
        {activeStep < CONSENTS.length - 1 ? (
          <Button onClick={handleNext} variant="contained">{t('common.next')}</Button>
        ) : (
          <Button onClick={handleConfirm} variant="contained" disabled={!allRequired}>
            {t('consent.confirm')}
          </Button>
        )}
      </DialogActions>
    </Dialog>
  );
}
