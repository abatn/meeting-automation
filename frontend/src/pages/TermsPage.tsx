import React from 'react';
import { Container, Typography, Box, Divider, Link as MuiLink, Paper, CssBaseline } from '@mui/material';
import { useTranslation } from 'react-i18next';
import { Link as RouterLink } from 'react-router-dom';

export default function TermsPage() {
  const { t, i18n } = useTranslation();
  const isRtl = i18n.dir() === 'rtl';

  const sections = [
    { key: 'terms.acceptance' },
    { key: 'terms.service_description' },
    { key: 'terms.consent' },
    { key: 'terms.user_obligations' },
    { key: 'terms.intellectual_property' },
    { key: 'terms.limitation_of_liability' },
    { key: 'terms.termination' },
    { key: 'terms.governing_law' },
  ];

  return (
    <Box sx={{ bgcolor: '#050505', color: '#FAFAFA', minHeight: '100vh', direction: isRtl ? 'rtl' : 'ltr', fontFamily: isRtl ? "'Noto Sans Arabic', sans-serif" : "'Inter', sans-serif" }}>
      <CssBaseline />
      <Container maxWidth="md" sx={{ py: { xs: 6, md: 10 } }}>
        <Typography variant="h4" fontWeight={800} gutterBottom>{t('terms.title')}</Typography>

        <Paper elevation={0} sx={{ p: { xs: 3, md: 5 }, bgcolor: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.06)', borderRadius: '16px' }}>
          {sections.map((section, idx) => (
            <Box key={idx} sx={{ mb: 4 }}>
              <Divider sx={{ mb: 2, borderColor: 'rgba(255,255,255,0.08)' }} />
              <Typography variant="h6" fontWeight={700} gutterBottom sx={{ color: '#FFF' }}>
                {t(`${section.key}.short`)}
              </Typography>
              <Typography variant="body1" sx={{ color: '#A1A1AA', lineHeight: 1.7, whiteSpace: 'pre-line' }}>
                {t(`${section.key}.text`)}
              </Typography>
              {section.key === 'terms.consent' && (
                <MuiLink component={RouterLink} to="/privacy" sx={{ color: '#A1A1AA', display: 'inline-block', mt: 1 }}>
                  {t('terms.consent_link')}
                </MuiLink>
              )}
            </Box>
          ))}

          <Divider sx={{ mb: 2, borderColor: 'rgba(255,255,255,0.08)' }} />
          <Box sx={{ mt: 2 }}>
            <Typography variant="body2" sx={{ color: '#71717A' }}>
              Contact: legal@meeting-automation.com
            </Typography>
          </Box>
        </Paper>
      </Container>
    </Box>
  );
}
