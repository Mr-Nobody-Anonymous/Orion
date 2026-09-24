"use client";

import { useEffect } from "react";
import { useMarketStore } from "@/stores/market";
import { webSocketUrl } from "@/lib/api";

export function WebSocketProvider({ children }: { children: React.ReactNode }) {
  const { setMarketData, setIsConnected } = useMarketStore();

  useEffect(() => {
    let ws: WebSocket;
    let reconnectTimer: ReturnType<typeof setTimeout> | undefined;
    let isUnmounted = false;
    
    const connect = () => {
      if (isUnmounted) return;
      ws = new WebSocket(webSocketUrl("/ws/market"));
      
      ws.onopen = () => setIsConnected(true);
      ws.onclose = () => {
        setIsConnected(false);
        if (!isUnmounted) {
          reconnectTimer = setTimeout(connect, 3000);
        }
      };
      
      ws.onmessage = (event) => {
        const payload = JSON.parse(event.data);
        if (payload.event === "market.update") {
          setMarketData(payload.data);
        }
      };
    };

    connect();

    return () => {
      isUnmounted = true;
      if (reconnectTimer) clearTimeout(reconnectTimer);
      if (ws) ws.close();
    };
  }, [setMarketData, setIsConnected]);

  return <>{children}</>;
}
