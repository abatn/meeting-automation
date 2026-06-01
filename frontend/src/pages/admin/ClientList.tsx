import React, { useEffect, useState } from 'react';
import { 
  Box, Typography, Paper, Table, TableBody, TableCell, 
  TableContainer, TableHead, TableRow, Chip, CircularProgress,
  Button, Link, Divider
} from '@mui/material';
import { Link as RouterLink } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import adminService, { Client } from '../../services/adminService';

const ClientList: React.FC = () => {
  const { t } = useTranslation();
  const [clients, setClients] = useState<Client[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchClients = async () => {
      try {
        const data = await adminService.getClients();
        setClients(data);
      } catch (error) {
        console.error('Failed to fetch clients', error);
      } finally {
        setLoading(false);
      }
    };
    fetchClients();
  }, []);

  const handleStatusToggle = async (clientId: string, currentStatus: string) => {
    const newStatus = currentStatus === 'ACTIVE' ? 'DISABLED' : 'ACTIVE';
    try {
      await adminService.updateClientStatus(clientId, newStatus);
      // Optimistic update
      setClients(clients.map(c => c.id === clientId ? { ...c, subscription_status: newStatus } : c));
    } catch (error) {
      console.error('Failed to update status', error);
    }
  };

  if (loading) return <Box sx={{ display: 'flex', justifyContent: 'center', p: 5 }}><CircularProgress /></Box>;

  return (
    <Box sx={{ maxWidth: 1200, mx: 'auto', p: { xs: 2, md: 4 } }}>
      <Box sx={{ mb: 5 }}>
        <Typography variant="h4" fontWeight="800" color="text.primary" gutterBottom>
          {t('clientList.title')}
        </Typography>
        <Typography variant="body1" color="text.secondary">
          {t('clientList.subtitle')}
        </Typography>
      </Box>
      <Divider sx={{ mb: 4 }} />
      
      <TableContainer component={Paper} elevation={0} sx={{ border: '1px solid #E2E8F0', borderRadius: 3 }}>
        <Table>
          <TableHead sx={{ bgcolor: '#F8FAFC' }}>
            <TableRow>
              <TableCell sx={{ fontWeight: 'bold' }}>{t('clientList.companyName')}</TableCell>
              <TableCell sx={{ fontWeight: 'bold' }}>{t('clientList.plan')}</TableCell>
              <TableCell sx={{ fontWeight: 'bold' }}>{t('clientList.status')}</TableCell>
              <TableCell sx={{ fontWeight: 'bold' }}>{t('clientList.monthlyUsage')}</TableCell>
              <TableCell sx={{ fontWeight: 'bold' }}>{t('clientList.totalUsage')}</TableCell>
              <TableCell sx={{ fontWeight: 'bold' }}>{t('clientList.createdAt')}</TableCell>
              <TableCell sx={{ fontWeight: 'bold', textAlign: 'right' }}>{t('clientList.actions')}</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {clients.map((client: any) => (
              <TableRow key={client.id} sx={{ '&:last-child td, &:last-child th': { border: 0 }, '&:hover': { bgcolor: '#F1F5F9' } }}>
                <TableCell>
                  <Link component={RouterLink} to={`/admin/clients/${client.id}`} underline="hover" fontWeight="bold" color="primary.main">
                    {client.company_name}
                  </Link>
                </TableCell>
                <TableCell>
                  <Chip label={client.subscription_plan} size="small" variant="outlined" sx={{ fontWeight: '600' }} />
                </TableCell>
                <TableCell>
                  <Chip 
                    label={client.subscription_status} 
                    color={client.subscription_status === 'ACTIVE' ? 'success' : client.subscription_status === 'PENDING' ? 'warning' : 'default'} 
                    size="small" 
                    sx={{ fontWeight: '600' }}
                  />
                </TableCell>
                <TableCell sx={{ fontFamily: 'monospace' }}>
                  {client.minutes_used_month} / {client.minutes_included} min
                </TableCell>
                <TableCell sx={{ fontFamily: 'monospace' }}>{client.minutes_used_total} min</TableCell>
                <TableCell>{new Date(client.created_at).toLocaleDateString()}</TableCell>
                <TableCell align="right">
                  <Button 
                    variant="outlined" 
                    color={client.subscription_status === 'ACTIVE' ? 'secondary' : 'primary'}
                    size="small"
                    onClick={() => handleStatusToggle(client.id, client.subscription_status)}
                    sx={{ textTransform: 'none', fontWeight: 'bold', borderRadius: 2 }}
                  >
                    {client.subscription_status === 'ACTIVE' ? t('clientList.disable') : t('clientList.activate')}
                  </Button>
                </TableCell>
              </TableRow>
            ))}
            {clients.length === 0 && (
              <TableRow>
                <TableCell colSpan={7} align="center" sx={{ py: 4, color: 'text.secondary' }}>
                  {t('clientList.no_clients')}
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </TableContainer>
    </Box>
  );
};

export default ClientList;