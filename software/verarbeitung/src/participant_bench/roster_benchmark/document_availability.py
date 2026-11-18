"""Independent PDF review and projections of frozen field counters, never new matching."""

from collections import Counter, defaultdict
from copy import deepcopy
from datetime import datetime
from pathlib import Path

from ..io import digest, file_hash, read_json
from .field_assessment import alignment_unclear
from .matching import FIELDS, normalize
from .metrics import scores, sum_counts

VERSION = "document-availability-v1"
AVAILABILITY = {
    "unchecked": "Ungeprüft",
    "readable": "Vorhanden und lesbar",
    "unreadable": "Vorhanden, aber unleserlich",
    "absent": "Nachweislich leer / nicht enthalten",
    "uncertain": "Nicht eindeutig prüfbar",
}
CAUSES = {
    "not_in_document": "Nicht im Dokument vorhanden",
    "unreadable": "Im Dokument unleserlich",
    "not_recognized": "Lesbar, aber nicht extrahiert",
    "not_adopted": "Erkannt / vorgeschlagen, nicht übernommen",
    "wrong_assignment": "Falsch zugeordnet (Hinweis)",
    "reference_matching": "Referenz- oder Matchingproblem",
    "unknown": "Ursache unbekannt",
}


def field_id(row):
    """Method-independent key, bound to the reference snapshot by the review envelope."""
    return digest([str(row["class_id"]), int(row["reference_row"]), row["field"]])[:24]


def case_key(row):
    return tuple(
        str(row.get(k) if row.get(k) is not None else "")
        for k in ("class_id", "reference_row", "document_id", "page_number", "output_index", "field")
    )


def context(output, original_documents=None):
    from .detail_report import read_csv
    from .references import saved_reference

    if original_documents is not None and (
        not isinstance(original_documents, dict)
        or any(not isinstance(k, str) or not isinstance(v, str) for k, v in original_documents.items())
    ):
        raise ValueError("Originaldateien benötigen eine lokale Pfadzuordnung nach PDF-Prüfsumme")
    source, _, _, _, config = saved_reference(output)
    manifest = read_json(source / "manifest.json")
    scoped = read_csv(output / "documents.csv")
    courses = defaultdict(list)
    for row in scoped:
        if row.get("status") == "mapped":
            courses[row["class_id"]].append(row["document_id"])
    documents = {}
    for item in manifest["inputs"]:
        if item["kind"] != "pdf" or not any(item["sha256"] in ids for ids in courses.values()):
            continue
        path = Path((original_documents or {}).get(item["sha256"]) or item["path"])
        if path.drive.startswith("\\\\"):
            raise ValueError("Dokumentprüfung benötigt lokale Originaldateien, keine Netzwerkpfade")
        verified = path.is_file() and file_hash(path) == item["sha256"]
        pages = sorted(
            {
                int(p["page_number"])
                for p in manifest.get("pages", [])
                if (p.get("document_id") or p.get("source_sha256")) == item["sha256"]
                and p.get("page_number") is not None
            }
        )
        if verified:
            import pymupdf

            try:
                with pymupdf.open(path) as pdf:
                    pages = list(range(1, len(pdf) + 1))
            except (RuntimeError, ValueError, OSError):
                verified = False
        documents[item["sha256"]] = dict(
            document_id=item["sha256"], name=path.name, path=str(path), verified=verified, pages=pages
        )
    binding = dict(
        version=VERSION,
        reference_snapshot_sha256=file_hash(output / "reference_snapshot.json"),
        documents=sorted(documents),
    )
    return dict(source=source, config=config, documents=documents, courses=dict(courses), binding=binding)


def reference_fields(fields, ctx):
    result = {}
    names = defaultdict(dict)
    for row in fields:
        if row.get("reference_row") is not None:
            names[row["class_id"], row["reference_row"]][row["field"]] = row.get("reference_value")
    for row in fields:
        if row["reference_contribution"] != 1:
            continue
        key = field_id(row)
        entry = dict(
            field_id=key,
            class_id=row["class_id"],
            reference_row=row["reference_row"],
            field=row["field"],
            reference_value=row["reference_value"],
            schriftart=row.get("schriftart"),
            participant=" ".join(
                str(names[row["class_id"], row["reference_row"]].get(f) or "")
                for f in ("first_name", "last_name")
            ),
            documents=ctx["courses"].get(row["class_id"], []),
        )
        if key in result and any(result[key][f] != entry[f] for f in ("reference_value", "schriftart")):
            raise ValueError("Dokumentprüfung benötigt identische Referenzwerte aller Verfahren")
        result[key] = entry
    return result


