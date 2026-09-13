"use client";

import { useEffect, useState } from "react";
import { Server, Activity, ArrowRightLeft, CheckCircle2, XCircle, AlertCircle } from "lucide-react";
import { useMarketStore } from "@/stores/market";

export default function ExecutionPage() {
  const [brokers, setBrokers] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  
  // Form State
  const [symbol, setSymbol] = useState("NVDA");
  const [side, setSide] = useState("BUY");
  const [quantity, setQuantity] = useState("10");
  const [orderType, setOrderType] = useState("MARKET");
  const [dryRun, setDryRun] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [lastResult, setLastResult] = useState<any>(null);

  const { marketData } = useMarketStore();

  const loadBrokers = async () => {
    try {
      const res = await fetch("http://127.0.0.1:8000/api/v1/dashboard/brokers");
      if (res.ok) setBrokers(await res.json());
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadBrokers();
  }, []);

  const handleTrade = async (e: React.FormEvent) => {
    e.preventDefault();
    if (isSubmitting) return;
    setIsSubmitting(true);
    setLastResult(null);

    try {
      const res = await fetch("http://127.0.0.1:8000/api/v1/execution/trade", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          symbol: symbol.toUpperCase(),
          side,
          quantity: parseFloat(quantity) || 0,
          order_type: orderType,
          dry_run: dryRun,
        })
      });
      const data = await res.json();
      setLastResult(data);
    } catch (err) {
      setLastResult({ status: "error", error: String(err) });
    } finally {
      setIsSubmitting(false);
    }
  };

  if (loading) return <div className="flex-1 flex items-center justify-center bg-zinc-950 text-zinc-500">Connecting to execution venues...</div>;

  return (
    <div className="flex-1 flex overflow-hidden bg-zinc-950 text-zinc-100">
      
      {/* Left Sidebar: Venue Status */}
      <div className="w-1/4 border-r border-zinc-800 flex flex-col h-full bg-zinc-900/30">
        <div className="p-6 border-b border-zinc-800">
          <h1 className="text-xl font-bold tracking-tight text-white flex items-center mb-1">
            <Server className="w-5 h-5 mr-2 text-indigo-500" /> Execution
          </h1>
          <p className="text-xs text-zinc-400">Broker Venues & Order Routing</p>
        </div>
        
        <div className="overflow-y-auto flex-1 p-6 space-y-6">
          <h2 className="text-xs font-bold text-zinc-500 uppercase tracking-wider">Connected Venues</h2>
          
          <div className="space-y-4">
            {brokers?.catalogue && Object.entries(brokers.catalogue).map(([id, info]: [string, any]) => {
              const health = brokers.health?.find((h: any) => h.provider === id);
              const isLive = brokers.venues?.some((v: any) => v.venue === id);
              
              return (
                <div key={id} className={`bg-zinc-900 border rounded-lg p-4 ${isLive ? 'border-emerald-500/30' : 'border-zinc-800'}`}>
                  <div className="flex justify-between items-start mb-2">
                    <span className="font-bold text-sm text-zinc-200">{info.name}</span>
                    <span className={`text-[10px] uppercase px-2 py-0.5 rounded ${isLive ? 'bg-emerald-500/20 text-emerald-400' : 'bg-zinc-800 text-zinc-500'}`}>
                      {isLive ? 'ACTIVE' : 'INACTIVE'}
                    </span>
                  </div>
                  <div className="text-xs text-zinc-500 mb-3">{info.category}</div>
                  
                  {isLive && health && (
                    <div className="flex justify-between items-center text-xs border-t border-zinc-800/50 pt-2">
                      <span className="text-zinc-500">Latency</span>
                      <span className="font-mono text-emerald-400">{health.latency_ms.toFixed(1)}ms</span>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      </div>

      {/* Main Area: Order Ticket & Log */}
      <div className="flex-1 flex flex-col h-full">
        <div className="flex-1 overflow-y-auto p-8 grid grid-cols-1 lg:grid-cols-2 gap-8">
          
          {/* Order Ticket */}
          <div className="space-y-6">
            <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-6 shadow-sm">
              <h2 className="text-sm font-bold text-zinc-300 uppercase tracking-wider mb-6 flex items-center">
                <ArrowRightLeft className="w-4 h-4 mr-2 text-blue-500" /> Order Ticket
              </h2>
              
              <form onSubmit={handleTrade} className="space-y-5">
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-xs font-bold text-zinc-500 uppercase mb-2">Symbol</label>
                    <input 
                      type="text" 
                      value={symbol}
                      onChange={(e) => setSymbol(e.target.value.toUpperCase())}
                      className="w-full bg-zinc-950 border border-zinc-800 rounded-lg px-4 py-2.5 text-sm text-white font-bold placeholder-zinc-600 focus:outline-none focus:border-blue-500"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-bold text-zinc-500 uppercase mb-2">Side</label>
                    <select 
                      value={side}
                      onChange={(e) => setSide(e.target.value)}
                      className="w-full bg-zinc-950 border border-zinc-800 rounded-lg px-4 py-2.5 text-sm text-white font-bold focus:outline-none focus:border-blue-500"
                    >
                      <option value="BUY">BUY</option>
                      <option value="SELL">SELL</option>
                    </select>
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-xs font-bold text-zinc-500 uppercase mb-2">Quantity</label>
                    <input 
                      type="number" 
                      value={quantity}
                      onChange={(e) => setQuantity(e.target.value)}
                      className="w-full bg-zinc-950 border border-zinc-800 rounded-lg px-4 py-2.5 text-sm text-white font-mono focus:outline-none focus:border-blue-500"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-bold text-zinc-500 uppercase mb-2">Type</label>
                    <select 
                      value={orderType}
                      onChange={(e) => setOrderType(e.target.value)}
                      className="w-full bg-zinc-950 border border-zinc-800 rounded-lg px-4 py-2.5 text-sm text-white focus:outline-none focus:border-blue-500"
                    >
                      <option value="MARKET">MARKET</option>
                      <option value="LIMIT">LIMIT</option>
                    </select>
                  </div>
                </div>

                <div className="pt-2">
                  <label className="flex items-center space-x-3 cursor-pointer group">
                    <div className="relative">
                      <input 
                        type="checkbox" 
                        checked={dryRun} 
                        onChange={(e) => setDryRun(e.target.checked)}
                        className="sr-only" 
                      />
                      <div className={`block w-10 h-6 rounded-full transition-colors ${dryRun ? 'bg-indigo-500' : 'bg-zinc-700'}`}></div>
                      <div className={`dot absolute left-1 top-1 bg-white w-4 h-4 rounded-full transition-transform ${dryRun ? 'transform translate-x-4' : ''}`}></div>
                    </div>
                    <div className="text-sm">
                      <span className={`font-bold ${dryRun ? 'text-indigo-400' : 'text-zinc-500'}`}>Simulated Mode (Dry Run)</span>
                      <p className="text-xs text-zinc-500">Orders will not be sent to live exchanges.</p>
                    </div>
                  </label>
                </div>

                <div className="pt-4 border-t border-zinc-800/50">
                  <button 
                    type="submit"
                    disabled={isSubmitting}
                    className={`w-full py-3 rounded-lg font-bold text-sm tracking-wide transition-colors flex items-center justify-center
                      ${isSubmitting ? 'bg-zinc-800 text-zinc-500 cursor-not-allowed' 
                        : side === 'BUY' ? 'bg-emerald-600 hover:bg-emerald-500 text-white' 
                        : 'bg-red-600 hover:bg-red-500 text-white'}`}
                  >
                    {isSubmitting ? 'SUBMITTING...' : `${side} ${quantity} ${symbol}`}
                  </button>
                </div>
              </form>
            </div>

            {/* Execution Result Banner */}
            {lastResult && (
              <div className={`rounded-xl p-5 border ${
                lastResult.status === 'success' || lastResult.status === 'filled' ? 'bg-emerald-500/10 border-emerald-500/30' : 
                lastResult.status === 'error' ? 'bg-red-500/10 border-red-500/30' : 
                'bg-amber-500/10 border-amber-500/30'
              }`}>
                <div className="flex items-start">
                  {lastResult.status === 'success' || lastResult.status === 'filled' ? (
                    <CheckCircle2 className="w-5 h-5 text-emerald-400 mr-3 mt-0.5" />
                  ) : lastResult.status === 'error' ? (
                    <XCircle className="w-5 h-5 text-red-400 mr-3 mt-0.5" />
                  ) : (
                    <AlertCircle className="w-5 h-5 text-amber-400 mr-3 mt-0.5" />
                  )}
                  <div>
                    <h3 className={`text-sm font-bold capitalize ${
                      lastResult.status === 'success' || lastResult.status === 'filled' ? 'text-emerald-400' : 
                      lastResult.status === 'error' ? 'text-red-400' : 
                      'text-amber-400'
                    }`}>
                      Order {lastResult.status}
                    </h3>
                    {lastResult.error ? (
                      <p className="text-xs text-zinc-300 mt-1">{lastResult.error}</p>
                    ) : (
                      <div className="text-xs text-zinc-300 mt-1 space-y-1">
                        <div><span className="text-zinc-500">Order ID:</span> {lastResult.order_id}</div>
                        <div><span className="text-zinc-500">Fill Price:</span> ${lastResult.fill_price}</div>
                        <div><span className="text-zinc-500">Venue:</span> {lastResult.venue}</div>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* Execution Log */}
          <div>
            <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-6 h-full flex flex-col">
              <h2 className="text-sm font-bold text-zinc-300 uppercase tracking-wider mb-6 flex items-center">
                <Activity className="w-4 h-4 mr-2 text-emerald-500" /> Recent Executions
              </h2>
              
              <div className="flex-1 space-y-3">
                {marketData?.trades && marketData.trades.length > 0 ? (
                  marketData.trades.slice().reverse().filter((t:any) => t.kind === 'order').map((trade: any, i: number) => (
                    <div key={i} className="flex justify-between items-center p-3 bg-zinc-950 border border-zinc-800/80 rounded">
                      <div className="flex items-center">
                        <span className={`text-[10px] font-bold px-2 py-0.5 rounded mr-3 ${trade.side === 'BUY' ? 'bg-emerald-500/20 text-emerald-400' : 'bg-red-500/20 text-red-400'}`}>
                          {trade.side}
                        </span>
                        <div>
                          <div className="font-bold text-zinc-200 text-sm">{trade.quantity} {trade.symbol}</div>
                          <div className="text-[10px] text-zinc-500">{trade.venue || 'SIMULATED'}</div>
                        </div>
                      </div>
                      <div className="text-right">
                        <div className="text-sm text-zinc-300 font-mono">${trade.fill_price || trade.price}</div>
                        <div className="text-[10px] text-zinc-500">{trade.status?.toUpperCase() || 'FILLED'}</div>
                      </div>
                    </div>
                  ))
                ) : (
                  <div className="h-full flex items-center justify-center text-sm text-zinc-500 italic">
                    No recent execution orders.
                  </div>
                )}
              </div>
            </div>
          </div>

        </div>
      </div>
    </div>
  );
}
