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
  Divider,
} from "@mui/material";
import { useNavigate, useLocation } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useSelector, useDispatch } from "react-redux";
import { RootState, AppDispatch } from "../../store";
import { logoutThunk } from "../../store/authSlice";
import DashboardIcon from "@mui/icons-material/Dashboard";
import EventIcon from "@mui/icons-material/Event";
import CollectionsBookmarkIcon from "@mui/icons-material/CollectionsBookmark";
import AssignmentIcon from "@mui/icons-material/Assignment";
import AssessmentIcon from "@mui/icons-material/Assessment";
import PeopleIcon from "@mui/icons-material/People";
import PaymentIcon from "@mui/icons-material/Payment";
import LogoutIcon from "@mui/icons-material/Logout";

const drawerWidth = 240;

interface SidebarProps {
  mobileOpen: boolean;
  onDrawerToggle: () => void;
}

const Sidebar: React.FC<SidebarProps> = ({ mobileOpen, onDrawerToggle }) => {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const location = useLocation();
  const dispatch = useDispatch<AppDispatch>();
  const { user } = useSelector((state: RootState) => state.auth);

  // Define all available sidebar items for regular users
  const dashboardItem = { text: t("sidebar.dashboard"), icon: <DashboardIcon fontSize="small" />, path: "/" };
  const meetingsItem = { text: t("sidebar.meetings"), icon: <EventIcon fontSize="small" />, path: "/meetings" };
  const archiveItem = { text: t("sidebar.archive"), icon: <CollectionsBookmarkIcon fontSize="small" />, path: "/archive" };
  const actionsItem = { text: t("sidebar.actions"), icon: <AssignmentIcon fontSize="small" />, path: "/actions" };
  const reportsItem = { text: t("sidebar.reports"), icon: <AssessmentIcon fontSize="small" />, path: "/reports" };
  const teamItem = { text: t("sidebar.team", "Team"), icon: <PeopleIcon fontSize="small" />, path: "/team" };
  const billingItem = { text: t("sidebar.billing", "Billing"), icon: <PaymentIcon fontSize="small" />, path: "/billing" };

  // Logic for System Admin (God Mode)
  const adminItems = [
    { text: t("admin.businessOverview"), icon: <DashboardIcon fontSize="small" />, path: "/" },
    { text: t("admin.manageClients"), icon: <PeopleIcon fontSize="small" />, path: "/admin/clients" },
    { text: t("admin.revenueBilling"), icon: <PaymentIcon fontSize="small" />, path: "/billing" },
  ];

  // RBAC Sidebar Item Selection
  const getSidebarItems = () => {
    switch (user?.role) {
      case "system_admin":
        return adminItems;
      case "dg":
        return [dashboardItem, meetingsItem, archiveItem, actionsItem, reportsItem, teamItem, billingItem];
      case "manager":
        return [dashboardItem, meetingsItem, archiveItem, actionsItem, reportsItem, teamItem];
      case "participant":
        return [dashboardItem, meetingsItem, archiveItem, actionsItem];
      default:
        return [dashboardItem, meetingsItem, archiveItem, actionsItem];
    }
  };

  const currentItems = getSidebarItems();

  const drawer = (
    <Box sx={{ display: "flex", flexDirection: "column", height: "100%", overflow: "hidden" }}>
      <Box sx={{ flex: 1, overflow: "auto", px: 2, pt: 3 }}>
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
      <Divider sx={{ mx: 2, borderColor: "rgba(0, 0, 0, 0.06)", flexShrink: 0 }} />
      <Box sx={{ px: 2, pb: 2, pt: 1, flexShrink: 0 }}>
        <List disablePadding>
          <ListItem disablePadding>
            <ListItemButton
              onClick={() => {
                dispatch(logoutThunk()).then(() => {
                  navigate("/login");
                }).catch(() => {
                  navigate("/login");
                });
                if (mobileOpen) onDrawerToggle();
              }}
              sx={{
                borderRadius: "8px",
                py: 1,
                px: 1.5,
                color: "#D32F2F",
                "&:hover": {
                  bgcolor: "rgba(211, 47, 47, 0.04)",
                },
                "& .MuiListItemIcon-root": {
                  color: "#D32F2F",
                  minWidth: "40px",
                },
              }}
            >
              <ListItemIcon><LogoutIcon fontSize="small" /></ListItemIcon>
              <ListItemText
                primary={t("auth.logout")}
                primaryTypographyProps={{
                  fontWeight: 600,
                  fontSize: "14px",
                  letterSpacing: "-0.01em",
                }}
              />
            </ListItemButton>
          </ListItem>
        </List>
      </Box>
    </Box>
  );

  return (
    <Box
      component="nav"
      sx={{ width: { sm: drawerWidth }, flexShrink: { sm: 0 }, height: "100vh" }}
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
            height: "100%",
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
            height: "100%",
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