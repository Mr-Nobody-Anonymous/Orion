import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import { Sidebar } from "@/components/layout/Sidebar";
import { WebSocketProvider } from "@/components/providers/WebSocketProvider";

const inter = Inter({ subsets: ["latin"] });

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
      <body className={`${inter.className} bg-zinc-950 text-zinc-50 flex h-screen overflow-hidden`}>
        <WebSocketProvider>
          <Sidebar />
          <main className="flex-1 flex flex-col h-screen overflow-hidden">
            {children}
          </main>
        </WebSocketProvider>
      </body>
    </html>
  );
}
