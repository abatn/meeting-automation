import React, { useState, useRef, useEffect } from "react";
import {
  Box,
  Stack,
  Typography,
  TextField,
  IconButton,
  Paper,
  Avatar,
  alpha,
  useTheme,
} from "@mui/material";
import {
  Send as SendIcon,
  Close as CloseIcon,
} from "@mui/icons-material";
import { Chat as LiveKitChat, useChat } from "@livekit/components-react";

interface ChatMessage {
  id: string;
  sender: string;
  message: string;
  timestamp: Date;
  isOwn: boolean;
}

interface ChatPanelProps {
  isOpen: boolean;
  onClose?: () => void;
}

export const ChatPanel: React.FC<ChatPanelProps> = ({ isOpen, onClose }) => {
  const theme = useTheme();
  const [message, setMessage] = useState("");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const { send, chatMessages } = useChat();

  // Sync LiveKit chat messages with local state
  useEffect(() => {
    if (chatMessages) {
      const mappedMessages: ChatMessage[] = chatMessages.map((msg) => ({
        id: msg.id || String(Date.now()),
        sender: msg.from?.name || "Unknown",
        message: msg.message,
        timestamp: msg.timestamp ? new Date(msg.timestamp) : new Date(),
        isOwn: msg.from?.identity === "local",
      }));
      setMessages(mappedMessages);
    }
  }, [chatMessages]);

  // Auto-scroll to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const handleSend = async () => {
    if (!message.trim()) return;
    
    try {
      await send(message);
      setMessage("");
    } catch (error) {
      console.error("Failed to send message:", error);
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  if (!isOpen) return null;

  return (
    <Paper
      elevation={0}
      sx={{
        height: 400,
        display: "flex",
        flexDirection: "column",
        borderRadius: 3,
        border: `1px solid ${theme.palette.divider}`,
        overflow: "hidden",
      }}
    >
      {/* Header */}
      <Stack
        direction="row"
        alignItems="center"
        justifyContent="space-between"
        sx={{
          p: 1.5,
          borderBottom: `1px solid ${theme.palette.divider}`,
          bgcolor: alpha(theme.palette.primary.main, 0.03),
        }}
      >
        <Typography sx={{ fontSize: 13, fontWeight: 600 }}>
          Meeting Chat
        </Typography>
        <IconButton size="small" onClick={onClose}>
          <CloseIcon fontSize="small" />
        </IconButton>
      </Stack>

      {/* Messages */}
      <Box
        sx={{
          flexGrow: 1,
          overflowY: "auto",
          p: 1.5,
          display: "flex",
          flexDirection: "column",
          gap: 1,
        }}
      >
        {messages.length === 0 ? (
          <Box
            sx={{
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              height: "100%",
              color: theme.palette.text.secondary,
            }}
          >
            <Typography sx={{ fontSize: 13 }}>
              No messages yet. Start the conversation!
            </Typography>
          </Box>
        ) : (
          messages.map((msg) => (
            <Box
              key={msg.id}
              sx={{
                display: "flex",
                flexDirection: msg.isOwn ? "row-reverse" : "row",
                gap: 1,
              }}
            >
              <Avatar
                sx={{
                  width: 28,
                  height: 28,
                  fontSize: 11,
                  bgcolor: msg.isOwn
                    ? theme.palette.primary.main
                    : theme.palette.secondary.main,
                }}
              >
                {msg.sender.charAt(0).toUpperCase()}
              </Avatar>
              <Box
                sx={{
                  maxWidth: "75%",
                  p: 1,
                  borderRadius: 2,
                  bgcolor: msg.isOwn
                    ? theme.palette.primary.main
                    : alpha(theme.palette.text.primary, 0.06),
                  color: msg.isOwn ? "#FFF" : "inherit",
                }}
              >
                {!msg.isOwn && (
                  <Typography
                    sx={{
                      fontSize: 10,
                      fontWeight: 600,
                      color: theme.palette.primary.main,
                      mb: 0.25,
                    }}
                  >
                    {msg.sender}
                  </Typography>
                )}
                <Typography sx={{ fontSize: 12, wordBreak: "break-word" }}>
                  {msg.message}
                </Typography>
                <Typography
                  sx={{
                    fontSize: 9,
                    color: msg.isOwn
                      ? "rgba(255,255,255,0.7)"
                      : theme.palette.text.secondary,
                    mt: 0.25,
                  }}
                >
                  {msg.timestamp.toLocaleTimeString([], {
                    hour: "2-digit",
                    minute: "2-digit",
                  })}
                </Typography>
              </Box>
            </Box>
          ))
        )}
        <div ref={messagesEndRef} />
      </Box>

      {/* Input */}
      <Box
        sx={{
          p: 1.5,
          borderTop: `1px solid ${theme.palette.divider}`,
          bgcolor: alpha(theme.palette.background.paper, 0.95),
        }}
      >
        <Stack direction="row" spacing={1} alignItems="center">
          <TextField
            fullWidth
            size="small"
            placeholder="Type a message..."
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            onKeyPress={handleKeyPress}
            sx={{
              "& .MuiOutlinedInput-root": {
                borderRadius: 2,
                fontSize: 13,
              },
            }}
          />
          <IconButton
            onClick={handleSend}
            disabled={!message.trim()}
            sx={{
              bgcolor: message.trim()
                ? theme.palette.primary.main
                : alpha(theme.palette.text.primary, 0.08),
              color: message.trim() ? "#FFF" : theme.palette.text.secondary,
              "&:hover": {
                bgcolor: message.trim()
                  ? theme.palette.primary.dark
                  : alpha(theme.palette.text.primary, 0.12),
              },
            }}
          >
            <SendIcon fontSize="small" />
          </IconButton>
        </Stack>
      </Box>
    </Paper>
  );
};

export default ChatPanel;
