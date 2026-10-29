"""Course-local maximum-weight one-to-one alignment, including unmatched and ambiguous rows."""

import unicodedata
from collections import Counter, defaultdict
from dataclasses import dataclass
from functools import lru_cache

import numpy as np
from scipy.optimize import linear_sum_assignment

from ..evaluation import edits
from ..identifiers import normalized_user_id
from ..schema import Participant

FIELDS = {"first_name": "first_name", "last_name": "last_name", "user_id": "personnel_number", "short_code": "department"}
NAME_WEIGHTS = {"first_name": 1.0, "last_name": 1.0, "short_code": 0.5}


@dataclass
class Prediction:
    document_id: str
    page_number: int
    index: int
    person: Participant


@dataclass
class Match:
    prediction: int
    reference: int
    similarity: float
    source: str
    alternative_gap: float
    review_reasons: tuple[str, ...] = ()


def normalize(value, field, config):
    if field == "user_id":
        return normalized_user_id(value, ignore_leading_zeros=config.ignore_leading_user_id_zeros)
    value = unicodedata.normalize("NFC", value or "")
    value = value.strip() if field == "user_id" else " ".join(value.split())
    return value if field == "user_id" or config.case_sensitive else value.lower()


@lru_cache(maxsize=32768)
def similarity(left: str, right: str):
    length = max(len(left), len(right))
    return 1 - edits(left, right) / length if length else 1.0


def values(prediction, config):
    return {name: field.value if field.state in ("read", "empty") or
            (config.score_uncertain_values and field.state == "uncertain") else None
            for name, model_name in FIELDS.items() for field in [getattr(prediction.person, model_name)]}


def pair_evidence(row, reference, config, reference_config, id_count):
    """The same candidate gates are used for alignment and its human-readable explanation."""
    anchor = (reference_config.usable_id(row["user_id"]) and reference_config.usable_id(reference["user_id"])
              and row["user_id"] == reference["user_id"] and id_count == 1)
    observations = {field: similarity(row[field], reference[field]) for field in NAME_WEIGHTS
                    if row[field] and reference[field]}
    weight = sum(NAME_WEIGHTS[field] for field in observations)
    score = sum(NAME_WEIGHTS[field] * value for field, value in observations.items()) / weight if weight else 0.0
    name_evidence = max((value for field, value in observations.items() if field != "short_code"), default=0.0)
    qualifies = (len(observations) >= 2 and score >= config.minimum_similarity
                 and name_evidence >= config.minimum_name_similarity)
    reasons = []
    if not anchor:
        if len(observations) < 2:
            reasons.append("fewer_than_two_observed_fields")
        if score < config.minimum_similarity:
            reasons.append("below_minimum_similarity")
        if name_evidence < config.minimum_name_similarity:
            reasons.append("below_minimum_name_similarity")
    result = dict(anchor=bool(anchor), observations=observations, weight_sum=weight, weighted_similarity=score,
                name_evidence=name_evidence, qualifies=bool(anchor or qualifies), rejection_reasons=reasons,
                matching_source="exact_user_id" if anchor else "name_short_code_levenshtein")
    result["conservative_qualifies"] = result["qualifies"]
    if config.mode == "best_fit":
        eligible = {field for field in FIELDS if reference[field] and
                    (field != "user_id" or reference_config.usable_id(reference[field]))}
        if row["user_id"] and not reference_config.usable_id(row["user_id"]):
            eligible.discard("user_id")
        components = {field: similarity(row[field], reference[field]) for field in eligible if row[field]}
        credit = sum(components.values())
        readable = any(value and (field != "user_id" or reference_config.usable_id(value))
                       for field, value in row.items())
        result.update(observations=components, weight_sum=len(eligible),
                      optimization_credit=credit, weighted_similarity=credit / len(eligible) if eligible else 0.0,
                      qualifies=bool(readable), rejection_reasons=[] if readable else ["no_readable_fields"],
                      matching_source="global_best_fit")
    return result


