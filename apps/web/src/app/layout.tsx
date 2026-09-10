import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import MarketShell from "@/components/market-shell";
import { MarketDataProvider } from "@/components/market-data-provider";
import "./globals.css";

const geist = Geist({ subsets: ["latin"], variable: "--font-geist" });
const geistMono = Geist_Mono({ subsets: ["latin"], variable: "--font-mono" });

export const metadata: Metadata = {
  title: { default: "MarketBridge — Verify the market before leverage acts", template: "%s · MarketBridge" },
  description: "Free-first market safety infrastructure for 24/7 equity perpetuals: Market Truth, deterministic risk gating, Safety Passports and replay.",
  robots: { index: false, follow: false },
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en" className={`${geist.variable} ${geistMono.variable}`}><body>
    <MarketDataProvider><MarketShell>{children}</MarketShell></MarketDataProvider>
  </body></html>;
}
