"use client";

import { useEffect, useState } from "react";
import { apiUrl } from "@/lib/api";
import { Search, BrainCircuit, LineChart, FileText, Activity, ShieldAlert, Cpu } from "lucide-react";

export default function ResearchPage() {
  const [query, setQuery] = useState("");
  const [symbol, setSymbol] = useState("NVDA");
  const [assetData, setAssetData] = useState<any>(null);
  const [searchData, setSearchData] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  // Fetch specific asset
  useEffect(() => {
    async function fetchAsset() {
      setLoading(true);
      try {
        const res = await fetch(apiUrl(`/research/asset/${symbol}`));
        if (res.ok) setAssetData(await res.json());
      } catch (err) {
        console.error(err);
      } finally {
        setLoading(false);
      }
    }
    fetchAsset();
  }, [symbol]);

  // Handle Search
  useEffect(() => {
    if (!query) return;
    const delayDebounce = setTimeout(async () => {
      try {
        const res = await fetch(apiUrl(`/dashboard/search?q=${query}`));
        if (res.ok) setSearchData(await res.json());
      } catch (err) {
        console.error(err);
      }
    }, 500);
    return () => clearTimeout(delayDebounce);
  }, [query]);

  return (
    <div className="flex-1 flex flex-col h-screen overflow-hidden bg-zinc-950 text-zinc-100">
      {/* Omni-search Header */}
      <header className="p-6 border-b border-zinc-800 bg-zinc-900/50 flex items-center justify-between">
        <div className="relative w-full max-w-xl">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-zinc-500" />
          <input 
            type="text" 
            placeholder="Omni-search equities, crypto, macro, or prediction markets..." 
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            className="w-full bg-zinc-900 border border-zinc-700 rounded-lg pl-10 pr-4 py-2 text-sm text-white placeholder-zinc-500 focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500"
          />
          {query && searchData && searchData.results?.stocks?.length > 0 && (
            <div className="absolute top-full left-0 right-0 mt-2 bg-zinc-800 border border-zinc-700 rounded-lg shadow-xl z-50 p-2">
              <div className="text-xs font-bold text-zinc-500 uppercase tracking-wider mb-2 px-2">Equities</div>
              {searchData.results.stocks.map((stock: any) => (
                <button 
                  key={stock.symbol}
                  onClick={() => { setSymbol(stock.symbol); setQuery(""); setSearchData(null); }}
                  className="w-full text-left px-3 py-2 hover:bg-zinc-700 rounded text-sm flex justify-between items-center"
                >
                  <span className="font-bold">{stock.symbol}</span>
                  <span className="text-zinc-400">{stock.name}</span>
                </button>
              ))}
            </div>
          )}
        </div>
        
        <div className="flex items-center ml-4">
          <div className="flex space-x-1">
            <span className="text-xs bg-zinc-800 text-zinc-400 px-2 py-1 rounded">Alt</span>
            <span className="text-xs bg-zinc-800 text-zinc-400 px-2 py-1 rounded">K</span>
          </div>
        </div>
      </header>

      {/* Main Content Area */}
      {loading ? (
        <div className="flex-1 flex items-center justify-center text-zinc-500">Loading asset intelligence...</div>
      ) : assetData ? (
        <div className="flex-1 overflow-y-auto p-6">
          {/* Asset Header */}
          <div className="flex justify-between items-end mb-8">
            <div>
              <div className="flex items-center space-x-3 mb-2">
                <h1 className="text-3xl font-bold tracking-tight text-white">{assetData.symbol}</h1>
                <span className="text-sm font-medium bg-zinc-800 px-3 py-1 rounded-full text-zinc-300">
                  {assetData.is_crypto ? 'Digital Asset' : 'Equity'}
                </span>
                <span className="text-xs text-zinc-500">{assetData.live_feed}</span>
              </div>
              <p className="text-zinc-400">{assetData.name}</p>
            </div>
            <div className="text-right">
              <div className="text-3xl font-bold text-white mb-1">${assetData.price?.toFixed(2)}</div>
              <div className={`text-lg font-medium ${assetData.change_pct.includes('+') ? 'text-emerald-400' : 'text-red-400'}`}>
                {assetData.change_pct}
              </div>
            </div>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            
            {/* Left Column: AI Forecast & Fundamentals */}
            <div className="lg:col-span-1 space-y-6">
              
              <div className="bg-zinc-900 border border-blue-900/50 rounded-xl p-5 shadow-sm relative overflow-hidden">
                <div className="absolute top-0 right-0 p-4 opacity-10">
                  <BrainCircuit className="w-24 h-24" />
                </div>
                <h2 className="text-sm font-bold text-blue-400 uppercase tracking-wider mb-4 flex items-center relative z-10">
                  <BrainCircuit className="w-4 h-4 mr-2" /> Directional AI Forecast
                </h2>
                <div className="relative z-10">
                  <div className="text-2xl font-bold text-white mb-1">{assetData.ai_forecast?.direction}</div>
                  <div className="text-sm text-zinc-300 mb-4">{assetData.ai_forecast?.confidence}</div>
                  
                  <div className="space-y-3 mb-4">
                    {assetData.ai_forecast?.drivers?.map((driver: string, i: number) => (
                      <div key={i} className="flex items-start text-sm">
                        <div className="w-1.5 h-1.5 rounded-full bg-blue-500 mt-1.5 mr-2 flex-shrink-0" />
                        <span className="text-zinc-400 leading-snug">{driver}</span>
                      </div>
                    ))}
                  </div>
                  
                  <div className="pt-4 border-t border-zinc-800/50 text-xs">
                    <span className="text-zinc-500">Invalidation Level:</span> 
                    <span className="ml-2 font-bold text-red-400">${assetData.ai_forecast?.invalidation_price}</span>
                  </div>
                </div>
              </div>

              <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5 shadow-sm">
                <h2 className="text-sm font-bold text-zinc-300 uppercase tracking-wider mb-4 flex items-center">
                  <FileText className="w-4 h-4 mr-2 text-emerald-500" /> Piotroski F-Score
                </h2>
                <div className="flex items-end justify-between mb-4">
                  <div className="text-3xl font-bold text-emerald-400">
                    {assetData.f_score?.score}<span className="text-xl text-zinc-600">/{assetData.f_score?.max}</span>
                  </div>
                  <div className="text-sm font-medium text-emerald-500 bg-emerald-500/10 px-3 py-1 rounded">
                    {assetData.f_score?.rating}
                  </div>
                </div>
                <div className="space-y-2">
                  {assetData.f_score?.items?.slice(0,5).map((item: any, i: number) => (
                    <div key={i} className="flex justify-between text-xs py-1 border-b border-zinc-800/50 last:border-0">
                      <span className="text-zinc-400 truncate pr-4">{item.label}</span>
                      <span className="font-mono text-zinc-200 whitespace-nowrap">{item.value}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            {/* Right Column: Technicals, Book, Factors */}
            <div className="lg:col-span-2 space-y-6">
              
              {/* Factor Map */}
              <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5 shadow-sm">
                <h2 className="text-sm font-bold text-zinc-300 uppercase tracking-wider mb-4 flex items-center">
                  <ShieldAlert className="w-4 h-4 mr-2 text-amber-500" /> Aladdin Factor Profile
                </h2>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                  {['value', 'momentum', 'quality', 'growth'].map((factor) => {
                    const val = assetData.factors?.[factor] || 0;
                    return (
                      <div key={factor} className="bg-zinc-950 rounded border border-zinc-800/50 p-3">
                        <div className="text-xs text-zinc-500 uppercase tracking-wider mb-1">{factor}</div>
                        <div className={`text-lg font-bold ${val > 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                          {val > 0 ? '+' : ''}{val.toFixed(2)}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>

              {/* Order Book / Options */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5 shadow-sm">
                  <h2 className="text-sm font-bold text-zinc-300 uppercase tracking-wider mb-4 flex items-center">
                    <Activity className="w-4 h-4 mr-2 text-indigo-500" /> Order Book L2
                  </h2>
                  <div className="space-y-1">
                    {/* Asks (Red, descending) */}
                    {assetData.order_book?.asks?.slice().reverse().map((ask: any, i: number) => (
                      <div key={`ask-${i}`} className="flex justify-between text-xs font-mono py-0.5 relative group">
                        <div className="absolute right-0 top-0 bottom-0 bg-red-500/10" style={{width: `${(ask.size/300)*100}%`}}></div>
                        <span className="text-red-400 relative z-10">{ask.price.toFixed(2)}</span>
                        <span className="text-zinc-400 relative z-10">{ask.size.toFixed(1)}</span>
                      </div>
                    ))}
                    
                    <div className="py-2 flex justify-between items-center border-y border-zinc-800 my-2">
                      <span className="text-xs font-bold text-zinc-500">SPREAD</span>
                      <span className="text-sm font-mono font-bold text-white">${assetData.order_book?.spread.toFixed(2)}</span>
                    </div>

                    {/* Bids (Green, descending) */}
                    {assetData.order_book?.bids?.map((bid: any, i: number) => (
                      <div key={`bid-${i}`} className="flex justify-between text-xs font-mono py-0.5 relative group">
                        <div className="absolute right-0 top-0 bottom-0 bg-emerald-500/10" style={{width: `${(bid.size/300)*100}%`}}></div>
                        <span className="text-emerald-400 relative z-10">{bid.price.toFixed(2)}</span>
                        <span className="text-zinc-400 relative z-10">{bid.size.toFixed(1)}</span>
                      </div>
                    ))}
                  </div>
                </div>

                <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5 shadow-sm">
                  <h2 className="text-sm font-bold text-zinc-300 uppercase tracking-wider mb-4 flex items-center">
                    <LineChart className="w-4 h-4 mr-2 text-purple-500" /> Options Chain
                  </h2>
                  <div className="flex justify-between text-xs text-zinc-500 mb-3 border-b border-zinc-800 pb-2">
                    <span>CALLS (Bid)</span>
                    <span>STRIKE</span>
                    <span>PUTS (Ask)</span>
                  </div>
                  <div className="space-y-2">
                    {assetData.options?.chain?.map((opt: any, i: number) => (
                      <div key={i} className="flex justify-between text-xs font-mono py-1">
                        <span className="text-emerald-400">{opt.call_bid.toFixed(2)}</span>
                        <span className="font-bold text-white bg-zinc-800 px-2 rounded">{opt.strike.toFixed(1)}</span>
                        <span className="text-red-400">{opt.put_ask.toFixed(2)}</span>
                      </div>
                    ))}
                  </div>
                  <div className="mt-4 pt-4 border-t border-zinc-800 text-xs flex justify-between">
                    <span className="text-zinc-500">ATM Implied Volatility</span>
                    <span className="font-bold text-zinc-300">{assetData.options?.atm_iv}</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      ) : (
        <div className="flex-1 flex items-center justify-center text-zinc-500">No asset data found.</div>
      )}
    </div>
  );
}
