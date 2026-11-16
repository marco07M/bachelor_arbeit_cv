"""Shared display states alongside unchanged exact/coverage contributions.

An alignment warning is not a transcription error. These states explain saved
decisions; they never create a new pair or similarity credit.
"""

from collections import Counter

LABELS = {
    "correct": "Korrekt",
    "deviating": "Erkannt, aber abweichend",
    "missing": "Nicht erkannt",
    "unclear": "Zuordnung unklar",
    "unassessed": "Nicht bewertbar",
}
UNCLEAR_ALIGNMENT = {"ambiguous", "identity_conflict", "duplicate_prediction"}


def true(value):
    return value is True or str(value).lower() == "true"


def alignment_unclear(row):
    reasons = set(str(row.get("matching_review_reasons") or "").split(" | "))
    return row.get("status") in UNCLEAR_ALIGNMENT or bool(reasons & UNCLEAR_ALIGNMENT)


def scoring_status(row):
    """Historical R/P/E partition, accepting both typed decisions and CSV rows."""
    if str(row.get("reference_contribution")) == "1":
        if true(row.get("exact")):
            return "correct"
        return "missing" if not row.get("normalized_prediction") or row.get("exclusion_reason") == "invalid_prediction_placeholder" else "incorrect"
    return "extra" if str(row.get("prediction_contribution")) == "1" else "unassessed"


def assess(row, diagnosis=None):
    """Five exclusive display states. Metric status is retained as a separate axis."""
    metric = scoring_status(row)
    original = row.get("original_prediction_value", row.get("prediction_value"))
    text_present = bool(str(original or "").strip() or str(row.get("prediction_value") or "").strip())
    usable = bool(row.get("normalized_prediction")) and row.get("exclusion_reason") != "invalid_prediction_placeholder"
    known_empty = row.get("reference_state") == "empty"
    reference_known = str(row.get("reference_contribution")) == "1" or known_empty
    unpaired = row.get("reference_row") in (None, "")
    diagnosis = diagnosis or {}
    trace = diagnosis.get("pipeline_trace", {})
    proposal_present = any(s.get("stage") == "model_response" and
                           (bool(str(s.get("value") or "").strip()) or
                            any(str(v or "").strip() for v in s.get("cells", []))) for s in trace.get("stages", []))
    mapping_blocked = diagnosis.get("certainty") == "proven" and (
        diagnosis.get("category") in ("not_submitted", "model_omission") or
        diagnosis.get("category") == "column_mapping" and proposal_present)
    if (text_present and (unpaired or alignment_unclear(row))) or mapping_blocked:
        status = "unclear"
    elif not reference_known:
        status = "unassessed"
    elif metric == "correct":
        status = "correct"
    elif known_empty:
        status = "correct" if row.get("prediction_state") == "empty" else "deviating" if usable else "missing"
    elif metric == "incorrect":
        status = "deviating"
    elif text_present and not usable and row.get("exclusion_reason") != "invalid_prediction_placeholder":
        status = "unclear"
    else:
        status = "missing"
    reason = {
        "correct": "Exakt nach gespeicherter Normalisierung beziehungsweise ausdrücklich leer korrekt erkannt.",
        "deviating": "Ein verwertbarer zugeordneter Wert ist vorhanden, stimmt aber nicht exakt überein. Kein Exact-Match-Treffer.",
        "missing": "Kein verwertbarer finaler Feldwert. Ein ID-Platzhalter ist keine nutzbare Erkennung; die Ursache kann unbekannt sein.",
        "unclear": "Text oder ein belegter Zellvorschlag ist vorhanden, aber Personen-/Feldzuordnung oder Nutzbarkeit ist nicht gesichert. Keine bestätigte Identifikation.",
        "unassessed": "Keine verlässlich bestimmbare Feldreferenz; keine Aussage über die Richtigkeit.",
    }[status]
    # Saved field similarity comes from matching.similarity (normalized Levenshtein).
    # A zero contribution for an unpaired/missing value is not a measured text similarity.
    measured = row.get("detected_similarity", row.get("similarity"))
    percent = (100 * float(measured) if measured not in (None, "") and row.get("normalized_prediction") and not unpaired
               and str(row.get("reference_contribution")) == "1" else None)
    return dict(evaluation_status=status, evaluation_label=LABELS[status], evaluation_reason=reason,
                metric_status=metric, text_present=text_present or mapping_blocked,
                final_text_present=text_present, upstream_text_present=mapping_blocked or proposal_present,
                usable_value=usable,
                similarity_percent=percent, alignment_unclear=alignment_unclear(row) or mapping_blocked)


def counts(rows):
    tally = Counter(r.get("evaluation_status") or assess(r)["evaluation_status"] for r in rows)
    return {key: tally[key] for key in LABELS}


def percent(value):
    return "—" if value is None else f"{value:.2f} %".replace(".", ",")
