import type { Metadata } from "next";
import "./globals.css";
import { Sidebar } from "@/components/layout/Sidebar";
import { WebSocketProvider } from "@/components/providers/WebSocketProvider";

export const metadata: Metadata = {
  title: "Orion Mission Control",
  description: "Institutional Financial Operating System",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark">
      <body className="bg-zinc-950 text-zinc-50 flex h-screen overflow-hidden">
        <WebSocketProvider>
          <Sidebar />
          <main className="flex-1 flex flex-col h-screen overflow-hidden">
            <div className="bg-amber-500/10 border-b border-amber-500/20 px-4 py-1.5 text-xs text-amber-300 text-center font-medium shrink-0 flex items-center justify-center space-x-2">
              <span>⚠️ SIMULATION & RESEARCH MODE — ALL DATA IS SYNTHETIC / FOR RESEARCH PURPOSES ONLY</span>
            </div>
            {children}
          </main>
        </WebSocketProvider>
      </body>
    </html>
  );
}
