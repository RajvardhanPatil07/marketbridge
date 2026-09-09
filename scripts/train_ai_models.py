"""Train/export dependency-light MarketBridge fair-value and anomaly models.

Default mode generates a deterministic synthetic calibration set so the repository
is runnable without licensed market data. For a serious hackathon evaluation, pass
--csv with historical/research rows created by build_ml_dataset.py and label the
result HISTORICAL_RESEARCH. The runtime reads only the exported JSON bundle.
"""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import random
FAIR_FEATURES = [
    "qqq_return_bps",
    "spy_return_bps",
    "soxx_return_bps",
    "single_source_return_bps",
    "minutes_since_anchor",
    "source_age_ms",
    "provider_count",
    "venue_count",
]
ANOMALY_FEATURES = [
    "mark_divergence_bps",
    "dispersion_bps",
    "source_age_ms",
    "provider_count",
    "venue_count",
    "status_estimated",
]
SYMBOL_BETA = {"NVDA": 1.45, "TSLA": 1.30, "AAPL": 1.05, "MSFT": 1.00, "AMD": 1.35}


@dataclass
class Row:
    symbol: str
    x: dict[str, float]
    y: float


def percentile(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, round((len(ordered) - 1) * q)))
    return float(ordered[index])


def mae(y_true: list[float], y_pred: list[float]) -> float:
    return sum(abs(a - b) for a, b in zip(y_true, y_pred, strict=True)) / max(1, len(y_true))


def standardize(rows: list[dict[str, float]], names: list[str]) -> tuple[list[float], list[float]]:
    means = []
    scales = []
    for name in names:
        values = [row[name] for row in rows]
        mean = sum(values) / len(values)
        variance = sum((value - mean) ** 2 for value in values) / max(1, len(values))
        means.append(mean)
        scales.append(max(math.sqrt(variance), 1e-9))
    return means, scales


def normalized(row: dict[str, float], names: list[str], means: list[float], scales: list[float]) -> list[float]:
    return [(row[name] - means[idx]) / scales[idx] for idx, name in enumerate(names)]


def fit_ridge(rows: list[Row], alpha: float = 0.08, epochs: int = 420, learning_rate: float = 0.025) -> dict:
    xs = [row.x for row in rows]
    ys = [row.y for row in rows]
    means, scales = standardize(xs, FAIR_FEATURES)
    weights = [0.0] * len(FAIR_FEATURES)
    intercept = sum(ys) / len(ys)
    n = len(rows)
    for epoch in range(epochs):
        grad_w = [0.0] * len(weights)
        grad_b = 0.0
        for row in rows:
            z = normalized(row.x, FAIR_FEATURES, means, scales)
            pred = intercept + sum(weight * value for weight, value in zip(weights, z, strict=True))
            error = pred - row.y
            grad_b += error
            for idx, value in enumerate(z):
                grad_w[idx] += error * value
        step = learning_rate / (1.0 + epoch / 6000.0)
        intercept -= step * 2.0 * grad_b / n
        for idx in range(len(weights)):
            gradient = 2.0 * grad_w[idx] / n + 2.0 * alpha * weights[idx]
            weights[idx] -= step * gradient
    return {
        "type": "ridge",
        "feature_names": FAIR_FEATURES,
        "means": means,
        "scales": scales,
        "coefficients": weights,
        "intercept": intercept,
    }


def ridge_predict(model: dict, row: dict[str, float]) -> float:
    z = normalized(row, model["feature_names"], model["means"], model["scales"])
    return model["intercept"] + sum(
        coefficient * value for coefficient, value in zip(model["coefficients"], z, strict=True)
    )


def threshold_candidates(values: list[float], count: int = 12) -> list[float]:
    unique = sorted(set(values))
    if len(unique) <= count:
        return unique[:-1]
    return [percentile(unique, i / (count + 1)) for i in range(1, count + 1)]


