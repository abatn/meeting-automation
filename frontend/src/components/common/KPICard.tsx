import React from "react";
import { Paper, Typography, Box } from "@mui/material";
import { ReactNode } from "react";

interface KPICardProps {
  title: string;
  value: number | string;
  icon?: ReactNode;
}

const KPICard: React.FC<KPICardProps> = ({ title, value, icon }) => {
  return (
    <Paper
      sx={{
        p: 2,
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        height: "100%",
      }}
    >
      <Box sx={{ mb: 1 }}>{icon}</Box>
      <Typography variant="subtitle1" color="text.secondary">
        {title}
      </Typography>
      <Typography variant="h5" component="div" sx={{ mt: 1 }}>
        {value}
      </Typography>
    </Paper>
  );
};

export default KPICard;
