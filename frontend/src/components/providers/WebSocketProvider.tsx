"use client";

import { useEffect } from "react";
import { useMarketStore } from "@/stores/market";

export function WebSocketProvider({ children }: { children: React.ReactNode }) {
  const { setMarketData, setIsConnected } = useMarketStore();

  useEffect(() => {
    let ws: WebSocket | null = null;
    let reconnectTimeout: NodeJS.Timeout | null = null;
    let isUnmounted = false;

    const getWsUrl = () => {
      if (process.env.NEXT_PUBLIC_WS_URL) {
        return process.env.NEXT_PUBLIC_WS_URL;
      }
      if (typeof window !== "undefined") {
        const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
        const host = window.location.hostname === "localhost" || window.location.hostname === "127.0.0.1"
          ? "127.0.0.1:8000"
          : window.location.host;
        return `${protocol}//${host}/api/v1/ws/market`;
      }
      return "ws://127.0.0.1:8000/api/v1/ws/market";
    };

    const connect = () => {
      if (isUnmounted) return;
      try {
        ws = new WebSocket(getWsUrl());

        ws.onopen = () => {
          if (!isUnmounted) setIsConnected(true);
        };

        ws.onclose = () => {
          if (!isUnmounted) {
            setIsConnected(false);
            reconnectTimeout = setTimeout(connect, 3000);
          }
        };

        ws.onmessage = (event) => {
          try {
            const payload = JSON.parse(event.data);
            if (payload.event === "market.update") {
              setMarketData(payload.data);
            }
          } catch {
            // ignore non-json messages
          }
        };
      } catch {
        if (!isUnmounted) {
          reconnectTimeout = setTimeout(connect, 3000);
        }
      }
    };

    connect();

    return () => {
      isUnmounted = true;
      if (reconnectTimeout) clearTimeout(reconnectTimeout);
      if (ws) ws.close();
    };
  }, [setMarketData, setIsConnected]);

  return <>{children}</>;
}
