import React from "react";
import { Paper, Typography, Box, useTheme, alpha } from "@mui/material";
import { ReactNode } from "react";

interface KPICardProps {
  title: string;
  value: number | string;
  icon?: ReactNode;
}

const KPICard: React.FC<KPICardProps> = ({ title, value, icon }) => {
  const theme = useTheme();
  
  return (
    <Paper
      sx={{
        p: { xs: 2, md: 3 },
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        height: "100%",
        borderRadius: "16px",
        background: theme.palette.mode === 'dark' 
          ? alpha(theme.palette.background.paper, 0.05) 
          : alpha(theme.palette.background.paper, 0.8),
        backdropFilter: "blur(12px)",
        border: `1px solid ${theme.palette.mode === 'dark' 
          ? 'rgba(255, 255, 255, 0.08)' 
          : 'rgba(0, 0, 0, 0.05)'}`,
        boxShadow: "none",
        transition: "transform 0.2s ease-in-out",
        "&:hover": {
          transform: "translateY(-4px)",
          borderColor: alpha(theme.palette.primary.main, 0.2),
        }
      }}
    >
      <Box sx={{ 
        mb: 1.5, 
        color: theme.palette.primary.main,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        p: 1.5,
        borderRadius: '12px',
        bgcolor: alpha(theme.palette.primary.main, 0.08)
      }}>
        {icon}
      </Box>
      <Typography variant="body2" sx={{ color: '#71717A', fontWeight: 600, textAlign: 'center' }}>
        {title}
      </Typography>
      <Typography variant="h4" component="div" sx={{ mt: 1, fontWeight: 800, letterSpacing: '-0.02em' }}>
        {value}
      </Typography>
    </Paper>
  );
};

export default KPICard;
