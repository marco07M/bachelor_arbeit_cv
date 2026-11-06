"""Lossless local OCR ledger, separate from admission to participant fields."""

import html
import json
from collections import Counter
from pathlib import Path

from .io import digest, write_csv, write_json
from .schema import TEXT_FIELDS

VERSION = "ocr-observation-ledger-v1"


def _box(value, size):
    if not value:
        return None
    if set(("x0", "y0", "x1", "y1")).issubset(value):
        return value
    from .structure_assignment import rectangle

    try:
        return rectangle(value, size.get("width"), size.get("height")) if all(size.get(k) for k in ("width", "height")) else None
    except (TypeError, ValueError, KeyError):
        return None


def observations(raw):
    """Keep nonempty engine text even if position/score/row metadata is unavailable."""
    output = []
    if "ocr" in raw:
        for index, word in enumerate(raw["ocr"].get("words", [])):
            if str(word.get("text", "")).strip():
                output.append(dict(id=f"words/{index}", text=word["text"],
                    bbox=word.get("bbox"), confidence=word.get("ocr_confidence"),
                    raw_confidence=word.get("raw_ocr_confidence", word.get("ocr_confidence")),
                    confidence_scale="0..100_engine_score", line=word.get("line"),
                    engine=raw["ocr"].get("text_source", "tesseract"), capture_stage="engine_words"))
        return output, "engine_words"
    recognized = raw.get("structure", {})
    native = recognized.get("native", {})
    if "overall_ocr_res" in native:
        source = native["overall_ocr_res"]
        boxes = source.get("rec_boxes", source.get("rec_polys", []))
        scores = source.get("rec_scores", [])
        size = {k: native.get(k) for k in ("width", "height")}
        for index, text in enumerate(source.get("rec_texts", [])):
            if str(text).strip():
                box = boxes[index] if index < len(boxes) else None
                if box is not None:
                    from .structure_assignment import rectangle

                    try:
                        box = rectangle(box, size["width"], size["height"])
                    except (TypeError, ValueError, KeyError):
                        box = None
                output.append(dict(id=f"overall_ocr_res/{index}", text=text, bbox=box,
                    confidence=scores[index] if index < len(scores) else None,
                    confidence_scale="0..1_engine_score", engine="paddle", capture_stage="engine_recognition"))
        return output, "engine_recognition"
    pages = native.get("pages", {})
    size = pages.get("1", pages.get(1, {})).get("size", {})
    captured = recognized.get("engine_ocr_observations")
    post_cells = Counter((c.get("text"), json.dumps(c.get("bbox"), sort_keys=True))
                         for c in recognized.get("ocr_cells", []) if c.get("from_ocr", True))
    cells = list(captured) if captured is not None else list(recognized.get("ocr_cells", []))
    if captured is not None:
        cells.extend(c for c in recognized.get("ocr_cells", []) if not c.get("from_ocr", True))
    for index, cell in enumerate(cells):
        if str(cell.get("text", "")).strip():
            key = cell.get("text"), json.dumps(cell.get("bbox"), sort_keys=True)
            kept = bool(post_cells[key]) if captured is not None and cell.get("from_ocr", True) else None
            if kept:
                post_cells[key] -= 1
            output.append(dict(id=cell.get("native_ref", f"ocr_cells/{index}"), text=cell["text"],
                bbox=_box(cell.get("bbox"), size), raw_bbox=cell.get("bbox"),
                confidence=cell.get("confidence"), confidence_scale="0..1_engine_score",
                engine="docling_tesseract" if cell.get("from_ocr", True) else "pdf_text",
                line=cell.get("engine_cell_index"), engine_page=cell.get("engine_page"),
                post_sdk_preserved=kept,
                capture_stage=cell.get("capture_stage", "post_sdk_cells")))
    return output, "before_sdk_merge" if captured is not None else "post_sdk_only_historical"


