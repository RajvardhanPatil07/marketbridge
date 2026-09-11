"use client";

import { useEffect, useMemo, useState } from "react";

const API_BASE = (process.env.NEXT_PUBLIC_API_BASE ?? "").replace(/\/$/, "");

type HistoricalPoint = {
  seconds: number;
  timestamp: string;
  external_price: number;
  oracle_price: number;
  reported_mark: number;
  divergence_bps: number;
  action: string;
  permitted_leverage: number;
  permitted_notional_usd: number;
  reasons: string[];
};

type HistoricalPayload = {
  incident: {
    id: string;
    title: string;
    date: string;
    venue: string;
    summary: string;
    limitations: string[];
    sources: Array<{ title: string; url: string }>;
  };
  proof: {
    data_mode: string;
    decision_engine: string;
    policy_version: string;
    same_policy_function_as_live_gate: boolean;
    hindsight_used_by_decision: boolean;
    claim: string;
  };
  timeline: HistoricalPoint[];
};

type BenchmarkPayload = {
  data_mode: string;
  seed: number;
  cases: number;
  generator: { version: string; claim: string };
  actions: Record<string, number>;
  coverage: Record<string, number>;
  invariants: {
    total_violations: number;
    violations: {
      stale_evidence_accepted: number;
      insufficient_independence_accepted: number;
      halted_market_accepted: number;
      correlated_sources_counted_as_independent: number;
      exit_path_violations: number;
    };
  };
  latency: {
    core_policy_ms: { p50: number; p95: number; p99: number; mean: number };
    in_process_gateway_ms: { p50: number; p95: number; p99: number; mean: number };
    boundary: string;
  };
  economics: {
    llm_calls_in_risk_critical_path: number;
    paid_api_calls_required_by_policy_function: number;
    market_data_license_cost_per_million_decisions_usd: number | null;
    note: string;
  };
};

type PortfolioPayload = {
  data_mode: string;
  inputs_are_editable?: boolean;
  order: {
    symbol: string;
    requested_notional_usd: number;
    requested_leverage: number;
    session: string;
  };
  account?: {
    equity_usd: number;
    existing_position_usd: number;
    portfolio_positions: Array<{ symbol: string; notional_usd: number; sector?: string; correlation_group?: string }>;
  };
  result: {
    action: string;
    permitted_leverage: number;
    permitted_notional_usd: number;
    safe_alternative: {
      available: boolean;
      max_leverage: number;
      max_notional_usd: number;
      message: string;
    };
    portfolio_risk: {
      enabled: boolean;
      method: string;
      breaches: string[];
      before: {
        gross_notional_usd: number;
        single_name_concentration: number;
        sector_concentration: number;
        correlated_concentration: number;
      };
      after_requested: {
        gross_notional_usd: number;
        top_symbol: string | null;
        single_name_concentration: number;
        top_sector: string | null;
        sector_concentration: number;
        top_correlation_group: string | null;
        correlated_concentration: number;
      };
    };
    passport_id: string;
    reasons: string[];
  };
  boundary: string;
};

function money(value: number | null | undefined) {
  if (value == null) return "—";
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 0,
  }).format(value);
}

function percent(value: number | null | undefined, digits = 2) {
  if (value == null) return "—";
  return (value * 100).toFixed(digits) + "%";
}

function ms(value: number | null | undefined) {
  if (value == null) return "—";
  return value.toFixed(value < 1 ? 3 : 2) + " ms";
}

