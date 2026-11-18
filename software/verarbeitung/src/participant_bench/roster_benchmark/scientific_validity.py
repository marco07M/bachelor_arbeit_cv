"""Additional diagnostics on fixed decisions; no extraction, rematching or score replacement."""

import re
from collections import Counter, defaultdict
from datetime import datetime

from ..io import file_hash, read_json, read_jsonl, write_json
from .field_assessment import alignment_unclear
from .matching import FIELDS, normalize
from .metrics import aggregate_participants, divide, scores, sum_counts

VERSION = "scientific-validity-v1"
ERROR_CAUSES = {
    "document": "Dokumentinhalt fehlt / unleserlich",
    "perception": "OCR / Wahrnehmung (Stufe offen)",
    "assignment": "Struktur / Spalten / Teilnehmerzuordnung",
    "validation": "Validierung / Filter / Übergabe",
    "extra": "Zusätzliche unbelegte Extraktion; Halluzination unbewiesen",
    "reference": "Referenz / Matching",
    "unknown": "Ursache unbekannt",
}


def anls_credit(row):
    """ST-VQA distance cutoff: NL < .5; equality receives zero, on existing normalized pairs."""
    value = row.get("similarity") or 0.0
    return value if row["reference_contribution"] and value > 0.5 else 0.0


def field_projection(fields, *, anls=False):
    result = scores(sum_counts(r["field_counts"] for r in fields))
    credit = sum(anls_credit(r) for r in fields)
    result.update(
        anls_enabled=anls,
        anls_credit=credit if anls else None,
        anls=divide(credit, result["reference_fields"]) if anls else None,
    )
    return result


def row_consistency(participants, fields, config):
    """All three readable identity fields in the ORIGINAL roles, on one reliable fixed pair."""
    indexed = defaultdict(dict)
    for field in fields:
        if field.get("reference_row") is not None:
            indexed[field["class_id"], field["reference_row"]][field["field"]] = field
    cases = []
    for row in participants:
        if row.get("reference_row") is None:
            continue
        fs = indexed[row["class_id"], row["reference_row"]]
        eligible = all(fs[f]["reference_state"] == "read" for f in ("first_name", "last_name", "user_id"))
        original_exact = all(
            normalize(fs[f].get("original_prediction_value"), f, config) == fs[f]["normalized_reference"]
            for f in ("first_name", "last_name", "user_id")
        )
        correct = bool(eligible and row.get("identity_exact") and original_exact)
        cases.append(
            dict(
                class_id=row["class_id"],
                reference_row=row["reference_row"],
                eligible=eligible,
                correct=correct,
                missing=row["status"] == "missing",
                ambiguous_anchor=not row.get("identity_assessable"),
                reason="Alle drei Identitätsfelder in Originalrollen exakt auf zuverlässigem Paar."
                if correct
                else "Nicht alle drei Referenzfelder lesbar."
                if not eligible
                else "Fehlende, abweichende oder unsicher zugeordnete Identitätsfelder; kein Zeilentreffer.",
            )
        )
    n, c = sum(r["eligible"] for r in cases), sum(r["correct"] for r in cases)
    return dict(
        eligible_rows=n,
        correct_rows=c,
        row_consistency=divide(c, n),
        unassessable_rows=len(cases) - n,
        ambiguous_reference_rows=sum(r["ambiguous_anchor"] for r in cases),
        cases=cases,
    )


def page_template(ctx, participants):
    refs = sorted(
        {(r["class_id"], r["reference_row"]) for r in participants if r.get("reference_row") is not None}
    )
    return dict(
        version="page-strata-v1",
        binding=ctx["binding"],
        pages=[
            dict(
                document_id=d,
                page_number=p,
                role="unknown",
                header="unknown",
                scan_quality="unknown",
                independent_of_predictions=False,
                reviewer="",
                reviewed_at="",
                note="",
            )
            for d, doc in ctx["documents"].items()
            for p in doc["pages"]
        ],
        participants=[
            dict(
                class_id=c,
                reference_row=r,
                document_id=None,
                page_number=None,
                independent_of_predictions=False,
                reviewer="",
                reviewed_at="",
                anchor_note="",
            )
            for c, r in refs
        ],
    )


