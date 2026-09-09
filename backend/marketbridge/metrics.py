"""Bounded-cardinality Prometheus instrumentation for the shadow pipeline."""

from prometheus_client import Counter, Gauge, Histogram


DECISIONS = Counter(
    "marketbridge_decisions_total",
    "Issued advisory decisions.",
    ("symbol", "status", "risk_state"),
)
DECISION_LATENCY = Histogram(
    "marketbridge_decision_latency_seconds",
    "Receipt-to-decision latency.",
    ("symbol",),
    buckets=(0.0005, 0.001, 0.0025, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 1),
)
EVIDENCE_AGE = Gauge(
    "marketbridge_evidence_max_age_seconds",
    "Oldest evidence item represented in the latest decision.",
    ("symbol",),
)
REFERENCE_AVAILABLE = Gauge(
    "marketbridge_reference_available",
    "Whether the latest decision has a publishable reference.",
    ("symbol",),
)
MARK_DIVERGENCE = Gauge(
    "marketbridge_mark_divergence_basis_points",
    "Absolute venue-mark divergence from the independent reference.",
    ("symbol",),
)


def observe_decision(decision: dict) -> None:
    symbol = decision["symbol"]
    DECISIONS.labels(symbol, decision["status"], decision["risk_state"]).inc()
    DECISION_LATENCY.labels(symbol).observe(max(0.0, float(decision["decision_latency_ms"])) / 1000)
    ages = [float(item["age_seconds"]) for item in decision.get("evidence", [])]
    EVIDENCE_AGE.labels(symbol).set(max(ages, default=0.0))
    REFERENCE_AVAILABLE.labels(symbol).set(decision.get("reference") is not None)
    divergence = decision.get("mark_divergence_bps")
    if divergence is not None:
        MARK_DIVERGENCE.labels(symbol).set(float(divergence))