def review_template(refs, ctx):
    return dict(
        **ctx["binding"],
        original_documents={k: d["path"] for k, d in ctx["documents"].items() if d["verified"]},
        annotations=[
            dict(
                field_id=k,
                availability="unchecked",
                document_value=None,
                locations=[],
                reviewed_pages=[],
                reviewer="",
                reviewed_at="",
                anchor_note="",
                note="",
                independent_of_predictions=False,
                reference_person_verified=False,
            )
            for k in refs
        ],
    )


def load_reviews(path, refs, ctx):
    """No automatic document label from output/OCR. Manual assertions need provenance."""
    envelope = read_json(path) if path else review_template(refs, ctx)
    if not isinstance(envelope, dict) or not isinstance(envelope.get("annotations"), list):
        raise ValueError("Dokumentannotation benötigt ein JSON-Objekt mit annotations-Liste")
    if any(envelope.get(k) != v for k, v in ctx["binding"].items()):
        raise ValueError("Dokumentannotation gehört nicht zu Referenzsnapshot und PDF-Datenbasis")
    result = {}
    for item in envelope.get("annotations", []):
        if not isinstance(item, dict):
            raise ValueError("Dokumentannotation enthält keine gültigen Feldobjekte")
        key = item.get("field_id")
        if (
            not isinstance(key, str)
            or key not in refs
            or key in result
            or item.get("availability") not in AVAILABILITY
        ):
            raise ValueError("Unbekannte, doppelte oder ungültige Dokumentannotation")
        item = dict(item)
        state, reference = item["availability"], refs[key]
        if state in ("readable", "unreadable", "absent"):
            if (
                item.get("independent_of_predictions") is not True
                or item.get("reference_person_verified") is not True
                or not all(
                    str(item.get(k) or "").strip() for k in ("reviewer", "reviewed_at", "anchor_note", "note")
                )
            ):
                raise ValueError(
                    "Geprüfte Dokumentlabels benötigen unabhängige Personenprüfung und Prüfprotokoll"
                )
            if item.get("review_method") not in (
                "manual_pdf_review",
                "assistant_visual_pdf_review",
                "independent_document_gt",
            ):
                raise ValueError("Geprüftes Dokumentlabel benötigt eine explizite Prüfmethode")
            try:
                datetime.fromisoformat(item["reviewed_at"])
            except (TypeError, ValueError):
                raise ValueError("Prüfdatum muss im ISO-Format vorliegen") from None
            locations = item.get("locations") or []
            if (
                not isinstance(locations, list)
                or not locations
                or any(not isinstance(loc, dict) for loc in locations)
            ):
                raise ValueError("Geprüftes Dokumentfeld benötigt mindestens eine Originalseitenposition")
            for loc in locations:
                doc = ctx["documents"].get(loc.get("document_id"))
                if (
                    not doc
                    or not doc["verified"]
                    or loc["document_id"] not in reference["documents"]
                    or loc.get("page_number") not in doc["pages"]
                ):
                    raise ValueError(
                        "Dokumentannotation benötigt eine verifizierte Originalseite des Referenzkurses"
                    )
                box = loc.get("bbox")
                if box is not None and (
                    not isinstance(box, dict)
                    or set(box) != {"x0", "y0", "x1", "y1"}
                    or not all(
                        isinstance(v, (int, float)) and not isinstance(v, bool) and 0 <= v <= 1
                        for v in box.values()
                    )
                    or box["x0"] >= box["x1"]
                    or box["y0"] >= box["y1"]
                ):
                    raise ValueError(
                        "Dokumentausschnitt muss auf die unveränderte Originalseite normiert sein"
                    )
            if state == "readable" and (
                not isinstance(item.get("document_value"), str) or not item["document_value"].strip()
            ):
                raise ValueError("Lesbare Dokumentfelder benötigen eine unabhängige Transkription")
            if state == "absent":
                if not all(ctx["documents"][d]["verified"] for d in reference["documents"]):
                    raise ValueError("Abwesenheit benötigt verifizierte Originale aller Kursdokumente")
                required = {(d, n) for d in reference["documents"] for n in ctx["documents"][d]["pages"]}
                if not isinstance(item.get("reviewed_pages"), list) or any(
                    not isinstance(p, dict) for p in item["reviewed_pages"]
                ):
                    raise ValueError("Geprüfte Seiten benötigen eine Dokument-/Seitenliste")
                reviewed = {
                    (p.get("document_id"), p.get("page_number")) for p in item.get("reviewed_pages", [])
                }
                if reviewed != required:
                    raise ValueError("Abwesenheit benötigt die Prüfung aller Kursdokumentseiten")
        item["reference_agrees"] = (
            normalize(item.get("document_value"), reference["field"], ctx["config"].matching)
            == normalize(reference["reference_value"], reference["field"], ctx["config"].matching)
            if state == "readable"
            else None
        )
        item["eligible"] = state == "readable" and item["reference_agrees"]
        result[key] = item
    for key in refs:
        result.setdefault(
            key,
            dict(
                field_id=key,
                availability="unchecked",
                eligible=False,
                reference_agrees=None,
                locations=[],
                note="",
                document_value=None,
            ),
        )
    return result


