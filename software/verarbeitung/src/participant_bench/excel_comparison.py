"""Course-scoped roster agreement. Never used to guide or repair extraction."""

import csv
import html
import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from vorverarbeitung.vorbereiten import document_number

from .evaluation import normalized, prf, ratio
from .excel_columns import field_labels, write_participants_xlsx
from .excel_reference import ExcelConfig, ReferencePerson, read_reference
from .identifiers import normalized_user_id
from .io import file_hash, read_json, read_jsonl, write_csv, write_json
from .output_order import document_order, ordered_rows, page_key
from .schema import PageResult, Participant

FIELDS = {"user_id": "personnel_number", "first_name": "first_name", "last_name": "last_name", "short_code": "department"}
DEFINITIONS = {
    "output_order": "Ausgaben folgen PDF-Eingabereihenfolge, Seite und ursprünglichem Eintragsindex. "
                    "Nur in der Referenz vorhandene Personen folgen anschließend; die Referenz sortiert keine Ausgaben.",
    "scope": "Nur Kurse aus dem Lauf mit Excel-Referenz. Andere Excel-Kurse bleiben außerhalb des Nenners.",
    "course": "Class ID aus sechsstelliger PDF-ID; alternativ explizite document_id/class_id-Zuordnung.",
    "matching": "Exakte eindeutige Kombination Vorname+Nachname+Organization, sonst eindeutige lesbare User ID, "
    "immer innerhalb derselben Class ID. Widersprüche und Mehrdeutigkeiten bleiben ungeklärt. Kein Fuzzy-Matching.",
    "normalization": "NFC, Leerraum vereinheitlichen, casefold für Namen/Organization; führende Nullen numerischer User IDs "
    "werden nur für Zuordnung und Bewertung entfernt. Originalwerte und Class IDs bleiben erhalten.",
    "masked": "Leere/maskierte Excel-IDs und unleserliche oder sichtbar maskierte Vorhersage-IDs werden "
    "aus der ID-Feldmetrik ausgeschlossen. Fehlende Einträge und sonst unbekannte Vorhersagen bleiben Fehler.",
    "identity_bias": "Zur Zuordnung verwendete Felder sind keine unabhängige Erkennungsmessung. "
    "Unabhängiger ID-Exact-Match wird separat nur für über Name+Organization zugeordnete Personen ausgewiesen.",
    "limitations": "Rosterabgleich misst Übereinstimmung mit Excel, keine bestätigte Seitentranskription. "
    "Kursbuchung/Completion beweist keine Anwesenheit. Abweichungen können Referenzunterschiede sein. "
    "Unterschriften werden mit dieser Excel-Datei nicht bewertet.",
    "ambiguity": "Ungeklärte Vorhersagen zählen konservativ als zusätzliche Einträge, nicht zugeordnete "
    "Referenzen als fehlend. Exakte wiederholte Vorhersagen zählen einmal zugeordnet und zusätzlich als Duplikate.",
}


def course_mapping(manifest: dict, mapping_file: Path | None) -> tuple[dict, list[dict]]:
    explicit = {}
    if mapping_file:
        with mapping_file.open(encoding="utf-8-sig", newline="") as stream:
            reader = csv.DictReader(stream)
            if not {"document_id", "class_id"}.issubset(reader.fieldnames or []):
                raise ValueError("Kurszuordnung benötigt die Spalten document_id und class_id")
            for row in reader:
                key, value = row["document_id"].strip(), row["class_id"].strip()
                if not key or not value or (key in explicit and explicit[key] != value):
                    raise ValueError("Leere oder widersprüchliche Kurszuordnung")
                explicit[key] = value
    candidates, sources = defaultdict(set), defaultdict(list)
    for item in manifest["inputs"]:
        if item["kind"] != "pdf":
            continue
        document_id = item["sha256"]
        sources[document_id].append(item["path"])
        stem = Path(item["path"]).stem
        try:
            candidates[document_id].add(stem if re.fullmatch(r"[0-9]{6}", stem) else document_number(item["path"]))
        except ValueError:
            pass
    if set(explicit) - set(sources):
        raise ValueError("Kurszuordnung enthält Dokumente außerhalb dieses Laufs")
    mapping, details = {}, []
    for document_id, paths in sources.items():
        choices = candidates[document_id]
        value = explicit.get(document_id) or (next(iter(choices)) if len(choices) == 1 else "")
        if value:
            mapping[document_id] = value
        details.append({
            "document_id": document_id, "source_paths": " | ".join(paths), "class_id": value,
            "status": "explicit" if document_id in explicit else "mapped" if value else "review_required",
        })
    return mapping, details


