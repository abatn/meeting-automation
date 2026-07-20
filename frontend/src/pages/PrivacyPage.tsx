import React from 'react';
import { Container, Typography, Box, Divider, Link as MuiLink, Paper, CssBaseline } from '@mui/material';
import { useTranslation } from 'react-i18next';
import { Link as RouterLink } from 'react-router-dom';

export default function PrivacyPage() {
  const { t, i18n } = useTranslation();
  const isRtl = i18n.dir() === 'rtl';

  const sections = [
    'data_controller',
    'scope',
    'legal_basis',
    'data_collected',
    'c1_audio',
    'c2_voice',
    'c3_sharing',
    'c4_storage',
    'data_retention',
    'your_rights',
    'inpdp_reference',
    'contact',
  ];

  return (
    <Box sx={{ bgcolor: '#050505', color: '#FAFAFA', minHeight: '100vh', direction: isRtl ? 'rtl' : 'ltr', fontFamily: isRtl ? "'Noto Sans Arabic', sans-serif" : "'Inter', sans-serif" }}>
      <CssBaseline />
      <Container maxWidth="md" sx={{ py: { xs: 6, md: 10 } }}>
        <Typography variant="h3" fontWeight={800} gutterBottom sx={{ letterSpacing: '-0.02em' }}>
          {t('privacy.title')}
        </Typography>
        <Typography variant="body2" sx={{ color: '#71717A', mb: 4 }}>
          {t('privacy.last_updated')}
        </Typography>

        <Paper elevation={0} sx={{ p: { xs: 3, md: 5 }, bgcolor: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.06)', borderRadius: '16px' }}>
          {sections.map((key) => (
            <Box key={key} sx={{ mb: 4 }}>
              <Divider sx={{ mb: 2, borderColor: 'rgba(255,255,255,0.08)' }} />
              <Typography variant="h6" fontWeight={700} gutterBottom sx={{ color: '#FFF' }}>
                {t(`privacy.${key}.title`)}
              </Typography>
              <Typography variant="body1" sx={{ color: '#A1A1AA', lineHeight: 1.7, whiteSpace: 'pre-line' }}>
                {t(`privacy.${key}.text`)}
              </Typography>
            </Box>
          ))}

          <Divider sx={{ mb: 2, borderColor: 'rgba(255,255,255,0.08)' }} />
          <Box sx={{ mt: 2 }}>
            <Typography variant="body2" sx={{ color: '#71717A' }}>
              {t('privacy.footer_note')}{' '}
              <MuiLink component={RouterLink} to="/terms" sx={{ color: '#A1A1AA' }}>
                {t('landing.footer.terms')}
              </MuiLink>
            </Typography>
          </Box>
        </Paper>
      </Container>
    </Box>
  );
}
