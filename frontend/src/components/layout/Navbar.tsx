import React from 'react';
import { AppBar, Toolbar, Typography, Button } from '@mui/material';
import { useTranslation } from 'react-i18next';

const Navbar: React.FC = () => {
  const { t, i18n } = useTranslation();

  const changeLanguage = (lng: string) => {
    i18n.changeLanguage(lng);
  };

  return (
    <AppBar position="static">
      <Toolbar>
        <Typography variant="h6" component="div" sx={{ flexGrow: 1 }}>
          {t('appName')}
        </Typography>
        <Button color="inherit" onClick={() => changeLanguage('en')}>EN</Button>
        <Button color="inherit" onClick={() => changeLanguage('fr-TN')}>FR</Button>
        <Button color="inherit" onClick={() => changeLanguage('ar-TN')}>AR</Button>
      </Toolbar>
    </AppBar>
  );
};

export default Navbar;