def fit_boosting(rows: list[Row], rounds: int = 36, learning_rate: float = 0.08) -> dict:
    base = sum(row.y for row in rows) / len(rows)
    predictions = [base] * len(rows)
    stumps = []
    for _ in range(rounds):
        residuals = [row.y - predictions[idx] for idx, row in enumerate(rows)]
        best = None
        best_loss = float("inf")
        for feature in FAIR_FEATURES:
            values = [row.x[feature] for row in rows]
            for threshold in threshold_candidates(values):
                left_idx = [idx for idx, value in enumerate(values) if value <= threshold]
                right_idx = [idx for idx, value in enumerate(values) if value > threshold]
                if len(left_idx) < 12 or len(right_idx) < 12:
                    continue
                left_value = sum(residuals[idx] for idx in left_idx) / len(left_idx)
                right_value = sum(residuals[idx] for idx in right_idx) / len(right_idx)
                loss = sum((residuals[idx] - left_value) ** 2 for idx in left_idx)
                loss += sum((residuals[idx] - right_value) ** 2 for idx in right_idx)
                if loss < best_loss:
                    best_loss = loss
                    best = (feature, threshold, left_value, right_value)
        if best is None:
            break
        feature, threshold, left_value, right_value = best
        stumps.append({
            "feature": feature,
            "threshold": threshold,
            "left_value": left_value,
            "right_value": right_value,
        })
        for idx, row in enumerate(rows):
            update = left_value if row.x[feature] <= threshold else right_value
            predictions[idx] += learning_rate * update
    return {
        "type": "gradient_boosted_stumps",
        "feature_names": FAIR_FEATURES,
        "base_value": base,
        "learning_rate": learning_rate,
        "stumps": stumps,
    }


def boosting_predict(model: dict, row: dict[str, float]) -> float:
    value = model["base_value"]
    for stump in model["stumps"]:
        update = stump["left_value"] if row[stump["feature"]] <= stump["threshold"] else stump["right_value"]
        value += model["learning_rate"] * update
    return value


def model_predict(model: dict, row: dict[str, float]) -> float:
    if model["type"] == "ridge":
        return ridge_predict(model, row)
    return boosting_predict(model, row)


def synthetic_fair_rows(seed: int = 73, per_symbol: int = 1000) -> list[Row]:
    rng = random.Random(seed)
    rows: list[Row] = []
    for symbol, beta in SYMBOL_BETA.items():
        for index in range(per_symbol):
            # Slowly varying regimes ensure chronological validation is meaningful.
            regime = math.sin(index / 137.0) * 0.18
            qqq = rng.gauss(0, 70 + 40 * abs(regime))
            spy = qqq * 0.78 + rng.gauss(0, 18)
            soxx = qqq * 1.18 + rng.gauss(0, 35)
            minutes = rng.uniform(1, 900)
            age = min(10_000.0, rng.expovariate(1 / 900.0))
            providers = rng.choice([1.0, 1.0, 2.0, 2.0, 3.0])
            venues = rng.choice([1.0, 2.0, 2.0, 3.0])
            single = beta * qqq + 0.22 * (soxx - qqq) + rng.gauss(0, 45 + minutes / 45)
            nonlinear = 0.0018 * qqq * abs(qqq) / 100.0
            time_decay = -math.copysign(min(18.0, minutes / 60.0), qqq) if abs(qqq) > 80 else 0.0
            target = (
                beta * qqq
                + 0.16 * (soxx - qqq)
                + 0.08 * (spy - qqq)
                + 0.14 * single
                + nonlinear
                + time_decay
                + rng.gauss(0, 24 + minutes / 70)
            )
            rows.append(Row(symbol=symbol, x={
                "qqq_return_bps": qqq,
                "spy_return_bps": spy,
                "soxx_return_bps": soxx,
                "single_source_return_bps": single,
                "minutes_since_anchor": minutes,
                "source_age_ms": age,
                "provider_count": providers,
                "venue_count": venues,
            }, y=target))
    return rows


def load_csv_rows(path: Path) -> list[Row]:
    rows: list[Row] = []
    with path.open(newline="", encoding="utf-8") as handle:
        for raw in csv.DictReader(handle):
            symbol = raw["symbol"].upper()
            if symbol not in SYMBOL_BETA:
                continue
            try:
                features = {name: float(raw.get(name) or 0.0) for name in FAIR_FEATURES}
                target = float(raw["target_return_bps"])
            except (TypeError, ValueError, KeyError):
                continue
            rows.append(Row(symbol=symbol, x=features, y=target))
    if not rows:
        raise RuntimeError(f"No usable training rows in {path}")
    return rows


def chronological_split(rows: list[Row]) -> tuple[list[Row], list[Row], list[Row]]:
    train_end = max(1, int(len(rows) * 0.70))
    validation_end = max(train_end + 1, int(len(rows) * 0.85))
    return rows[:train_end], rows[train_end:validation_end], rows[validation_end:]


