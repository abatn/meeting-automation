import React, { useEffect, useState } from 'react';
import { 
  Box, Typography, Grid, Paper, Divider, Button, 
  CircularProgress, Table, TableBody, TableCell, 
  TableContainer, TableHead, TableRow, Chip,
  Card, CardContent, CardActions, IconButton, useTheme, alpha
} from '@mui/material';
import { 
  CheckCircle as ActiveIcon, 
  GetApp as DownloadIcon,
  Stars as ProIcon,
  BusinessCenter as EnterpriseIcon
} from '@mui/icons-material';
import { useTranslation } from 'react-i18next';
import api from '../../services/api';
import UsageProgressBar from '../../components/common/UsageProgressBar';

const BillingPanel: React.FC = () => {
  const { t } = useTranslation();
  const theme = useTheme();
  const [invoices, setInvoices] = useState<any[]>([]);
  const [usage, setUsage] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [invoicesRes, usageRes] = await Promise.all([
          api.get('/billing/invoices'),
          api.get('/billing/usage')
        ]);
        setInvoices(invoicesRes.data);
        setUsage(usageRes.data);
      } catch (error) {
        console.error('Failed to fetch billing data', error);
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, []);

  const handleUpgrade = async (plan: string) => {
    try {
      const response = await api.post('/billing/checkout', {
        plan,
        success_url: window.location.origin + '/billing?success=true',
        cancel_url: window.location.origin + '/billing?canceled=true',
      });
      if (response.data.checkout_url) {
        window.location.href = response.data.checkout_url;
      }
    } catch (error) {
      console.error('Failed to initiate checkout', error);
    }
  };

  if (loading) return <Box sx={{ display: 'flex', justifyContent: 'center', p: 5 }}><CircularProgress /></Box>;

  return (
    <Box sx={{ maxWidth: 1200, mx: 'auto', p: { xs: 2, md: 4 } }}>
      <Box sx={{ mb: 5 }}>
        <Typography variant="h4" fontWeight="800" color="text.primary" gutterBottom>
          {t('billing.title')}
        </Typography>
      </Box>
      <Divider sx={{ mb: 4 }} />

      <Grid container spacing={4}>
        {/* Current Plan and Usage */}
        <Grid item xs={12} md={5}>
          <Typography variant="h6" fontWeight="700" gutterBottom sx={{ mb: 3 }}>
            {t('billing.currentStatus')}
          </Typography>
          
          <Paper elevation={0} sx={{ p: 3, mb: 3, display: 'flex', alignItems: 'flex-start', bgcolor: alpha(theme.palette.success.main, 0.05), border: `1px solid ${alpha(theme.palette.success.main, 0.2)}`, borderRadius: 3 }}>
            <ActiveIcon sx={{ mr: 2, fontSize: 32, color: theme.palette.success.main, mt: 0.5 }} />
            <Box>
              <Typography variant="h6" fontWeight="700" color="success.dark" gutterBottom>
                {t('billing.activeSub')}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                {t('billing.nextBilling')} {usage?.next_billing_date || 'N/A'}
              </Typography>
            </Box>
          </Paper>

          {usage && (
            <Box sx={{ p: 3, border: '1px solid #E2E8F0', borderRadius: 3 }}>
              <UsageProgressBar 
                used={usage.minutes_used} 
                total={usage.minutes_included} 
                label={t('billing.monthlyLimit')}
              />
            </Box>
          )}
        </Grid>

        {/* Upgrade Options */}
        <Grid item xs={12} md={7}>
          <Typography variant="h6" fontWeight="700" gutterBottom sx={{ mb: 3 }}>
            {t('billing.availableUpgrades')}
          </Typography>
          <Grid container spacing={3}>
            <Grid item xs={12} sm={6}>
              <Card elevation={0} sx={{ border: '2px solid #0070F3', borderRadius: 3, height: '100%', display: 'flex', flexDirection: 'column' }}>
                <CardContent sx={{ flexGrow: 1, p: 3 }}>
                  <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
                    <ProIcon color="primary" sx={{ mr: 1 }} />
                    <Typography variant="h6" fontWeight="700">{t('billing.proPlan')}</Typography>
                  </Box>
                  <Typography variant="h3" fontWeight="800" sx={{ mb: 3 }}>
                    $99<Typography component="span" variant="subtitle1" color="text.secondary">/mo</Typography>
                  </Typography>
                  <Typography variant="body2" sx={{ mb: 1, display: 'flex', alignItems: 'center' }}>• {t('billing.unlimitedMeetings')}</Typography>
                  <Typography variant="body2" sx={{ mb: 1, display: 'flex', alignItems: 'center' }}>• {t('billing.proHours')}</Typography>
                </CardContent>
                <CardActions sx={{ p: 3, pt: 0 }}>
                  <Button fullWidth variant="contained" color="primary" onClick={() => handleUpgrade('PRO')} sx={{ borderRadius: 2, py: 1, fontWeight: 'bold', textTransform: 'none' }}>
                    {t('billing.upgradeNow')}
                  </Button>
                </CardActions>
              </Card>
            </Grid>
            <Grid item xs={12} sm={6}>
              <Card elevation={0} sx={{ border: '1px solid #E2E8F0', borderRadius: 3, height: '100%', display: 'flex', flexDirection: 'column' }}>
                <CardContent sx={{ flexGrow: 1, p: 3 }}>
                  <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
                    <EnterpriseIcon color="action" sx={{ mr: 1 }} />
                    <Typography variant="h6" fontWeight="700">{t('billing.enterprisePlan')}</Typography>
                  </Box>
                  <Typography variant="h3" fontWeight="800" sx={{ mb: 3 }}>
                    $499<Typography component="span" variant="subtitle1" color="text.secondary">/mo</Typography>
                  </Typography>
                  <Typography variant="body2" sx={{ mb: 1, display: 'flex', alignItems: 'center' }}>• {t('billing.dedicatedSupport')}</Typography>
                  <Typography variant="body2" sx={{ mb: 1, display: 'flex', alignItems: 'center' }}>• {t('billing.entHours')}</Typography>
                </CardContent>
                <CardActions sx={{ p: 3, pt: 0 }}>
                  <Button fullWidth variant="outlined" color="inherit" onClick={() => handleUpgrade('ENTREPRISE')} sx={{ borderRadius: 2, py: 1, fontWeight: 'bold', textTransform: 'none' }}>
                    {t('billing.contactSales')}
                  </Button>
                </CardActions>
              </Card>
            </Grid>
          </Grid>
        </Grid>

        {/* Invoice List */}
        <Grid item xs={12}>
          <Box sx={{ mt: 4, mb: 3 }}>
            <Typography variant="h6" fontWeight="700">
              {t('billing.invoiceHistory')}
            </Typography>
          </Box>
          <TableContainer component={Paper} elevation={0} sx={{ border: '1px solid #E2E8F0', borderRadius: 3 }}>
            <Table>
              <TableHead sx={{ bgcolor: '#F8FAFC' }}>
                <TableRow>
                  <TableCell sx={{ fontWeight: 'bold' }}>{t('billing.date')}</TableCell>
                  <TableCell sx={{ fontWeight: 'bold' }}>{t('billing.invoiceId')}</TableCell>
                  <TableCell sx={{ fontWeight: 'bold' }}>{t('billing.amount')}</TableCell>
                  <TableCell sx={{ fontWeight: 'bold' }}>{t('billing.status')}</TableCell>
                  <TableCell align="right" sx={{ fontWeight: 'bold' }}>{t('billing.action')}</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {invoices.map((inv) => (
                  <TableRow key={inv.id} sx={{ '&:last-child td, &:last-child th': { border: 0 } }}>
                    <TableCell>{new Date(inv.created_at).toLocaleDateString()}</TableCell>
                    <TableCell sx={{ fontFamily: 'monospace' }}>{inv.stripe_invoice_id}</TableCell>
                    <TableCell fontWeight="bold">{inv.currency} {inv.amount}</TableCell>
                    <TableCell>
                      <Chip label={inv.status} size="small" color="success" sx={{ fontWeight: 'bold' }} />
                    </TableCell>
                    <TableCell align="right">
                      <IconButton 
                        size="small" 
                        color="primary"
                        onClick={() => window.open(`${api.defaults.baseURL}/billing/invoices/download/${inv.id}`, '_blank')}
                        disabled={!inv.invoice_pdf_url}
                        sx={{ bgcolor: alpha(theme.palette.primary.main, 0.1) }}
                      >
                        <DownloadIcon />
                      </IconButton>
                    </TableCell>
                  </TableRow>
                ))}
                {invoices.length === 0 && (
                  <TableRow>
                    <TableCell colSpan={5} align="center" sx={{ py: 6, color: 'text.secondary' }}>
                      <Typography variant="body1">{t('billing.noHistory')}</Typography>
                    </TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
          </TableContainer>
        </Grid>
      </Grid>
    </Box>
  );
};

export default BillingPanel;