def prediction_values(person: Participant) -> dict[str, str | None]:
    return {
        field: getattr(person, model_field).value if getattr(person, model_field).state == "read" else None
        for field, model_field in FIELDS.items()
    }


def assign(predictions: list[dict], references: list[ReferencePerson], config: ExcelConfig):
    ids, names = defaultdict(set), defaultdict(set)
    for index, reference in enumerate(references):
        if config.usable_id(reference.user_id):
            ids[normalized_user_id(reference.user_id)].add(index)
        if reference.name_key:
            names[reference.name_key].add(index)
    proposed, issues = defaultdict(list), {}
    for index, prediction in enumerate(predictions):
        values = prediction_values(prediction["person"])
        identity = tuple(normalized(values[k], "name") for k in ("first_name", "last_name", "short_code"))
        by_name = names.get(identity, set()) if all(identity) else set()
        by_id = ids.get(normalized_user_id(values["user_id"]), set()) if config.usable_id(values["user_id"]) else set()
        if by_name and by_id and not by_name.intersection(by_id):
            issues[index] = "identity_conflict"
            continue
        candidates = by_name.intersection(by_id) if by_name and by_id else by_name or by_id
        if len(candidates) == 1:
            source = "name_short_code" if len(by_name) == 1 else "user_id"
            proposed[next(iter(candidates))].append((index, source))
        else:
            issues[index] = "ambiguous" if candidates else "extra"
    matches = {}
    for reference_index, items in proposed.items():
        if len(items) > 1:
            fingerprints = {
                tuple((normalized_user_id(getattr(predictions[i]["person"], f).value) if f == "personnel_number"
                       else getattr(predictions[i]["person"], f).value, getattr(predictions[i]["person"], f).state)
                      for f in FIELDS.values())
                for i, _ in items
            }
            if len(fingerprints) != 1:
                issues.update({i: "ambiguous" for i, _ in items})
                continue
            issues.update({i: "duplicate_prediction" for i, _ in items[1:]})
        matches[reference_index] = items[0]
    return matches, issues


def compare_course(predictions: list[dict], references: list[ReferencePerson], config: ExcelConfig):
    matches, issues = assign(predictions, references, config)
    counts = {field: Counter() for field in FIELDS}
    details, rows, sources = [], [], Counter()
    independent_ids = Counter()
    for index, reference in enumerate(references):
        match = matches.get(index)
        prediction = predictions[match[0]] if match else None
        person = prediction["person"] if prediction else None
        source = match[1] if match else "missing"
        sources[source] += 1
        rows.append({
            "class_id": reference.class_id, "excel_row": reference.row_number,
            "document_id": prediction["document_id"] if prediction else "",
            "page_number": prediction["page_number"] if prediction else "",
            "prediction_index": prediction["index"] if prediction else "",
            "status": "matched" if match else "missing", "matching_source": source,
        })
        for field, model_field in FIELDS.items():
            expected = getattr(reference, field)
            actual = getattr(person, model_field) if person else None
            eligible = bool(expected.strip())
            reason = "" if eligible else "Referenzfeld fehlt"
            if field == "user_id":
                if not config.usable_id(expected):
                    eligible, reason = False, "Excel-ID fehlt oder ist maskiert"
                elif actual and (actual.state == "illegible" or (actual.value and not config.usable_id(actual.value))):
                    eligible, reason = False, "Vorhersage-ID unleserlich oder maskiert"
            same = None
            if eligible:
                known = actual is not None and actual.state == "read"
                same = bool(known and (
                    normalized_user_id(actual.value) == normalized_user_id(expected) if field == "user_id"
                    else normalized(actual.value, "name") == normalized(expected, "name")
                ))
                counts[field].update(denominator=1, correct=int(same), fn=int(not same), fp=int(known and not same))
                if field == "user_id" and source == "name_short_code":
                    independent_ids.update(denominator=1, correct=int(same))
            else:
                counts[field]["excluded"] += 1
            details.append({
                **rows[-1], "field": field, "reference_value": expected,
                "prediction_value": actual.value if actual else None,
                "prediction_state": actual.state if actual else "missing",
                "assessable": eligible, "exact": same, "exclusion_reason": reason,
                "used_for_matching": source == "user_id" and field == "user_id"
                or source == "name_short_code" and field != "user_id",
            })
    for index, status in issues.items():
        prediction = predictions[index]
        rows.append({
            "class_id": prediction["class_id"], "excel_row": "", "document_id": prediction["document_id"],
            "page_number": prediction["page_number"], "prediction_index": prediction["index"],
            "status": status, "matching_source": "unresolved",
        })
        for field, value in prediction_values(prediction["person"]).items():
            counts[field]["fp"] += int(bool(value) and (field != "user_id" or config.usable_id(value)))
    documents = {doc: i for i, doc in enumerate(dict.fromkeys(p["document_id"] for p in predictions))}
    return counts, independent_ids, ordered_rows(rows, documents), ordered_rows(details, documents), sources