def train_fair_models(rows: list[Row]) -> tuple[dict, dict]:
    models = {}
    report = {}
    for symbol in SYMBOL_BETA:
        symbol_rows = [row for row in rows if row.symbol == symbol]
        if len(symbol_rows) < 100:
            continue
        train, validation, test = chronological_split(symbol_rows)
        ridge = fit_ridge(train)
        boosted = fit_boosting(train)
        candidates = [ridge, boosted]
        val_scores = {}
        for candidate in candidates:
            predictions = [model_predict(candidate, row.x) for row in validation]
            val_scores[candidate["type"]] = mae([row.y for row in validation], predictions)
        winner = min(candidates, key=lambda candidate: val_scores[candidate["type"]])
        validation_predictions = [model_predict(winner, row.x) for row in validation]
        test_predictions = [model_predict(winner, row.x) for row in test]
        residuals = [abs(row.y - pred) for row, pred in zip(validation, validation_predictions, strict=True)]
        static_predictions = [SYMBOL_BETA[symbol] * row.x["qqq_return_bps"] for row in test]
        winner.update({
            "validation_mae_bps": val_scores[winner["type"]],
            "test_mae_bps": mae([row.y for row in test], test_predictions),
            "residual_p90_bps": percentile(residuals, 0.90),
            "residual_p95_bps": percentile(residuals, 0.95),
            "max_abs_return_bps": 1500.0,
        })
        models[symbol] = winner
        report[symbol] = {
            "rows": len(symbol_rows),
            "selected_model": winner["type"],
            "ridge_validation_mae_bps": round(val_scores["ridge"], 3),
            "boosting_validation_mae_bps": round(val_scores["gradient_boosted_stumps"], 3),
            "selected_test_mae_bps": round(winner["test_mae_bps"], 3),
            "static_beta_test_mae_bps": round(mae([row.y for row in test], static_predictions), 3),
            "residual_p95_bps": round(winner["residual_p95_bps"], 3),
        }
    return models, report


def synthetic_anomaly_rows(seed: int = 144, count: int = 5000) -> tuple[list[dict[str, float]], list[int]]:
    rng = random.Random(seed)
    xs = []
    ys = []
    for _ in range(count):
        anomaly = rng.random() < 0.34
        if anomaly:
            divergence = abs(rng.gauss(520, 330)) + 90
            if rng.random() < 0.55:
                # Critical MarketBridge case: the venue mark is isolated while
                # independent underlying feeds remain fresh and mutually consistent.
                dispersion = abs(rng.gauss(14, 14))
                age = min(5000.0, abs(rng.gauss(550, 550)))
                providers = rng.choice([2.0, 2.0, 3.0])
                venues = rng.choice([2.0, 2.0, 3.0])
                estimated = 0.0
            else:
                # Separate failure regime: stale/concentrated/disagreeing evidence.
                dispersion = abs(rng.gauss(160, 130)) + 30
                age = min(20_000.0, abs(rng.gauss(4200, 3600)))
                providers = rng.choice([1.0, 1.0, 1.0, 2.0])
                venues = rng.choice([1.0, 1.0, 2.0])
                estimated = rng.choice([0.0, 1.0, 1.0])
        else:
            divergence = abs(rng.gauss(22, 22))
            dispersion = abs(rng.gauss(16, 18))
            age = min(8000.0, abs(rng.gauss(650, 700)))
            providers = rng.choice([1.0, 2.0, 2.0, 3.0])
            venues = rng.choice([2.0, 2.0, 3.0])
            estimated = rng.choice([0.0, 0.0, 0.0, 1.0])
        xs.append({
            "mark_divergence_bps": divergence,
            "dispersion_bps": dispersion,
            "source_age_ms": age,
            "provider_count": providers,
            "venue_count": venues,
            "status_estimated": estimated,
        })
        ys.append(1 if anomaly else 0)
    return xs, ys