def pipeline(method):
    return {
        "vlm": "Direktes VLM (kein vorgeschaltetes OCR)",
        "ocr_llm": "Tesseract → LLM",
        "paddle_llm": "Paddle-OCR → LLM",
        "ocr_vlm": "OCR + VLM",
        "ocr_rules": "OCR + Regeln",
        "docling": "Docling: OCR / Dokumentstruktur",
        "docling_vlm": "Docling + VLM-Assist",
    }.get(method, method)


def classify(row, review, diagnosis, other_values):
    """Document state and saved stage evidence remain separate axes of certainty."""
    state = review["availability"]
    if state == "absent":
        return (
            "not_in_document",
            "document_verified",
            "Unabhängige Originalprüfung: Feld leer oder nicht enthalten.",
        )
    if state == "unreadable":
        return (
            "unreadable",
            "document_verified",
            "Unabhängige Originalprüfung: Inhalt vorhanden, nicht zuverlässig lesbar.",
        )
    if state == "readable" and not review["reference_agrees"]:
        return (
            "reference_matching",
            "document_verified",
            "Lesbarer Originalwert weicht nach bestehender Normalisierung von der Kursreferenz ab.",
        )
    flags = set(str(row.get("matching_review_reasons") or "").split(" | "))
    if alignment_unclear(row) or flags & {"role_unconfirmed"}:
        return (
            "reference_matching",
            "hypothesis",
            "Die bestehende Personenpaarung ist prüfpflichtig; keine automatische Korrektur.",
        )
    category, certainty = diagnosis.get("category"), diagnosis.get("certainty")
    if row.get("candidate") == "vlm" and category in ("not_submitted", "model_omission"):
        category = None  # Auxiliary OCR is not the direct VLM's primary input.
    if (
        category in ("column_mapping", "validation", "not_submitted", "model_omission")
        and certainty == "proven"
    ):
        return (
            "not_adopted",
            "stage_verified",
            (
                "Gespeicherter Mapping-/Validierungs-/Übergabeschritt nachgewiesen. "
                "Dies bestätigt keine Lesbarkeit oder Richtigkeit des vorgeschlagenen Referenzinhalts. "
                + diagnosis.get("reason", "")
            ),
        )
    if other_values:
        return (
            "wrong_assignment",
            "hypothesis",
            "Ein gleicher Referenztext erscheint in einer anderen Ausgabeposition; Gleichheit beweist keine Fehlzuordnung.",
        )
    if review["eligible"]:
        return (
            "not_recognized",
            "document_verified",
            (
                "Referenzwert im Original unabhängig lesbar bestätigt; im eingefrorenen Feldvergleich fehlt ein nutzbarer Wert. "
                "Die genaue interne Erkennungsstufe ist nicht automatisch bestimmbar."
            ),
        )
    return "unknown", "unknown", "Dokumentverfügbarkeit ungeprüft/unklar und kein eindeutiger kausaler Beleg."


def project(fields, reviews):
    """Sum existing per-field vectors on fixed pairs; unreviewed fields remain in baseline."""
    selected = [r for r in fields if r["reference_contribution"] == 1 and reviews[field_id(r)]["eligible"]]
    count = sum_counts(r["field_counts"] for r in selected)
    baseline = scores(sum_counts(r["field_counts"] for r in fields))
    states = Counter(reviews[field_id(r)]["availability"] for r in fields if r["reference_contribution"] == 1)
    conflicts = sum(
        reviews[field_id(r)].get("reference_agrees") is False
        for r in fields
        if r["reference_contribution"] == 1
    )
    contributions = {
        state: scores(
            sum_counts(
                r["field_counts"]
                for r in fields
                if r["reference_contribution"] == 1 and reviews[field_id(r)]["availability"] == state
            )
        )
        for state in AVAILABILITY
    }
    return dict(
        baseline=baseline,
        readable_reference_subset=scores(count),
        availability_counts=dict(states),
        availability_contributions=contributions,
        readable_reference_conflicts=conflicts,
        expected_fields=baseline["reference_fields"],
        reviewed_fields=sum(n for s, n in states.items() if s in ("readable", "unreadable", "absent")),
        eligible_fields=count["reference_fields"],
        unchecked_in_baseline=True,
        subset_is_conditional=True,
        subset_extras_policy="GT-paired fields only; extras remain in unchanged baseline P/FP/F1",
        unknown_outcomes_not_estimated=True,
    )


