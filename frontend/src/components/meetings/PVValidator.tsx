import React, { useState } from 'react';
import { 
  Box, 
  Grid, 
  Paper, 
  Typography, 
  TextField, 
  Button, 
  Divider,
  Stack,
  IconButton,
  Tooltip
} from '@mui/material';
import { 
  CheckCircle as ApproveIcon, 
  Edit as EditIcon, 
  History as HistoryIcon,
  PictureAsPdf as PdfIcon,
  Draw as SignatureIcon,
  Save as SaveIcon
} from '@mui/icons-material';
import { useTranslation } from 'react-i18next';

const PVValidator: React.FC = () => {
  const { t } = useTranslation();
  const [pvContent, setPvContent] = useState(`
# Procès-Verbal de Réunion - IT Strategy
Date: 20/02/2026

## Agenda
1. Migration Cloud
2. Recrutement Devs

## Décisions
- Migration vers Azure approuvée pour Q3.
- Recrutement de 3 développeurs backend.
  `);

  const originalTranscript = `
Sami: Alors, on passe au point suivant, le Cloud.
Mohamed: Je propose Azure, c'est mieux pour notre stack actuelle.
DG: Ok, c'est validé pour le troisième trimestre.
Sami: Et pour les devs ?
DG: On a le budget pour trois nouveaux profils backend.
  `;

  return (
    <Box sx={{ p: 3, height: 'calc(100vh - 100px)' }}>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 2 }}>
        <Typography variant="h5">{t('pv.validator_title', 'PV Validation Workflow')}</Typography>
        <Stack direction="row" spacing={2}>
          <Button variant="outlined" startIcon={<HistoryIcon />}>{t('pv.versions', 'Versions')}</Button>
          <Button variant="outlined" startIcon={<PdfIcon />}>{t('pv.preview', 'PDF Preview')}</Button>
          <Button variant="contained" color="success" startIcon={<ApproveIcon />}>{t('pv.approve', 'Approve & Sign')}</Button>
        </Stack>
      </Box>

      <Grid container spacing={2} sx={{ height: '90%' }}>
        {/* Left: Original Transcript */}
        <Grid item xs={12} md={5} sx={{ height: '100%' }}>
          <Paper sx={{ p: 2, height: '100%', overflowY: 'auto', bgcolor: '#f8f9fa' }}>
            <Typography variant="subtitle2" gutterBottom color="textSecondary">
              {t('pv.original_transcript', 'Original Transcription (AI)')}
            </Typography>
            <Typography variant="body2" sx={{ whiteSpace: 'pre-wrap', fontFamily: 'monospace' }}>
              {originalTranscript}
            </Typography>
          </Paper>
        </Grid>

        {/* Right: AI Generated PV (Editable) */}
        <Grid item xs={12} md={7} sx={{ height: '100%' }}>
          <Paper sx={{ p: 2, height: '100%', display: 'flex', flexDirection: 'column' }}>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
              <Typography variant="subtitle2" color="primary">
                {t('pv.ai_draft', 'AI-Generated PV Draft')}
              </Typography>
              <Tooltip title="Save Draft">
                <IconButton size="small"><SaveIcon fontSize="small" /></IconButton>
              </Tooltip>
            </Box>
            <TextField
              multiline
              fullWidth
              value={pvContent}
              onChange={(e) => setPvContent(e.target.value)}
              variant="outlined"
              sx={{ 
                flexGrow: 1,
                '& .MuiInputBase-root': { height: '100%', alignItems: 'flex-start' },
                '& textarea': { height: '100% !important', fontFamily: 'serif', fontSize: '1.1rem' }
              }}
            />
            <Box sx={{ mt: 2, p: 2, border: '1px dashed #ccc', borderRadius: 1, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
               <Typography variant="caption" sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                 <EditIcon fontSize="small" /> {t('pv.signature_placeholder', 'Electronic Signature Area (ISO 27001)')}
               </Typography>
            </Box>
          </Paper>
        </Grid>
      </Grid>
    </Box>
  );
};

export default PVValidator;