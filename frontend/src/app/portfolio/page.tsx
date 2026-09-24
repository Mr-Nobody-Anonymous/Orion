"use client";

import { useEffect, useState } from "react";
import { Briefcase, TrendingUp, TrendingDown, PieChart, BarChart, Activity } from "lucide-react";
import { apiUrl } from "@/lib/api";

export default function PortfolioPage() {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function loadData() {
      try {
        const res = await fetch(apiUrl("/portfolio"));
        if (res.ok) setData(await res.json());
      } catch (err) {
        console.error(err);
      } finally {
        setLoading(false);
      }
    }
    loadData();
  }, []);

  if (loading) return <div className="flex-1 flex items-center justify-center bg-zinc-950 text-zinc-500">Loading portfolio structure...</div>;

  const pnlIsPositive = data?.portfolio?.today_pnl >= 0;

  return (
    <div className="flex-1 overflow-y-auto p-8 bg-zinc-950 text-zinc-100">
      <header className="mb-8 flex justify-between items-end">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-white flex items-center">
            <Briefcase className="w-6 h-6 mr-3 text-emerald-500" /> Portfolio Manager
          </h1>
          <p className="text-sm text-zinc-400 mt-1">Hierarchical exposure and performance attribution</p>
        </div>
        <div className="text-right">
          <div className="text-sm font-medium text-emerald-400 flex items-center justify-end">
            Score: {data?.portfolio?.risk_score}
          </div>
        </div>
      </header>

      {/* Top Metrics */}
      <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-4 mb-8">
        <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-4">
          <h3 className="text-xs font-medium text-zinc-400 mb-1">Total Value</h3>
          <div className="text-lg font-bold text-white">${data?.portfolio?.total_value.toLocaleString(undefined, {minimumFractionDigits: 2})}</div>
        </div>
        <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-4">
          <h3 className="text-xs font-medium text-zinc-400 mb-1">Today's PnL</h3>
          <div className={`text-lg font-bold flex items-center ${pnlIsPositive ? 'text-emerald-400' : 'text-red-400'}`}>
            {pnlIsPositive ? '+' : ''}${data?.portfolio?.today_pnl.toLocaleString()} 
            <span className="text-xs ml-2 opacity-80">({data?.portfolio?.today_pnl_pct})</span>
          </div>
        </div>
        <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-4">
          <h3 className="text-xs font-medium text-zinc-400 mb-1">Total Return</h3>
          <div className="text-lg font-bold text-emerald-400">{data?.portfolio?.total_return_pct}</div>
        </div>
        <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-4">
          <h3 className="text-xs font-medium text-zinc-400 mb-1">Sharpe Ratio</h3>
          <div className="text-lg font-bold text-blue-400">{data?.portfolio?.sharpe_ratio}</div>
        </div>
        <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-4">
          <h3 className="text-xs font-medium text-zinc-400 mb-1">Sortino Ratio</h3>
          <div className="text-lg font-bold text-blue-400">{data?.portfolio?.sortino_ratio}</div>
        </div>
        <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-4">
          <h3 className="text-xs font-medium text-zinc-400 mb-1">Volatility (Ann)</h3>
          <div className="text-lg font-bold text-amber-400">{data?.portfolio?.volatility_ann_pct}%</div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        
        {/* Left Column: Exposure Tree */}
        <div className="lg:col-span-2">
          <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-6 h-full">
            <h2 className="text-sm font-bold text-zinc-300 uppercase tracking-wider mb-6 flex items-center">
              <PieChart className="w-4 h-4 mr-2 text-emerald-500" /> Allocation Tree
            </h2>
            
            <div className="space-y-4 font-mono text-sm">
              <div className="flex items-center text-zinc-300 font-bold border-b border-zinc-800 pb-2">
                <div className="w-4 h-4 bg-emerald-500 rounded-sm mr-3" />
                {data?.exposure_tree?.name}
              </div>
              
              <div className="pl-6 space-y-4">
                {data?.exposure_tree?.children?.map((group: any, i: number) => (
                  <div key={i}>
                    <div className="flex items-center text-zinc-400 font-bold mb-2">
                      <div className="w-3 h-3 bg-zinc-700 rounded-sm mr-3" />
                      {group.name}
                    </div>
                    <div className="pl-6 space-y-2">
                      {group.children?.map((leaf: any, j: number) => (
                        <div key={j} className="flex justify-between items-center group/leaf">
                          <div className="flex items-center text-zinc-500">
                            <div className="w-1.5 h-1.5 bg-zinc-600 rounded-full mr-3" />
                            <span className="group-hover/leaf:text-zinc-300 transition-colors">{leaf.name}</span>
                          </div>
                          <span className="text-xs text-zinc-600 font-sans">{leaf.detail}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>

        {/* Right Column: Performance Breakdown */}
        <div className="lg:col-span-1 space-y-6">
          <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-6">
            <h2 className="text-sm font-bold text-zinc-300 uppercase tracking-wider mb-4 flex items-center">
              <BarChart className="w-4 h-4 mr-2 text-blue-500" /> Drawdown Profile
            </h2>
            <div className="space-y-4">
              <div>
                <div className="flex justify-between text-xs text-zinc-400 mb-1">
                  <span>Current Drawdown</span>
                  <span>-1.2%</span>
                </div>
                <div className="w-full bg-zinc-800 rounded-full h-1.5">
                  <div className="bg-red-500 h-1.5 rounded-full" style={{ width: '1.2%' }}></div>
                </div>
              </div>
              <div>
                <div className="flex justify-between text-xs text-zinc-400 mb-1">
                  <span>Max Historical Drawdown</span>
                  <span>{data?.portfolio?.max_drawdown_pct}%</span>
                </div>
                <div className="w-full bg-zinc-800 rounded-full h-1.5">
                  <div className="bg-red-900 h-1.5 rounded-full" style={{ width: `${Math.abs(data?.portfolio?.max_drawdown_pct || 0)}%` }}></div>
                </div>
              </div>
            </div>
          </div>
          
          <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-6">
            <h2 className="text-sm font-bold text-zinc-300 uppercase tracking-wider mb-4 flex items-center">
              <Activity className="w-4 h-4 mr-2 text-indigo-500" /> Rebalancing Engine
            </h2>
            <div className="text-sm text-zinc-400 mb-4">
              Continuous autonomous reconciliation is active. Tolerances are within target ranges.
            </div>
            <button className="w-full py-2 bg-zinc-800 hover:bg-zinc-700 text-zinc-300 rounded text-sm font-medium transition-colors">
              Force Rebalance Check
            </button>
          </div>
        </div>

      </div>
    </div>
  );
}
