"""Post-hoc reference comparison across all pages/files of the same training ID."""

import importlib.metadata
import platform
import re
import time
from collections import defaultdict
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from pydantic import ValidationError

from vorverarbeitung.vorbereiten import document_number

from ..config import ALL_METHODS
from ..excel_columns import field_labels, write_participants_xlsx
from ..io import file_hash, read_json, read_jsonl, write_csv, write_json
from ..output_order import document_order, ordered_rows, page_key
from ..schema import PageResult
from .matching import Prediction
from .metrics import aggregate, course_metrics
from .references import read_reference

VERSION = "roster-levenshtein-v4-source-order"
DEFINITIONS = {
    "output_order": "PDF input order, page number and original output_index. Reference-only rows follow "
                    "the extracted participants separately; reference order never reorders predictions.",
    "score": "100 * 2 * sum(field_similarity) / (assessable_reference_fields + predicted_assessable_fields). "
             "Micro-average over training IDs. Missing fields contribute zero, extra predictions increase the denominator.",
    "similarity": "1 - Levenshtein distance / max(reference length, prediction length), in [0,1]. "
                  "NFC and documented whitespace/case normalization; no spelling repairs. Leading numeric User ID "
                  "zeroes are ignored when matching.ignore_leading_user_id_zeros=true; original values remain unchanged.",
    "matching": "All predictions across all pages/PDFs of one training ID compete for reference rows via "
                "global one-to-one assignment. In best_fit mode first maximize the number of readable paired rows, "
                "then the sum of assessable field similarities, including non-exact readable IDs. Low similarities and "
                "ties remain paired and are flagged for review. Conservative mode retains exact-ID priority and gates.",
    "best_fit_objective": "For N readable predictions and M references, each real pair has utility "
                          "4*min(N,M)+1 plus its assessable field-similarity sum; dummy pairs have utility zero. "
                          "This implements lexicographic maximization of pair count and then total field credit. "
                          "It does not claim to maximize the F1 ratio under pair-dependent masking exclusions.",
    "ambiguity": "If removing a selected pair admits a near-equivalent global solution, best_fit retains the "
                 "evaluation pairing with a review flag; conservative mode discards it. A best-fit pairing is "
                 "not a confirmed identity. The conservative score is reported separately for comparison.",
    "identity_bias": "Alignment itself uses the reference values. The score measures best-aligned roster agreement; "
                     "it is not an independent authentication of participant identity or a calibrated correctness probability.",
    "scope": "Only reference training IDs present in the input PDF filenames enter the denominator. "
             "Unprocessed reference courses and PDFs without a reference course are separately disclosed.",
    "masking": "Empty/masked reference IDs are excluded. Explicit masked/placeholder prediction IDs are excluded and "
               "flagged for confirmation in the PDF. Unknown/missing prediction IDs with readable reference IDs remain errors. "
               "Excluded counts are disclosed because coverage can differ between methods.",
    "raw": "Pure OCR text cannot be scored as participant fields against a roster. ocr_raw remains not_applicable; "
           "use independent page transcripts and evaluate-ocr for CER/WER.",
    "limitations": "A course roster may contain enrolled or completed users who do not appear in the PDF. "
                    "The reference must reflect the intended participants. Signatures are not assessed by these five columns. "
                    "Thresholds are explicit defaults, not validated probabilities; tune only on separate development data.",
}


def identify_course(filename: str, known: set[str]):
    stem = Path(filename).stem.strip()
    if stem in known:
        return stem
    collision = re.fullmatch(r"([0-9]{6})(?:__\d+)?", stem)
    if collision:
        return collision[1]
    try:
        return document_number(filename)
    except ValueError:
        return stem  # Non-numeric course IDs are valid; absent reference groups remain explicitly unassessed.


def map_documents(manifest, known):
    choices, paths = defaultdict(set), defaultdict(list)
    for item in manifest["inputs"]:
        if item["kind"] != "pdf":
            continue
        document_id = item["sha256"]
        choices[document_id].add(identify_course(item["path"], known))
        paths[document_id].append(item["path"])
    mapping, details = {}, []
    courses = set().union(*choices.values()) if choices else set()
    for document_id, options in choices.items():
        course = next(iter(options)) if len(options) == 1 else None
        if course:
            mapping[document_id] = course
        details.append(dict(document_id=document_id, source_files=" | ".join(paths[document_id]),
                            class_id=course, candidate_class_ids=" | ".join(sorted(options)),
                            status="ambiguous_document_course" if course is None else
                                   "mapped" if course in known else "no_reference_course"))
    return mapping, details, courses