def build(output, annotation_path=None):
    output = Path(output)
    envelope = read_json(annotation_path) if annotation_path else {}
    if not isinstance(envelope, dict):
        raise ValueError("Dokumentannotation benötigt ein JSON-Objekt")
    origins = envelope.get("original_documents", {})
    ctx = context(output, origins)
    audit = read_json(output / "scientific/metric_audit.json")
    fields = audit["fields"]
    refs = reference_fields(fields, ctx)
    reviews = load_reviews(annotation_path, refs, ctx)
    evidence = read_json(output / "error_analysis/fields.json")["fields"]
    diagnoses = {(r["method"], case_key(r)): r["analysis"] for r in evidence}
    index = defaultdict(list)
    reference_values = defaultdict(set)
    for row in fields:
        if row["reference_contribution"] == 1:
            reference_values[row["class_id"], row["field"], row["normalized_reference"]].add(
                row["reference_row"]
            )
        value = row.get("original_prediction_value", row.get("prediction_value"))
        if value:
            for target in FIELDS:
                index[
                    row["candidate"],
                    row["class_id"],
                    target,
                    normalize(value, target, ctx["config"].matching),
                ].append(row)
    cases = []
    for row in fields:
        if row["reference_contribution"] != 1:
            continue
        review = reviews[field_id(row)]
        diagnosis = diagnoses.get((row["candidate"], case_key(row)), {})
        if row["candidate"] == "vlm":
            diagnosis = deepcopy(diagnosis)
            diagnosis["auxiliary_ocr_observations"] = diagnosis.pop("observations", [])
            diagnosis["primary_ocr_applicable"] = False
            for stage in diagnosis.get("pipeline_trace", {}).get("stages", []):
                if stage["stage"] == "recognition":
                    stage.update(status="direct_vlm_image_reading_no_separate_ocr", value=None)
                elif stage["stage"] == "model_input":
                    stage.update(status="image_input_no_ocr_submission", value=None)
        missing = row["field_counts"]["missing_fields"] == 1
        others = [
            dict(
                field=p["field"],
                reference_row=p["reference_row"],
                document_id=p["document_id"],
                page_number=p["page_number"],
                value=p.get("original_prediction_value"),
            )
            for p in index[row["candidate"], row["class_id"], row["field"], row["normalized_reference"]]
            if case_key(p) != case_key(row)
            and (
                p["reference_row"] == row["reference_row"]
                and p["field"] != row["field"]
                or len(reference_values[row["class_id"], row["field"], row["normalized_reference"]]) == 1
            )
        ]
        cause, certainty, reason = (
            classify(row, review, diagnosis, others)
            if (missing or review.get("reference_agrees") is False)
            else (None, None, None)
        )
        cases.append(
            dict(
                row,
                field_id=field_id(row),
                availability=review["availability"],
                review=review,
                missing=missing,
                cause=cause,
                certainty=certainty,
                cause_reason=reason,
                diagnosis=diagnosis,
                assignment_hints=others,
                pipeline=pipeline(row["candidate"]),
            )
        )
    methods = sorted({r["candidate"] for r in fields})
    projections = {m: project([r for r in fields if r["candidate"] == m], reviews) for m in methods}
    causes = {
        m: dict(Counter(r["cause"] for r in cases if r["candidate"] == m and r["missing"])) for m in methods
    }
    for method in methods:
        if sum(causes[method].values()) != projections[method]["baseline"]["missing_fields"]:
            raise ValueError("Ursachenanalyse stimmt nicht mit gespeicherten fehlenden Feldbeiträgen überein")
    return dict(
        version=VERSION,
        normalization=ctx["config"].matching.model_dump(),
        binding=ctx["binding"],
        fields=list(refs.values()),
        reviews=reviews,
        cases=cases,
        projections=projections,
        missing_causes=causes,
        annotation_sha256=file_hash(annotation_path) if annotation_path else None,
        field_grading_sha256=file_hash(output / "scientific/metric_audit.json"),
        baseline_unchanged=True,
        matching_unchanged=True,
        implementation_sha256=file_hash(Path(__file__)),
    ), ctx
