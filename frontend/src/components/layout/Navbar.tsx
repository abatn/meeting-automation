import React from 'react';
import { AppBar, Toolbar, Typography, Button, Box, IconButton } from '@mui/material';
import { useTranslation } from 'react-i18next';
import LanguageIcon from '@mui/icons-material/Language';
import LogoutIcon from '@mui/icons-material/Logout';
import { useDispatch, useSelector } from 'react-redux';
import { RootState } from '../../store';
import { logout } from '../../store/authSlice';

const Navbar: React.FC = () => {
  const { t, i18n } = useTranslation();
  const dispatch = useDispatch();
  const { isAuthenticated, user } = useSelector((state: RootState) => state.auth);

  const toggleLanguage = () => {
    const nextLang = i18n.language === 'fr-TN' ? 'ar-TN' : 'fr-TN';
    i18n.changeLanguage(nextLang);
  };

  return (
    <AppBar position="static" color="primary" elevation={0}>
      <Toolbar>
        <Typography variant="h6" component="div" sx={{ flexGrow: 1 }}>
          {t('common.appName', 'Meeting Automation')}
        </Typography>
        
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
          <IconButton color="inherit" onClick={toggleLanguage} title={t('common.toggleLanguage', 'Toggle Language')}>
            <LanguageIcon />
            <Typography variant="body2" sx={{ ml: 1, display: { xs: 'none', sm: 'block' } }}>
              {i18n.language.toUpperCase()}
            </Typography>
          </IconButton>

          {isAuthenticated && (
            <>
              <Typography variant="body2" sx={{ display: { xs: 'none', md: 'block' } }}>
                {user?.full_name}
              </Typography>
              <Button 
                color="inherit" 
                startIcon={<LogoutIcon />}
                onClick={() => dispatch(logout())}
              >
                {t('auth.logout', 'Logout')}
              </Button>
            </>
          )}
        </Box>
      </Toolbar>
    </AppBar>
  );
};

export default Navbar;