def audit(raw, page):
    from .ocr_layout import line_groups
    from .structured_mapping import table_rows

    items, capture = observations(raw)
    final = page.model_dump() if hasattr(page, "model_dump") else page
    method = final.get("method_id", raw.get("method_id"))
    recognized, layout = raw.get("structure", {}), raw.get("ocr_layout_analysis", {})
    groups = line_groups(raw.get("ocr", {}))
    submitted, row_refs = set(), {}
    submission_known = "text_rows" in layout
    proposed = 0
    for response in raw.get("responses", []):
        try:
            payload = json.loads(response.get("raw_response", "{}"))
            proposed += len(payload if isinstance(payload, list) else payload.get("participants", [])) if isinstance(payload, (dict, list)) else 0
        except (TypeError, ValueError):
            pass
        prompt = response.get("text_prompt", "")
        if prompt.startswith("OCR_LAYOUT_DATA:"):
            try:
                payload = json.JSONDecoder().raw_decode(prompt.split("\n", 1)[1])[0]
                submitted.update(f"words/{word[0]}" for word in payload.get("words", []))
                submission_known = True
            except (TypeError, ValueError, IndexError):
                pass
    assignment = raw.get("assignment", {})
    if assignment:
        proposed = len(assignment.get("participants_before_validation", []))
        try:
            payload = json.loads(assignment.get("text_prompt", "{}"))
            # Exact text AND native geometry prove an observation was in the saved
            # prompt. Older prompts without cell evidence remain unknown.
            prompt_rows = payload.get("current_rows", payload.get("rows", []))
            if prompt_rows and all("layout_cells" in row for row in prompt_rows):
                for item in items:
                    matches = [row["id"] for row in prompt_rows for cell in row["layout_cells"]
                               if len(cell) >= 2 and cell[0] == item["text"] and cell[1] == item["bbox"]]
                    if matches:
                        submitted.add(item["id"])
                        row_refs[item["id"]] = matches[0]
                submission_known = True
        except (ValueError, TypeError, KeyError):
            pass
    for row in layout.get("text_rows", []):
        indices = {i for cell in row["cells"] for i in cell.get("word_ids", [])}
        if not indices and row.get("original_source_row", "").startswith("r"):
            index = int(row["original_source_row"][1:])-1
            indices = set(groups[index]) if 0 <= index < len(groups) else set()
        submitted.update(f"words/{i}" for i in indices)
        row_refs.update({f"words/{i}": row["id"] for i in indices})
    submitted.update(f"words/{i}" for i in layout.get("unassigned_word_ids", []))
    proofs = [*recognized.get("row_evidence", []), *[proof for response in raw.get("responses", [])
              for proof in response.get("ocr_field_evidence", [])]]
    pages = recognized.get("native", {}).get("pages", {})
    size = pages.get("1", pages.get(1, {})).get("size", {})
    native_rows = [row for index, table in enumerate(recognized.get("tables", []))
                   for row in table_rows(table, index, size)[0]]
    grid = [cell for row in native_rows for cell in row["cells"]]
    people = final.get("participants", [])
    rejected = [item for response in raw.get("responses", []) for item in response.get("rejected_rows", [])]
    rejected.extend(assignment.get("rejected_rows", []))
    for item in items:
        item.update(page_id=final.get("page_id", raw.get("page_id")), page_number=final.get("page_number"),
                    document_id=final.get("document_id"), source_row=row_refs.get(item["id"]))
        box = item["bbox"]
        def inside(candidate):
            return box and candidate and candidate["x0"] <= (box["x0"]+box["x1"])/2 <= candidate["x1"] and (
                candidate["y0"] <= (box["y0"]+box["y1"])/2 <= candidate["y1"])
        item["table_cells"] = [c.get("native_ref") for c in grid if inside(c.get("bbox")) and item["text"] in c["text"]]
        item["submitted_to_assignment"] = (item["id"] in submitted if submission_known else None) if "ocr" in raw or assignment else (
            True if method == "docling" and item["table_cells"] else None)
        item["input_link_basis"] = ("saved_word_or_row_reference" if "ocr" in raw else
                                    "saved_layout_cell_text_and_position" if assignment else "native_cell_literal_and_position")
        item["structured_fields"] = [dict(output_index=i, field=field, state=person[field]["state"])
            for i, person in enumerate(people) for field in TEXT_FIELDS
            if person[field].get("value") and inside(person[field].get("bbox")) and
            (item["text"] in person[field]["value"] or person[field]["value"] in item["text"])]
        refs = [dict(output_index=p.get("output_index"), field=field, rejected=e.get("rejected"))
                for p in proofs for field, e in p.get("fields", {}).items()
                if e.get("native_ref") in item["table_cells"] or any(
                    c.get("native_ref") == item["id"] for c in e.get("ocr_observations", []))]
        item["field_evidence"] = refs
        # A literal/position link is traceability, never semantic correctness or a verified identity.
        item["assignment_state"] = "structured_uncertain" if any(f["state"] == "uncertain" for f in item["structured_fields"]) else (
            "structured_observed" if item["structured_fields"] else "unassigned")
        item["reason"] = ("field_has_literal_position_link" if item["structured_fields"] else
            "no_reliable_ocr_row" if item["id"] in {f"words/{i}" for i in layout.get("unassigned_word_ids", [])} else
            "not_submitted_by_row_selection" if item["submitted_to_assignment"] is False else
            "no_reliable_column_mapping_or_table_cell" if method == "docling" and not item["table_cells"] else
            "no_final_field_for_observation")
    count = Counter(item["assignment_state"] for item in items)
    return dict(version=VERSION, capture_coverage=capture, observations=items,
        counts=dict(observations=len(items), submitted=sum(i["submitted_to_assignment"] is True for i in items),
            not_submitted=sum(i["submitted_to_assignment"] is False for i in items),
            submission_unknown=sum(i["submitted_to_assignment"] is None for i in items),
            sdk_merge_removed=sum(i.get("post_sdk_preserved") is False for i in items) if capture == "before_sdk_merge" else None,
            native_mapper_cells=len(grid), native_mapper_rows=len(native_rows),
            model_rows_proposed=proposed,
            failed_final_fields=sum(p[f]["state"] == "failed" for p in people for f in TEXT_FIELDS),
            uncertain_nonempty_fields=sum(bool(p[f].get("value")) and p[f]["state"] == "uncertain" for p in people for f in TEXT_FIELDS),
            unassigned=count["unassigned"], structured_observed=count["structured_observed"],
            structured_uncertain=count["structured_uncertain"],
            model_rows_rejected=len(rejected), final_participants=len(people)),
        row_selection=layout.get("selection_diagnostics"), rejected_model_rows=rejected,
        field_warnings=[w for response in raw.get("responses", []) for w in response.get("field_warnings", [])],
        mapper_row_decisions=recognized.get("row_decisions", []),
        role_filter=raw.get("person_role_filter", {}), mapping=recognized.get("mapping_diagnostics", []),
        policy="OCR observations are retained independently of score/identity. Raw observations never count as extracted fields.")


