import Link from "next/link";
import { 
  LayoutDashboard, 
  LineChart, 
  Search, 
  BrainCircuit, 
  ShieldAlert, 
  Zap, 
  Briefcase 
} from "lucide-react";

const navItems = [
  { name: "Dashboard", href: "/dashboard", icon: LayoutDashboard },
  { name: "Markets", href: "/markets", icon: LineChart },
  { name: "Research", href: "/research", icon: Search },
  { name: "AI Council", href: "/ai-council", icon: BrainCircuit },
  { name: "Portfolio", href: "/portfolio", icon: Briefcase },
  { name: "Risk", href: "/risk", icon: ShieldAlert },
  { name: "Execution", href: "/execution", icon: Zap },
];

export function Sidebar() {
  return (
    <div className="w-64 border-r border-zinc-800 bg-zinc-950 flex flex-col h-screen text-zinc-300">
      <div className="p-6 border-b border-zinc-800 flex items-center space-x-3">
        <div className="w-3 h-3 rounded-full bg-blue-500 shadow-[0_0_10px_rgba(59,130,246,0.8)] animate-pulse" />
        <span className="font-bold tracking-widest text-zinc-100">ORION</span>
        <span className="px-2 py-0.5 rounded text-[10px] font-mono bg-red-500/20 text-red-400 border border-red-500/30 uppercase">Live</span>
      </div>
      
      <div className="flex-1 overflow-y-auto py-4">
        <div className="px-4 text-xs font-semibold text-zinc-600 mb-2 uppercase tracking-wider">Workspace</div>
        <nav className="space-y-1 px-2">
          {navItems.map((item) => {
            const Icon = item.icon;
            return (
              <Link
                key={item.name}
                href={item.href}
                className="flex items-center px-3 py-2 text-sm rounded-md transition-colors hover:bg-zinc-800 hover:text-white"
              >
                <Icon className="mr-3 h-4 w-4 text-zinc-500" />
                {item.name}
              </Link>
            );
          })}
        </nav>
      </div>
    </div>
  );
}
