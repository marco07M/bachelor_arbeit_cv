"""Read-only, local stage tracing. Absent OCR text alone never proves an OCR cause."""

import html
import json
import unicodedata
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image, ImageDraw

from .column_headers import ORGANIZATION_ALIASES, field_roles
from .io import file_hash, read_json, read_jsonl, write_csv, write_json
from .structure_assignment import header_bands, native_items, prepare_rows, rectangle
from .structured_mapping import table_rows

VERSION = "organization-stage-diagnosis-v1"
CATEGORIES = ("ocr_detection_failed", "ocr_recognition_failed", "table_structure_failed",
              "cell_assignment_failed", "column_mapping_failed", "llm_extraction_failed", "normalization_failed", "unknown")


def normalized(value):
    return " ".join(unicodedata.normalize("NFC", value or "").split())


def field_value(value):
    if isinstance(value, dict):
        return value.get("value")
    if isinstance(value, (tuple, list)):
        return value[-1] if value else None
    return value


def reference_ocr_cause(recognized, value, box=None, method="docling"):
    """Only a manually provided field box can disambiguate detection and recognition."""
    cells, _ = native_items(recognized, "paddle_structure" if method.startswith("paddle") else "docling")
    if value and any(normalized(value) in normalized(c["text"]) for c in cells):
        return None
    if not box or not value:
        return "unknown"
    detection = recognized.get("detection_boxes")
    if detection is None and method.startswith("paddle"):
        native = recognized.get("native", {})
        raw_boxes = native.get("overall_ocr_res", {}).get("dt_polys")
        if raw_boxes is not None and native.get("width") and native.get("height"):
            detection = [rectangle(b, native["width"], native["height"]) for b in raw_boxes]
    if detection is None:
        return "unknown"
    def intersects(candidate):
        return candidate and min(box["x1"], candidate["x1"]) > max(box["x0"], candidate["x0"]) and (
            min(box["y1"], candidate["y1"]) > max(box["y0"], candidate["y0"]))
    return "ocr_recognition_failed" if any(intersects(b) for b in detection) else "ocr_detection_failed"


