import React, { useEffect, useState } from 'react';
import { 
  Box, Typography, Paper, Table, TableBody, TableCell, 
  TableContainer, TableHead, TableRow, Chip, CircularProgress,
  Button
} from '@mui/material';
import adminService, { Client } from '../../services/adminService';

const ClientList: React.FC = () => {
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

  if (loading) return <CircularProgress />;

  return (
    <Box sx={{ p: 3 }}>
      <Typography variant="h4" gutterBottom>Manage Clients</Typography>
      
      <TableContainer component={Paper}>
        <Table>
          <TableHead>
            <TableRow>
              <TableCell>Company Name</TableCell>
              <TableCell>Plan</TableCell>
              <TableCell>Status</TableCell>
              <TableCell>Created At</TableCell>
              <TableCell>Actions</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {clients.map((client) => (
              <TableRow key={client.id}>
                <TableCell>{client.company_name}</TableCell>
                <TableCell>{client.subscription_plan}</TableCell>
                <TableCell>
                  <Chip 
                    label={client.subscription_status} 
                    color={client.subscription_status === 'ACTIVE' ? 'success' : 'error'} 
                    size="small" 
                  />
                </TableCell>
                <TableCell>{new Date(client.created_at).toLocaleDateString()}</TableCell>
                <TableCell>
                  <Button 
                    variant="outlined" 
                    color={client.subscription_status === 'ACTIVE' ? 'error' : 'success'}
                    size="small"
                    onClick={() => handleStatusToggle(client.id, client.subscription_status)}
                  >
                    {client.subscription_status === 'ACTIVE' ? 'Disable' : 'Activate'}
                  </Button>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>
    </Box>
  );
};

export default ClientList;