"""Explain existing field/participant decisions, without rematching or awarding credit."""

import json
import math
from collections import Counter, defaultdict
from pathlib import Path

from ..io import file_hash, read_json, read_jsonl, write_csv, write_json
from .error_report import field_status, relative_link
from .field_assessment import alignment_unclear, assess
from .field_assessment import counts as assessment_counts
from .metrics import correct_empty

VERSION = "metric-audit-v2-field-states"
CATEGORIES = {
    "correct": "Exakt nach Normalisierung",
    "missing_participant": "Referenzperson ohne Paarung",
    "missing_value": "Kein nutzbarer Wert",
    "invalid_placeholder": "Ungültiger ID-Platzhalter",
    "wrong_value": "Abweichender Wert; Ursache offen",
    "wrong_field": "Wert passt exakt in anderes Feld derselben Referenz",
    "other_reference": "Wert passt in andere Referenzzeile (Zuordnungshypothese)",
    "extra": "Zusatzwert ohne Referenzpaar; Halluzination unbewiesen",
    "hallucinated_empty": "Zusatzwert gegen bestätigt leere Referenz",
    "correct_empty": "Bestätigt leer korrekt erkannt",
    "unknown_empty": "Bestätigte Leerzelle nicht als leer erkannt",
    "unassessed": "Referenz nicht bewertbar",
}


def key(row):
    return (row["class_id"], row.get("reference_row"), row.get("document_id"),
            row.get("page_number"), row.get("output_index"))


def explain(row, siblings, reference_index):
    """Categories partition decisions. Cross-field/row equality is evidence, not identity proof."""
    status = field_status({k: "" if v is None else str(v) for k, v in row.items()})
    result = dict(result=status, category="unassessed", reason="Unbekannte/maskierte Referenz: kein Feldpunkt.")
    if row.get("reference_state") == "empty":
        empty = correct_empty(row["prediction_state"], row.get("normalized_prediction"))
        result.update(category="hallucinated_empty" if row["prediction_contribution"] else
                      "correct_empty" if empty else "unknown_empty",
                      reason="Bestätigt leere Referenz; Leerzellenerkennung separat, nichtleere Ausgabe erhöht P.")
    elif status == "correct":
        result.update(category="correct", reason="Normalisierte Werte identisch; kein Schreibweisenfehler angerechnet.")
    elif status == "missing":
        category = ("missing_participant" if row["status"] == "missing" else "invalid_placeholder"
                    if row.get("exclusion_reason") == "invalid_prediction_placeholder" else "missing_value")
        result.update(category=category, reason={
            "missing_participant": "Keine Ausgabe gepaart. Ein fehlender Feldbeitrag; Personenfehler nicht nochmals zu Feldfehlern addiert.",
            "invalid_placeholder": "Nichtleerer Platzhalter: null Treffer, fehlende nutzbare Information und ein P-Beitrag.",
            "missing_value": "Leer, null oder laut Bewertungsprofil nicht nutzbar. Zustand und Rohwert sind separat sichtbar.",
        }[category])
    elif status == "extra":
        result.update(category="extra", reason="Nichtleerer bewertbarer Zusatzwert erhöht P. Ohne Bildreferenz kein Halluzinationsnachweis.")
    elif status == "incorrect":
        result.update(category="wrong_value", reason="Nutzbarer Wert weicht nach bestehender Normalisierung ab; zählt als FP und FN.")
        other_fields = [r["field"] for r in siblings if r["field"] != row["field"]
                        and r.get("reference_state") == "read" and r.get("normalized_reference")
                        and r["normalized_reference"] == row.get("normalized_prediction")]
        targets = reference_index.get((row["class_id"], row["field"], row.get("normalized_prediction")), set())
        targets = sorted(targets - {row["reference_row"]})
        if other_fields:
            result.update(category="wrong_field", reason="Normalisierter Wert entspricht anderem Sollfeld derselben Person: "
                          + ", ".join(other_fields) + ". Gleichheit belegt; ursprüngliche Ursache offen.")
        elif targets:
            result.update(category="other_reference", reason="Wert entspricht demselben Feld anderer Referenzzeilen: "
                          + ", ".join(map(str, targets)) + ". Mögliche Zeilenverwechslung; keine automatische Neuzuordnung.")
    return result


