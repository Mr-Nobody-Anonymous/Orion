"use client";

import { useEffect, useState } from "react";
import { Activity, Globe, TrendingUp, TrendingDown, DollarSign, Target, BarChart2 } from "lucide-react";
import { apiUrl } from "@/lib/api";

export default function MarketsPage() {
  const [macro, setMacro] = useState<any>(null);
  const [predictions, setPredictions] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function loadData() {
      try {
        const [macroRes, predRes] = await Promise.all([
          fetch(apiUrl("/dashboard/macro")),
          fetch(apiUrl("/research/prediction"))
        ]);
        if (macroRes.ok) setMacro(await macroRes.json());
        if (predRes.ok) setPredictions(await predRes.json());
      } catch (err) {
        console.error("Failed to fetch market data:", err);
      } finally {
        setLoading(false);
      }
    }
    loadData();
  }, []);

  if (loading) {
    return <div className="flex-1 flex items-center justify-center bg-zinc-950 text-zinc-500">Loading market telemetrics...</div>;
  }

  return (
    <div className="flex-1 overflow-y-auto p-8 bg-zinc-950 text-zinc-100">
      <header className="mb-8 flex justify-between items-end">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-white flex items-center">
            <Globe className="w-6 h-6 mr-3 text-blue-500" /> Global Markets
          </h1>
          <p className="text-sm text-zinc-400 mt-1">Macroeconomic regime and prediction market edge detection</p>
        </div>
        <div className="text-right">
          <div className="text-sm font-medium text-emerald-400 flex items-center justify-end">
            <Activity className="w-4 h-4 mr-1" /> {macro?.regime || "Unknown Regime"}
          </div>
          <div className="text-xs text-zinc-500 mt-1">{macro?.data_source}</div>
        </div>
      </header>

      {/* Macro Indicators */}
      <div className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-6 gap-4 mb-8">
        {macro?.indicators?.map((ind: any, i: number) => (
          <div key={i} className="bg-zinc-900 border border-zinc-800 rounded-xl p-4 shadow-sm">
            <h3 className="text-xs font-medium text-zinc-400 mb-1 line-clamp-1">{ind.name}</h3>
            <div className="text-xl font-bold text-white mb-1">{ind.value}</div>
            <div className={`text-xs font-medium flex items-center ${ind.trend === 'UP' ? 'text-emerald-400' : ind.trend === 'DOWN' ? 'text-red-400' : 'text-zinc-500'}`}>
              {ind.trend === 'UP' ? <TrendingUp className="w-3 h-3 mr-1" /> : ind.trend === 'DOWN' ? <TrendingDown className="w-3 h-3 mr-1" /> : <Activity className="w-3 h-3 mr-1" />}
              {ind.status}
            </div>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Central Banks & Yields */}
        <div className="col-span-1 space-y-8">
          <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-6">
            <h2 className="text-sm font-bold text-zinc-300 uppercase tracking-wider mb-4 flex items-center">
              <DollarSign className="w-4 h-4 mr-2 text-yellow-500" /> Central Banks
            </h2>
            <div className="space-y-4">
              {macro?.central_banks && Object.entries(macro.central_banks).map(([name, data]: [string, any]) => (
                <div key={name} className="flex justify-between items-center pb-3 border-b border-zinc-800 last:border-0 last:pb-0">
                  <div className="uppercase font-bold text-zinc-200">{name}</div>
                  <div className="text-right">
                    <div className="text-lg font-bold text-white">{data.current_rate}</div>
                    <div className="text-xs text-zinc-400">{data.stance || data.orion_stance}</div>
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-6">
            <h2 className="text-sm font-bold text-zinc-300 uppercase tracking-wider mb-4 flex items-center">
              <BarChart2 className="w-4 h-4 mr-2 text-indigo-500" /> US Yield Curve
            </h2>
            <div className="space-y-4">
              <div className="flex justify-between text-sm">
                <span className="text-zinc-400">2-Year Yield</span>
                <span className="font-bold text-white">{macro?.yield_curve?.us_2y}</span>
              </div>
              <div className="flex justify-between text-sm">
                <span className="text-zinc-400">10-Year Yield</span>
                <span className="font-bold text-white">{macro?.yield_curve?.us_10y}</span>
              </div>
              <div className="pt-2 border-t border-zinc-800">
                <div className="text-xs text-zinc-500 mb-1">Spread (2s10s)</div>
                <div className="font-bold text-emerald-400">{macro?.yield_curve?.spread_2s10s_bps}</div>
                <p className="text-xs text-zinc-400 mt-2 italic">{macro?.yield_curve?.signal}</p>
              </div>
            </div>
          </div>
        </div>

        {/* Prediction Markets */}
        <div className="col-span-1 lg:col-span-2">
          <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-6 h-full">
            <div className="flex justify-between items-center mb-6">
              <h2 className="text-sm font-bold text-zinc-300 uppercase tracking-wider flex items-center">
                <Target className="w-4 h-4 mr-2 text-purple-500" /> AI Edge vs Prediction Markets
              </h2>
              <div className="text-xs text-zinc-500 bg-zinc-950 px-3 py-1 rounded-full border border-zinc-800">
                {predictions?.exchange}
              </div>
            </div>

            <div className="space-y-4">
              {predictions?.contracts?.map((contract: any, i: number) => (
                <div key={i} className="bg-zinc-950 border border-zinc-800/50 rounded-lg p-4 hover:border-zinc-700 transition-colors">
                  <div className="flex justify-between items-start mb-3">
                    <h3 className="text-sm font-medium text-white max-w-[75%]">{contract.title}</h3>
                    <span className="text-xs font-mono font-bold bg-purple-500/10 text-purple-400 px-2 py-1 rounded">
                      Edge: {contract.statistical_edge_pct}
                    </span>
                  </div>
                  
                  <div className="grid grid-cols-2 gap-4 mb-4">
                    <div>
                      <div className="text-xs text-zinc-500 mb-1">Market Probability</div>
                      <div className="text-lg font-bold text-zinc-300">{(contract.market_probability * 100).toFixed(1)}%</div>
                    </div>
                    <div>
                      <div className="text-xs text-zinc-500 mb-1">Orion AI Probability</div>
                      <div className="text-lg font-bold text-blue-400">{(contract.orion_probability * 100).toFixed(1)}%</div>
                    </div>
                  </div>
                  
                  <div className="bg-zinc-900 rounded p-3 text-sm">
                    <div className="font-bold text-zinc-300 mb-1 flex items-center">
                      Action: <span className="text-emerald-400 ml-2">{contract.recommendation}</span>
                    </div>
                    <div className="text-zinc-500 text-xs leading-relaxed">
                      <span className="text-zinc-400 font-medium mr-1">Rationale:</span> 
                      {contract.ai_reasoning}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