export function ProofLab() {
  const [historical, setHistorical] = useState<HistoricalPayload | null>(null);
  const [benchmark, setBenchmark] = useState<BenchmarkPayload | null>(null);
  const [portfolio, setPortfolio] = useState<PortfolioPayload | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [portfolioSymbol, setPortfolioSymbol] = useState("NVDA");
  const [portfolioNotional, setPortfolioNotional] = useState(10000);
  const [portfolioLeverage, setPortfolioLeverage] = useState(10);
  const [portfolioEquity, setPortfolioEquity] = useState(10000);
  const [portfolioExisting, setPortfolioExisting] = useState(22000);
  const [portfolioBusy, setPortfolioBusy] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    Promise.all([
      fetch(API_BASE + "/v1/proof/historical", { signal: controller.signal, cache: "no-store" }),
      fetch(API_BASE + "/v1/proof/benchmark", { signal: controller.signal, cache: "no-store" }),
      fetch(API_BASE + "/v1/proof/portfolio", { signal: controller.signal, cache: "no-store" }),
    ])
      .then(async ([historicalResponse, benchmarkResponse, portfolioResponse]) => {
        if (!historicalResponse.ok || !benchmarkResponse.ok || !portfolioResponse.ok) {
          throw new Error("One or more proof endpoints are unavailable.");
        }
        const [historicalData, benchmarkData, portfolioData] = await Promise.all([
          historicalResponse.json(),
          benchmarkResponse.json(),
          portfolioResponse.json(),
        ]);
        setHistorical(historicalData);
        setBenchmark(benchmarkData);
        setPortfolio(portfolioData);
      })
      .catch((caught) => {
        if (!controller.signal.aborted) {
          setError(caught instanceof Error ? caught.message : "Proof surfaces unavailable.");
        }
      });
    return () => controller.abort();
  }, []);

  const runPortfolio = async () => {
    setPortfolioBusy(true);
    setError(null);
    try {
      const response = await fetch(API_BASE + "/v1/proof/portfolio", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          symbol: portfolioSymbol,
          requested_notional_usd: portfolioNotional,
          requested_leverage: portfolioLeverage,
          account_equity_usd: portfolioEquity,
          existing_position_usd: portfolioExisting,
        }),
      });
      if (!response.ok) throw new Error(`Portfolio demo failed (${response.status})`);
      setPortfolio(await response.json() as PortfolioPayload);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Portfolio demo failed.");
    } finally {
      setPortfolioBusy(false);
    }
  };

  const incidentSamples = useMemo(() => {
    if (!historical?.timeline.length) return [];
    const points = historical.timeline;
    const wanted = [0, 1, 5, 10, 15, points.length - 1];
    return [...new Set(wanted)]
      .filter((index) => index >= 0 && index < points.length)
      .map((index) => points[index]);
  }, [historical]);

  return (
    <section className="proof-lab">
      <header className="proof-hero">
        <div>
          <span className="v1-eyebrow">STEP 0 · PROVE IT BEFORE THE SYNTHETIC ATTACK</span>
          <h1>Evidence, operating characteristics, and safe alternatives.</h1>
          <p>
            The War Room clearly labels live-derived versus synthetic evidence. This layer adds a published historical
            reconstruction, measured policy/gateway latency, a seeded multi-dimensional policy-regression
            suite, and an editable portfolio-aware pre-trade cap.
          </p>
        </div>
        <div className="proof-badges">
          <span>REAL INCIDENT RECONSTRUCTION</span>
          <span>NO HINDSIGHT IN DECISION</span>
          <span>0 LLM CALLS IN RISK PATH</span>
        </div>
      </header>

      {error && <div className="v1-error">{error}</div>}

      <div className="proof-grid">
        <article className="proof-card proof-incident">
          <div className="v1-card-title">
            <span>HISTORICAL INCIDENT REPLAY</span>
            <b>{historical?.proof.data_mode ?? "LOADING"}</b>
          </div>
          <h2>{historical?.incident.title ?? "Loading published incident…"}</h2>
          <p>{historical?.incident.summary}</p>
          {historical && (
            <>
              <div className="proof-facts">
                <div><span>Venue</span><strong>{historical.incident.venue}</strong></div>
                <div><span>Date</span><strong>{historical.incident.date}</strong></div>
                <div><span>Policy</span><strong>{historical.proof.policy_version}</strong></div>
                <div><span>Same decision function</span><strong>{historical.proof.same_policy_function_as_live_gate ? "YES" : "NO"}</strong></div>
              </div>
              <div className="incident-timeline">
                {incidentSamples.map((point) => (
                  <div key={point.timestamp} className={point.action === "ALLOW" ? "allow" : "block"}>
                    <span>{"T+" + point.seconds + "s"}</span>
                    <strong>{money(point.reported_mark)}</strong>
                    <small>{"external " + money(point.external_price)}</small>
                    <b>{point.divergence_bps.toFixed(0) + " bps"}</b>
                    <em>{point.action.replaceAll("_", " ")}</em>
                  </div>
                ))}
              </div>
              <p className="proof-boundary">{historical.proof.claim}</p>
              <div className="proof-links">
                {historical.incident.sources.map((source) => (
                  <a key={source.url} href={source.url} target="_blank" rel="noreferrer">
                    {source.title} ↗
                  </a>
                ))}
              </div>
            </>
          )}
        </article>

        <article className="proof-card">
          <div className="v1-card-title">
            <span>SEEDED POLICY REGRESSION</span>
            <b>{benchmark ? benchmark.cases + " VARIED CASES" : "MEASURING"}</b>
          </div>
          <h2>Does the safety policy hold across a changing state space?</h2>
          {benchmark ? (
            <>
              <div className="metric-grid">
                <div><span>Invariant violations</span><strong>{benchmark.invariants.total_violations}</strong></div>
                <div><span>Stale accepted</span><strong>{benchmark.invariants.violations.stale_evidence_accepted}</strong></div>
                <div><span>Bad independence accepted</span><strong>{benchmark.invariants.violations.insufficient_independence_accepted}</strong></div>
                <div><span>Exit-path violations</span><strong>{benchmark.invariants.violations.exit_path_violations}</strong></div>
              </div>
              <div className="confusion">
                <div className="confusion-head">ACTION DISTRIBUTION · SEED {benchmark.seed}</div>
                <div><span>ALLOW</span><strong>{benchmark.actions.ALLOW ?? 0}</strong></div>
                <div><span>CAP</span><strong>{benchmark.actions.CAP_LEVERAGE ?? 0}</strong></div>
                <div><span>REVIEW</span><strong>{benchmark.actions.REVIEW ?? 0}</strong></div>
                <div><span>BLOCK</span><strong>{benchmark.actions.BLOCK_NEW_RISK ?? 0}</strong></div>
              </div>
              <div className="latency-row">
                <div><span>Core p50</span><strong>{ms(benchmark.latency.core_policy_ms.p50)}</strong></div>
                <div><span>Core p95</span><strong>{ms(benchmark.latency.core_policy_ms.p95)}</strong></div>
                <div><span>Core p99</span><strong>{ms(benchmark.latency.core_policy_ms.p99)}</strong></div>
                <div><span>Gateway p95</span><strong>{ms(benchmark.latency.in_process_gateway_ms.p95)}</strong></div>
              </div>
              <p className="proof-boundary">
                {benchmark.data_mode}. {benchmark.generator.claim} {benchmark.latency.boundary}
              </p>
              <p className="proof-boundary">
                Coverage: {benchmark.coverage.stale ?? 0} stale · {benchmark.coverage.single_or_zero_source ?? 0} insufficient-source · {benchmark.coverage.large_divergence ?? 0} large-divergence · {benchmark.coverage.portfolio_cases ?? 0} portfolio states.
              </p>
              <a className="proof-json-link" href={API_BASE + "/v1/proof/benchmark?cases=2000&seed=" + benchmark.seed} target="_blank" rel="noreferrer">Open benchmark JSON ↗</a>
            </>
          ) : (
            <p>Generating reproducible varied policy states and measuring the same decision function…</p>
          )}
        </article>

        <article className="proof-card">
          <div className="v1-card-title">
            <span>PORTFOLIO RISK FIREWALL</span>
            <b>{portfolio?.data_mode ?? "LOADING"}</b>
          </div>
          <h2>Market Truth is necessary, not sufficient.</h2>
          <p>
            Even when the price is accepted, the account may already carry too much correlated or
            single-name exposure.
          </p>
          <div className="proof-inputs">
            <label><span>Symbol</span><select value={portfolioSymbol} onChange={(event) => setPortfolioSymbol(event.target.value)}>{["NVDA","TSLA","AAPL","MSFT","AMD"].map((item) => <option key={item}>{item}</option>)}</select></label>
            <label><span>New notional</span><input type="number" min="1" step="500" value={portfolioNotional} onChange={(event) => setPortfolioNotional(Number(event.target.value))}/></label>
            <label><span>Leverage</span><input type="number" min="1" max="100" value={portfolioLeverage} onChange={(event) => setPortfolioLeverage(Number(event.target.value))}/></label>
            <label><span>Equity</span><input type="number" min="1" step="1000" value={portfolioEquity} onChange={(event) => setPortfolioEquity(Number(event.target.value))}/></label>
            <label><span>Existing exposure</span><input type="number" min="0" step="1000" value={portfolioExisting} onChange={(event) => setPortfolioExisting(Number(event.target.value))}/></label>
            <button onClick={runPortfolio} disabled={portfolioBusy}>{portfolioBusy ? "Recomputing…" : "Recompute risk"}</button>
          </div>
          {portfolio && (
            <>
              <div className="order-compare">
                <div>
                  <span>REQUESTED</span>
                  <strong>{portfolio.order.requested_leverage + "× · " + money(portfolio.order.requested_notional_usd)}</strong>
                  <small>{portfolio.order.symbol + " · " + portfolio.order.session}</small>
                </div>
                <div className="safe">
                  <span>SAFE ALTERNATIVE</span>
                  <strong>{portfolio.result.safe_alternative.max_leverage + "× · " + money(portfolio.result.safe_alternative.max_notional_usd)}</strong>
                  <small>{portfolio.result.action.replaceAll("_", " ")}</small>
                </div>
              </div>
              <div className="metric-grid">
                <div>
                  <span>Single name after</span>
                  <strong>{percent(portfolio.result.portfolio_risk.after_requested.single_name_concentration, 1)}</strong>
                </div>
                <div>
                  <span>Sector after</span>
                  <strong>{percent(portfolio.result.portfolio_risk.after_requested.sector_concentration, 1)}</strong>
                </div>
                <div>
                  <span>Risk bucket after</span>
                  <strong>{percent(portfolio.result.portfolio_risk.after_requested.correlated_concentration, 1)}</strong>
                </div>
                <div>
                  <span>Passport</span>
                  <strong className="mono">{portfolio.result.passport_id.slice(0, 14) + "…"}</strong>
                </div>
              </div>
              <div className="reason-strip compact">
                <span>WHY</span>
                {portfolio.result.reasons.map((reason) => (
                  <b key={reason}>{reason.replaceAll("_", " ")}</b>
                ))}
              </div>
              <p className="proof-boundary">{portfolio.boundary}</p>
            </>
          )}
        </article>

        <article className="proof-card">
          <div className="v1-card-title">
            <span>MOCHATRADE HOST INTEGRATION</span>
            <b>REFERENCE FLOW</b>
          </div>
          <h2>One pre-trade call, one short-lived passport.</h2>
          <div className="host-flow">
            <div><span>MOCHATRADE ORDER</span><strong>{portfolio?.order.symbol ?? "SYMBOL"} · {portfolio?.order.requested_leverage ?? "—"}×</strong></div>
            <i>→</i>
            <div><span>POST /risk-check</span><strong>MarketBridge</strong></div>
            <i>→</i>
            <div className="blocked"><span>HOST ACTION</span><strong>CAP / BLOCK</strong></div>
          </div>
          <pre>{"const check = await marketBridgeRiskCheck(order, account, market);\nif (check.action === \"BLOCK_NEW_RISK\") disableSubmit();\nif (check.action === \"CAP_LEVERAGE\") applyCap(check.safe_alternative);\nattachPassport(check.passport_id);"}</pre>
          <p className="proof-boundary">
            This is a reference host integration, not a claim that this repository routes a live Mochatrade
            order. The production boundary remains broker-owned execution.
          </p>
        </article>

        <article className="proof-card">
          <div className="v1-card-title">
            <span>DEPLOYMENT ECONOMICS</span>
            <b>NO MADE-UP DOLLARS</b>
          </div>
          <h2>The risk-critical path does not call an LLM.</h2>
          {benchmark && (
            <div className="metric-grid">
              <div><span>LLM calls / decision</span><strong>{benchmark.economics.llm_calls_in_risk_critical_path}</strong></div>
              <div><span>Paid API calls in policy</span><strong>{benchmark.economics.paid_api_calls_required_by_policy_function}</strong></div>
              <div><span>License $ / 1M</span><strong>DEPLOYMENT-SPECIFIC</strong></div>
              <div><span>Compute</span><strong>MEASURE FROM HOST</strong></div>
            </div>
          )}
          <p className="proof-boundary">{benchmark?.economics.note}</p>
        </article>
      </div>

      <div className="proof-divider">
        <span>THEN RUN THE CONTROLLED ATTACK</span>
      </div>
    </section>
  );
}