def build(output, details, cases, overview, specs, documents):
    """Use primary course_metrics outputs; reconcile their contributions with saved aggregates."""
    def identifier(row):
        return tuple("" if row.get(k) is None else str(row[k]) for k in
                     ("method", "class_id", "reference_row", "document_id", "page_number", "output_index", "field"))

    evidence_path = output / "error_analysis/fields.json"
    diagnoses = {identifier(r): r["analysis"] for r in read_json(evidence_path)["fields"]} if evidence_path.is_file() else {}
    sources, manifests = {}, {}
    for candidate, spec in specs.items():
        source = Path(spec["source"])
        manifests[candidate] = read_json(source / "manifest.json")
        sources[candidate] = {r["sha256"]: r["path"] for r in manifests[candidate]["inputs"] if r["kind"] == "pdf"}
    by_course = defaultdict(list)
    for row in documents:
        if row.get("status") == "mapped":
            by_course[row["class_id"]].append(row["document_id"])

    def location(candidate, row):
        ids = [row["document_id"]] if row.get("document_id") else by_course[row["class_id"]]
        links = []
        for doc in ids:
            path = Path(sources[candidate][doc])
            if path.is_file():
                links.append(dict(label=path.name, href=relative_link(path, output)
                                  + (f'#page={row["page_number"]}' if row.get("page_number") else "")))
        return dict(document_label=" | ".join(Path(sources[candidate][doc]).name for doc in ids),
                    location_status="prediction_page" if row.get("document_id") else "course_only_page_unknown",
                    original_links=links)

    fields, participants, checks, summaries, pages = [], [], {}, [], []
    for candidate in details:
        primary = next(r for r in overview if r.get("mode") == "original_roles" and r["candidate"] == candidate)
        grouped, reference_index = defaultdict(list), defaultdict(set)
        for row in details[candidate]["original_roles"]:
            grouped[key(row)].append(row)
            if row.get("reference_state") == "read":
                reference_index[row["class_id"], row["field"], row["normalized_reference"]].add(row["reference_row"])
        method_fields, method_cases = [], []
        for row in cases[candidate]["original_roles"]:
            siblings = grouped[key(row)]
            participant = dict(candidate=candidate, **row, **location(candidate, row))
            participant["participant_label"] = " ".join(str(r.get("reference_value") or r.get("prediction_value") or "")
                                                       for f in ("first_name", "last_name") for r in siblings if r["field"] == f)
            participant["participant_result"] = ("extra" if row["reference_row"] is None else "missing" if row["status"] == "missing"
                                                  else "unclear" if alignment_unclear(row)
                                                  else "complete" if row["fully_correct_required"] else "identity_only"
                                                  if row["identity_exact"] else "identity_error")
            method_cases.append(participant)
            reasons = []
            for field in siblings:
                explanation = explain(field, siblings, reference_index)
                diagnosis = diagnoses.get(identifier(dict(field, method=candidate)), {})
                record = dict(candidate=candidate, **field, **location(candidate, row), **explanation,
                              participant_label=participant["participant_label"])
                record.update(assess(field, diagnosis))
                record["cause"] = {k: diagnosis.get(k, "unknown") for k in ("category", "stage", "certainty", "reason")}
                method_fields.append(record)
                if explanation["category"] not in ("correct", "correct_empty", "unassessed"):
                    reasons.append(field["field"] + ": " + CATEGORIES[explanation["category"]])
            participant["reason"] = "; ".join(reasons) or "Alle bestimmbaren Felder korrekt."
            if row.get("reference_row") is not None and not row.get("identity_assessable"):
                participant["reason"] += " Identitätsnenner ausgeschlossen: kein eindeutiger lesbarer Referenzanker."
        tally = Counter(r["result"] for r in method_fields)
        contributions = dict(reference_fields=sum(r["reference_contribution"] for r in method_fields),
                             detected_fields=sum(r["detected_contribution"] for r in method_fields),
                             detected_similarity_credit=sum(r.get("detected_similarity") or 0 for r in method_fields),
                             predicted_fields=sum(r["prediction_contribution"] for r in method_fields),
                             exact_fields=tally["correct"], incorrect_fields=tally["incorrect"], missing_fields=tally["missing"],
                             extra_fields=tally["extra"])
        q = primary["participant_quality"]
        agreement = all(math.isclose(primary[k], v, rel_tol=1e-12, abs_tol=1e-9) for k, v in contributions.items())
        agreement &= sum(bool(r.get("identity_exact")) for r in method_cases) == q["identity_exact_participants"]
        agreement &= sum(bool(r.get("fully_correct_required")) for r in method_cases) == q["fully_correct_complete_participants"]
        if not agreement:
            raise ValueError("Feld-/Teilnehmeraudit stimmt nicht mit den Qualitätszählern überein: " + candidate)
        checks[candidate] = dict(contributions=contributions, matches_metrics=agreement,
                                 evaluation_status_partition=sum(assessment_counts(method_fields).values()) == len(method_fields),
                                 reference_partition=contributions["exact_fields"] + contributions["incorrect_fields"]
                                 + contributions["missing_fields"] == contributions["reference_fields"])
        summaries.append(dict(candidate=candidate, **contributions,
                              available_reference_fields=primary["reference_fields"] - primary["missing_fields"],
                              assigned_participants=sum(r["status"] == "matched" for r in method_cases),
                              predicted_participants=sum(r.get("output_index") is not None for r in method_cases),
                              evaluation_status_counts=assessment_counts(method_fields),
                              reference_status_counts=assessment_counts([r for r in method_fields if r["reference_contribution"]]),
                              **q))
        source = Path(specs[candidate]["source"])
        method = specs[candidate]["method"]
        extraction = source / method / "extractions.jsonl"
        selected_ids = {doc for ids in by_course.values() for doc in ids}
        for page in read_jsonl(extraction) if extraction.is_file() else []:
            if page["document_id"] not in selected_ids:
                continue
            raw_path = (source / method / ("raw-" + page["page_id"] + ".json")).resolve()
            if not raw_path.is_relative_to((source / method).resolve()):
                raise ValueError("Ungültiger Rohdatenpfad")
            raw = read_json(raw_path) if raw_path.is_file() else {}
            timings = page.get("timings", {})
            pages.append(dict(candidate=candidate, document_id=page["document_id"], page_number=page["page_number"],
                              document_label=Path(sources[candidate][page["document_id"]]).name,
                              participants=len(page["participants"]), status=page["status"], parse_status=page["parse_status"],
                              review_notes=page.get("review_notes", []), error=raw.get("error"),
                              output_tokens=[r.get("output_tokens") for r in raw.get("responses", [])],
                              ocr_observations=raw.get("ocr_observation_audit", {}).get("counts", {}).get("observations"),
                              page_wall_seconds=timings.get("page_wall_seconds"),
                              cached_components=[k for k, v in timings.items() if k.endswith("cache_hit") and v],
                              assignment_cache=raw.get("assignment", {}).get("cache_hit")))
        fields.extend(method_fields)
        participants.extend(method_cases)
    payload = dict(version=VERSION, grading="original_roles", fields=fields, participants=participants,
                   summaries=summaries, checks=checks, categories=CATEGORIES, pages=pages)
    payload["implementation_sha256"] = file_hash(Path(__file__))
    folder = output / "scientific"
    write_json(folder / "metric_audit.json", payload)
    for name, rows in (("field_cases", fields), ("participant_audit", participants)):
        write_csv(folder / (name + ".csv"), [{k: json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else v
                                             for k, v in r.items()} for r in rows])
    write_json(folder / "metric_audit_checks.json", checks)
    return payload