def _provenance(item, note):
    if item.get("independent_of_predictions") is not True or not all(
        isinstance(item.get(k), str) and item[k].strip() for k in ("reviewer", "reviewed_at", note)
    ):
        raise ValueError("Seitenstrata benötigen unabhängige Prüfung mit Autor, Datum und Beleg")
    try:
        datetime.fromisoformat(item["reviewed_at"])
    except (ValueError, TypeError):
        raise ValueError("Seitenprüfung benötigt ein ISO-Datum") from None


def load_pages(path, ctx, participants):
    template = page_template(ctx, participants)
    data = read_json(path) if path else template
    if (
        not isinstance(data, dict)
        or data.get("version") != template["version"]
        or data.get("binding") != ctx["binding"]
        or not isinstance(data.get("pages"), list)
        or not isinstance(data.get("participants"), list)
    ):
        raise ValueError("Seitenannotation gehört nicht zu PDF-/Referenzsnapshot oder ist ungültig")
    valid = {(p["document_id"], p["page_number"]) for p in template["pages"]}
    refs = {(p["class_id"], p["reference_row"]) for p in template["participants"]}
    pages, locations = {}, {}
    for p in data["pages"]:
        if not isinstance(p, dict):
            raise ValueError("Ungültige Seitenannotation")
        key = (p.get("document_id"), p.get("page_number"))
        if not isinstance(key[0], str) or type(key[1]) is not int or key not in valid or key in pages:
            raise ValueError("Fremde oder doppelte Seite")
        if (
            p.get("role") not in {"first", "continuation", "non_participant", "unknown"}
            or p.get("header") not in {"present", "absent", "unknown"}
            or p.get("scan_quality") not in {"clean", "degraded", "unknown"}
        ):
            raise ValueError("Unbekanntes Seitenstratum")
        if any(p[k] != "unknown" for k in ("role", "header", "scan_quality")):
            _provenance(p, "note")
            if not ctx["documents"][key[0]]["verified"]:
                raise ValueError("Seitenprüfung benötigt das hashgeprüfte Original")
        pages[key] = p
    for p in template["pages"]:
        pages.setdefault((p["document_id"], p["page_number"]), p)
    for d in ctx["documents"]:
        first = [p["page_number"] for p in pages.values() if p["document_id"] == d and p["role"] == "first"]
        if (
            len(first) > 1
            or first
            and any(
                p["role"] == "continuation" and p["page_number"] <= first[0]
                for p in pages.values()
                if p["document_id"] == d
            )
        ):
            raise ValueError("Widersprüchliche erste Teilnehmerseite / Folgeseite")
    seen = set()
    for p in data["participants"]:
        if not isinstance(p, dict):
            raise ValueError("Ungültige Referenzlokalisierung")
        key = (p.get("class_id"), p.get("reference_row"))
        if not isinstance(key[0], str) or type(key[1]) is not int or key not in refs or key in seen:
            raise ValueError("Fremde oder doppelte Referenzlokalisierung")
        seen.add(key)
        if p.get("document_id") is None and p.get("page_number") is None:
            continue
        _provenance(p, "anchor_note")
        site = (p.get("document_id"), p.get("page_number"))
        if (
            not isinstance(site[0], str)
            or type(site[1]) is not int
            or site not in valid
            or site[0] not in ctx["courses"].get(key[0], [])
            or not ctx["documents"][site[0]]["verified"]
            or pages[site]["role"] == "non_participant"
        ):
            raise ValueError("Referenzperson gehört nicht zur geprüften Originalseite")
        locations[key] = site
    return pages, locations, template