def fit_logistic(xs: list[dict[str, float]], ys: list[int], epochs: int = 650, lr: float = 0.08) -> dict:
    means, scales = standardize(xs, ANOMALY_FEATURES)
    weights = [0.0] * len(ANOMALY_FEATURES)
    positives = sum(ys)
    prior = min(0.99, max(0.01, positives / len(ys)))
    intercept = math.log(prior / (1 - prior))
    n = len(xs)
    for epoch in range(epochs):
        grad_w = [0.0] * len(weights)
        grad_b = 0.0
        for row, label in zip(xs, ys, strict=True):
            z = normalized(row, ANOMALY_FEATURES, means, scales)
            score = intercept + sum(weight * value for weight, value in zip(weights, z, strict=True))
            probability = 1 / (1 + math.exp(-max(-30.0, min(30.0, score))))
            error = probability - label
            grad_b += error
            for idx, value in enumerate(z):
                grad_w[idx] += error * value
        step = lr / (1 + epoch / 1600)
        intercept -= step * grad_b / n
        for idx in range(len(weights)):
            weights[idx] -= step * (grad_w[idx] / n + 0.002 * weights[idx])
    return {
        "type": "logistic_regression",
        "feature_names": ANOMALY_FEATURES,
        "means": means,
        "scales": scales,
        "coefficients": weights,
        "intercept": intercept,
    }


def logistic_probability(model: dict, row: dict[str, float]) -> float:
    z = normalized(row, model["feature_names"], model["means"], model["scales"])
    score = model["intercept"] + sum(
        weight * value for weight, value in zip(model["coefficients"], z, strict=True)
    )
    return 1 / (1 + math.exp(-max(-30.0, min(30.0, score))))


def classifier_metrics(model: dict, xs: list[dict[str, float]], ys: list[int]) -> dict:
    predictions = [1 if logistic_probability(model, row) >= 0.5 else 0 for row in xs]
    tp = sum(pred == 1 and actual == 1 for pred, actual in zip(predictions, ys, strict=True))
    tn = sum(pred == 0 and actual == 0 for pred, actual in zip(predictions, ys, strict=True))
    fp = sum(pred == 1 and actual == 0 for pred, actual in zip(predictions, ys, strict=True))
    fn = sum(pred == 0 and actual == 1 for pred, actual in zip(predictions, ys, strict=True))
    return {
        "accuracy": (tp + tn) / len(ys),
        "precision": tp / max(1, tp + fp),
        "recall": tp / max(1, tp + fn),
        "false_positive_rate": fp / max(1, fp + tn),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", type=Path, help="Optional historical/research fair-value training CSV")
    parser.add_argument("--data-mode", default=None, help="Explicit provenance label for the exported bundle")
    parser.add_argument("--output", type=Path, default=Path("models/marketbridge-ai-v0.3.json"))
    parser.add_argument("--report", type=Path, default=Path("reports/ml-evaluation.json"))
    args = parser.parse_args()

    if args.csv:
        rows = load_csv_rows(args.csv)
        data_mode = args.data_mode or "HISTORICAL_RESEARCH"
        source_note = str(args.csv)
    else:
        rows = synthetic_fair_rows()
        data_mode = args.data_mode or "SYNTHETIC_CALIBRATION_DEMO"
        source_note = "deterministic synthetic market regimes"

    fair_models, fair_report = train_fair_models(rows)
    anomaly_x, anomaly_y = synthetic_anomaly_rows()
    split = int(len(anomaly_x) * 0.8)
    anomaly_model = fit_logistic(anomaly_x[:split], anomaly_y[:split])
    anomaly_report = classifier_metrics(anomaly_model, anomaly_x[split:], anomaly_y[split:])

    model_version = "marketbridge-ai-v0.3"
    bundle = {
        "schema_version": 1,
        "model_version": model_version,
        "data_mode": data_mode,
        "trained_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "training_source": source_note,
        "fair_value": {
            "feature_names": FAIR_FEATURES,
            "models": fair_models,
            "static_beta_baseline": SYMBOL_BETA,
        },
        "anomaly": {
            "feature_names": ANOMALY_FEATURES,
            "model": anomaly_model,
            "evaluation": anomaly_report,
        },
        "limitations": [
            "Direct independent market consensus always outranks the learned fair-value estimate.",
            "The anomaly model can only tighten risk; it cannot approve a mark or loosen deterministic controls.",
            "The bundled default is synthetic calibration data until retrained with historical research data.",
            "Model confidence is prototype calibration, not a production liquidation guarantee.",
        ],
    }
    report = {
        "model_version": model_version,
        "data_mode": data_mode,
        "training_source": source_note,
        "fair_value": fair_report,
        "anomaly": {key: round(value, 4) for key, value in anomaly_report.items()},
        "claim_boundary": (
            "Metrics are synthetic functional calibration unless data_mode is explicitly HISTORICAL_RESEARCH. "
            "Do not present synthetic MAE as live-market performance."
        ),
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(bundle, indent=2) + "\n", encoding="utf-8")
    args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