def evaluate_method(predictions: list[dict], references: list[ReferencePerson], mapping: dict, config: ExcelConfig):
    by_course, reference_courses = defaultdict(list), defaultdict(list)
    covered_courses = set(mapping.values())
    for reference in references:
        if reference.class_id in covered_courses:
            reference_courses[reference.class_id].append(reference)
    skipped, usable_predictions = [], []
    for prediction in predictions:
        class_id = mapping.get(prediction["document_id"], "")
        prediction["class_id"] = class_id
        if not class_id or class_id not in reference_courses:
            skipped.append({
                "class_id": class_id, "document_id": prediction["document_id"],
                "page_number": prediction["page_number"], "prediction_index": prediction["index"],
                "excel_row": "", "matching_source": "unresolved",
                "status": "unmapped_course" if not class_id else "no_excel_course",
            })
        else:
            by_course[class_id].append(prediction)
            usable_predictions.append(prediction)
    totals = {field: Counter() for field in FIELDS}
    independent, sources = Counter(), Counter()
    rows, details = skipped[:], []
    for class_id, course_references in reference_courses.items():
        counts, ids, matches, fields, origins = compare_course(by_course[class_id], course_references, config)
        for field in FIELDS:
            totals[field].update(counts[field])
        independent.update(ids)
        sources.update(origins)
        rows.extend(matches)
        details.extend(fields)
    statuses = Counter(row["status"] for row in rows)
    matched, reference_count = statuses["matched"], sum(map(len, reference_courses.values()))
    scores = {
        "counts": {
            "reference_rows": reference_count, "reference_rows_outside_run": len(references) - reference_count,
            "predictions": len(predictions), "assessed_predictions": len(usable_predictions),
            "courses_compared": len(reference_courses),
            "courses_without_reference": len(covered_courses - set(reference_courses)),
            **dict(statuses),
        },
        "participant_assignment": prf(matched, len(usable_predictions) - matched, reference_count - matched),
        "matching_sources": dict(sources),
        "fields": {
            field: {
                "exact_match": ratio(count["correct"], count["denominator"]),
                "prf": prf(count["correct"], count["fp"], count["fn"]),
                "excluded": count["excluded"],
            } for field, count in totals.items()
        },
        "independent_user_id_exact_match": ratio(independent["correct"], independent["denominator"]),
    }
    documents = {doc: i for i, doc in enumerate(dict.fromkeys(p["document_id"] for p in predictions))}
    return scores, ordered_rows(rows, documents), ordered_rows(details, documents)


