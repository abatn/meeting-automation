import React, { useState } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Box,
  Typography,
  Button,
  Stack,
  Chip,
  FormControlLabel,
  Checkbox,
  Stepper,
  Step,
  StepLabel,
  Divider,
} from '@mui/material';
import { useTranslation } from 'react-i18next';

export interface ConsentValue {
  consent_type: 'C1_AUDIO' | 'C2_VOICE' | 'C3_SHARING' | 'C4_STORAGE';
  consented: boolean;
}

interface ConsentDialogProps {
  open: boolean;
  onClose: () => void;
  onSubmit: (consents: ConsentValue[]) => void;
}

const STEPS = ['c1', 'c2', 'c3', 'c4'] as const;

const ConsentDialog: React.FC<ConsentDialogProps> = ({ open, onClose, onSubmit }) => {
  const { t } = useTranslation();
  const [activeStep, setActiveStep] = useState(0);
  const [values, setValues] = useState<Record<string, boolean>>({
    c1: false,
    c2: false,
    c3: false,
    c4: false,
  });

  const isRequired = (key: string) => key !== 'c2';

  const handleToggle = (key: string) => (e: React.ChangeEvent<HTMLInputElement>) => {
    setValues((prev) => ({ ...prev, [key]: e.target.checked }));
  };

  const currentKey = STEPS[activeStep];
  const canProceed =
    activeStep === STEPS.length - 1
      ? values.c1 && values.c3 && values.c4
      : true;

  const handleNext = () => {
    if (activeStep < STEPS.length - 1) {
      setActiveStep((s) => s + 1);
    }
  };

  const handleBack = () => {
    if (activeStep > 0) setActiveStep((s) => s - 1);
  };

  const handleSubmit = () => {
    const consents: ConsentValue[] = STEPS.map((key) => ({
      consent_type:
        key === 'c1'
          ? 'C1_AUDIO'
          : key === 'c2'
          ? 'C2_VOICE'
          : key === 'c3'
          ? 'C3_SHARING'
          : 'C4_STORAGE',
      consented: values[key],
    }));
    onSubmit(consents);
  };

  return (
    <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
      <DialogTitle>
        <Typography variant="h6" fontWeight={800}>{t('consent.title')}</Typography>
        <Typography variant="caption" color="text.secondary">{t('consent.subtitle')}</Typography>
      </DialogTitle>
      <DialogContent dividers>
        <Stepper activeStep={activeStep} alternativeLabel sx={{ mb: 2 }}>
          {STEPS.map((s) => (
            <Step key={s}>
              <StepLabel>{t(`consent.${s}.short`)}</StepLabel>
            </Step>
          ))}
        </Stepper>

        <Box>
          <Stack direction="row" alignItems="center" spacing={1} sx={{ mb: 1 }}>
            <Typography variant="subtitle1" fontWeight={700}>
              {t(`consent.${currentKey}.title`)}
            </Typography>
            <Chip
              size="small"
              color={isRequired(currentKey) ? 'error' : 'default'}
              label={isRequired(currentKey) ? t('consent.required_badge') : t('consent.optional_badge')}
            />
          </Stack>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
            {t(`consent.${currentKey}.body`)}
          </Typography>
          <FormControlLabel
            control={
              <Checkbox
                checked={values[currentKey]}
                onChange={handleToggle(currentKey)}
                color={isRequired(currentKey) ? 'primary' : 'secondary'}
              />
            }
            label={
              isRequired(currentKey)
                ? t('consent.accept_all')
                : t('consent.c2.title')
            }
          />
          <Divider sx={{ mt: 2 }} />
          <Typography variant="caption" color="text.secondary">
            {t('consent.step', { current: activeStep + 1, total: STEPS.length })}
            {' — '}
            {t('consent.required_note')}
          </Typography>
        </Box>
      </DialogContent>
      <DialogActions sx={{ px: 3, py: 2 }}>
        <Button onClick={handleBack} disabled={activeStep === 0}>
          {t('consent.back')}
        </Button>
        {activeStep < STEPS.length - 1 ? (
          <Button variant="contained" onClick={handleNext}>
            {t('consent.next')}
          </Button>
        ) : (
          <Button
            variant="contained"
            onClick={handleSubmit}
            disabled={!canProceed}
          >
            {t('consent.submit')}
          </Button>
        )}
      </DialogActions>
    </Dialog>
  );
};

export default ConsentDialog;
