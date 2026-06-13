import React from "react";
import {
  Box,
  Grid,
  Typography,
  Avatar,
  alpha,
  useTheme,
} from "@mui/material";
import {
  Mic as MicIcon,
  MicOff as MicOffIcon,
} from "@mui/icons-material";

interface Participant {
  name?: string;
  identity?: string;
  isSpeaking?: boolean;
  isMuted?: boolean;
}

interface ParticipantGridProps {
  participants?: Participant[];
  maxParticipants?: number;
}

export const ParticipantGrid: React.FC<ParticipantGridProps> = ({
  participants = [],
  maxParticipants = 6,
}) => {
  const theme = useTheme();
  const displayParticipants = participants.slice(0, maxParticipants);

  if (displayParticipants.length === 0) {
    return (
      <Box
        sx={{
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          height: 200,
          bgcolor: alpha(theme.palette.text.primary, 0.02),
          borderRadius: 2,
        }}
      >
        <Typography sx={{ fontSize: 13, color: theme.palette.text.secondary }}>
          Waiting for participants...
        </Typography>
      </Box>
    );
  }

  return (
    <Grid container spacing={1.5}>
      {displayParticipants.map((participant, idx) => (
        <Grid item xs={12} sm={6} md={4} key={participant.identity || idx}>
          <ParticipantCard participant={participant} />
        </Grid>
      ))}
    </Grid>
  );
};

interface ParticipantCardProps {
  participant: Participant;
}

const ParticipantCard: React.FC<ParticipantCardProps> = ({ participant }) => {
  const theme = useTheme();
  const isSpeaking = participant.isSpeaking;
  const isMuted = participant.isMuted;

  return (
    <Box
      sx={{
        position: "relative",
        aspectRatio: "16/9",
        borderRadius: 2,
        overflow: "hidden",
        border: `2px solid ${
          isSpeaking ? theme.palette.success.main : theme.palette.divider
        }`,
        transition: "border-color 0.2s ease",
        bgcolor: alpha(theme.palette.text.primary, 0.03),
      }}
    >
      {/* Participant Avatar */}
      <Box
        sx={{
          width: "100%",
          height: "100%",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          bgcolor: alpha(theme.palette.primary.main, 0.1),
        }}
      >
        <Avatar
          sx={{
            width: 64,
            height: 64,
            fontSize: 24,
            bgcolor: theme.palette.primary.main,
            color: "#FFF",
          }}
        >
          {participant.name?.charAt(0).toUpperCase() ||
            participant.identity?.charAt(0).toUpperCase() ||
            "?"}
        </Avatar>
      </Box>

      {/* Name Label */}
      <Box
        sx={{
          position: "absolute",
          bottom: 0,
          left: 0,
          right: 0,
          p: 0.75,
          background: "linear-gradient(transparent, rgba(0,0,0,0.7))",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
        }}
      >
        <Typography
          sx={{
            fontSize: 11,
            fontWeight: 600,
            color: "#FFF",
            textShadow: "0 1px 2px rgba(0,0,0,0.5)",
          }}
        >
          {participant.name || participant.identity}
        </Typography>
        {isMuted !== undefined && (
          <Box
            sx={{
              p: 0.25,
              borderRadius: 1,
              bgcolor: isMuted
                ? alpha(theme.palette.error.main, 0.8)
                : alpha(theme.palette.success.main, 0.8),
            }}
          >
            {isMuted ? (
              <MicOffIcon sx={{ fontSize: 12, color: "#FFF" }} />
            ) : (
              <MicIcon sx={{ fontSize: 12, color: "#FFF" }} />
            )}
          </Box>
        )}
      </Box>

      {/* Speaking Indicator */}
      {isSpeaking && (
        <Box
          sx={{
            position: "absolute",
            top: 8,
            right: 8,
            width: 12,
            height: 12,
            borderRadius: "50%",
            bgcolor: theme.palette.success.main,
            animation: "pulse 1s infinite",
            boxShadow: `0 0 8px ${theme.palette.success.main}`,
          }}
        />
      )}
    </Box>
  );
};

export default ParticipantGrid;