def evaluate_run(source: Path, reference_file: Path, config, output_root: Path, methods=None, *, output=None,
                 frozen_reference=None):
    started = time.perf_counter()
    source, reference_file = source.resolve(), reference_file.resolve()
    manifest_path, summary_path = source / "manifest.json", source / "summary.json"
    manifest_hash, summary_hash = file_hash(manifest_path), file_hash(summary_path)
    manifest, summary = read_json(manifest_path), read_json(summary_path)
    documents_in_order = document_order(manifest)
    selected = methods or list(summary)
    allowed = set(ALL_METHODS)
    if not selected or len(selected) != len(set(selected)) or any(name not in summary or name not in allowed for name in selected):
        raise ValueError("Ungültige oder doppelte Methodenauswahl für den Quelllauf")
    if frozen_reference is not None:
        data, reference_hash = frozen_reference
    else:
        reference_hash = file_hash(reference_file)
        data = read_reference(reference_file, config.reference)
        if file_hash(reference_file) != reference_hash:
            raise ValueError("Referenzdatei wurde während des Einlesens geändert")
    known = {person.class_id for person in data.people}
    mapping, documents, input_courses = map_documents(manifest, known)
    known_documents = {row["document_id"] for row in documents}
    source_names = {row["document_id"]: " | ".join(Path(path).name for path in row["source_files"].split(" | "))
                    for row in documents}
    courses_in_scope = known & input_courses
    if not courses_in_scope:
        raise ValueError("Keine gemeinsamen Schulungs-IDs: PDF-Dateinamen und Class ID der Referenz prüfen")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid4().hex[:8]
    output = Path(output) if output else output_root / stamp
    output.mkdir(parents=True, exist_ok=False)
    references = defaultdict(list)
    for person in data.people:
        references[person.class_id].append(person)
    metrics, course_rows, row_details, field_details, all_candidates, unassessed = {}, [], [], [], [], []
    extraction_hashes = {}
    workbook_groups = {method: [] for method in selected}
    for method in selected:
        status = summary[method].get("status", "unknown")
        if summary[method].get("output_kind", "structured") == "ocr_text":
            metrics[method] = dict(status="not_applicable", extraction_status=status, score_percent=None,
                                   reason="Reiner OCR-Text; keine Teilnehmerfeldmetrik gegen Kurslisten")
            continue
        extraction = source / method / "extractions.jsonl"
        extraction_hashes[method] = file_hash(extraction) if extraction.is_file() else None
        predicted, seen, failed_pages, excluded_instructors = defaultdict(list), set(), 0, 0
        pages = []
        for item in read_jsonl(extraction) if extraction.is_file() else []:
            try:
                pages.append(PageResult.model_validate(item))
            except ValidationError:
                raise ValueError("Ungültiges Seitenergebnis; Schema und Methode im lokalen Quelllauf prüfen") from None
        for page in sorted(pages, key=lambda p: page_key(p, documents_in_order)):
            key = page.document_id, page.page_number
            if key in seen or page.method_id != method:
                raise ValueError("Doppelte Seite oder abweichende Methode in den Vorhersagen")
            if page.document_id not in known_documents:
                raise ValueError("Vorhersagen gehören nicht zum Eingabemanifest")
            seen.add(key)
            failed_pages += page.status in ("failed", "unavailable")
            class_id = mapping.get(page.document_id)
            if class_id not in courses_in_scope:
                unassessed.append(dict(method=method, document_id=page.document_id, page_number=page.page_number,
                                       reason="ambiguous_document_course" if class_id is None else "no_reference_course",
                                       participants=len(page.participants)))
                continue
            predicted[class_id].extend(Prediction(page.document_id, page.page_number, index, person)
                                       for index, person in enumerate(page.participants))
            workbook_groups[method].extend(dict(
                class_id=class_id, user_id=person.personnel_number.value,
                first_name=person.first_name.value, last_name=person.last_name.value,
                short_code=person.department.value, source_file=source_names.get(page.document_id, ""),
                document_id=page.document_id, page_number=page.page_number, output_index=index)
                for index, person in enumerate(page.participants))
            excluded_instructors += len(page.excluded_instructors)
        course_scores, conservative_scores = [], []
        for class_id in sorted(courses_in_scope):
            score, rows, fields, candidates = course_metrics(class_id, predicted[class_id], references[class_id],
                                                           config.matching, config.reference)
            course_scores.append(score)
            if config.matching.mode == "best_fit":
                conservative = config.matching.model_copy(update={"mode": "conservative"})
                conservative_scores.append(course_metrics(class_id, predicted[class_id], references[class_id],
                                                            conservative, config.reference)[0])
            course_rows.append(dict(method=method, **{key: value for key, value in score.items()
                                                     if key not in ("fields", "overall")}, **score["overall"]))
            row_details.extend(dict(method=method, source_file=source_names.get(row["document_id"], ""), **row)
                               for row in rows)
            field_details.extend(dict(method=method, source_file=source_names.get(row["document_id"], ""), **row)
                                 for row in fields)
            for candidate in candidates:
                person = predicted[class_id][candidate["prediction_index"]]
                all_candidates.append(dict(method=method, class_id=class_id, **candidate,
                                           document_id=person.document_id, page_number=person.page_number,
                                           output_index=person.index))
        metrics[method] = dict(status="evaluated", extraction_status=status if extraction.is_file() else "missing_extractions_file",
                               **aggregate(course_scores),
                               failed_pages=failed_pages,
                               excluded_instructors=excluded_instructors,
                               source_extraction_file_present=extraction.is_file(),
                               runtime_seconds=summary[method].get("actual_method_wall_seconds"))
        if conservative_scores:
            baseline = aggregate(conservative_scores)
            metrics[method]["conservative_score_percent"] = baseline["score_percent"]
            metrics[method]["conservative_assigned_participants"] = baseline["assigned_participants"]
        if extraction.is_file() and file_hash(extraction) != extraction_hashes[method]:
            raise ValueError("Vorhersagen wurden während der Bewertung verändert")
    scope = dict(input_pdfs=sum(item["kind"] == "pdf" for item in manifest["inputs"]),
                 unique_pdf_contents=len(documents), input_courses=len(input_courses),
                 reference_rows=len(data.people), reference_courses=len(known), courses_compared=len(courses_in_scope),
                 reference_rows_in_scope=sum(len(references[course]) for course in courses_in_scope),
                 reference_rows_outside_input=sum(len(references[course]) for course in known - courses_in_scope),
                 courses_without_reference=sorted(input_courses - known),
                 ambiguous_documents=sum(row["status"] == "ambiguous_document_course" for row in documents),
                 reference_changed_after_snapshot=(file_hash(reference_file) if reference_file.is_file() else None) != reference_hash,
                 merged_identical_reference_rows=sum(row["copies"] - 1 for row in data.duplicate_rows),
                 user_id_column_present=data.user_id_column_present)
    if file_hash(manifest_path) != manifest_hash or file_hash(summary_path) != summary_hash:
        raise ValueError("Quelllauf wurde während des Vergleichs verändert; nach Abschluss erneut vergleichen")
    columns = data.columns or config.reference.columns.model_dump()
    labels = field_labels(columns)
    for row in field_details:
        row["field_label"] = labels[row["field"]]
    methods_in_order = {method: index for index, method in enumerate(selected)}
    row_details = ordered_rows(row_details, documents_in_order, methods_in_order)
    field_details = ordered_rows(field_details, documents_in_order, methods_in_order)
    write_json(output / "metrics.json", dict(version=VERSION, scope=scope, methods=metrics, matching_mode=config.matching.mode,
                                            definitions=DEFINITIONS, columns=columns))
    write_json(output / "reference_snapshot.json", dict(people=[asdict(person) for person in data.people],
                                                        duplicate_rows=data.duplicate_rows, columns=columns))
    write_json(output / "config.json", config.model_dump())
    write_csv(output / "documents.csv", documents)
    write_csv(output / "courses.csv", course_rows, fields=None if course_rows else ["method", "class_id", "score_percent"])
    write_csv(output / "participants.csv", row_details,
              fields=None if row_details else ["method", "class_id", "reference_row", "document_id", "status"])
    write_csv(output / "fields.csv", field_details,
              fields=None if field_details else ["method", "class_id", "field", "reference_value", "prediction_value", "similarity"])
    write_csv(output / "matching_candidates.csv", all_candidates,
              fields=None if all_candidates else ["method", "class_id", "prediction_index", "reference_row", "identity_similarity"])
    write_csv(output / "unassessed_pages.csv", unassessed, fields=["method", "document_id", "page_number", "reason", "participants"])
    write_json(output / "identity.json", dict(version=VERSION, source_run=str(source), reference_file=str(reference_file),
               reference_sha256=reference_hash, reference_sheet=data.sheet, reference_columns=columns,
               source_reference_changed=scope["reference_changed_after_snapshot"],
               manifest_sha256=manifest_hash, summary_sha256=summary_hash,
               extraction_sha256=extraction_hashes,
               source_identity_sha256=file_hash(source / "identity.json") if (source / "identity.json").is_file() else None,
               python=platform.python_version(),
               packages={name: importlib.metadata.version(name) for name in ("numpy", "scipy", "openpyxl", "pydantic", "pyyaml")},
               implementation={path.name: file_hash(path) for path in Path(__file__).parent.glob("*.py")},
               shared_implementation={name: file_hash(Path(__file__).parent.parent / name) for name in
                   ("hybrid_evaluation.py", "evaluation.py", "identifiers.py", "excel_columns.py", "output_order.py")},
               evaluated_at=datetime.now(timezone.utc).isoformat(), duration_seconds=time.perf_counter() - started))
    from .report import render

    write_participants_xlsx(output / "participants.xlsx", workbook_groups, columns,
                            references=(person for person in data.people if person.class_id in courses_in_scope))
    if "vlm" in selected and "ocr_vlm" in selected:
        from ..hybrid_evaluation import compare_fields, export_analysis
        from .matching import normalize

        analysis, paired = compare_fields([r for r in field_details if r["method"] == "vlm"],
            [r for r in field_details if r["method"] == "ocr_vlm"],
            key_fields=("class_id", "reference_row"), normalize=lambda value, field: normalize(value, field, config.matching),
            source="course_scoped_excel_reference")
        export_analysis(output, analysis, paired, summaries=summary, source=source)
    render(output, metrics, scope, course_rows, source, columns=columns, matching=config.matching)
    from .detail_report import render_details

    render_details(output)
    return output, metrics
