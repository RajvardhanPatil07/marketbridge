import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "MarketBridge — Evidence-aware risk for 24/7 stock perpetuals",
  description: "Stop weak off-hours price evidence from silently becoming a leveraged liquidation reference.",
  robots: { index: false, follow: false },
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en"><body>{children}</body></html>;
}
