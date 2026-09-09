"""Dependency-light ML inference for MarketBridge.

The hot path intentionally does not depend on scikit-learn. Training scripts export
small JSON model bundles that can be evaluated with the Python standard library.
This keeps deployment deterministic while still allowing learned fair-value and
anomaly models to be retrained offline.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import math
import os
from pathlib import Path
from typing import Mapping

FAIR_VALUE_FEATURES = (
    "qqq_return_bps",
    "spy_return_bps",
    "soxx_return_bps",
    "single_source_return_bps",
    "minutes_since_anchor",
    "source_age_ms",
    "provider_count",
    "venue_count",
)

ANOMALY_FEATURES = (
    "mark_divergence_bps",
    "dispersion_bps",
    "source_age_ms",
    "provider_count",
    "venue_count",
    "status_estimated",
)


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _sigmoid(value: float) -> float:
    if value >= 0:
        z = math.exp(-value)
        return 1.0 / (1.0 + z)
    z = math.exp(value)
    return z / (1.0 + z)


@dataclass(frozen=True)
class FairValuePrediction:
    predicted_return_bps: float
    predicted_reference: float
    confidence: float
    band_bps: float
    model_type: str
    model_version: str
    data_mode: str
    top_factors: list[dict]


class JsonModelBundle:
    """Evaluate an exported MarketBridge AI model bundle."""

    def __init__(self, payload: dict):
        self.payload = payload
        self.model_version = str(payload.get("model_version", "unknown"))
        self.data_mode = str(payload.get("data_mode", "UNKNOWN"))
        self.fair_value = payload.get("fair_value", {})
        self.anomaly = payload.get("anomaly", {})

    @classmethod
    def load(cls, path: Path) -> "JsonModelBundle":
        return cls(json.loads(path.read_text(encoding="utf-8")))

    def status(self) -> dict:
        fair_models = self.fair_value.get("models", {})
        return {
            "enabled": bool(fair_models),
            "model_version": self.model_version,
            "data_mode": self.data_mode,
            "symbols": sorted(fair_models),
            "fair_value_model_types": {
                symbol: model.get("type", "unknown") for symbol, model in fair_models.items()
            },
            "anomaly_model_type": self.anomaly.get("model", {}).get("type"),
            "limitations": self.payload.get("limitations", []),
        }

    @staticmethod
    def _ridge_predict(model: dict, features: Mapping[str, float]) -> tuple[float, list[dict]]:
        names = model["feature_names"]
        means = model["means"]
        scales = model["scales"]
        coefficients = model["coefficients"]
        value = float(model["intercept"])
        contributions: list[tuple[str, float]] = []
        for idx, name in enumerate(names):
            scale = float(scales[idx]) or 1.0
            normalized = (float(features.get(name, 0.0)) - float(means[idx])) / scale
            contribution = normalized * float(coefficients[idx])
            value += contribution
            contributions.append((name, contribution))
        top = [
            {"feature": name, "contribution_bps": round(contribution, 2)}
            for name, contribution in sorted(contributions, key=lambda item: abs(item[1]), reverse=True)[:4]
        ]
        return value, top

    @staticmethod
    def _boosted_predict(model: dict, features: Mapping[str, float]) -> tuple[float, list[dict]]:
        prediction = float(model.get("base_value", 0.0))
        learning_rate = float(model.get("learning_rate", 0.1))
        contributions: dict[str, float] = {}
        for stump in model.get("stumps", []):
            feature = str(stump["feature"])
            raw = float(features.get(feature, 0.0))
            branch = float(stump["left_value"] if raw <= float(stump["threshold"]) else stump["right_value"])
            contribution = learning_rate * branch
            prediction += contribution
            contributions[feature] = contributions.get(feature, 0.0) + contribution
        top = [
            {"feature": name, "contribution_bps": round(contribution, 2)}
            for name, contribution in sorted(contributions.items(), key=lambda item: abs(item[1]), reverse=True)[:4]
        ]
        return prediction, top

    def predict_fair_value(
        self,
        symbol: str,
        anchor_price: float,
        features: Mapping[str, float],
    ) -> FairValuePrediction | None:
        model = self.fair_value.get("models", {}).get(symbol)
        if not model or not math.isfinite(anchor_price) or anchor_price <= 0:
            return None

        model_type = str(model.get("type", ""))
        if model_type == "ridge":
            predicted_bps, top = self._ridge_predict(model, features)
        elif model_type == "gradient_boosted_stumps":
            predicted_bps, top = self._boosted_predict(model, features)
        else:
            return None

        # Prevent a learned fallback from creating an absurd mark when features are
        # outside the training regime. Hard deterministic guards still sit after it.
        max_abs_return_bps = float(model.get("max_abs_return_bps", 1500.0))
        predicted_bps = _clamp(predicted_bps, -max_abs_return_bps, max_abs_return_bps)
        predicted_reference = anchor_price * math.exp(predicted_bps / 10_000)

        validation_mae = float(model.get("validation_mae_bps", 100.0))
        residual_p95 = float(model.get("residual_p95_bps", max(150.0, validation_mae * 2)))
        freshness_penalty = min(16.0, float(features.get("source_age_ms", 0.0)) / 1000.0 * 1.5)
        independence_bonus = min(8.0, float(features.get("provider_count", 0.0)) * 2.0)
        confidence = 78.0 - min(30.0, validation_mae / 5.0) - freshness_penalty + independence_bonus
        if self.data_mode.startswith("SYNTHETIC"):
            confidence = min(confidence, 68.0)
        confidence = _clamp(confidence, 35.0, 78.0)
        band_bps = _clamp(residual_p95, 75.0, 500.0)

        return FairValuePrediction(
            predicted_return_bps=predicted_bps,
            predicted_reference=predicted_reference,
            confidence=confidence,
            band_bps=band_bps,
            model_type=model_type,
            model_version=self.model_version,
            data_mode=self.data_mode,
            top_factors=top,
        )

    def anomaly_probability(self, features: Mapping[str, float]) -> tuple[float | None, list[dict]]:
        model = self.anomaly.get("model", {})
        if model.get("type") != "logistic_regression":
            return None, []
        names = model["feature_names"]
        means = model["means"]
        scales = model["scales"]
        coefficients = model["coefficients"]
        score = float(model["intercept"])
        contributions: list[tuple[str, float]] = []
        for idx, name in enumerate(names):
            scale = float(scales[idx]) or 1.0
            normalized = (float(features.get(name, 0.0)) - float(means[idx])) / scale
            contribution = normalized * float(coefficients[idx])
            score += contribution
            contributions.append((name, contribution))
        probability = _clamp(_sigmoid(score), 0.0, 1.0)
        top = [
            {"feature": name, "logit_contribution": round(contribution, 3)}
            for name, contribution in sorted(contributions, key=lambda item: abs(item[1]), reverse=True)[:4]
        ]
        return probability, top


class MarketBridgeAI:
    """Safe wrapper around a JSON model bundle with graceful fallback."""

    def __init__(self, bundle: JsonModelBundle | None):
        self.bundle = bundle

    @classmethod
    def from_environment(cls) -> "MarketBridgeAI":
        configured = os.environ.get("MARKETBRIDGE_AI_MODEL")
        default = Path(__file__).resolve().parents[2] / "models" / "marketbridge-ai-v0.3.json"
        path = Path(configured).expanduser().resolve() if configured else default
        try:
            return cls(JsonModelBundle.load(path))
        except (OSError, ValueError, json.JSONDecodeError, KeyError, TypeError):
            return cls(None)

    def status(self) -> dict:
        if not self.bundle:
            return {
                "enabled": False,
                "model_version": None,
                "data_mode": None,
                "symbols": [],
                "fair_value_model_types": {},
                "anomaly_model_type": None,
                "limitations": ["No valid MARKETBRIDGE_AI_MODEL bundle is loaded."],
            }
        return self.bundle.status()

    def predict_fair_value(
        self,
        symbol: str,
        anchor_price: float,
        features: Mapping[str, float],
    ) -> FairValuePrediction | None:
        if not self.bundle:
            return None
        return self.bundle.predict_fair_value(symbol, anchor_price, features)

    def anomaly_probability(self, features: Mapping[str, float]) -> tuple[float | None, list[dict]]:
        if not self.bundle:
            return None, []
        return self.bundle.anomaly_probability(features)