def analyze_page(raw, final):
    recognized = raw.get("structure", {})
    method = raw.get("method_id", "docling")
    engine = "paddle_structure" if method in ("paddle_llm", "paddle_structure", "ocr_vlm") else "docling"
    cells, _ = native_items(recognized, engine)
    annotated = dict(recognized, organization_header_aliases=list(ORGANIZATION_ALIASES))
    rows, _, _ = prepare_rows(annotated, engine)
    bands = header_bands(rows)
    org_band = bands.get("department")
    headings = [dict(text=c["text"], bbox=c["bbox"], roles=sorted(field_roles(c["text"]))) for c in cells
                if field_roles(c["text"])]
    assignment = raw.get("assignment", {})
    try:
        answer = json.loads(assignment.get("raw_response", "{}"))
        input_data = json.loads(assignment.get("text_prompt", "{}"))
    except (TypeError, ValueError):
        answer, input_data = {}, {}
    modeled = {p.get("source_row"): p for p in answer.get("participants", []) if isinstance(p, dict)}
    source_rows = {row["id"]: row for row in rows}
    prompt_rows = {row["id"]: row for row in input_data.get("current_rows", [])}
    proofs = recognized.get("row_evidence", [])
    traces = []
    for proof in proofs:
        index, source_id = proof["output_index"], proof.get("source_row")
        original = source_rows.get(source_id)
        supplied = prompt_rows.get(source_id)
        if original is None and supplied:
            # New compact source IDs can be traced through an exact unique transcript.
            supplied_text = [str(c[1]) for c in supplied.get("cells", []) if isinstance(c, list) and len(c) > 1]
            matches = [r for r in rows if normalized(r["cells"][0]["text"]) in map(normalized, supplied_text)]
            original = matches[0] if len(matches) == 1 else None
        candidates = [c for c in (original or {}).get("native_cells", []) if org_band and
                      org_band[0] <= c["bbox"]["x0"] < org_band[1]]
        if not candidates:
            columns = proof.get("column_mapping", {}).get("department", [])
            candidates = [c for c in proof.get("source_cells", []) if len(columns) == 1 and
                          c.get("column_start") in columns and c.get("colspan", 1) == 1]
        candidate = candidates[0]["text"] if len(candidates) == 1 else None
        predicted = field_value(modeled.get(source_id, {}).get("department"))
        people = final.get("participants", [])
        # The role filter may renumber final rows; use its recorded source mapping.
        indices = raw.get("person_role_filter", {}).get("output_index_mapping", [])
        final_index = next((r["output_index"] for r in indices if r["source_output_index"] == index), index)
        final_value = field_value(people[final_index].get("department")) if final_index < len(people) else None
        in_input = candidate is not None and supplied is not None and candidate in json.dumps(supplied, ensure_ascii=False)
        issue, reason = None, "No loss established"
        normalized_snapshot = assignment.get("participants_after_position_validation") or []
        before_normalization = field_value(normalized_snapshot[index].get("department")) if index < len(normalized_snapshot) else None
        if normalized(before_normalization) and normalized(before_normalization) != normalized(final_value):
            issue, reason = "normalization_failed", "A position-validated organization changed before final export; compare recorded snapshots"
        elif candidate and not normalized(final_value):
            if method != "docling" and source_id in modeled and in_input and not normalized(predicted):
                issue, reason = "llm_extraction_failed", "Recognized heading-aligned value was supplied in this source row; LLM returned no organization"
            elif method != "docling" and normalized(predicted) and normalized(predicted) != normalized(final_value):
                issue, reason = "cell_assignment_failed", "LLM value was rejected or changed during source/position validation; inspect snapshots"
            elif supplied is not None and not in_input:
                issue, reason = "cell_assignment_failed", "Source evidence is absent from the serialized current row"
            else:
                issue, reason = "column_mapping_failed", "Observed organization cell did not reach the assigned field"
        elif not normalized(final_value) and not org_band and not proof.get("column_mapping", {}).get("department"):
            issue, reason = "column_mapping_failed", "No unique organization column; underlying OCR/structure cause remains unknown"
        elif candidate is None and not normalized(final_value):
            issue, reason = "unknown", "Missing text does not establish detection, recognition or an empty cell"
        traces.append(dict(output_index=final_index, source_row=source_id, candidate_organization=candidate,
            organization_in_ocr=bool(candidate and any(candidate in c["text"] for c in cells)),
            organization_in_input=in_input, llm_organization=predicted, final_organization=final_value,
            cause=issue, reason=reason, candidate_cells=len(candidates)))
    grids = []
    size = recognized.get("native", {}).get("pages", {}).get("1", {}).get("size", {})
    for index, table in enumerate(recognized.get("tables", [])):
        grid, source, notes = table_rows(table, index, size)
        grids.append(dict(table_index=index, source=source, rows=grid, notes=notes,
            original_html=table.get("html"), original_native=table.get("native")))
    page_issues = []
    if not any("department" in h["roles"] for h in headings):
        page_issues.append(dict(cause="column_mapping_failed", reason="Organization heading not found; OCR root cause unknown"))
    if not grids and cells:
        page_issues.append(dict(cause="table_structure_failed", reason="Native OCR exists but no table was reconstructed"))
    if any(g["notes"] for g in grids):
        page_issues.append(dict(cause="table_structure_failed", reason="Invalid native grid; details retained"))
    if not cells:
        page_issues.append(dict(cause="unknown", reason="No positioned OCR cells; cannot distinguish detection and recognition without labeled regions"))
    return dict(version=VERSION, method=method, page_id=raw.get("page_id"),
        effective_options=recognized.get("effective_options", "not recorded in historical output"),
        source_kind=recognized.get("source_kind"), ocr_statistics=recognized.get("ocr_statistics"),
        ocr_cells=cells, tables=grids, recognized_headings=headings, reconstructed_field_bands=bands,
        original_field_bands=assignment.get("current_field_bands", {}),
        used_mapping=recognized.get("mapping_diagnostics", []),
        participants_before_validation=assignment.get("participants_before_validation"),
        participants_after_literal_grounding=assignment.get("participants_after_literal_grounding"),
        participants_after_position_validation=assignment.get("participants_after_position_validation"),
        final_participants=final.get("participants", []), traces=traces, issues=page_issues,
        quality_measured=False, root_cause_policy="Only observed stage losses are diagnosed. Missing OCR text alone has unknown cause.")


def overlay(image_path, target, analysis, recognized):
    with Image.open(image_path) as source:
        image = source.convert("RGB")
    draw = ImageDraw.Draw(image)
    def paint(box, color, label):
        if not box:
            return
        rect = [box[k]*size for k, size in zip(("x0", "y0", "x1", "y1"),
                                             (image.width, image.height, image.width, image.height))]
        draw.rectangle(rect, outline=color, width=2)
        draw.text((rect[0]+2, rect[1]+2), label, fill=color)
    for grid in analysis["tables"]:
        for row in grid["rows"]:
            for cell in row["cells"]:
                paint(cell.get("bbox"), "#1864ab", f"T{grid['table_index']} R{row['row_index']} C{cell['column_start']}")
    native = recognized.get("native", {})
    for index, table in enumerate(recognized.get("tables", [])):
        for box in table.get("native", {}).get("cell_box_list", []):
            if native.get("width") and native.get("height"):
                paint(rectangle(box, native["width"], native["height"]), "#1864ab", f"T{index}")
    for item in analysis["recognized_headings"]:
        paint(item["bbox"], "#197a34" if "department" in item["roles"] else "#9b59b6", "/".join(item["roles"]))
    for item in analysis["ocr_cells"]:
        paint(item["bbox"], "#df8b00", "OCR")
    if not any("department" in h["roles"] for h in analysis["recognized_headings"]):
        draw.rectangle((0, 0, image.width, 32), fill="white")
        draw.text((5, 6), "REVIEW: no unique Organization heading / OCR cause unknown", fill="#a11")
    image.save(target, format="PNG")
    image.close()


