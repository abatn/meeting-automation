import React, { useEffect, useState } from 'react';
import { 
  Box, Typography, Grid, Paper, Divider, Button, 
  CircularProgress, Table, TableBody, TableCell, 
  TableContainer, TableHead, TableRow, Chip,
  Card, CardContent, CardActions, IconButton
} from '@mui/material';
import { 
  CheckCircle as ActiveIcon, 
  Payment as PaymentIcon,
  GetApp as DownloadIcon
} from '@mui/icons-material';
import api from '../../services/api';
import UsageProgressBar from '../../components/common/UsageProgressBar';

const BillingPanel: React.FC = () => {
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

  if (loading) return <CircularProgress />;

  return (
    <Box sx={{ p: 3 }}>
      <Typography variant="h4" gutterBottom>Subscription & Billing</Typography>
      <Divider sx={{ mb: 4 }} />

      <Grid container spacing={3}>
        {/* Current Plan and Usage */}
        <Grid item xs={12} md={6}>
          <Typography variant="h6" gutterBottom>Current Status</Typography>
          {usage && (
            <UsageProgressBar 
              used={usage.minutes_used} 
              total={usage.minutes_included} 
              label="Monthly Transcription Limit"
            />
          )}
          <Paper sx={{ p: 2, display: 'flex', alignItems: 'center', bgcolor: 'primary.main', color: 'primary.contrastText' }}>
            <ActiveIcon sx={{ mr: 2, fontSize: 40 }} />
            <Box>
              <Typography variant="h5">Active Subscription</Typography>
              <Typography variant="body2">Your next billing date is April 21, 2026</Typography>
            </Box>
          </Paper>
        </Grid>

        {/* Upgrade Options */}
        <Grid item xs={12} md={6}>
          <Typography variant="h6" gutterBottom>Available Upgrades</Typography>
          <Grid container spacing={2}>
            <Grid item xs={12} sm={6}>
              <Card variant="outlined">
                <CardContent>
                  <Typography variant="h6">Pro Plan</Typography>
                  <Typography variant="h4">$99<Typography component="span" variant="body2">/mo</Typography></Typography>
                  <Typography variant="body2" sx={{ mt: 1 }}>• Unlimited Meetings</Typography>
                  <Typography variant="body2">• 50h Transcription</Typography>
                </CardContent>
                <CardActions>
                  <Button fullWidth variant="contained" onClick={() => handleUpgrade('PRO')}>Upgrade Now</Button>
                </CardActions>
              </Card>
            </Grid>
            <Grid item xs={12} sm={6}>
              <Card variant="outlined">
                <CardContent>
                  <Typography variant="h6">Enterprise</Typography>
                  <Typography variant="h4">$499<Typography component="span" variant="body2">/mo</Typography></Typography>
                  <Typography variant="body2" sx={{ mt: 1 }}>• Dedicated Support</Typography>
                  <Typography variant="body2">• 200h Transcription</Typography>
                </CardContent>
                <CardActions>
                  <Button fullWidth variant="outlined" onClick={() => handleUpgrade('ENTREPRISE')}>Contact Sales</Button>
                </CardActions>
              </Card>
            </Grid>
          </Grid>
        </Grid>

        {/* Invoice List */}
        <Grid item xs={12}>
          <Typography variant="h6" gutterBottom sx={{ mt: 2 }}>Invoice History</Typography>
          <TableContainer component={Paper}>
            <Table>
              <TableHead>
                <TableRow>
                  <TableCell>Date</TableCell>
                  <TableCell>Invoice ID</TableCell>
                  <TableCell>Amount</TableCell>
                  <TableCell>Status</TableCell>
                  <TableCell align="right">Action</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {invoices.map((inv) => (
                  <TableRow key={inv.id}>
                    <TableCell>{new Date(inv.created_at).toLocaleDateString()}</TableCell>
                    <TableCell>{inv.stripe_invoice_id}</TableCell>
                    <TableCell>{inv.currency} {inv.amount}</TableCell>
                    <TableCell><Chip label={inv.status} size="small" color="success" /></TableCell>
                    <TableCell align="right">
                      <IconButton size="small"><DownloadIcon /></IconButton>
                    </TableCell>
                  </TableRow>
                ))}
                {invoices.length === 0 && (
                  <TableRow><TableCell colSpan={5} align="center">No invoice history available.</TableCell></TableRow>
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