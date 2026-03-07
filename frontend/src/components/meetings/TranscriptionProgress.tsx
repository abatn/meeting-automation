import React, { useState, useEffect } from "react";
import {
  Box,
  LinearProgress,
  Typography,
  CircularProgress,
  useTheme,
} from "@mui/material";
import { useTranslation } from "react-i18next";

interface Props {
  recordingId: string;
  onComplete?: () => void;
}

const TranscriptionProgress: React.FC<Props> = ({
  recordingId,
  onComplete,
}) => {
  const { t } = useTranslation();
  const theme = useTheme();
  const isRtl = theme.direction === "rtl";

  const [progress, setProgress] = useState(0);
  const [statusText, setStatusText] = useState(t("Connecting..."));
  const [isConnected, setIsConnected] = useState(false);
  const [error, setError] = useState(false);

  useEffect(() => {
    let ws: WebSocket;
    let reconnectTimeout: NodeJS.Timeout;
    let pingInterval: NodeJS.Timeout;

    const connectWebSocket = () => {
      const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
      // Fallback localhost:8000 for local dev
      const host =
        window.location.hostname === "localhost"
          ? "localhost:8000"
          : window.location.host;
      const wsUrl = `${protocol}//${host}/api/v1/websockets/transcription/${recordingId}`;

      ws = new WebSocket(wsUrl);

      ws.onopen = () => {
        setIsConnected(true);
        setError(false);
        // Start Ping/Pong to keep connection alive
        pingInterval = setInterval(() => {
          if (ws.readyState === WebSocket.OPEN) {
            ws.send("ping");
          }
        }, 30000);
      };

      ws.onmessage = (event) => {
        if (event.data === "pong") return;

        try {
          const data = JSON.parse(event.data);
          if (data.progress !== undefined) {
            setProgress(data.progress);
          }
          if (data.message) {
            setStatusText(data.message);
          }
          if (data.status === "completed" && onComplete) {
            onComplete();
          }
          if (data.status === "failed") {
            setError(true);
          }
        } catch (err) {
          console.error("WebSocket message parsing error:", err);
        }
      };

      ws.onclose = () => {
        setIsConnected(false);
        clearInterval(pingInterval);
        // Automatischer Reconnect nach 3 Sekunden, außer bei Erfolg/Fehler
        if (progress < 100 && !error) {
          reconnectTimeout = setTimeout(connectWebSocket, 3000);
        }
      };

      ws.onerror = (err) => {
        console.error("WebSocket error:", err);
        ws.close();
      };
    };

    connectWebSocket();

    return () => {
      clearTimeout(reconnectTimeout);
      clearInterval(pingInterval);
      if (ws) {
        ws.close();
      }
    };
  }, [recordingId, progress, error, onComplete]);

  return (
    <Box sx={{ width: "100%", mt: 2, mb: 2, direction: isRtl ? "rtl" : "ltr" }}>
      <Box sx={{ display: "flex", justifyContent: "space-between", mb: 1 }}>
        <Typography variant="body2" color={error ? "error" : "textSecondary"}>
          {error ? t("Error during processing") : statusText}
        </Typography>
        <Typography variant="body2" color="textSecondary">
          {progress}%
        </Typography>
      </Box>
      <Box sx={{ display: "flex", alignItems: "center" }}>
        <Box sx={{ width: "100%", mr: isRtl ? 0 : 1, ml: isRtl ? 1 : 0 }}>
          <LinearProgress
            variant="determinate"
            value={progress}
            color={error ? "error" : progress === 100 ? "success" : "primary"}
            sx={{ height: 8, borderRadius: 4 }}
          />
        </Box>
        {!isConnected && !error && progress < 100 && (
          <CircularProgress
            size={16}
            sx={{ ml: isRtl ? 0 : 1, mr: isRtl ? 1 : 0 }}
          />
        )}
      </Box>
    </Box>
  );
};

export default TranscriptionProgress;