def page_strata(participants, fields, pages, locations, *, anls=False):
    """Unknown-location FNs stay in unknown, never disappear through prediction-side slicing."""
    result = []
    reference_rows = [r for r in participants if r.get("reference_row") is not None]
    for feature in ("position", "scan_quality"):
        levels = (
            ("first", "continuation_headerless", "continuation_header", "continuation_unknown", "unknown")
            if feature == "position"
            else ("clean", "degraded", "unknown")
        )
        for level in levels:
            selected = []
            for row in reference_rows:
                site = locations.get((row["class_id"], row["reference_row"]))
                p = pages.get(site, {})
                value = (
                    p.get("scan_quality", "unknown")
                    if feature == "scan_quality"
                    else (
                        "first"
                        if p.get("role") == "first"
                        else "continuation_"
                        + {"absent": "headerless", "present": "header"}.get(p.get("header"), "unknown")
                        if p.get("role") == "continuation"
                        else "unknown"
                    )
                )
                if value == level:
                    selected.append(row)
            keys = {(r["class_id"], r["reference_row"]) for r in selected}
            fs = [r for r in fields if (r["class_id"], r.get("reference_row")) in keys]
            sites = {locations[k] for k in keys if k in locations}
            result.append(
                dict(
                    feature=feature,
                    level=level,
                    participants=len(selected),
                    pages=len(sites),
                    documents=len({s[0] for s in sites}),
                    overall=field_projection(fs, anls=anls),
                    participant_quality=aggregate_participants(r["participant_counts"] for r in selected),
                    fields={
                        f: field_projection([r for r in fs if r["field"] == f], anls=anls) for f in FIELDS
                    },
                )
            )
    return result


def evidence_axes(row, missing_case=None):
    """Multiple independent axes; counts of findings must not be added as unique field errors."""
    axes = []
    if missing_case:
        state = missing_case["availability"]
        if state in ("absent", "unreadable"):
            axes.append(("document", "document_verified", state))
        if missing_case["review"].get("reference_agrees") is False:
            axes.append(("reference", "document_verified", "reference_document_difference"))
        cause = missing_case.get("cause")
        if cause in ("reference_matching", "wrong_assignment") and not axes:
            axes.append(("reference" if cause == "reference_matching" else "assignment", "hypothesis", cause))
        if cause == "not_recognized":
            axes.append(("perception", "pipeline_unresolved", "readable_but_missing_final_value"))
    diagnosis = row.get("cause", {})
    if missing_case:
        diagnosis = missing_case.get("diagnosis", {}) or diagnosis
    category = diagnosis.get("category")
    mapped = {
        "name_swap": "assignment",
        "column_mapping": "assignment",
        "validation": "validation",
        "not_submitted": "validation",
        "model_omission": "validation",
        "ocr_suspected": "perception",
    }
    if category in mapped and not (
        row["candidate"] == "vlm" and category in ("not_submitted", "model_omission")
    ):
        axes.append(
            (mapped[category], diagnosis.get("certainty", "unknown"), str(diagnosis.get("stage", "unknown")))
        )
    if row.get("result") == "extra":
        axes.append(("extra", "reference_only", "additional_output_not_visual_hallucination_proof"))
    if row.get("category") in ("wrong_field", "other_reference"):
        axes.append(("assignment", "hypothesis", "equal_value_elsewhere_not_causal_proof"))
    if alignment_unclear(row):
        axes.append(("reference", "hypothesis", "ambiguous_reference_alignment"))
    return [dict(cause=c, certainty=s, stage=t) for c, s, t in sorted(set(axes))] or [
        dict(cause="unknown", certainty="unknown", stage="unknown")
    ]


