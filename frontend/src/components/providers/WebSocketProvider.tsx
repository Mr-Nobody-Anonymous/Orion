"use client";

import { useEffect } from "react";
import { useMarketStore } from "@/stores/market";

export function WebSocketProvider({ children }: { children: React.ReactNode }) {
  const { setMarketData, setIsConnected } = useMarketStore();

  useEffect(() => {
    let ws: WebSocket;
    
    const connect = () => {
      ws = new WebSocket("ws://127.0.0.1:8000/api/v1/ws/market");
      
      ws.onopen = () => setIsConnected(true);
      ws.onclose = () => {
        setIsConnected(false);
        setTimeout(connect, 3000); // Reconnect
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
      if (ws) ws.close();
    };
  }, [setMarketData, setIsConnected]);

  return <>{children}</>;
}
