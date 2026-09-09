# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

Market operators, risk teams, quantitative researchers, and technically sophisticated traders who need to inspect live equity-perpetual reference quality, compare venue marks, understand evidence provenance, and act on paper-trading or risk-policy decisions from one dense interface.

## Product Purpose

MarketBridge is a unified market-intelligence and advisory risk platform for 24/7 equity perpetuals. It combines live and research market data, professional financial charts, market discovery, portfolio-style exposure views, evidence-aware reference pricing, deterministic risk controls, and a compact learned-model intelligence layer. Success means users can quickly distinguish a qualified reference from an estimate or unavailable mark and understand the evidence and risk implications behind that state.

## Positioning

MarketBridge's distinctive mechanism is proof-carrying reference pricing: direct independent consensus outranks learned estimation, every decision exposes evidence quality and provenance, and AI may tighten but never loosen deterministic risk policy.

## Operating Context

The primary operating scene is a desktop or laptop financial terminal used during live monitoring, incident review, and scenario replay. Users scan dense market tables, charts, provider health, venue divergence, latency, watchlists, and exposure controls. Tablet and mobile experiences must preserve the price, chart, core statistics, watchlist, risk state, and primary actions while reducing secondary panels.

## Capabilities and Constraints

- Existing Python/FastAPI endpoints provide health, live research snapshots, a shadow-oracle stream and snapshot, synthetic scenario replays, evaluation results, incident reconstruction, ML status, and signed Mochatrade market ingestion.
- Alpaca and Databento credentials remain backend-only. Yahoo is display/research data and is not oracle-eligible. Hyperliquid/Mochatrade marks are comparison marks, not self-validating evidence.
- Direct independent consensus is highest trust. Learned estimates remain `ESTIMATED`, cannot create source independence, cannot become a trusted anchor, and cannot relax deterministic restrictions.
- Current trading behavior is advisory and paper/simulator oriented. The interface must not imply live order execution where no supported backend order API exists.
- Synthetic and reconstructed data must be labeled honestly and must not be presented as measured historical performance.
- Preserve the existing static Next.js export and same-origin FastAPI hosting model unless a future deployment decision changes it.

## Brand Commitments

- Product name: MarketBridge.
- The product must feel like a professional financial terminal first and an AI product second.
- Voice is concise, sober, precise, and evidence-led. Avoid hype, generic AI claims, decorative finance tropes, or casino-like presentation.
- CoinMarketCap, TradingView, Webull, and Robinhood are craft and information-architecture references only; no proprietary brand assets, exact layouts, or copied styling.

## Evidence on Hand

- Live and shadow decision APIs in `backend/marketbridge/api.py`.
- Typed frontend data contracts in `apps/web/src/lib/types.ts`.
- Synthetic scenario and evaluation fixtures, with explicit claim boundaries.
- Historical incident reconstruction and cited sources.
- Checked-in ML model provenance and evaluation artifacts; these are synthetic unless separately retrained and labeled as historical research.
- No verified brokerage order-entry endpoint or real portfolio ledger is currently present; future UI must show those integrations as unavailable rather than fabricate positions or fills.

## Product Principles

1. Data, state, and evidence lead; AI explains and qualifies.
2. Uncertainty is visible and operationally actionable.
3. Never invent live prices, portfolio holdings, execution capability, or source independence.
4. Dense information remains calm through hierarchy, alignment, and restrained interaction.
5. Security boundaries and provenance remain legible without exposing secrets.

## Accessibility & Inclusion

Keyboard navigation, visible focus states, semantic tables and controls, sufficient contrast, reduced-motion support, and non-color status cues are required. Positive/negative color is reserved for financial movement and paired with signs or labels.