def raw_text_coverage(pages, reviews, refs, config):
    """Full normalized field string at token boundaries, no CER/WER, identity or precision claim."""
    lookup = {(p.document_id, p.page_number): p for p in pages if p.output_kind == "ocr_text"}
    cases = []
    for key, review in reviews.items():
        loc = review.get("locations") or []
        if review["availability"] != "readable" or len(loc) != 1:
            continue
        site = (loc[0]["document_id"], loc[0]["page_number"])
        p = lookup.get(site)
        expected = normalize(review["document_value"], refs[key]["field"], config)
        observed = normalize(p.page_text, refs[key]["field"], config) if p else ""
        found = bool(expected and re.search(r"(?<!\w)" + re.escape(expected) + r"(?!\w)", observed))
        if p and refs[key]["field"] == "user_id" and expected.isdecimal():
            found = any(
                normalize(token, "user_id", config) == expected
                for token in re.findall(r"(?<!\w)[0-9]+(?!\w)", p.page_text or "")
            )
        cases.append(
            dict(
                field_id=key,
                document_id=site[0],
                page_number=site[1],
                field=refs[key]["field"],
                found=found,
                page_available=p is not None,
            )
        )
    n, c = len(cases), sum(r["found"] for r in cases)
    return dict(
        fields=n,
        found=c,
        text_findability=divide(c, n),
        cases=cases,
        missing_pages=sum(not r["page_available"] for r in cases),
        note="Unabhängig lesbare Originalwerte; jede Feldzeichenfolge auf ihrer Originalseite. Keine Zeilenidentität, keine Präzision, kein CER/WER; Signaturen ausgeschlossen.",
    )


