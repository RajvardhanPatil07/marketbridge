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
RISK_CHECKS = Counter("marketbridge_risk_check_total", "Order risk checks.", ("action", "intent"))
RISK_CHECK_LATENCY = Histogram(
    "marketbridge_risk_check_latency_seconds", "Risk-check latency.",
    buckets=(0.0005, 0.001, 0.0025, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 1),
)
ALLOW_TOTAL = Counter("marketbridge_allow_total", "Allowed risk checks.")
CAP_TOTAL = Counter("marketbridge_cap_total", "Capped risk checks.")
BLOCK_TOTAL = Counter("marketbridge_block_total", "Blocked new-risk checks.")
REVIEW_TOTAL = Counter("marketbridge_review_total", "Manual-review risk checks.")
EXPIRED_DECISIONS = Counter("marketbridge_expired_decision_total", "Expired decisions presented for use.")
PASSPORT_CREATED = Counter("marketbridge_passport_created_total", "Safety Passports created.")
PASSPORT_VERIFICATION_FAILURE = Counter(
    "marketbridge_passport_verification_failure_total", "Safety Passport verification failures."
)
REPLAY_MISMATCH = Counter("marketbridge_replay_mismatch_total", "Unexpected deterministic replay mismatches.")
NEW_RISK_REQUESTED = Counter("marketbridge_new_risk_notional_requested", "Requested new-risk USD notional.")
NEW_RISK_PERMITTED = Counter("marketbridge_new_risk_notional_permitted", "Permitted new-risk USD notional.")
NEW_RISK_BLOCKED = Counter("marketbridge_new_risk_notional_blocked", "Blocked new-risk USD notional.")
REFERENCE_CONFIDENCE = Gauge("marketbridge_reference_confidence", "Latest reference confidence, zero to one.")
VENUE_DIVERGENCE = Gauge("marketbridge_venue_divergence_bps", "Latest venue divergence in basis points.")
RECOVERY_PENDING = Gauge("marketbridge_recovery_pending_seconds", "Current recovery-pending duration.")
STATE_TRANSITIONS = Counter("marketbridge_state_transition_total", "Risk recovery state transitions.", ("state",))


def observe_risk_check(response: dict, intent: str, elapsed_seconds: float) -> None:
    action = response["action"]
    RISK_CHECKS.labels(action, intent).inc()
    RISK_CHECK_LATENCY.observe(max(0.0, elapsed_seconds))
    {"ALLOW": ALLOW_TOTAL, "CAP_LEVERAGE": CAP_TOTAL, "BLOCK_NEW_RISK": BLOCK_TOTAL, "REVIEW": REVIEW_TOTAL}[action].inc()
    PASSPORT_CREATED.inc()
    if intent in {"OPEN", "INCREASE"}:
        requested = float(response["requested_notional_usd"])
        permitted = float(response["permitted_notional_usd"])
        NEW_RISK_REQUESTED.inc(requested)
        NEW_RISK_PERMITTED.inc(permitted)
        NEW_RISK_BLOCKED.inc(max(0.0, requested - permitted))
    market = response["market"]
    REFERENCE_CONFIDENCE.set(float(market["confidence"]))
    if market.get("divergence_bps") is not None:
        VENUE_DIVERGENCE.set(float(market["divergence_bps"]))
    recovery = market.get("recovery", {})
    RECOVERY_PENDING.set(float(recovery.get("elapsed_seconds", 0)))


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
