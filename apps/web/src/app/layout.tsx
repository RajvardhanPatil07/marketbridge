import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import MarketShell from "@/components/market-shell";
import { MarketDataProvider } from "@/components/market-data-provider";
import "./globals.css";

const geist = Geist({ subsets: ["latin"], variable: "--font-geist" });
const geistMono = Geist_Mono({ subsets: ["latin"], variable: "--font-mono" });

export const metadata: Metadata = {
  title: { default: "MarketBridge — Markets, intelligence, risk", template: "%s · MarketBridge" },
  description: "Live market intelligence, evidence-aware reference pricing, and advisory risk controls for 24/7 equity perpetuals.",
  robots: { index: false, follow: false },
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en" className={`${geist.variable} ${geistMono.variable}`}><body>
    <div hidden dangerouslySetInnerHTML={{ __html: "<!-- THESIS: Market data and evidence lead; the generic AI-dashboard card wall is refused. OWN-WORLD: graphite terminal surfaces, thin seams, tabular numerals, compact controls, signal blue, financial green/red only. STORY: scan the market, inspect the mark, understand its evidence, act within explicit advisory boundaries. FIRST VIEWPORT: a live ticker and command header frame a table- or chart-led workspace with contextual risk at right. FORM: professional multi-route market terminal; pinned user direction, seed marketbridge-terminal-v1. FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, and DESIGN.md -->" }} />
    <MarketDataProvider><MarketShell>{children}</MarketShell></MarketDataProvider>
  </body></html>;
}
