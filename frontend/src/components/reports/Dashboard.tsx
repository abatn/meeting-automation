import React from 'react';
import { useSelector } from 'react-redux';
import { RootState } from '../../store';
import DashboardDG from './DashboardDG';
import DashboardManager from './DashboardManager';
import DashboardParticipant from './DashboardParticipant';
import { Typography, Box } from '@mui/material';

const Dashboard: React.FC = () => {
  const { user } = useSelector((state: RootState) => state.auth);
  const role = user?.role || 'participant';

  const renderDashboard = () => {
    switch (role) {
      case 'dg':
        return <DashboardDG />;
      case 'manager':
        return <DashboardManager />;
      case 'participant':
      default:
        return <DashboardParticipant />;
    }
  };

  return (
    <Box>
      {renderDashboard()}
    </Box>
  );
};

export default Dashboard;