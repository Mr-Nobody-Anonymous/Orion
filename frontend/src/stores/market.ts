import { create } from 'zustand';

interface MarketState {
  marketData: any | null;
  setMarketData: (data: any) => void;
  isConnected: boolean;
  setIsConnected: (connected: boolean) => void;
}

export const useMarketStore = create<MarketState>((set) => ({
  marketData: null,
  setMarketData: (data) => set({ marketData: data }),
  isConnected: false,
  setIsConnected: (connected) => set({ isConnected: connected }),
}));
