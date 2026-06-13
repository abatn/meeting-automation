import React from "react";
import {
  Box,
  Stack,
  Typography,
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
import { useConnectionQualityIndicator } from "@livekit/components-react";
import { ConnectionQuality } from "livekit-client";

export const ConnectionIndicator: React.FC = () => {
  const theme = useTheme();
  const qualityIndicator = useConnectionQualityIndicator();
  const quality = qualityIndicator.quality;

  const getQualityConfig = () => {
    switch (quality) {
      case ConnectionQuality.Excellent:
        return {
          icon: <ExcellentIcon sx={{ fontSize: 16 }} />,
          label: "Excellent",
          color: theme.palette.success.main,
          bgcolor: alpha(theme.palette.success.main, 0.1),
        };
      case ConnectionQuality.Good:
        return {
          icon: <GoodIcon sx={{ fontSize: 16 }} />,
          label: "Good",
          color: theme.palette.warning.main,
          bgcolor: alpha(theme.palette.warning.main, 0.1),
        };
      case ConnectionQuality.Poor:
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
