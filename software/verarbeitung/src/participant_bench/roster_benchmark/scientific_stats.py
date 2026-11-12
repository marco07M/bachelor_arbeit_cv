"""Cluster bootstrap of pooled field counters; never bootstrap individual fields or average course F1."""

from collections import Counter

import numpy as np

from .metrics import empty_counts, scores

METRICS = ("exact_recall", "exact_f1", "soft_f1")


def pooled(counts):
    total = empty_counts()
    for count in counts:
        total.update({key: count.get(key, 0) for key in total})
    return scores(total)


def cluster_bootstrap(left, right=None, *, seed=42, resamples=2000, minimum_groups=10, eligible=True):
    """Percentile 95% intervals; paired differences use the SAME sampled cluster indices.

    Inputs contain one counter vector per independent group. Duplicate courses in
    a group have already been summed. Missing groups are not silently intersected.
    Differences are right minus left, in percentage points.
    """
    if not 200 <= resamples <= 20000 or minimum_groups < 2:
        raise ValueError("Bootstrap benötigt 200–20000 Wiederholungen und mindestens zwei Gruppen")
    if right is not None and set(left) != set(right):
        return dict(
            status="unpaired_groups",
            groups=0,
            intervals={},
            missing_left=sorted(set(right) - set(left)),
            missing_right=sorted(set(left) - set(right)),
        )
    groups = sorted(left)
    a, b = pooled(left.values()), pooled(right.values()) if right is not None else None
    estimates = {
        key: (100 * (b[key] - a[key]) if a[key] is not None and b[key] is not None else None)
        if b is not None
        else a[key]
        for key in METRICS
    }
    result = dict(
        status="estimated",
        groups=len(groups),
        resamples=resamples,
        seed=seed,
        confidence_level=0.95,
        method="cluster_percentile",
        paired=right is not None,
        unit="percentage_points" if right is not None else "fraction",
        estimates=estimates,
        intervals={key: dict(low=None, high=None, valid_resamples=0) for key in METRICS},
    )
    if right is not None and any(
        left[g].get("reference_fields", 0) != right[g].get("reference_fields", 0) for g in groups
    ):
        raise ValueError("Gepaarte Gruppen müssen dieselben Referenznenner besitzen")
    if len(groups) < minimum_groups:
        result["status"] = "insufficient_groups"
        return result
    if not eligible:
        result["status"] = "unverified_grouping_or_mixed_phases"
        return result
    keys = list(empty_counts())
    x = np.array([[left[g].get(k, 0) for k in keys] for g in groups], dtype=float)
    y = (
        np.array([[right[g].get(k, 0) for k in keys] for g in groups], dtype=float)
        if right is not None
        else None
    )
    distributions = {key: [] for key in METRICS}
    rng = np.random.default_rng(seed)
    for _ in range(resamples):
        indices = rng.integers(0, len(groups), size=len(groups))
        sa = scores(Counter(dict(zip(keys, x[indices].sum(axis=0), strict=True))))
        sb = scores(Counter(dict(zip(keys, y[indices].sum(axis=0), strict=True)))) if y is not None else None
        for key in METRICS:
            if sa[key] is not None and (sb is None or sb[key] is not None):
                distributions[key].append(100 * (sb[key] - sa[key]) if sb is not None else sa[key])
    for key, distribution in distributions.items():
        item = result["intervals"][key]
        item["valid_resamples"] = len(distribution)
        if len(distribution) < 0.95 * resamples or estimates[key] is None:
            result["status"] = "undefined_resamples"
            continue
        item.update(zip(("low", "high"), map(float, np.quantile(distribution, [0.025, 0.975])), strict=True))
    result["degenerate"] = any(
        i["low"] is not None and i["low"] == i["high"] for i in result["intervals"].values()
    )
    return result


def pareto(rows):
    """Descriptive frontier only among complete pipelines measured on the same courses/time basis."""
    usable = [
        r
        for r in rows
        if r.get("quality") is not None
        and r.get("seconds") is not None
        and r.get("complete")
        and r.get("comparable")
    ]
    result = {}
    for row in rows:
        if row not in usable:
            result[row["candidate"]] = "not_assessed"
            continue
        dominated = any(
            other["quality"] >= row["quality"]
            and other["seconds"] <= row["seconds"]
            and (other["quality"] > row["quality"] or other["seconds"] < row["seconds"])
            for other in usable
        )
        result[row["candidate"]] = "dominated" if dominated else "pareto_efficient"
    return result