def export(output, method, page, raw):
    data = audit(raw, page)
    page_id = page.page_id
    relative = Path(method) / "observations" / (digest(page_id)[:16]+".json")
    write_json(output / relative, data)
    csv_path = relative.with_suffix(".csv")
    write_csv(output / csv_path, data["observations"], fields=None if data["observations"] else ["id", "text", "confidence", "reason"])
    def esc(text):
        return html.escape(str(text))
    rows = "".join("<tr>"+"".join(f"<td><pre>{esc(item.get(key))}</pre></td>" for key in
        ("id", "text", "confidence", "bbox", "source_row", "submitted_to_assignment", "assignment_state", "reason"))+"</tr>"
        for item in data["observations"])
    return (f'<details><summary>{esc(method)} – Seite {page.page_number}: {len(data["observations"])} OCR-Beobachtungen</summary>'
        f'<p>{esc(json.dumps(data["counts"]))}; Erfassung: {esc(data["capture_coverage"])}. '
        'Eine Positions-/Textverknüpfung ist keine bestätigte Inhaltsrichtigkeit. '
        'Bei Docling wird der Eingang über wörtliche native Zellbelege mit Position verknüpft; '
        'fehlende Verknüpfung bleibt unbekannt und beweist keinen OCR-Verlust.</p>'
        f'<p><a href="{relative.as_posix()}">Vollständige Belege und Ablehnungen (JSON)</a> · '
        f'<a href="{csv_path.as_posix()}">Alle Beobachtungen (CSV)</a></p>'
        '<details><summary>Zeilen- und Feldentscheidungen</summary><pre>' + esc(json.dumps(dict(
            mapper_rows=data["mapper_row_decisions"], rejected_model_rows=data["rejected_model_rows"],
            field_warnings=data["field_warnings"]), ensure_ascii=False, indent=2)) + '</pre></details>'
        '<table><tr><th>Quell-ID</th><th>Originaltext</th><th>Engine-Score</th><th>Position</th>'
        '<th>Quellzeile</th><th>Im Zuordnungseingang</th><th>Zuordnung</th><th>Grund</th></tr>'+rows+'</table></details>')
