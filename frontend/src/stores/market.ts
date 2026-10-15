import { create } from 'zustand';

export interface MarketTrade {
  kind?: string;
  side: string;
  quantity: number;
  symbol: string;
  venue?: string;
  fill_price?: number;
  price?: number;
  status?: string;
}

export interface MarketPayload {
  symbol?: string;
  price?: number;
  change?: string | number;
  timestamp?: string | number;
  trades?: MarketTrade[];
  equity_history?: number[];
  limits?: {
    max_portfolio_exposure: number;
    max_position_fraction: number;
    max_daily_loss_fraction: number;
  };
  [key: string]: unknown;
}

interface MarketState {
  marketData: MarketPayload | null;
  setMarketData: (data: MarketPayload | null) => void;
  isConnected: boolean;
  setIsConnected: (connected: boolean) => void;
}

export const useMarketStore = create<MarketState>((set) => ({
  marketData: null,
  setMarketData: (data) => set({ marketData: data }),
  isConnected: false,
  setIsConnected: (connected) => set({ isConnected: connected }),
}));
