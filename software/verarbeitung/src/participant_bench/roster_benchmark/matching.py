"""Course-local maximum-weight one-to-one alignment, including unmatched and ambiguous rows."""

import unicodedata
from collections import Counter, defaultdict
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import numpy as np
import yaml
from scipy.optimize import linear_sum_assignment

from ..config import SignatureConfig
from ..evaluation import edits
from ..identifiers import normalized_user_id
from ..io import file_hash, read_json
from ..reference_states import assessable_reference
from ..schema import Participant

FIELDS = {"first_name": "first_name", "last_name": "last_name", "user_id": "personnel_number", "short_code": "department"}
NAME_WEIGHTS = {"first_name": 1.0, "last_name": 1.0, "short_code": 0.5}


@dataclass
class Prediction:
    document_id: str
    page_number: int
    index: int
    person: Participant
    signature_evidence: dict | None = None


def page_predictions(page, method_dir):
    """Attach existing signature records, never infer absence from missing OCR text."""
    from ..signatures import evaluation_evidence

    root = Path(method_dir).resolve()
    path = (root / f"raw-{page.page_id}.json").resolve()
    if not path.is_relative_to(root):
        raise ValueError("Ungültiger Rohdatenpfad")
    raw = read_json(path) if path.is_file() else {}
    artifact_hash = file_hash(path) if path.is_file() else None
    config_path = root.parent / "config.yaml"
    source_config = yaml.safe_load(config_path.read_text(encoding="utf8")) if config_path.is_file() else {}
    signature_config = SignatureConfig.model_validate((source_config or {}).get("signature") or {})
    records = raw.get("signature_checks", [])
    cell_records = raw.get("signature_cell_checks", [])
    predictions = []
    for i, person in enumerate(page.participants):
        found = [r for r in records if r.get("output_index") == i]
        # A record must also agree with the saved person's geometry and final state.
        record = found[0] if len(found) == 1 else {}
        cells = [r for r in cell_records if r.get("output_index") == i]
        evidence = evaluation_evidence(person, page.participants, record, signature_config,
                                       cells[0] if len(cells) == 1 else {})
        evidence.update(raw_artifact=path.name, raw_artifact_sha256=artifact_hash)
        predictions.append(Prediction(page.document_id, page.page_number, i, person, evidence))
    return predictions


def unmatched_review(prediction, references, config, reference_config, status):
    """Post-match exclusion only; similarity guards never create identity credit."""
    from ..signatures import evaluation_evidence

    evidence = prediction.signature_evidence or evaluation_evidence(prediction.person, [prediction.person], {})
    observed = {f: normalize(v, f, config) for f, v in values(prediction, config).items()}
    expected = [expected_values(r, config, reference_config) for r in references]
    ids = Counter(r["user_id"] for r in expected)
    reference_unclear = any(not (r["first_name"] or r["last_name"] or reference_config.usable_id(r["user_id"])) for r in expected)
    near = []
    # A stricter scoring view must not turn a recognizable name swap into an exclusion.
    name_guard = config.model_copy(update={"compare_name_orientations": True})
    for reference, row in zip(references, expected):
        pair = pair_evidence(observed, row, config, reference_config, ids[row["user_id"]])
        oriented = name_orientation(observed, row, name_guard)[0]
        names = [similarity(oriented[f], row[f]) for f in ("first_name", "last_name") if oriented[f] and row[f]]
        name_score = sum(names) / len(names) if names else None
        same_id = bool(reference_config.usable_id(observed["user_id"]) and observed["user_id"] == row["user_id"])
        if same_id or pair["conservative_qualifies"] or (names and name_score >= config.minimum_name_similarity):
            near.append(dict(reference_row=reference.row_number, name_similarity=name_score,
                             exact_user_id=same_id, conservative_qualifies=pair["conservative_qualifies"]))
    excluded = bool(config.exclude_probably_unsigned_extras and references and not reference_unclear and status == "extra"
                    and not near and evidence["probable_absence"])
    reason = ("Keine Referenzpaarung oder hinreichend ähnliche Namenskandidaten; lokalisierter Signaturbeleg spricht für ein leeres Feld. "
              "Wahrscheinlicher Nichtunterzeichner, nicht visuell bestätigt." if excluded else
              "Ähnliche oder identische Referenzanker vorhanden; mögliche Schreibabweichung, Doppelung oder Zuordnungsfehler." if near else
              "Mehrdeutige, widersprüchliche oder leere Teilnehmerausgabe; kein automatischer Ausschluss." if status != "extra" else
              "Keine Teilnehmerreferenz für eine belastbare Ausschlussentscheidung." if not references else
              "Referenz enthält Personen ohne lesbaren Namen oder nutzbare ID; fehlende Zuordnung ist nicht belastbar." if reference_unclear else
              "Signatur vorhanden, unbekannt oder ohne verlässlichen Zeilenbeleg; mögliche Fehlzuordnung manuell prüfen." if not evidence["probable_absence"] else
              "Automatischer Ausschluss ist in der gespeicherten Vergleichskonfiguration deaktiviert.")
    return dict(excluded_from_quality=excluded, exclusion_reason_participant=reason,
                manual_review_required=not excluded, reference_assignment="unassigned",
                reference_candidates=near, signature_assessment=evidence)


