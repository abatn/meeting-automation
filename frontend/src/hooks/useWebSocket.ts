import { useEffect, useRef, useState } from 'react';

// TODO: Implement robust WebSocket hook with reconnection logic
export const useWebSocket = (url: string) => {
  const [messages, setMessages] = useState<any[]>([]);
  const ws = useRef<WebSocket | null>(null);

  useEffect(() => {
    ws.current = new WebSocket(url);
    ws.current.onmessage = (event) => {
      setMessages((prev) => [...prev, JSON.parse(event.data)]);
    };

    return () => {
      ws.current?.close();
    };
  }, [url]);

  const sendMessage = (message: any) => {
    ws.current?.send(JSON.stringify(message));
  };

  return { messages, sendMessage };
};