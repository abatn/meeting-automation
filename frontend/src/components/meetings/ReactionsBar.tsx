import React from "react";
import {
  Box,
  Stack,
  IconButton,
  Tooltip,
  Paper,
  alpha,
  useTheme,
} from "@mui/material";

interface Reaction {
  emoji: string;
  label: string;
}

interface ReactionsBarProps {
  onReaction?: (emoji: string) => void;
  isOpen?: boolean;
}

const DEFAULT_REACTIONS: Reaction[] = [
  { emoji: "👍", label: "Thumbs Up" },
  { emoji: "👏", label: "Clap" },
  { emoji: "😊", label: "Smile" },
  { emoji: "❤️", label: "Love" },
  { emoji: "🎉", label: "Celebrate" },
  { emoji: "🤔", label: "Thinking" },
  { emoji: "👋", label: "Wave" },
  { emoji: "✅", label: "Check" },
];

export const ReactionsBar: React.FC<ReactionsBarProps> = ({
  onReaction,
  isOpen = false,
}) => {
  const theme = useTheme();

  if (!isOpen) return null;

  return (
    <Paper
      elevation={0}
      sx={{
        p: 1.5,
        borderRadius: 3,
        border: `1px solid ${theme.palette.divider}`,
        bgcolor: alpha(theme.palette.background.paper, 0.95),
        boxShadow: "0 2px 8px rgba(0,0,0,0.08)",
      }}
    >
      <Stack direction="row" spacing={0.5} flexWrap="wrap" justifyContent="center">
        {DEFAULT_REACTIONS.map((reaction) => (
          <Tooltip key={reaction.emoji} title={reaction.label}>
            <IconButton
              onClick={() => onReaction?.(reaction.emoji)}
              sx={{
                width: 44,
                height: 44,
                fontSize: 24,
                borderRadius: 2,
                transition: "all 0.15s ease",
                "&:hover": {
                  bgcolor: alpha(theme.palette.primary.main, 0.1),
                  transform: "scale(1.15)",
                },
              }}
            >
              {reaction.emoji}
            </IconButton>
          </Tooltip>
        ))}
      </Stack>
    </Paper>
  );
};

export default ReactionsBar;