def build(output, payload, availability, ctx, *, anls=False, page_annotations=None):
    audit = payload["metric_audit"]
    pages, locations, template = load_pages(page_annotations, ctx, audit["participants"])
    missing = {
        (r["candidate"], r["class_id"], r["reference_row"], r["field"]): r for r in availability["cases"]
    }
    methods, modes, fields, errors = [], [], [], []
    all_participants = payload["metric_audit"]["participants"]
    reference_scopes = {
        c: {
            (
                r["class_id"],
                r["reference_row"],
                r["field"],
                r.get("reference_state"),
                r.get("normalized_reference"),
            )
            for r in audit["fields"]
            if r["candidate"] == c and r.get("reference_row") is not None
        }
        for c in {r["candidate"] for r in audit["fields"]}
    }
    if reference_scopes and any(
        v != next(iter(reference_scopes.values())) for v in reference_scopes.values()
    ):
        raise ValueError(
            "Zusatzdiagnostik benötigt dieselben Referenzfelder und Normalisierungen aller strukturierten Verfahren"
        )
    for candidate in sorted({r["candidate"] for r in audit["fields"]}):
        fs = [r for r in audit["fields"] if r["candidate"] == candidate]
        ps = [r for r in all_participants if r["candidate"] == candidate]
        methods.append(
            dict(
                candidate=candidate,
                overall=field_projection(fs, anls=anls),
                rows=row_consistency(ps, fs, ctx["config"].matching),
                strata=page_strata(ps, fs, pages, locations, anls=anls),
                unassigned=field_projection([r for r in fs if r.get("reference_row") is None], anls=anls),
            )
        )
        for f in fs:
            fields.append(
                dict(
                    candidate=candidate,
                    class_id=f["class_id"],
                    reference_row=f.get("reference_row"),
                    document_id=f.get("document_id"),
                    page_number=f.get("page_number"),
                    field=f["field"],
                    ground_truth=f.get("reference_value"),
                    prediction=f.get("original_prediction_value"),
                    evaluation_status=f.get("evaluation_status"),
                    similarity=f.get("detected_similarity"),
                    anls_credit=anls_credit(f) if anls else None,
                    reference_contribution=f["reference_contribution"],
                )
            )
            if f.get("result") not in ("missing", "incorrect", "extra"):
                continue
            independent_site = locations.get((f["class_id"], f.get("reference_row")))
            site = independent_site or (f.get("document_id") or "unknown", f.get("page_number") or "unknown")
            axes = evidence_axes(
                f, missing.get((candidate, f["class_id"], f.get("reference_row"), f["field"]))
            )
            errors.append(
                dict(
                    candidate=candidate,
                    class_id=f["class_id"],
                    document_id=site[0],
                    page_number=site[1],
                    location_basis="independent_reference" if independent_site else "prediction_or_unknown",
                    field=f["field"],
                    result=f["result"],
                    axes=axes,
                )
            )
    tallies = Counter(
        (
            r["candidate"],
            r["document_id"],
            r["page_number"],
            r["field"],
            a["cause"],
            a["certainty"],
            a["stage"],
        )
        for r in errors
        for a in r["axes"]
    )
    error_groups = [
        dict(
            zip(
                ("candidate", "document_id", "page_number", "field", "cause", "certainty", "stage"),
                k,
                strict=True,
            ),
            count=v,
        )
        for k, v in sorted(tallies.items(), key=lambda kv: tuple(map(str, kv[0])))
    ]
    # All variants were evaluated by the existing matcher. This is a counter projection only.
    from .detail_report import read_csv

    by_mode_participants = read_csv(output / "scientific/participant_cases.csv")
    for row in payload["overview"]:
        if not row.get("mode"):
            continue
        ps = [
            r for r in by_mode_participants if r["candidate"] == row["candidate"] and r["mode"] == row["mode"]
        ]
        modes.append(
            dict(
                candidate=row["candidate"],
                mode=row["mode"],
                exact_recall=row["exact_recall"],
                exact_f1=row["exact_f1"],
                soft_f1=row["soft_f1"],
                predicted_fields=row["predicted_fields"],
                assigned=sum(r["status"] == "matched" for r in ps),
                name_swaps=row["name_swapped_participants"],
                participant_recall=row["participant_quality"]["participant_recall"],
            )
        )
    result = dict(
        version=VERSION,
        anls_enabled=anls,
        anls_distance_threshold=0.5,
        anls_rule="NL < 0.5; missing=0; denominator=R; fixed original_roles; extras only in global F1",
        normalization=ctx["config"].matching.model_dump(),
        binding=ctx["binding"],
        page_annotation_sha256=file_hash(page_annotations) if page_annotations else None,
        localized_reference_participants=len(locations),
        page_annotations=list(pages.values()),
        methods=methods,
        matching=modes,
        fields=fields,
        errors=errors,
        error_groups=error_groups,
        causes=ERROR_CAUSES,
        baseline_unchanged=True,
        matching_unchanged=True,
        reference_scope_equal=True,
    )
    result["raw_text"] = []
    from pathlib import Path

    from ..schema import PageResult

    for candidate, spec in payload["identity"]["sources"].items():
        if not any(
            r["candidate"] == candidate and r.get("reason") == "diagnostic_raw_text"
            for r in payload["overview"]
        ):
            continue
        path = Path(spec["source"]) / spec["method"] / "extractions.jsonl"
        raw_pages = [PageResult.model_validate(r) for r in read_jsonl(path)] if path.is_file() else []
        result["raw_text"].append(
            dict(
                candidate=candidate,
                **raw_text_coverage(
                    raw_pages,
                    availability["reviews"],
                    {r["field_id"]: r for r in availability["fields"]},
                    ctx["config"].matching,
                ),
            )
        )
    manifest = read_json(ctx["source"] / "manifest.json")
    result["image_observations"] = [
        {
            k: p.get(k)
            for k in (
                "document_id",
                "page_number",
                "width",
                "height",
                "pdf_rotation_metadata",
                "additional_rotation_clockwise",
                "curation_rotation_clockwise",
                "orientation_status",
            )
        }
        | {"scan_dpi": None, "scan_quality": "not_inferred"}
        for p in manifest.get("pages", [])
        if p.get("document_id") in ctx["documents"]
    ]
    folder = output / "scientific"
    write_json(folder / "page_annotations.template.json", template)
    write_json(
        folder / "page_annotations.snapshot.json",
        read_json(page_annotations) if page_annotations else template,
    )
    write_json(folder / "validity.json", result)
    return result
