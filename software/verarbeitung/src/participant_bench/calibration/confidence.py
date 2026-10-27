"""Field-correctness calibration, reliability and explicit review gates; never alter values."""

import math

import numpy as np
from scipy.optimize import isotonic_regression, minimize
from scipy.special import expit

from ..evaluation import prf, ratio
from ..schema import TEXT_FIELDS


def reliability(probabilities: list[float], labels: list[int], bins=10) -> dict:
    if len(probabilities) != len(labels) or any(
        not math.isfinite(p) or not 0 <= p <= 1 for p in probabilities
    ):
        raise ValueError("Ungültige Kalibrierungsstichprobe")
    if any(y not in (0, 1) for y in labels):
        raise ValueError("Kalibrierungsziel muss binär sein")
    records = []
    for i in range(bins):
        indices = [j for j, p in enumerate(probabilities) if min(bins - 1, int(p * bins)) == i]
        records.append(
            dict(
                lower=i / bins,
                upper=(i + 1) / bins,
                count=len(indices),
                predicted=sum(probabilities[j] for j in indices) / len(indices) if indices else None,
                observed=sum(labels[j] for j in indices) / len(indices) if indices else None,
            )
        )
    n = len(labels)
    return dict(
        n=n,
        bins=records,
        ece=sum(r["count"] * abs(r["predicted"] - r["observed"]) for r in records if r["count"]) / n
        if n
        else None,
        brier=sum((p - y) ** 2 for p, y in zip(probabilities, labels)) / n if n else None,
        note="Raw-score diagnostics are pseudo-probability comparisons, not proof of probability calibration. Brier includes discrimination and uncertainty.",
    )


def fit(events: list[dict], method="sigmoid", min_samples=50, min_class=5, min_documents=3) -> dict:
    usable = [e for e in events if e["raw_score"] is not None]
    x, y = np.array([e["raw_score"] for e in usable]), np.array([e["correct"] for e in usable])
    if (
        len(usable) < min_samples
        or len({e.get("dependency_group", e["document_id"]) for e in usable}) < min_documents
        or min(sum(y == 0), sum(y == 1)) < min_class
    ):
        return dict(
            status="insufficient_data",
            method=method,
            samples=len(usable),
            correct=int(sum(y)),
            incorrect=int(len(y) - sum(y)),
        )
    if method == "isotonic":
        unique, inverse, counts = np.unique(x, return_inverse=True, return_counts=True)
        means = np.bincount(inverse, weights=y) / counts
        fitted = isotonic_regression(means, weights=counts).x
        return dict(status="fitted", method=method, x=unique.tolist(), y=fitted.tolist(), samples=len(y))
    if method != "sigmoid":
        raise ValueError("Kalibrierungsverfahren muss sigmoid oder isotonic sein")

    # Monotone regularized logistic fit on the raw score, with stable log loss.
    def loss(parameters):
        logits = parameters[0] * x + parameters[1]
        return float(np.mean(np.logaddexp(0, logits) - y * logits) + 1e-4 * parameters[0] ** 2)

    result = minimize(loss, [1.0, 0.0], method="L-BFGS-B", bounds=[(0, None), (None, None)])
    if not result.success or not np.all(np.isfinite(result.x)):
        return dict(status="fit_failed", method=method, samples=len(y))
    return dict(
        status="fitted", method=method, slope=float(result.x[0]), intercept=float(result.x[1]), samples=len(y)
    )


def predict(model: dict, score: float | None) -> float | None:
    if score is None or model.get("status") != "fitted":
        return None
    if model["method"] == "isotonic":
        return float(np.interp(score, model["x"], model["y"]))
    return float(expit(model["slope"] * score + model["intercept"]))


def decide(policy: dict, raw_score: float | None, has_value: bool) -> dict:
    """Apply a frozen rule without reading reference labels."""
    probability = predict(policy["model"], raw_score)
    accepted = (
        has_value
        and policy["status"] == "validated"
        and probability is not None
        and policy["threshold"] is not None
        and probability >= policy["threshold"]
    )
    return dict(
        probability=probability, decision="failed" if not has_value else "accepted" if accepted else "review"
    )


