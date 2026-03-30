import React, { useState } from "react";
import {
  AppBar,
  Toolbar,
  Typography,
  Box,
  IconButton,
  Menu,
  MenuItem,
  Avatar,
  Divider,
  Stack,
  ListItemIcon,
} from "@mui/material";
import { useTranslation } from "react-i18next";
import { useDispatch, useSelector } from "react-redux";
import { useNavigate } from "react-router-dom";
import { RootState } from "../../store";
import { logout } from "../../store/authSlice";

import TranslateIcon from "@mui/icons-material/Translate";
import LogoutIcon from "@mui/icons-material/Logout";
import PeopleIcon from "@mui/icons-material/People";
import PaymentIcon from "@mui/icons-material/Payment";
import SecurityIcon from "@mui/icons-material/Security";
import MenuIcon from "@mui/icons-material/Menu";
import { AutoFixHigh as IAIcon } from "@mui/icons-material";

interface NavbarProps {
  onMenuClick: () => void;
}

const Navbar: React.FC<NavbarProps> = ({ onMenuClick }) => {
  const { t, i18n } = useTranslation();
  const dispatch = useDispatch();
  const navigate = useNavigate();
  const { isAuthenticated, user } = useSelector((state: RootState) => state.auth);
  
  const isBusinessAdmin = user?.role === "system_admin";

  const [anchorElLang, setAnchorElLang] = useState<null | HTMLElement>(null);
  const [anchorElProfile, setAnchorElProfile] = useState<null | HTMLElement>(null);

  const changeLanguage = (lng: string) => {
    i18n.changeLanguage(lng);
    setAnchorElLang(null);
  };

  const getInitials = (name?: string) => {
    if (!name) return "U";
    return name.split(" ").map(n => n[0]).join("").substring(0, 2).toUpperCase();
  };

  return (
    <AppBar
      position="fixed"
      elevation={0}
      sx={{ 
        zIndex: (theme) => theme.zIndex.drawer + 1,
        bgcolor: "rgba(255, 255, 255, 0.8)",
        backdropFilter: "blur(12px)",
        borderBottom: "1px solid rgba(0, 0, 0, 0.05)",
        color: "#000"
      }}
    >
      <Toolbar sx={{ justifyContent: "space-between", minHeight: "64px !important" }}>
        
        <Stack direction="row" alignItems="center" spacing={1}>
          {/* HAMBURGER FOR MOBILE */}
          <IconButton
            color="inherit"
            aria-label="open drawer"
            edge="start"
            onClick={onMenuClick}
            sx={{ display: { sm: "none" } }}
          >
            <MenuIcon fontSize="small" />
          </IconButton>

          {/* BRANDING */}
          <Stack direction="row" alignItems="center" spacing={1.5} sx={{ cursor: 'pointer' }} onClick={() => navigate('/')}>
            <Box sx={{ width: 28, height: 28, bgcolor: '#000', borderRadius: '6px', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <IAIcon sx={{ color: '#FFF', fontSize: 16 }} />
            </Box>
            <Typography variant="h6" fontWeight="700" sx={{ letterSpacing: '-0.5px', fontSize: '16px' }}>
              {t('common.appNamePart1')}<Box component="span" sx={{ color: '#71717A' }}>{t('common.appNamePart2')}</Box>
            </Typography>
          </Stack>
        </Stack>

        <Box sx={{ display: "flex", alignItems: "center", gap: 2 }}>
          {/* LANGUAGE SELECTOR */}
          <IconButton onClick={(e) => setAnchorElLang(e.currentTarget)} sx={{ color: "#71717A" }}>
            <TranslateIcon fontSize="small" />
            <Typography variant="body2" sx={{ ml: 1, fontWeight: 500, fontSize: "14px" }}>
              {i18n.language.split('-')[0].toUpperCase()}
            </Typography>
          </IconButton>
          <Menu 
            anchorEl={anchorElLang} 
            open={Boolean(anchorElLang)} 
            onClose={() => setAnchorElLang(null)}
            PaperProps={{ sx: { mt: 1, borderRadius: 2, border: "1px solid rgba(0,0,0,0.05)", boxShadow: "0 10px 30px rgba(0,0,0,0.1)" } }}
          >
            <MenuItem onClick={() => changeLanguage("en")} sx={{ fontSize: "14px" }}>English</MenuItem>
            <MenuItem onClick={() => changeLanguage("fr-TN")} sx={{ fontSize: "14px" }}>Français</MenuItem>
            <MenuItem onClick={() => changeLanguage("ar-TN")} sx={{ fontSize: "14px" }}>العربية</MenuItem>
          </Menu>

          {/* USER PROFILE */}
          {isAuthenticated && (
            <>
              <IconButton onClick={(e) => setAnchorElProfile(e.currentTarget)} sx={{ p: 0.5, border: "1px solid rgba(0,0,0,0.05)" }}>
                <Avatar sx={{ width: 32, height: 32, bgcolor: "#000", fontSize: "12px", fontWeight: 600 }}>
                  {getInitials(user?.full_name)}
                </Avatar>
              </IconButton>
              
              <Menu
                anchorEl={anchorElProfile}
                open={Boolean(anchorElProfile)}
                onClose={() => setAnchorElProfile(null)}
                PaperProps={{ sx: { mt: 1, width: 240, borderRadius: 3, border: "1px solid rgba(0,0,0,0.05)", boxShadow: "0 10px 40px rgba(0,0,0,0.08)", p: 1 } }}
              >
                <Box sx={{ px: 2, py: 1.5 }}>
                  <Typography variant="body2" fontWeight="600" noWrap>{user?.full_name}</Typography>
                  <Typography variant="caption" color="text.secondary" noWrap>{user?.email}</Typography>
                </Box>
                <Divider sx={{ my: 1 }} />
                
                {!isBusinessAdmin && (
                  <Box>
                    <MenuItem onClick={() => { navigate("/team"); setAnchorElProfile(null); }} sx={{ borderRadius: 1.5, py: 1, mb: 0.5 }}>
                      <ListItemIcon><PeopleIcon fontSize="small" sx={{ color: "#71717A" }} /></ListItemIcon>
                      <Typography variant="body2" fontWeight="500">{t("sidebar.team")}</Typography>
                    </MenuItem>
                    <MenuItem onClick={() => { navigate("/billing"); setAnchorElProfile(null); }} sx={{ borderRadius: 1.5, py: 1, mb: 0.5 }}>
                      <ListItemIcon><PaymentIcon fontSize="small" sx={{ color: "#71717A" }} /></ListItemIcon>
                      <Typography variant="body2" fontWeight="500">{t("sidebar.billing")}</Typography>
                    </MenuItem>
                  </Box>
                )}

                <MenuItem onClick={() => { navigate("/settings"); setAnchorElProfile(null); }} sx={{ borderRadius: 1.5, py: 1, mb: 0.5 }}>
                  <ListItemIcon><SecurityIcon fontSize="small" sx={{ color: "#71717A" }} /></ListItemIcon>
                  <Typography variant="body2" fontWeight="500">{t("sidebar.security")}</Typography>
                </MenuItem>
                
                <Divider sx={{ my: 1 }} />
                
                <MenuItem onClick={() => { dispatch(logout()); setAnchorElProfile(null); }} sx={{ borderRadius: 1.5, py: 1, color: "#D32F2F" }}>
                  <ListItemIcon><LogoutIcon fontSize="small" sx={{ color: "#D32F2F" }} /></ListItemIcon>
                  <Typography variant="body2" fontWeight="500">{t("auth.logout")}</Typography>
                </MenuItem>
              </Menu>
            </>
          )}
        </Box>
      </Toolbar>
    </AppBar>
  );
};

export default Navbar;