@dataclass
class Match:
    prediction: int
    reference: int
    similarity: float
    source: str
    alternative_gap: float
    review_reasons: tuple[str, ...] = ()
    name_swapped: bool = False


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


def expected_values(reference, config, reference_config):
    return {field: normalize(getattr(reference, field), field, config)
            if assessable_reference(reference, field, reference_config) else "" for field in FIELDS}


def exact_name_target(row, reference, config):
    selected, *_ = name_orientation(row, reference, config)
    return all(selected[field] and selected[field] == reference[field] for field in NAME_WEIGHTS)


def name_orientation(row, reference, config):
    direct = sum(similarity(row[field], reference[field]) for field in ("first_name", "last_name")
                 if row[field] and reference[field])
    swapped = dict(row, first_name=row["last_name"], last_name=row["first_name"])
    reverse = sum(similarity(swapped[field], reference[field]) for field in ("first_name", "last_name")
                  if swapped[field] and reference[field])
    use_swap = config.compare_name_orientations and reverse > direct + 1e-10
    return swapped if use_swap else row, bool(use_swap), direct, reverse


def pair_evidence(row, reference, config, reference_config, id_count):
    row, swapped, direct, reverse = name_orientation(row, reference, config)
    result = _pair_evidence(row, reference, config, reference_config, id_count)
    result.update(name_swapped=swapped, direct_name_credit=direct, swapped_name_credit=reverse)
    return result


def _pair_evidence(row, reference, config, reference_config, id_count):
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
        components = {field: similarity(row[field], reference[field]) for field in eligible if row[field]
                      and (field != "user_id" or reference_config.usable_id(row[field]))}
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
    expected = [expected_values(reference, config, reference_config) for reference in references]
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
        name_targets = {j for j, ref in enumerate(expected) if exact_name_target(row, ref, config)}
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
                                   name_swapped=evidence["name_swapped"], direct_name_credit=evidence["direct_name_credit"],
                                   swapped_name_credit=evidence["swapped_name_credit"],
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
        matches.append(Match(readable[position], j, evidence["weighted_similarity"], "global_best_fit", gap,
                             tuple(reasons), evidence["name_swapped"]))
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
    expected = [expected_values(reference, config, reference_config) for reference in references]
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
        name_targets = {i for i, ref in enumerate(expected) if exact_name_target(row, ref, config)}
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
            metadata[i, j] = (1.0 if anchor else score, source, evidence["name_swapped"])
            candidates.append({"prediction_index": i, "reference_row": references[j].row_number,
                               "name_swapped": evidence["name_swapped"], "direct_name_credit": evidence["direct_name_credit"],
                               "swapped_name_credit": evidence["swapped_name_credit"],
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
            score, source, swapped = metadata[i, j]
            matches.append(Match(i, j, score, source, gap, name_swapped=swapped))
    assigned = {match.prediction for match in matches}
    for i in range(count):
        if i not in assigned:
            issues.setdefault(i, "extra")
    return matches, issues, candidates