def align_best_fit(predictions, references, config, reference_config):
    """Maximize pair count, then total field similarity; retain weak pairs with explicit review flags."""
    observed = [values(prediction, config) for prediction in predictions]
    normalized = [{field: normalize(value, field, config) for field, value in row.items()} for row in observed]
    expected = [{field: normalize(getattr(reference, field), field, config) for field in FIELDS}
                for reference in references]
    ids = Counter(row["user_id"] for row in expected if reference_config.usable_id(row["user_id"]))
    readable = [i for i, row in enumerate(normalized) if any(
        value and (field != "user_id" or reference_config.usable_id(value)) for field, value in row.items())]
    # Stable tie handling also preserves raw-exact results for normalized duplicate outputs.
    readable.sort(key=lambda i: (tuple(normalized[i][field] for field in FIELDS),
                                -sum(getattr(predictions[i].person, field).state == "read" for field in FIELDS.values()),
                                tuple(observed[i][field] or "" for field in FIELDS),
                                predictions[i].document_id, predictions[i].page_number, predictions[i].index))
    issues = {i: "empty_prediction" for i in range(len(predictions)) if i not in readable}
    if not readable or not references:
        issues.update({i: "extra" for i in readable})
        return [], issues, []
    fingerprints, duplicate = set(), set()
    for i in readable:
        fingerprint = tuple(normalized[i][field] for field in FIELDS)
        if fingerprint in fingerprints:
            duplicate.add(i)
        fingerprints.add(fingerprint)
    # One additional pair must outweigh every possible field-credit difference.
    bonus = len(FIELDS) * min(len(readable), len(references)) + 1
    utilities = np.zeros((len(readable), len(references) + len(readable)), dtype=float)
    metadata, candidates = {}, []
    for position, i in enumerate(readable):
        row = normalized[i]
        id_targets = {j for j, ref in enumerate(expected) if reference_config.usable_id(row["user_id"])
                      and row["user_id"] == ref["user_id"]}
        name_targets = {j for j, ref in enumerate(expected) if all(row[field] and row[field] == ref[field]
                        for field in NAME_WEIGHTS)}
        conflict = bool(id_targets and name_targets and not id_targets.intersection(name_targets))
        for j, ref in enumerate(expected):
            evidence = pair_evidence(row, ref, config, reference_config, ids[ref["user_id"]])
            utilities[position, j] = bonus + evidence["optimization_credit"]
            reasons = []
            if evidence["weighted_similarity"] < config.minimum_similarity or not evidence["conservative_qualifies"]:
                reasons.append("low_similarity")
            if conflict:
                reasons.append("identity_conflict")
            if i in duplicate:
                reasons.append("duplicate_prediction")
            metadata[position, j] = evidence, reasons
            candidates.append(dict(prediction_index=i, reference_row=references[j].row_number,
                                   identity_similarity=evidence["weighted_similarity"],
                                   matching_source="global_best_fit", optimization_credit=evidence["optimization_credit"],
                                   conservative_qualifies=evidence["conservative_qualifies"]))
    selected, optimum = solve(utilities, len(references))
    matches = []
    for position, j in selected:
        alternative = utilities.copy()
        alternative[position, j] = -1e6
        _, changed = solve(alternative, len(references))
        gap = max(0.0, optimum - changed)
        evidence, reasons = metadata[position, j]
        if gap <= config.ambiguity_margin + 1e-10:
            reasons.append("ambiguous")
        matches.append(Match(readable[position], j, evidence["weighted_similarity"], "global_best_fit", gap, tuple(reasons)))
    assigned = {match.prediction for match in matches}
    issues.update({i: "duplicate_prediction" if i in duplicate else "extra" for i in readable if i not in assigned})
    return matches, issues, candidates


def solve(utilities, reference_count):
    """Dummy columns allow every prediction to remain unmatched instead of forcing a bad pair."""
    rows, columns = linear_sum_assignment(utilities, maximize=True)
    score = float(utilities[rows, columns].sum())
    pairs = [(int(row), int(column)) for row, column in zip(rows, columns)
             if column < reference_count and utilities[row, column] > 0]
    return pairs, score


def align(predictions, references, config, reference_config):
    if config.mode == "best_fit":
        return align_best_fit(predictions, references, config, reference_config)
    count, ref_count = len(predictions), len(references)
    if not count or not ref_count:
        return [], {i: "extra" for i in range(count)}, []
    observed = [values(prediction, config) for prediction in predictions]
    normalized = [{field: normalize(value, field, config) for field, value in row.items()} for row in observed]
    expected = [{field: normalize(getattr(reference, field), field, config) for field in FIELDS}
                for reference in references]
    ids = Counter(row["user_id"] for row in expected if reference_config.usable_id(row["user_id"]))
    issues, fingerprints = {}, defaultdict(list)
    for index, row in enumerate(normalized):
        fingerprint = tuple(row[field] for field in FIELDS)
        fingerprints[fingerprint].append(index)
    for indices in fingerprints.values():
        # Deterministic canonical copy, independent of input order and without consulting the reference.
        chosen = min(indices, key=lambda i: (
            -sum(getattr(predictions[i].person, field).state == "read" for field in FIELDS.values()),
            tuple(observed[i][field] or "" for field in FIELDS)))
        issues.update({i: "duplicate_prediction" for i in indices if i != chosen})
    for index, row in enumerate(normalized):
        id_targets = {i for i, ref in enumerate(expected) if reference_config.usable_id(row["user_id"])
                      and reference_config.usable_id(ref["user_id"]) and row["user_id"] == ref["user_id"]}
        name_targets = {i for i, ref in enumerate(expected) if all(row[field] and row[field] == ref[field]
                        for field in ("first_name", "last_name", "short_code"))}
        if id_targets and name_targets and not id_targets.intersection(name_targets):
            issues[index] = "identity_conflict"
    utilities = np.full((count, ref_count + count), -1e6, dtype=float)
    utilities[:, ref_count:] = 0
    metadata, candidates = {}, []
    for i, row in enumerate(normalized):
        if i in issues:
            continue
        for j, ref in enumerate(expected):
            evidence = pair_evidence(row, ref, config, reference_config, ids[ref["user_id"]])
            anchor, score = evidence["anchor"], evidence["weighted_similarity"]
            if not evidence["qualifies"]:
                continue
            source = evidence["matching_source"]
            # A unique exact identifier has priority over any combination of fuzzy-only matches.
            utility = max(count, ref_count) + 1 + score if anchor else score
            utilities[i, j] = utility
            metadata[i, j] = (1.0 if anchor else score, source)
            candidates.append({"prediction_index": i, "reference_row": references[j].row_number,
                               "identity_similarity": 1.0 if anchor else score, "matching_source": source})
    selected, optimum = solve(utilities, ref_count)
    matches = []
    for i, j in selected:
        # Check global alternatives, rather than rejecting a locally close match that other rows disambiguate.
        alternative = utilities.copy()
        alternative[i, j] = -1e6
        _, changed = solve(alternative, ref_count)
        gap = max(0.0, optimum - changed)
        if gap <= config.ambiguity_margin + 1e-10:
            issues[i] = "ambiguous"
        else:
            score, source = metadata[i, j]
            matches.append(Match(i, j, score, source, gap))
    assigned = {match.prediction for match in matches}
    for i in range(count):
        if i not in assigned:
            issues.setdefault(i, "extra")
    return matches, issues, candidates
