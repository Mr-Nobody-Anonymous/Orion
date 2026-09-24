"use client";

import { useEffect, useState } from "react";
import { apiUrl } from "@/lib/api";
import { BrainCircuit, AlertCircle, Bot, Send, Users } from "lucide-react";

export default function AICouncilPage() {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [query, setQuery] = useState("");
  const [deliberating, setDeliberating] = useState(false);
  const [chatHistory, setChatHistory] = useState<any[]>([]);

  useEffect(() => {
    async function loadData() {
      try {
        const res = await fetch(apiUrl("/ai-council/peers"));
        if (res.ok) setData(await res.json());
      } catch (err) {
        console.error(err);
      } finally {
        setLoading(false);
      }
    }
    loadData();
  }, []);

  const handleDeliberate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim() || deliberating) return;

    const userMessage = { role: "user", text: query };
    setChatHistory(prev => [...prev, userMessage]);
    setQuery("");
    setDeliberating(true);

    try {
      const res = await fetch(apiUrl("/ai-council/deliberate"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query: userMessage.text, symbol: "NVDA" })
      });
      if (res.ok) {
        const result = await res.json();
        setChatHistory(prev => [
          ...prev, 
          { role: "council", consensus: result.consensus, insights: result.insights }
        ]);
        // Refresh peer data to get latest insights
        const peersRes = await fetch(apiUrl("/ai-council/peers"));
        if (peersRes.ok) setData(await peersRes.json());
      }
    } catch (err) {
      console.error(err);
      setChatHistory(prev => [...prev, { role: "council", error: "Failed to connect to the AI Council." }]);
    } finally {
      setDeliberating(false);
    }
  };

  if (loading) return <div className="flex-1 flex items-center justify-center bg-zinc-950 text-zinc-500">Connecting to AI Council...</div>;

  return (
    <div className="flex-1 flex overflow-hidden bg-zinc-950 text-zinc-100">
      
      {/* Left Sidebar: Peers & Insights */}
      <div className="w-1/3 border-r border-zinc-800 flex flex-col h-full bg-zinc-900/50">
        <div className="p-6 border-b border-zinc-800">
          <h1 className="text-xl font-bold tracking-tight text-white flex items-center mb-1">
            <Users className="w-5 h-5 mr-2 text-indigo-500" /> AI Council
          </h1>
          <p className="text-xs text-zinc-400">Multi-Agent Deliberation Network</p>
        </div>
        
        <div className="overflow-y-auto flex-1 p-6 space-y-8">
          {/* Peer Status */}
          <div>
            <h2 className="text-xs font-bold text-zinc-500 uppercase tracking-wider mb-3">Active Peers ({data?.available})</h2>
            <div className="space-y-3">
              {data?.peers && Object.entries(data.peers).map(([name, status]: [string, any]) => (
                <div key={name} className="flex items-center justify-between bg-zinc-900 border border-zinc-800 p-3 rounded-lg">
                  <div className="flex items-center">
                    <Bot className="w-4 h-4 mr-3 text-zinc-500" />
                    <span className="font-medium text-sm text-zinc-300">{name}</span>
                  </div>
                  <div className="flex items-center">
                    <div className={`w-2 h-2 rounded-full mr-2 ${status === 'online' ? 'bg-emerald-500' : 'bg-red-500'}`} />
                    <span className="text-xs text-zinc-500">{status}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Recent Insights */}
          <div>
            <h2 className="text-xs font-bold text-zinc-500 uppercase tracking-wider mb-3">Recent Insights</h2>
            <div className="space-y-4">
              {data?.insights?.map((insight: any, i: number) => (
                <div key={i} className="bg-zinc-900 border border-zinc-800 p-4 rounded-lg relative overflow-hidden group">
                  <div className="absolute top-0 left-0 w-1 h-full bg-indigo-500/50 group-hover:bg-indigo-500 transition-colors" />
                  <div className="flex justify-between items-start mb-2">
                    <span className="text-xs font-bold text-indigo-400">{insight.provider}</span>
                    <span className="text-xs font-mono text-zinc-600">{new Date(insight.timestamp).toLocaleTimeString()}</span>
                  </div>
                  <p className="text-sm text-zinc-300 mb-2 leading-relaxed">{insight.content}</p>
                  <div className="flex items-center text-xs font-mono">
                    <span className="text-zinc-500 mr-2">CONFIDENCE:</span>
                    <span className={insight.confidence > 0.7 ? 'text-emerald-400' : 'text-amber-400'}>
                      {(insight.confidence * 100).toFixed(0)}%
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* Right Area: Chat Console */}
      <div className="flex-1 flex flex-col h-full bg-zinc-950">
        <div className="flex-1 overflow-y-auto p-8 space-y-6">
          {chatHistory.length === 0 ? (
            <div className="h-full flex flex-col items-center justify-center text-center max-w-lg mx-auto">
              <BrainCircuit className="w-16 h-16 text-zinc-800 mb-6" />
              <h2 className="text-xl font-bold text-zinc-300 mb-2">Deliberation Console</h2>
              <p className="text-zinc-500 text-sm">
                Submit a thesis or question. The AI Council will asynchronously deliberate across multiple language models, 
                synthesizing their individual insights into a unified consensus.
              </p>
            </div>
          ) : (
            chatHistory.map((msg, i) => (
              <div key={i} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                {msg.role === 'user' ? (
                  <div className="bg-blue-600 text-white rounded-2xl rounded-tr-sm px-5 py-3 max-w-xl shadow-md">
                    {msg.text}
                  </div>
                ) : (
                  <div className="bg-zinc-900 border border-zinc-800 rounded-2xl rounded-tl-sm p-6 w-full max-w-3xl shadow-sm">
                    <div className="flex items-center mb-4">
                      <div className="w-8 h-8 rounded-full bg-indigo-500/20 flex items-center justify-center mr-3">
                        <Users className="w-4 h-4 text-indigo-400" />
                      </div>
                      <span className="font-bold text-indigo-400">Council Consensus</span>
                    </div>
                    
                    {msg.error ? (
                      <div className="text-red-400 flex items-center"><AlertCircle className="w-4 h-4 mr-2" />{msg.error}</div>
                    ) : (
                      <>
                        <div className="prose prose-invert prose-sm max-w-none mb-6">
                          <p className="text-zinc-200 leading-relaxed text-base">{msg.consensus}</p>
                        </div>
                        
                        <div className="border-t border-zinc-800/50 pt-4">
                          <h4 className="text-xs font-bold text-zinc-500 uppercase tracking-wider mb-3">Individual Peer Contributions</h4>
                          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                            {msg.insights?.map((insight: any, j: number) => (
                              <div key={j} className="bg-zinc-950 border border-zinc-800/80 rounded p-3 text-sm">
                                <span className="font-bold text-zinc-400 block mb-1">{insight.provider}</span>
                                <span className="text-zinc-500 line-clamp-3">{insight.content}</span>
                              </div>
                            ))}
                          </div>
                        </div>
                      </>
                    )}
                  </div>
                )}
              </div>
            ))
          )}
          
          {deliberating && (
            <div className="flex justify-start">
              <div className="bg-zinc-900 border border-zinc-800 rounded-2xl rounded-tl-sm p-5 shadow-sm flex items-center space-x-3 text-indigo-400">
                <BrainCircuit className="w-5 h-5 animate-pulse" />
                <span className="text-sm font-medium animate-pulse">Council is deliberating...</span>
              </div>
            </div>
          )}
        </div>

        {/* Input Area */}
        <div className="p-6 bg-zinc-950 border-t border-zinc-900">
          <form onSubmit={handleDeliberate} className="max-w-4xl mx-auto relative">
            <input 
              type="text"
              disabled={deliberating}
              placeholder="E.g., Based on recent inflation data, should we increase exposure to short-duration treasuries?"
              className="w-full bg-zinc-900 border border-zinc-800 rounded-xl pl-5 pr-14 py-4 text-sm text-white placeholder-zinc-500 focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 disabled:opacity-50"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
            <button 
              type="submit"
              disabled={!query.trim() || deliberating}
              className="absolute right-3 top-1/2 -translate-y-1/2 w-10 h-10 bg-indigo-600 hover:bg-indigo-500 disabled:bg-zinc-800 disabled:text-zinc-600 text-white rounded-lg flex items-center justify-center transition-colors"
            >
              <Send className="w-4 h-4" />
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}
