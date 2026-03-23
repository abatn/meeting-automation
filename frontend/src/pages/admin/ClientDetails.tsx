import React, { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { 
  Box, Typography, Grid, Paper, Divider, Button, 
  CircularProgress, Table, TableBody, TableCell, 
  TableContainer, TableHead, TableRow, Chip,
  TextField, IconButton
} from '@mui/material';
import { ArrowBack as BackIcon, Save as SaveIcon } from '@mui/icons-material';
import adminService, { Client } from '../../services/adminService';
import UsageProgressBar from '../../components/common/UsageProgressBar';

const ClientDetails: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [client, setClient] = useState<Client | null>(null);
  const [invoices, setInvoices] = useState<any[]>([]);
  const [usage, setUsage] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [obsText, setObsText] = useState('');

  useEffect(() => {
    const fetchData = async () => {
      if (!id) return;
      try {
        const [clientData, invoicesData, usageData] = await Promise.all([
          adminService.getClientDetails(id),
          adminService.getClientInvoices(id),
          adminService.getClientUsage(id)
        ]);
        setClient(clientData);
        setInvoices(invoicesData);
        setUsage(usageData);
      } catch (error) {
        console.error('Failed to fetch client details', error);
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, [id]);

  const handleAddObservation = async () => {
    if (!id || !obsText.trim()) return;
    try {
      const updatedClient = await adminService.addClientObservation(id, obsText);
      setClient(updatedClient);
      setObsText('');
    } catch (error) {
      console.error('Failed to add observation', error);
    }
  };

  if (loading) return <CircularProgress />;
  if (!client) return <Typography color="error">Client not found.</Typography>;

  return (
    <Box sx={{ p: 3 }}>
      <Button startIcon={<BackIcon />} onClick={() => navigate('/admin/clients')} sx={{ mb: 2 }}>
        Back to List
      </Button>
      
      <Grid container spacing={3}>
        {/* Header Information */}
        <Grid item xs={12} md={8}>
          <Paper sx={{ p: 3 }}>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
              <Typography variant="h4">{client.company_name}</Typography>
              <Chip 
                label={client.subscription_status} 
                color={client.subscription_status === 'ACTIVE' ? 'success' : client.subscription_status === 'PENDING' ? 'warning' : 'default'} 
              />
            </Box>
            <Divider sx={{ my: 2 }} />
            <Grid container spacing={2}>
              <Grid item xs={6}><Typography variant="body2" color="text.secondary">Plan</Typography><Typography variant="body1">{client.subscription_plan}</Typography></Grid>
              <Grid item xs={6}><Typography variant="body2" color="text.secondary">Joined At</Typography><Typography variant="body1">{new Date(client.created_at).toLocaleDateString()}</Typography></Grid>
            </Grid>
          </Paper>
        </Grid>

        {/* Usage Card */}
        <Grid item xs={12} md={4}>
          <UsageProgressBar 
            used={client.minutes_used} 
            total={client.minutes_included} 
            label="Transcription Usage"
          />
        </Grid>

        {/* Invoices */}
        <Grid item xs={12} md={7}>
          <Typography variant="h6" gutterBottom sx={{ mt: 2 }}>Invoice History</Typography>
          <TableContainer component={Paper}>
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>Date</TableCell>
                  <TableCell>Amount</TableCell>
                  <TableCell>Status</TableCell>
                  <TableCell>Invoice #</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {invoices.length > 0 ? invoices.map((inv) => (
                  <TableRow key={inv.id}>
                    <TableCell>{new Date(inv.created_at).toLocaleDateString()}</TableCell>
                    <TableCell>{inv.currency} {inv.amount}</TableCell>
                    <TableCell><Chip label={inv.status} size="small" variant="outlined" /></TableCell>
                    <TableCell>{inv.stripe_invoice_id}</TableCell>
                  </TableRow>
                )) : (
                  <TableRow><TableCell colSpan={4} align="center">No invoices found.</TableCell></TableRow>
                )}
              </TableBody>
            </Table>
          </TableContainer>
        </Grid>

        {/* Internal Observations */}
        <Grid item xs={12} md={5}>
          <Typography variant="h6" gutterBottom sx={{ mt: 2 }}>Internal Observations</Typography>
          <Paper sx={{ p: 2, bgcolor: 'grey.50' }}>
            <Box sx={{ whiteSpace: 'pre-wrap', mb: 2, maxHeight: 200, overflowY: 'auto', fontSize: '0.875rem' }}>
              {client.observations || "No observations recorded."}
            </Box>
            <Box sx={{ display: 'flex', gap: 1 }}>
              <TextField 
                fullWidth 
                size="small" 
                placeholder="Add note..." 
                value={obsText}
                onChange={(e) => setObsText(e.target.value)}
              />
              <IconButton color="primary" onClick={handleAddObservation} disabled={!obsText.trim()}>
                <SaveIcon />
              </IconButton>
            </Box>
          </Paper>
        </Grid>
      </Grid>
    </Box>
  );
};

export default ClientDetails;