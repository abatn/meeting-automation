import React from "react";
import {
  Chip,
  alpha,
  useTheme,
} from "@mui/material";
import {
  SignalCellular1Bar as PoorIcon,
  SignalCellular3Bar as GoodIcon,
  SignalCellular4Bar as ExcellentIcon,
  SignalCellular0Bar as DisconnectedIcon,
} from "@mui/icons-material";

interface ConnectionIndicatorProps {
  quality?: "excellent" | "good" | "poor" | "disconnected";
}

export const ConnectionIndicator: React.FC<ConnectionIndicatorProps> = ({
  quality = "disconnected",
}) => {
  const theme = useTheme();

  const getQualityConfig = () => {
    switch (quality) {
      case "excellent":
        return {
          icon: <ExcellentIcon sx={{ fontSize: 16 }} />,
          label: "Excellent",
          color: theme.palette.success.main,
          bgcolor: alpha(theme.palette.success.main, 0.1),
        };
      case "good":
        return {
          icon: <GoodIcon sx={{ fontSize: 16 }} />,
          label: "Good",
          color: theme.palette.warning.main,
          bgcolor: alpha(theme.palette.warning.main, 0.1),
        };
      case "poor":
        return {
          icon: <PoorIcon sx={{ fontSize: 16 }} />,
          label: "Poor",
          color: theme.palette.error.main,
          bgcolor: alpha(theme.palette.error.main, 0.1),
        };
      default:
        return {
          icon: <DisconnectedIcon sx={{ fontSize: 16 }} />,
          label: "Disconnected",
          color: theme.palette.text.secondary,
          bgcolor: alpha(theme.palette.text.primary, 0.06),
        };
    }
  };

  const config = getQualityConfig();

  return (
    <Chip
      icon={config.icon}
      label={config.label}
      size="small"
      sx={{
        bgcolor: config.bgcolor,
        color: config.color,
        fontSize: 11,
        fontWeight: 600,
        height: 24,
        "& .MuiChip-icon": {
          color: "inherit",
        },
      }}
    />
  );
};

export default ConnectionIndicator;
