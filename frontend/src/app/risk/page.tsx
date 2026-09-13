"use client";

import { useEffect, useState } from "react";
import { ShieldAlert, AlertTriangle, Crosshair, BarChart2, Shield } from "lucide-react";

export default function RiskPage() {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function loadData() {
      try {
        const res = await fetch("http://127.0.0.1:8000/api/v1/risk");
        if (res.ok) setData(await res.json());
      } catch (err) {
        console.error(err);
      } finally {
        setLoading(false);
      }
    }
    loadData();
  }, []);

  if (loading) return <div className="flex-1 flex items-center justify-center bg-zinc-950 text-zinc-500">Loading risk telemetrics...</div>;

  return (
    <div className="flex-1 overflow-y-auto p-8 bg-zinc-950 text-zinc-100">
      <header className="mb-8 flex justify-between items-end">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-white flex items-center">
            <ShieldAlert className="w-6 h-6 mr-3 text-red-500" /> Risk Management
          </h1>
          <p className="text-sm text-zinc-400 mt-1">Aladdin-class factor decomposition and stress testing</p>
        </div>
        <div className="flex space-x-4">
          <div className="bg-red-500/10 border border-red-500/20 text-red-400 px-4 py-2 rounded-lg text-sm font-bold flex items-center shadow-[0_0_15px_rgba(239,68,68,0.2)]">
            <AlertTriangle className="w-4 h-4 mr-2" /> Global Kill Switch
          </div>
        </div>
      </header>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        
        {/* Left Column: Stress Tests */}
        <div className="lg:col-span-2 space-y-6">
          <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-6">
            <h2 className="text-sm font-bold text-zinc-300 uppercase tracking-wider mb-6 flex items-center">
              <Crosshair className="w-4 h-4 mr-2 text-indigo-500" /> Scenario Stress Testing
            </h2>
            
            <div className="space-y-6">
              {data?.stress_tests?.map((test: any, i: number) => (
                <div key={i} className="bg-zinc-950 border border-zinc-800/80 rounded-lg p-5">
                  <div className="flex justify-between items-start mb-3">
                    <div>
                      <h3 className="font-bold text-white text-base">{test.scenario}</h3>
                      <p className="text-xs text-zinc-500 mt-1">{test.shock_description}</p>
                    </div>
                    <div className="text-right">
                      <div className="text-xl font-bold text-red-400">{test.portfolio_drawdown_pct}%</div>
                      <div className="text-xs text-zinc-500 font-mono">${Math.abs(test.estimated_loss).toLocaleString()}</div>
                    </div>
                  </div>
                  
                  <div className="grid grid-cols-2 gap-4 mt-4 pt-4 border-t border-zinc-800/50">
                    <div>
                      <span className="text-xs font-bold text-zinc-600 block mb-2">Worst Hit Assets</span>
                      <div className="flex flex-wrap gap-2">
                        {test.worst_hit_assets?.map((asset: string, j: number) => (
                          <span key={j} className="text-xs bg-red-500/10 text-red-400 px-2 py-1 rounded">
                            {asset}
                          </span>
                        ))}
                      </div>
                    </div>
                    <div>
                      <span className="text-xs font-bold text-zinc-600 block mb-2">Resilience Factor</span>
                      <p className="text-xs text-zinc-400 leading-relaxed">
                        {test.resilience_factor}
                      </p>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Right Column: Factors & Sources */}
        <div className="lg:col-span-1 space-y-6">
          
          {/* Factor Profile */}
          <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-6">
            <h2 className="text-sm font-bold text-zinc-300 uppercase tracking-wider mb-6 flex items-center">
              <BarChart2 className="w-4 h-4 mr-2 text-blue-500" /> Factor Exposure Map
            </h2>
            <div className="space-y-4">
              {data?.factors?.map((factor: any, i: number) => (
                <div key={i}>
                  <div className="flex justify-between text-xs mb-1">
                    <span className="text-zinc-300 font-medium">{factor.name}</span>
                    <span className="font-mono text-zinc-500">{factor.exposure > 0 ? '+' : ''}{factor.exposure}</span>
                  </div>
                  <div className="w-full bg-zinc-950 rounded-full h-1.5 flex overflow-hidden">
                    {/* Zero line in middle */}
                    <div className="w-1/2 h-full flex justify-end">
                      {factor.exposure < 0 && (
                        <div className="h-full bg-red-400 rounded-l-full" style={{ width: `${Math.min(Math.abs(factor.exposure)*50, 100)}%` }} />
                      )}
                    </div>
                    <div className="w-px h-full bg-zinc-700" />
                    <div className="w-1/2 h-full flex justify-start">
                      {factor.exposure > 0 && (
                        <div className="h-full bg-emerald-400 rounded-r-full" style={{ width: `${Math.min(factor.exposure*50, 100)}%` }} />
                      )}
                    </div>
                  </div>
                  <div className="text-[10px] text-zinc-600 text-right mt-1">
                    Risk Contrib: {factor.risk_contrib_pct}%
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Risk Sources */}
          <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-6">
            <h2 className="text-sm font-bold text-zinc-300 uppercase tracking-wider mb-6 flex items-center">
              <Shield className="w-4 h-4 mr-2 text-amber-500" /> Marginal Risk Sources
            </h2>
            <div className="space-y-3">
              {data?.risk_sources?.map((source: any, i: number) => (
                <div key={i} className="flex items-center">
                  <div className="w-full">
                    <div className="flex justify-between text-xs mb-1">
                      <span className="text-zinc-400">{source.source}</span>
                      <span className="font-bold text-zinc-200">{source.pct}%</span>
                    </div>
                    <div className="w-full bg-zinc-950 rounded-full h-1.5">
                      <div className="bg-amber-500 h-1.5 rounded-full" style={{ width: `${source.pct}%` }} />
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
