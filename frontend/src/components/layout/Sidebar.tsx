import React from "react";
import {
  Drawer,
  List,
  ListItem,
  ListItemIcon,
  ListItemText,
  ListItemButton,
  Box,
  Toolbar,
} from "@mui/material";
import { useNavigate, useLocation } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useSelector } from "react-redux";
import { RootState } from "../../store";
import DashboardIcon from "@mui/icons-material/Dashboard";
import EventIcon from "@mui/icons-material/Event";
import CollectionsBookmarkIcon from "@mui/icons-material/CollectionsBookmark";
import AssignmentIcon from "@mui/icons-material/Assignment";
import AssessmentIcon from "@mui/icons-material/Assessment";
import PeopleIcon from "@mui/icons-material/People";
import PaymentIcon from "@mui/icons-material/Payment";

const drawerWidth = 240;

interface SidebarProps {
  mobileOpen: boolean;
  onDrawerToggle: () => void;
}

const Sidebar: React.FC<SidebarProps> = ({ mobileOpen, onDrawerToggle }) => {
  const { t, i18n } = useTranslation();
  const navigate = useNavigate();
  const location = useLocation();
  const { user } = useSelector((state: RootState) => state.auth);

  const isBusinessAdmin = user?.role === "system_admin";

  const coreItems = [
    { text: t("sidebar.dashboard"), icon: <DashboardIcon fontSize="small" />, path: "/" },
    { text: t("sidebar.meetings"), icon: <EventIcon fontSize="small" />, path: "/meetings" },
    { text: t("sidebar.archive"), icon: <CollectionsBookmarkIcon fontSize="small" />, path: "/archive" },
    { text: t("sidebar.actions"), icon: <AssignmentIcon fontSize="small" />, path: "/actions" },
    { text: t("sidebar.reports"), icon: <AssessmentIcon fontSize="small" />, path: "/reports" },
  ];

  const adminItems = [
    { text: t("admin.businessOverview"), icon: <DashboardIcon fontSize="small" />, path: "/" },
    { text: t("admin.manageClients"), icon: <PeopleIcon fontSize="small" />, path: "/admin/clients" },
    { text: t("admin.revenueBilling"), icon: <PaymentIcon fontSize="small" />, path: "/billing" },
  ];

  const currentItems = isBusinessAdmin ? adminItems : coreItems;

  const drawer = (
    <Box sx={{ overflow: "auto", px: 2, pt: 3 }}>
      <List>
        {currentItems.map((item) => {
          const isActive = location.pathname === item.path;
          return (
            <ListItem key={item.text} disablePadding sx={{ mb: 1 }}>
              <ListItemButton
                onClick={() => {
                  navigate(item.path);
                  if (mobileOpen) onDrawerToggle();
                }}
                sx={{
                  borderRadius: "8px",
                  py: 1,
                  px: 1.5,
                  bgcolor: isActive ? "rgba(0, 0, 0, 0.04)" : "transparent",
                  color: isActive ? "#000" : "#52525B",
                  "&:hover": {
                    bgcolor: isActive ? "rgba(0, 0, 0, 0.04)" : "rgba(0, 0, 0, 0.02)",
                    color: "#000",
                  },
                  "& .MuiListItemIcon-root": {
                    color: isActive ? "#000" : "#71717A",
                    minWidth: "40px",
                  },
                }}
              >
                <ListItemIcon>{item.icon}</ListItemIcon>
                <ListItemText
                  primary={item.text}
                  primaryTypographyProps={{
                    fontWeight: isActive ? 700 : 600,
                    fontSize: "14px",
                    letterSpacing: "-0.01em",
                  }}
                />
              </ListItemButton>
            </ListItem>
          );
        })}
      </List>
    </Box>
  );

  return (
    <Box
      component="nav"
      sx={{ width: { sm: drawerWidth }, flexShrink: { sm: 0 } }}
    >
      <Drawer
        variant="temporary"
        anchor="left"
        open={mobileOpen}
        onClose={onDrawerToggle}
        ModalProps={{ keepMounted: true }}
        sx={{
          display: { xs: "block", sm: "none" },
          "& .MuiDrawer-paper": {
            boxSizing: "border-box",
            width: drawerWidth,
            bgcolor: "#FAFAFA",
            borderRight: "1px solid rgba(0, 0, 0, 0.05)",
          },
        }}
      >
        <Toolbar />
        {drawer}
      </Drawer>
      <Drawer
        variant="permanent"
        anchor="left"
        sx={{
          display: { xs: "none", sm: "block" },
          "& .MuiDrawer-paper": {
            width: drawerWidth,
            boxSizing: "border-box",
            bgcolor: "#FAFAFA",
            borderRight: "1px solid rgba(0, 0, 0, 0.05)",
          },
        }}
        open
      >
        <Toolbar />
        {drawer}
      </Drawer>
    </Box>
  );
};

export default Sidebar;
