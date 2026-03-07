import React from "react";
import { Box, Toolbar } from "@mui/material";
import Navbar from "./Navbar";
import Sidebar from "./Sidebar";
import RTLLayout from "./RTLLayout";

interface MainLayoutProps {
  children: React.ReactNode;
}

const drawerWidth = 240;

const MainLayout: React.FC<MainLayoutProps> = ({ children }) => {
  return (
    <RTLLayout>
      <Box sx={{ display: "flex" }}>
        <Navbar />
        <Sidebar />
        <Box
          component="main"
          sx={{
            flexGrow: 1,
            p: 3,
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
