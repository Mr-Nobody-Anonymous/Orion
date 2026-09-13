"use client";

import { useMarketStore } from "@/stores/market";
import { Activity, Briefcase, TrendingUp, ShieldAlert, ArrowRight } from "lucide-react";

export default function DashboardPage() {
  const { marketData, isConnected } = useMarketStore();

  const status = marketData || {
    limits: { max_portfolio_exposure: 0, max_position_fraction: 0, max_daily_loss_fraction: 0 },
    equity_history: [100000],
    trades: []
  };

  const currentEquity = status.equity_history[status.equity_history.length - 1] || 100000;
  const initialEquity = status.equity_history[0] || 100000;
  const pnl = currentEquity - initialEquity;
  const pnlPercent = (pnl / initialEquity) * 100;

  return (
    <div className="flex-1 overflow-y-auto p-8 bg-zinc-950 text-zinc-100">
      <header className="flex justify-between items-center mb-8">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Mission Control</h1>
          <p className="text-sm text-zinc-500 mt-1">
            Real-time portfolio and risk telemetrics
          </p>
        </div>
        <div className="flex items-center space-x-2 bg-zinc-900 border border-zinc-800 rounded-full px-4 py-1.5 text-sm">
          <div className={`w-2 h-2 rounded-full ${isConnected ? 'bg-green-500 shadow-[0_0_8px_rgba(34,197,94,0.6)]' : 'bg-red-500'}`} />
          <span className="text-zinc-300 font-medium">{isConnected ? 'System Connected' : 'Disconnected'}</span>
        </div>
      </header>

      {/* Top Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-8">
        <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5 shadow-sm">
          <div className="flex justify-between items-start mb-2">
            <h3 className="text-sm font-medium text-zinc-400">Net Asset Value</h3>
            <Briefcase className="w-4 h-4 text-zinc-500" />
          </div>
          <div className="text-2xl font-bold text-white mb-1">
            ${currentEquity.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
          </div>
          <div className={`text-xs font-medium flex items-center ${pnl >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
            <TrendingUp className="w-3 h-3 mr-1" />
            {pnl >= 0 ? '+' : ''}{pnl.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })} ({pnlPercent.toFixed(2)}%)
          </div>
        </div>

        <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5 shadow-sm">
          <div className="flex justify-between items-start mb-2">
            <h3 className="text-sm font-medium text-zinc-400">Value at Risk (VaR)</h3>
            <ShieldAlert className="w-4 h-4 text-zinc-500" />
          </div>
          <div className="text-2xl font-bold text-amber-500 mb-1">
            $184.5K
          </div>
          <div className="text-xs font-medium text-zinc-500 flex items-center">
            95% Confidence (Parametric)
          </div>
        </div>

        <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5 shadow-sm">
          <div className="flex justify-between items-start mb-2">
            <h3 className="text-sm font-medium text-zinc-400">Leverage</h3>
            <Activity className="w-4 h-4 text-zinc-500" />
          </div>
          <div className="text-2xl font-bold text-white mb-1">
            2.31x
          </div>
          <div className="text-xs font-medium text-zinc-500 flex items-center">
            Max Policy Limit: {(status.limits?.max_portfolio_exposure || 0) * 100}%
          </div>
        </div>

        <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5 shadow-sm flex flex-col justify-center items-center group cursor-pointer hover:bg-zinc-800 transition-colors">
          <div className="w-10 h-10 rounded-full bg-blue-500/10 text-blue-400 flex items-center justify-center mb-2 group-hover:bg-blue-500 group-hover:text-white transition-colors">
            <ArrowRight className="w-5 h-5" />
          </div>
          <span className="text-sm font-medium text-zinc-300">New Order Ticket</span>
        </div>
      </div>
      
      {/* Risk and Trading Split */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-6">
          <h2 className="text-lg font-bold mb-4 flex items-center">
            <ShieldAlert className="w-5 h-5 mr-2 text-red-400" />
            Top Risk Contributors
          </h2>
          <div className="space-y-4">
            <div>
              <div className="flex justify-between text-sm mb-1">
                <span className="text-zinc-300">Technology Sector</span>
                <span className="text-zinc-400">27%</span>
              </div>
              <div className="w-full bg-zinc-800 rounded-full h-2">
                <div className="bg-red-400 h-2 rounded-full" style={{ width: '27%' }}></div>
              </div>
            </div>
            <div>
              <div className="flex justify-between text-sm mb-1">
                <span className="text-zinc-300">Momentum Factor</span>
                <span className="text-zinc-400">19%</span>
              </div>
              <div className="w-full bg-zinc-800 rounded-full h-2">
                <div className="bg-amber-400 h-2 rounded-full" style={{ width: '19%' }}></div>
              </div>
            </div>
            <div>
              <div className="flex justify-between text-sm mb-1">
                <span className="text-zinc-300">Interest Rates Duration</span>
                <span className="text-zinc-400">11%</span>
              </div>
              <div className="w-full bg-zinc-800 rounded-full h-2">
                <div className="bg-yellow-400 h-2 rounded-full" style={{ width: '11%' }}></div>
              </div>
            </div>
          </div>
        </div>

        <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-6">
          <h2 className="text-lg font-bold mb-4 flex items-center">
            <Activity className="w-5 h-5 mr-2 text-blue-400" />
            Recent Activity
          </h2>
          <div className="space-y-3">
            {status.trades && status.trades.length > 0 ? (
              status.trades.slice(-4).reverse().map((trade: any, i: number) => (
                <div key={i} className="flex justify-between items-center py-2 border-b border-zinc-800 last:border-0">
                  <div>
                    <span className={`text-xs font-bold px-2 py-1 rounded mr-2 ${trade.side === 'BUY' ? 'bg-green-500/20 text-green-400' : 'bg-red-500/20 text-red-400'}`}>
                      {trade.side}
                    </span>
                    <span className="font-medium text-zinc-200">{trade.quantity} {trade.symbol}</span>
                  </div>
                  <div className="text-sm text-zinc-500 font-mono">
                    @ {trade.price ? `$${trade.price}` : 'MKT'}
                  </div>
                </div>
              ))
            ) : (
              <div className="text-sm text-zinc-500 italic py-4 text-center">No recent trades in log.</div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
