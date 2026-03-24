import React from "react";
import {
  Drawer,
  List,
  ListItem,
  ListItemIcon,
  ListItemText,
  ListItemButton,
  Divider,
  Box,
  Toolbar,
  Typography,
} from "@mui/material";
import { useNavigate, useLocation } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useSelector } from "react-redux";
import { RootState } from "../../store";
import DashboardIcon from "@mui/icons-material/Dashboard";
import EventIcon from "@mui/icons-material/Event";
import AssignmentIcon from "@mui/icons-material/Assignment";
import AssessmentIcon from "@mui/icons-material/Assessment";
import SecurityIcon from "@mui/icons-material/Security";
import PaymentIcon from "@mui/icons-material/Payment";
import PeopleIcon from "@mui/icons-material/People";

const drawerWidth = 240;

const Sidebar: React.FC = () => {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const location = useLocation();
  const { user } = useSelector((state: RootState) => state.auth);

  const isBusinessAdmin = user?.role === "system_admin";

  const menuItems = [
    { text: t("sidebar.dashboard"), icon: <DashboardIcon />, path: "/" },
    { text: t("sidebar.meetings"), icon: <EventIcon />, path: "/meetings" },
    { text: t("sidebar.actions"), icon: <AssignmentIcon />, path: "/actions" },
    { text: t("sidebar.reports"), icon: <AssessmentIcon />, path: "/reports" },
    { text: t("sidebar.team"), icon: <PeopleIcon />, path: "/team" },
    { text: "Billing", icon: <PaymentIcon />, path: "/billing" },
  ];

  const adminItems = [
    { text: t("admin.businessOverview"), icon: <DashboardIcon />, path: "/" },
    { text: t("admin.manageClients"), icon: <PeopleIcon />, path: "/admin/clients" },
    { text: t("admin.revenueBilling"), icon: <PaymentIcon />, path: "/billing" },
  ];

  const currentItems = isBusinessAdmin ? adminItems : menuItems;

  return (
    <Drawer
      variant="permanent"
      sx={{
        width: drawerWidth,
        flexShrink: 0,
        [`& .MuiDrawer-paper`]: {
          width: drawerWidth,
          boxSizing: "border-box",
          bgcolor: "background.paper",
          borderRight: "1px solid rgba(0, 0, 0, 0.12)",
        },
      }}
    >
      <Toolbar />
      <Box sx={{ overflow: "auto" }}>
        <List sx={{ pt: 2 }}>
          {currentItems.map((item) => (
            <ListItem key={item.text} disablePadding sx={{ mb: 1 }}>
              <ListItemButton
                selected={location.pathname === item.path}
                onClick={() => navigate(item.path)}
                sx={{
                  mx: 1,
                  borderRadius: 2,
                  "&.Mui-selected": {
                    bgcolor: isBusinessAdmin ? "secondary.light" : "primary.light",
                    color: isBusinessAdmin ? "secondary.main" : "primary.main",
                    "& .MuiListItemIcon-root": {
                      color: isBusinessAdmin ? "secondary.main" : "primary.main",
                    },
                  },
                }}
              >
                <ListItemIcon>{item.icon}</ListItemIcon>
                <ListItemText
                  primary={item.text}
                  primaryTypographyProps={{
                    fontWeight:
                      location.pathname === item.path ? "bold" : "normal",
                  }}
                />
              </ListItemButton>
            </ListItem>
          ))}
        </List>
        
        <Divider sx={{ my: 2 }} />
        <List>
          <ListItem disablePadding sx={{ mx: 1 }}>
            <ListItemButton
              onClick={() => navigate("/settings")}
              sx={{ borderRadius: 2 }}
            >
              <ListItemIcon>
                <SecurityIcon />
              </ListItemIcon>
              <ListItemText primary={t("sidebar.security")} />
            </ListItemButton>
          </ListItem>
        </List>
      </Box>
    </Drawer>
  );
};

export default Sidebar;
