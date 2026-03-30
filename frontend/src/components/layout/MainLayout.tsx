import React, { useState } from "react";
import { Box, Toolbar } from "@mui/material";
import Navbar from "./Navbar";
import Sidebar from "./Sidebar";
import RTLLayout from "./RTLLayout";

interface MainLayoutProps {
  children: React.ReactNode;
}

const drawerWidth = 240;

const MainLayout: React.FC<MainLayoutProps> = ({ children }) => {
  const [mobileOpen, setMobileOpen] = useState(false);

  const handleDrawerToggle = () => {
    setMobileOpen(!mobileOpen);
  };

  return (
    <RTLLayout>
      <Box sx={{ display: "flex" }}>
        <Navbar onMenuClick={handleDrawerToggle} />
        <Sidebar mobileOpen={mobileOpen} onDrawerToggle={handleDrawerToggle} />
        <Box
          component="main"
          sx={{
            flexGrow: 1,
            p: { xs: 2, md: 4 },
            width: { sm: `calc(100% - ${drawerWidth}px)` },
            minHeight: "100vh",
            bgcolor: "background.default",
          }}
        >
          <Toolbar />
          {children}
        </Box>
      </Box>
    </RTLLayout>
  );
};

export default MainLayout;