def threshold_curve(events: list[dict], model: dict) -> list[dict]:
    probabilities = [predict(model, e["raw_score"]) for e in events]
    thresholds = sorted({0.0, 1.0, 1.000001} | {p for p in probabilities if p is not None})
    scored = sorted(
        ((p, e["correct"]) for e, p in zip(events, probabilities) if p is not None and e["has_value"]),
        reverse=True,
    )
    curve, index, tp, fp = [], 0, 0, 0
    reference_fields = sum(e.get("matching_source") != "extra" for e in events)
    recoverable_correct = sum(e["correct"] for e in events)
    for threshold in reversed(thresholds):
        while index < len(scored) and scored[index][0] >= threshold:
            tp += scored[index][1]
            fp += 1 - scored[index][1]
            index += 1
        curve.append(
            dict(
                threshold=threshold,
                accepted=index,
                review=len(events) - index,
                review_fraction=1 - index / len(events) if events else None,
                correct_retention_recall=ratio(tp, recoverable_correct),
                **prf(tp, fp, reference_fields - tp),
            )
        )
    return list(reversed(curve))


def tune(development: list[dict], validation: list[dict], options) -> dict:
    result = {}
    for field in TEXT_FIELDS:
        dev = [e for e in development if e["field"] == field]
        val = [e for e in validation if e["field"] == field]
        model = fit(dev, options.calibrator, options.min_samples, options.min_class, options.min_documents)
        curve = threshold_curve(val, model)
        candidates = [
            row
            for row in curve
            if row["accepted"] >= options.min_accepted
            and row["precision"]["value"] >= options.target_precision
        ]
        selected = (
            max(candidates, key=lambda row: (row["accepted"], row["threshold"])) if candidates else None
        )
        result[field] = dict(
            model=model,
            threshold=selected["threshold"] if selected else None,
            status="pending_audit" if selected else "review_only",
            curve=curve,
            event="entire field value correct AND assigned to the reference person row",
            target_precision=options.target_precision,
        )
    return result


def evaluate_policy(
    events: list[dict], policy: dict, *, audit=False, min_accepted=10, min_documents=1
) -> dict:
    decisions, summaries = [], {}
    for field in TEXT_FIELDS:
        config = policy[field]
        samples = [e for e in events if e["field"] == field]
        raw = [e for e in samples if e["raw_score"] is not None]
        probs = [predict(config["model"], e["raw_score"]) for e in raw]
        prospective = [
            e
            for e in samples
            if (p := predict(config["model"], e["raw_score"])) is not None
            and config["threshold"] is not None
            and p >= config["threshold"]
            and e["has_value"]
        ]
        tp, fp = sum(e["correct"] for e in prospective), sum(not e["correct"] for e in prospective)
        raw_diagnostics = reliability([e["raw_score"] for e in raw], [e["correct"] for e in raw])
        calibrated = (
            reliability(probs, [e["correct"] for e in raw])
            if probs and all(p is not None for p in probs)
            else reliability([], [])
        )
        if audit:
            improved = (
                calibrated["brier"] is not None
                and calibrated["brier"] <= raw_diagnostics["brier"]
                and calibrated["ece"] <= raw_diagnostics["ece"]
            )
            config["status"] = (
                "validated"
                if (
                    improved
                    and len(prospective) >= min_accepted
                    and len({e.get("dependency_group", e["document_id"]) for e in prospective})
                    >= min_documents
                    and tp / len(prospective) >= config["target_precision"]
                )
                else "review_only"
            )
            config["calibration_audit"] = dict(
                raw_brier=raw_diagnostics["brier"],
                calibrated_brier=calibrated["brier"],
                raw_ece=raw_diagnostics["ece"],
                calibrated_ece=calibrated["ece"],
            )
        accepted = prospective if config["status"] == "validated" else []
        accepted_ids = {id(e) for e in accepted}
        for event in samples:
            probability = predict(config["model"], event["raw_score"])
            state = (
                "failed" if not event["has_value"] else "accepted" if id(event) in accepted_ids else "review"
            )
            decisions.append(event | {"probability": probability, "decision": state})
        summaries[field] = dict(
            acceptance_status=config["status"],
            n=len(samples),
            prospective_accepted=len(prospective),
            prospective_precision=ratio(tp, tp + fp),
            accepted=len(accepted),
            review=sum(e["has_value"] for e in samples) - len(accepted),
            failed=sum(not e["has_value"] for e in samples),
            raw_score_diagnostics=raw_diagnostics,
            calibrated=calibrated,
        )
    return dict(fields=summaries, decisions=decisions)