def compare_run(run: Path, excel: Path, config: ExcelConfig, *, output: Path | None = None,
                mapping_file: Path | None = None, methods: list[str] | None = None) -> tuple[Path, dict]:
    columns = {}
    references, sheet = read_reference(excel, config, column_names=columns)
    labels = field_labels(columns)
    mapping, mapping_rows = course_mapping(read_json(run / "manifest.json"), mapping_file)
    documents_in_order = document_order(read_json(run / "manifest.json"))
    if not set(mapping.values()).intersection(r.class_id for r in references):
        raise ValueError("Keine gemeinsamen Class IDs: PDF-Dateinamen bzw. explizite Kurszuordnung prüfen")
    run_summary = read_json(run / "summary.json")
    selected = methods or [name for name, summary in run_summary.items()
                           if summary.get("output_kind", "structured") == "structured"]
    if not selected or len(selected) != len(set(selected)) or any(m not in run_summary for m in selected):
        raise ValueError("Ungültige oder doppelte Methodenauswahl für diesen Lauf")
    metrics, matches, fields = {}, [], []
    workbook_groups = {}
    sources = {item["sha256"]: item["path"] for item in read_json(run / "manifest.json")["inputs"]
               if item["kind"] == "pdf"}
    for method in selected:
        if run_summary[method].get("output_kind") == "ocr_text":
            raise ValueError("Reiner OCR-Text kann nicht als strukturierte Teilnehmerliste mit Excel verglichen werden")
        predictions, seen = [], set()
        extraction = run / method / "extractions.jsonl"
        pages = [PageResult.model_validate(data) for data in read_jsonl(extraction)] if extraction.exists() else []
        for page in sorted(pages, key=lambda p: page_key(p, documents_in_order)):
            key = (page.document_id, page.page_number)
            if key in seen or page.method_id != method:
                raise ValueError("Doppelte Seite oder abweichende Methode in den Extraktionsergebnissen")
            seen.add(key)
            predictions.extend({"person": person, "document_id": page.document_id,
                                "page_number": page.page_number, "index": i}
                               for i, person in enumerate(page.participants))
        workbook_groups[method] = [dict(
            class_id=mapping.get(item["document_id"]),
            **{field: getattr(item["person"], model_field).value for field, model_field in FIELDS.items()},
            document_id=item["document_id"], source_file=sources.get(item["document_id"]),
            page_number=item["page_number"], output_index=item["index"]) for item in predictions]
        score, rows, details = evaluate_method(predictions, references, mapping, config)
        score["counts"]["unmapped_documents"] = sum(row["status"] == "review_required" for row in mapping_rows)
        score["extraction_status"] = run_summary[method]["status"]
        metrics[method] = score
        matches.extend(dict(method=method, **row) for row in rows)
        fields.extend(dict(method=method, field_label=labels[row["field"]], **row) for row in details)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid4().hex[:8]
    output = output or run / "excel-comparison" / stamp
    if output.exists() and any(output.iterdir()):
        raise ValueError("Abgleich-Ausgabeordner muss leer sein")
    output.mkdir(parents=True, exist_ok=True)
    write_json(output / "metrics.json", {"methods": metrics, "definitions": DEFINITIONS, "columns": columns})
    write_participants_xlsx(output / "participants.xlsx", workbook_groups, columns,
                            references=(r for r in references if r.class_id in set(mapping.values())))
    write_json(output / "identity.json", {
        "excel_sha256": file_hash(excel), "sheet": sheet, "config": config.model_dump(), "reference_columns": columns,
        "run_manifest_sha256": file_hash(run / "manifest.json"),
        "mapping_sha256": file_hash(mapping_file) if mapping_file else None,
        "extractions_sha256": {method: file_hash(run / method / "extractions.jsonl")
                               if (run / method / "extractions.jsonl").exists() else None for method in selected},
    })
    summary = []
    for method, score in metrics.items():
        summary.append({
            "method": method, **score["counts"],
            "extraction_status": score["extraction_status"],
            **{name: score["participant_assignment"][name]["value"] for name in ("precision", "recall", "f1")},
            **{field + "_exact_match": values["exact_match"]["value"] for field, values in score["fields"].items()},
            "independent_user_id_exact_match": score["independent_user_id_exact_match"]["value"],
        })
    for name, rows in (("summary", summary), ("matches", matches), ("field_comparison", fields),
                       ("course_mapping", mapping_rows)):
        write_csv(output / f"{name}.csv", rows)
    def table(rows: list[dict]) -> str:
        if not rows:
            return "<p>Keine Einträge.</p>"
        def display(row, key):
            value = row.get(key, "")
            return html.escape(str(labels.get(value, value) if key == "field" else value))
        keys = list(dict.fromkeys(key for row in rows for key in row))
        return "<table><tr>" + "".join(f"<th>{html.escape(labels.get(k, k))}</th>" for k in keys) + "</tr>" + "".join(
            "<tr>" + "".join(f"<td>{display(row, k)}</td>" for k in keys) + "</tr>"
            for row in rows
        ) + "</table>"
    report = '<!doctype html><html lang="de"><meta charset="utf-8">' + (
        '<meta http-equiv="Content-Security-Policy" content="default-src \'none\'; style-src \'unsafe-inline\'">'
        '<title>Excel-Abgleich</title><style>body{font-family:sans-serif}td,th{border:1px solid #ccc;padding:6px}'
        'table{border-collapse:collapse}</style><h1>Excel-Abgleich</h1>'
        '<p><a href="participants.xlsx">Teilnehmer und Referenz mit Original-Spaltennamen als Excel-Datei</a></p>'
    ) + table(summary) + "<h2>Ungeklärte und abweichende Zuordnungen</h2>" + table(
        [row for row in matches if row["status"] != "matched"]
    ) + "<h2>Abweichende oder nicht bewertbare Felder</h2>" + table(
        [row for row in fields if row["exact"] is not True]
    ) + "<h2>Definitionen und Grenzen</h2>" + "".join(
        f"<p><b>{html.escape(key)}</b>: {html.escape(value)}</p>" for key, value in DEFINITIONS.items()
    ) + "</html>"
    (output / "report.html").write_text(report, encoding="utf-8")
    print(f"Excel-Abgleich: {(output / 'report.html').resolve()}")
    for method, score in metrics.items():
        print(f"{method}: " + json.dumps(score["counts"], ensure_ascii=False))
    return output, metrics
