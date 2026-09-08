"""Receipt-ordered core. Synthetic truth and future outcomes never enter this class."""

import hashlib
import json
import math

from .models import PaperAccount, SOURCE_CONFIG, SYMBOLS, SourceState, number, timestamp


class Engine:
    fresh_seconds = 5.0
    stale_seconds = 10.0
    jump_threshold = 0.03
    agreement_tolerance = 0.005

    def __init__(self, symbol: str):
        if symbol not in SYMBOLS:
            raise ValueError(f"Unsupported symbol: {symbol}")
        self.symbol = symbol
        self.initial_price = SYMBOLS[symbol]
        self.clock = 0.0
        self.sources = {key: SourceState(key) for key in SOURCE_CONFIG}
        self.seen: set[str] = set()
        self.last_valid: float | None = None
        self.last_valid_at: float | None = None
        self.stock_anchor: float | None = None
        self.factor_anchor = 480.0
        self.anchor_weights: dict[str, float] = {}
        self.factor = 480.0
        self.comparator = self.initial_price
        self.pending: dict[str, dict] = {}
        self.assessments: list[dict] = []
        self.accepted_count = 0
        self.quarantined_count = 0
        self.first_quarantine_at: float | None = None
        self.recovered_at: float | None = None
        self.recovery_seconds: float | None = None
        self._step_assessments: list[dict] = []
        self.reference_account = PaperAccount(self.initial_price)
        self.baseline_account = PaperAccount(self.initial_price)

    def _assessment(self, event: dict, decision: str, reason: str, pre: float | None) -> None:
        item = {
            "observation_id": str(event.get("id", "unknown")),
            "decision": decision,
            "reason": reason,
            "pre_update_reference": pre,
            "received_at": self.clock,
        }
        self.assessments.append(item)
        self._step_assessments.append(item)
        if decision == "ACCEPT":
            self.accepted_count += 1
        elif decision == "QUARANTINE":
            self.quarantined_count += 1

    def _accept(self, source: SourceState, price: float, event_time: float) -> None:
        source.price, source.event_time = price, event_time
        source.quarantined = False
        source.candidate_price = source.candidate_time = None
        self.pending.pop(source.source_id, None)
        self.stock_anchor = self.last_valid = price
        self.factor_anchor = self.factor
        self.last_valid_at = event_time
        self.anchor_weights = {source.source_id: 1.0}

    def process(self, event: dict) -> None:
        """Process explicit received events; callers must not sort by event time."""
        received = number(event["received_at"])
        if received < self.clock:
            raise ValueError("Receipt order cannot rewind the engine clock")
        self.clock = received
        if event.get("kind") == "timer":
            return
        if event.get("kind") != "observation":
            raise ValueError("The engine accepts only observations and timer events")
        pre = self.last_valid
        identity = str(
            event.get("id") or hashlib.sha256(json.dumps(event, sort_keys=True).encode()).hexdigest()
        )
        if identity in self.seen:
            self._assessment(event, "NONE", "DUPLICATE_IGNORED_ORIGINAL_TIMESTAMP_PRESERVED", pre)
            return
        self.seen.add(identity)
        source_id = event.get("source_id")
        if source_id not in self.sources:
            self._assessment(event, "REJECT", "UNKNOWN_SOURCE", pre)
            return
        source = self.sources[source_id]
        try:
            event_time = number(event["event_time"])
            price = number(event["price"])
            bid, ask = number(event.get("bid", price)), number(event.get("ask", price))
            if price <= 0 or bid <= 0 or ask <= 0 or bid > ask:
                raise ValueError("Malformed price")
            if event_time < 0 or event_time > self.clock:
                raise ValueError("Invalid original timestamp")
            if event.get("symbol", self.symbol) != self.symbol and source_id != "qqq":
                raise ValueError("Wrong instrument")
            if event.get("representation", "USD_SHARE") != "USD_SHARE":
                raise ValueError("Unknown representation")
        except (ValueError, TypeError, KeyError):
            self._assessment(event, "REJECT", "MALFORMED_PRICE_TIMESTAMP_OR_REPRESENTATION", pre)
            return
        if source.latest_seen_time is not None and event_time < source.latest_seen_time:
            self._assessment(event, "REJECT", "LATE_EVENT_CANNOT_REWIND_SOURCE", pre)
            return
        if source.latest_seen_time == event_time:
            self._assessment(event, "NONE", "CACHED_OBSERVATION_TIMESTAMP_UNCHANGED", pre)
            return
        source.latest_seen_time = event_time
        if self.clock - event_time > self.fresh_seconds:
            self._assessment(event, "REJECT", "OBSERVATION_ALREADY_STALE", pre)
            return
        if source_id == "qqq":
            source.price, source.event_time, self.factor = price, event_time, price
            self._assessment(event, "ACCEPT", "FRESH_FACTOR_OBSERVATION", pre)
            return
        if source_id == "iex":
            self.comparator = price
        official = (
            source_id == "auction" and event.get("official_open") is True and event.get("verified") is True
        )
        if source_id == "auction" and not official:
            self._assessment(event, "REJECT", "UNVERIFIED_OFFICIAL_AUCTION", pre)
            return
        if official:
            self._accept(source, price, event_time)
            for candidate_source in list(self.pending):
                state = self.sources[candidate_source]
                state.quarantined = False
                state.candidate_price = state.candidate_time = None
            self.pending.clear()
            self.recovered_at = self.clock
            if self.first_quarantine_at is not None:
                self.recovery_seconds = self.clock - self.first_quarantine_at
            self._assessment(event, "ACCEPT", "VERIFIED_SYNTHETIC_OPENING_AUCTION", pre)
            return
        is_jump = pre is not None and abs(price / pre - 1) > self.jump_threshold
        if not is_jump:
            had_pending = source_id in self.pending
            self._accept(source, price, event_time)
            if had_pending and not self.pending:
                self.recovered_at = self.clock
                if self.first_quarantine_at is not None:
                    self.recovery_seconds = self.clock - self.first_quarantine_at
            self._assessment(event, "ACCEPT", "QUALIFIED_SYNTHETIC_OBSERVATION", pre)
            return
        if self.first_quarantine_at is None:
            self.first_quarantine_at = self.clock
        source.quarantined = True
        source.candidate_price, source.candidate_time = price, event_time
        self.pending[source_id] = {"price": price, "time": event_time, "family": SOURCE_CONFIG[source_id][1]}
        agreement = {
            key: value
            for key, value in self.pending.items()
            if self.clock - value["time"] <= self.fresh_seconds
            and abs(value["price"] / price - 1) <= self.agreement_tolerance
        }
        families = {value["family"] for value in agreement.values()}
        if len(families) >= 2:
            # Equal weight per original family, never per reseller.
            family_prices: dict[str, float] = {}
            for value in agreement.values():
                family_prices[value["family"]] = value["price"]
            accepted_price = math.exp(sum(math.log(p) for p in family_prices.values()) / len(families))
            for key, value in agreement.items():
                self._accept(self.sources[key], value["price"], value["time"])
            self.stock_anchor = self.last_valid = accepted_price
            self.factor_anchor = self.factor
            self.last_valid_at = event_time
            self.anchor_weights = {
                key: 1 / len(families) / sum(v["family"] == value["family"] for v in agreement.values())
                for key, value in agreement.items()
            }
            self.recovered_at = self.clock
            self.recovery_seconds = self.clock - self.first_quarantine_at
            self._assessment(event, "ACCEPT", "INDEPENDENT_FAMILIES_CORROBORATE_REPRICING", pre)
        else:
            self._assessment(event, "QUARANTINE", "LARGE_MOVE_REQUIRES_INDEPENDENT_CORROBORATION", pre)

    def snapshot(self, index: int, seconds: int) -> dict:
        if seconds != self.clock:
            raise ValueError("Snapshot requires the matching explicit timer event")
        age = self.clock - self.last_valid_at if self.last_valid_at is not None else self.clock
        factor_state = self.sources["qqq"]
        factor_fresh = (
            factor_state.event_time is not None and self.clock - factor_state.event_time <= self.fresh_seconds
        )
        reference = self.last_valid
        if reference is not None and factor_fresh:
            reference = self.stock_anchor * self.factor / self.factor_anchor
        reasons = [item["reason"] for item in self._step_assessments]
        if self.last_valid is None or self.pending or age > self.stale_seconds:
            quality, reference = "INSUFFICIENT_EVIDENCE", None
            reasons.append("UNCORROBORATED_JUMP" if self.pending else "NO_FRESH_UNDERLYING_EVIDENCE")
        elif self.recovered_at == self.clock:
            quality = "RECOVERING"
            reasons.append("QUALIFIED_RECOVERY_REANCHORS_STOCK_AND_FACTOR")
        elif age > self.fresh_seconds or not factor_fresh:
            quality = "CAUTION"
            reasons.append("SOURCE_AGE_EXCEEDS_FRESHNESS_POLICY")
        else:
            quality = "QUALIFIED"
        ranks = {"NONE": 0, "ACCEPT": 1, "QUARANTINE": 2, "REJECT": 3}
        assessment = max((a["decision"] for a in self._step_assessments), key=ranks.get, default="NONE")
        if quality == "RECOVERING":
            assessment = "ACCEPT"
        self._step_assessments.clear()
        underlying = [
            s
            for key, s in self.sources.items()
            if key != "qqq"
            and s.event_time is not None
            and not s.quarantined
            and self.clock - s.event_time <= self.fresh_seconds
        ]
        family_count = len({SOURCE_CONFIG[s.source_id][1] for s in underlying})
        source_rows = []
        for source_id, state in self.sources.items():
            if source_id == "reseller" and state.latest_seen_time is None:
                continue
            age_source = self.clock - state.event_time if state.event_time is not None else self.clock
            status = (
                "MISSING"
                if state.event_time is None
                else "FRESH"
                if age_source <= self.fresh_seconds
                else "STALE"
            )
            if state.quarantined:
                status = "QUARANTINED"
            family = SOURCE_CONFIG[source_id][1]
            weight = self.anchor_weights.get(source_id, 0.0) if reference is not None else 0.0
            # A factor is a separate explanatory baseline input, not another stock vote.
            source_rows.append(
                {
                    "id": source_id,
                    "name": SOURCE_CONFIG[source_id][0],
                    "family": family,
                    "price": state.candidate_price if state.quarantined else state.price,
                    "event_time": timestamp(state.candidate_time if state.quarantined else state.event_time)
                    if (state.candidate_time if state.quarantined else state.event_time) is not None
                    else None,
                    "age_seconds": self.clock - state.candidate_time if state.quarantined else age_source,
                    "status": status,
                    "weight": weight,
                }
            )
        equity = self.reference_account.mark(reference)
        baseline_equity = self.baseline_account.mark(self.comparator)
        spread = 0.0025 + age * 0.0005
        allowed = (
            quality in ("QUALIFIED", "CAUTION", "RECOVERING")
            and reference is not None
            and not self.reference_account.liquidated
            and equity is not None
            and equity > 0
        )
        return {
            "index": index,
            "seconds": seconds,
            "timestamp": timestamp(seconds),
            "reference": reference,
            "last_valid": self.last_valid,
            "comparator": self.comparator,
            "factor": self.factor,
            "baseline": self.initial_price * self.factor / 480.0,
            "lower": reference * (1 - spread) if reference is not None else None,
            "upper": reference * (1 + spread) if reference is not None else None,
            "quality": quality,
            "assessment": assessment,
            "reasons": list(dict.fromkeys(reasons)),
            "source_count": family_count,
            "age_seconds": age,
            "sources": source_rows,
            "simulation": {
                "equity": equity,
                "baseline_equity": baseline_equity,
                "new_exposure_allowed": allowed,
                "exposure_limit": (0.5 if quality in ("CAUTION", "RECOVERING") else 1.0) if allowed else 0.0,
                "valuation_status": "RESOLVED" if equity is not None else "UNRESOLVED",
                "reference_liquidated": self.reference_account.liquidated,
                "baseline_liquidated": self.baseline_account.liquidated,
            },
        }