def diagnose_run(source: Path, output: Path, methods=None, max_pages=None):
    source, output = source.resolve(), output.resolve()
    if output.exists() or output.is_relative_to(source):
        raise ValueError("Diagnose benötigt einen neuen Ausgabeordner außerhalb des Quelllaufs")
    summary = read_json(source / "summary.json")
    selected = methods or [m for m in ("docling", "paddle_llm", "paddle_structure") if m in summary]
    manifest = read_json(source / "manifest.json")
    pages = {p["page_id"]: p for p in manifest["pages"]}
    output.mkdir(parents=True)
    index, counts, hashes = [], Counter(), {}
    for method in selected:
        final = {p["page_id"]: p for p in read_jsonl(source / method / "extractions.jsonl")}
        for path in sorted((source / method).glob("raw-*.json"))[:max_pages]:
            raw = read_json(path)
            if "structure" not in raw:
                continue
            analysis = analyze_page(raw, final.get(raw["page_id"], {}))
            # Full SHA256 page IDs plus nested experiment paths exceed Windows
            # MAX_PATH on some company machines. The complete ID stays in JSON/CSV.
            folder = output / method / f"p{len(index)+1:05d}"
            folder.mkdir(parents=True)
            write_json(folder / "stages.json", analysis)
            write_csv(folder / "ocr_cells.csv", analysis["ocr_cells"], fields=None if analysis["ocr_cells"] else ["text", "bbox"])
            write_json(folder / "tables.json", analysis["tables"])
            write_json(folder / "original_raw.json", raw)
            assignment = raw.get("assignment", {})
            for key in ("text_prompt", "raw_response"):
                if key in assignment:
                    (folder / f"{key}.txt").write_text(assignment[key], encoding="utf-8")
            page = pages.get(raw["page_id"], {})
            run_image = source / "pages" / f"{raw['page_id']}.png"
            image = str(run_image) if run_image.is_file() else page.get("run_image", page.get("image", page.get("image_path")))
            if image and Path(image).is_file():
                overlay(Path(image), folder / "overlay.png", analysis, raw["structure"])
            issues = [*analysis["issues"], *[t for t in analysis["traces"] if t["cause"]]]
            counts.update(item["cause"] for item in issues)
            index.append(dict(method=method, page_id=raw["page_id"], ocr_cells=len(analysis["ocr_cells"]),
                tables=len(analysis["tables"]), participants=len(analysis["final_participants"]),
                organization_fields=sum(bool(field_value(p.get("department"))) for p in analysis["final_participants"]),
                issues=len(issues), artifacts=str(folder.relative_to(output))))
            hashes[str(path.relative_to(source))] = file_hash(path)
    write_json(output / "diagnosis.json", dict(version=VERSION, source_run=str(source), pages=index,
        issues=dict(counts), quality_measured=False, source_hashes=hashes,
        implementation_sha256=file_hash(Path(__file__)), created_at=datetime.now(timezone.utc).isoformat()))
    write_csv(output / "pages.csv", index, fields=None if index else ["method", "page_id"])
    rows = "".join(f'<tr><td>{html.escape(r["method"])}</td><td>{html.escape(r["page_id"])}</td>'
        f'<td>{r["ocr_cells"]}</td><td>{r["tables"]}</td><td>{r["participants"]}</td><td>{r["organization_fields"]}</td>'
        f'<td><a href="{r["artifacts"]}/stages.json">Stufen</a> · <a href="{r["artifacts"]}/overlay.png">Overlay</a></td></tr>' for r in index)
    (output / "report.html").write_text('<!doctype html><html lang="de"><meta charset="utf-8">'
        '<meta http-equiv="Content-Security-Policy" content="default-src \'none\'; img-src \'self\'; style-src \'unsafe-inline\'">'
        '<title>Organisationszuordnung diagnostizieren</title><style>body{font:16px system-ui;margin:2rem}'
        'th,td{border:1px solid #ccc;padding:.5rem}table{border-collapse:collapse}</style>'
        '<h1>Docling / Paddle: Datenfluss und Organisation</h1><p>Keine Genauigkeitsmessung ohne geprüfte Referenz. '
        'Fehlender OCR-Text beweist weder einen Detektions- noch einen Erkennungsfehler. '
        'Alle Originale und vorhandenen Reports bleiben unverändert. Artefakte enthalten personenbezogene Daten und bleiben lokal.</p>'
        '<p>Overlay: Blau native Tabellenzellen, Orange OCR, Grün Organisationsüberschrift, Violett andere Überschriften.</p>'
        f'<p>Diagnosen: {html.escape(json.dumps(dict(counts)))}</p><table><tr><th>Verfahren</th><th>Seite</th>'
        '<th>OCR-Zellen</th><th>Tabellen</th><th>Personen</th><th>Organisationen</th><th>Belege</th></tr>'+rows+'</table>', encoding="utf-8")
    return output
