import React, { useState } from "react";
import {
  Box,
  Stack,
  IconButton,
  Tooltip,
  Menu,
  MenuItem,
  ListItemIcon,
  ListItemText,
  Divider,
  alpha,
  useTheme,
} from "@mui/material";
import {
  Mic as MicIcon,
  MicOff as MicOffIcon,
  Videocam as VideocamIcon,
  VideocamOff as VideocamOffIcon,
  ScreenShare as ScreenShareIcon,
  StopScreenShare as StopScreenShareIcon,
  Chat as ChatIcon,
  EmojiEmotions as EmojiIcon,
  CallEnd as LeaveIcon,
  Settings as SettingsIcon,
  MoreVert as MoreIcon,
} from "@mui/icons-material";
import {
  useTrackToggle,
  useRoomContext,
} from "@livekit/components-react";
import { Track, ConnectionState } from "livekit-client";

interface ControlBarProps {
  onLeave?: () => void;
  onToggleChat?: () => void;
  onToggleReactions?: () => void;
  onToggleScreenShare?: () => void;
  isChatOpen?: boolean;
  isReactionsOpen?: boolean;
}

export const ControlBar: React.FC<ControlBarProps> = ({
  onLeave,
  onToggleChat,
  onToggleReactions,
  onToggleScreenShare,
  isChatOpen = false,
  isReactionsOpen = false,
}) => {
  const theme = useTheme();
  const room = useRoomContext();
  const [settingsAnchor, setSettingsAnchor] = useState<null | HTMLElement>(null);

  // Track toggles
  const micToggle = useTrackToggle({ source: Track.Source.Microphone });
  const cameraToggle = useTrackToggle({ source: Track.Source.Camera });
  const screenShareToggle = useTrackToggle({ source: Track.Source.ScreenShare });

  const handleLeave = () => {
    room?.disconnect();
    onLeave?.();
  };

  const buttonStyle = {
    width: 48,
    height: 48,
    borderRadius: "50%",
    transition: "all 0.2s ease",
  };

  const activeButtonStyle = {
    ...buttonStyle,
    bgcolor: theme.palette.primary.main,
    color: "#FFF",
    "&:hover": { bgcolor: theme.palette.primary.dark },
  };

  const inactiveButtonStyle = {
    ...buttonStyle,
    bgcolor: alpha(theme.palette.text.primary, 0.08),
    color: theme.palette.text.primary,
    "&:hover": { bgcolor: alpha(theme.palette.text.primary, 0.12) },
  };

  const dangerButtonStyle = {
    ...buttonStyle,
    bgcolor: theme.palette.error.main,
    color: "#FFF",
    "&:hover": { bgcolor: theme.palette.error.dark },
  };

  return (
    <Stack
      direction="row"
      alignItems="center"
      justifyContent="center"
      spacing={1.5}
      sx={{
        p: 2,
        borderRadius: 3,
        bgcolor: alpha(theme.palette.background.paper, 0.95),
        border: `1px solid ${theme.palette.divider}`,
        boxShadow: "0 2px 8px rgba(0,0,0,0.08)",
      }}
    >
      {/* Microphone Toggle */}
      <Tooltip title={micToggle.enabled ? "Mute Microphone" : "Unmute Microphone"}>
        <IconButton
          onClick={() => micToggle.toggle()}
          sx={micToggle.enabled ? activeButtonStyle : inactiveButtonStyle}
        >
          {micToggle.enabled ? <MicIcon /> : <MicOffIcon />}
        </IconButton>
      </Tooltip>

      {/* Camera Toggle */}
      <Tooltip title={cameraToggle.enabled ? "Turn Off Camera" : "Turn On Camera"}>
        <IconButton
          onClick={() => cameraToggle.toggle()}
          sx={cameraToggle.enabled ? activeButtonStyle : inactiveButtonStyle}
        >
          {cameraToggle.enabled ? <VideocamIcon /> : <VideocamOffIcon />}
        </IconButton>
      </Tooltip>

      {/* Screen Share Toggle */}
      <Tooltip title={screenShareToggle.enabled ? "Stop Screen Share" : "Share Screen"}>
        <IconButton
          onClick={() => {
            screenShareToggle.toggle();
            onToggleScreenShare?.();
          }}
          sx={screenShareToggle.enabled ? activeButtonStyle : inactiveButtonStyle}
        >
          {screenShareToggle.enabled ? <StopScreenShareIcon /> : <ScreenShareIcon />}
        </IconButton>
      </Tooltip>

      <Divider orientation="vertical" flexItem sx={{ mx: 0.5 }} />

      {/* Chat Toggle */}
      <Tooltip title="Toggle Chat">
        <IconButton
          onClick={onToggleChat}
          sx={isChatOpen ? activeButtonStyle : inactiveButtonStyle}
        >
          <ChatIcon />
        </IconButton>
      </Tooltip>

      {/* Reactions Toggle */}
      <Tooltip title="Reactions">
        <IconButton
          onClick={onToggleReactions}
          sx={isReactionsOpen ? activeButtonStyle : inactiveButtonStyle}
        >
          <EmojiIcon />
        </IconButton>
      </Tooltip>

      <Divider orientation="vertical" flexItem sx={{ mx: 0.5 }} />

      {/* Leave Button */}
      <Tooltip title="Leave Meeting">
        <IconButton onClick={handleLeave} sx={dangerButtonStyle}>
          <LeaveIcon />
        </IconButton>
      </Tooltip>
    </Stack>
  );
};

export default ControlBar;
