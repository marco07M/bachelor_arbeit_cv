"""Prepare native layout evidence for local, literal-grounded participant assignment.

Use recognized positions even when a table model misses the table or merges its
header. Never add text from another engine or infer a blank cell from missing OCR.
"""

import re
from difflib import SequenceMatcher
from statistics import median

from .schema import TEXT_FIELDS, Box, TextField
from .unlimited_assignment import header_fields, source_rows

VERSION = "structure-spatial-assignment-v6-organization-evidence"


def rectangle(value, width, height):
    if isinstance(value, dict):
        left, top, right, bottom = (value[key] for key in ("l", "t", "r", "b"))
        if value.get("coord_origin") == "BOTTOMLEFT":
            top, bottom = height - top, height - bottom
    elif len(value) == 4 and isinstance(value[0], (int, float)):
        left, top, right, bottom = value
    else:
        left, top = min(p[0] for p in value), min(p[1] for p in value)
        right, bottom = max(p[0] for p in value), max(p[1] for p in value)
    coords = [round(max(0.0, min(1.0, n / size)), 4)
              for n, size in zip((left, top, right, bottom), (width, height, width, height), strict=True)]
    return dict(zip(("x0", "y0", "x1", "y1"), coords, strict=True)) if (
        coords[2] > coords[0] and coords[3] > coords[1]) else None


def native_items(recognized, method):
    native = recognized.get("native", {})
    items = []

    def add(text, box, source, width, height, confidence=None):
        if box is not None and width and height:
            normalized = rectangle(box, width, height)
            if normalized:
                items.append(dict(text=" ".join(text.split()), raw_text=text,
                                  bbox=normalized, native_ref=source, ocr_confidence=confidence))

    if method == "paddle_structure":
        ocr = native.get("overall_ocr_res", {})
        boxes = ocr.get("rec_boxes", ocr.get("rec_polys", ocr.get("dt_polys", [])))
        texts = ocr.get("rec_texts", [])
        if len(boxes) != len(texts):
            return [], None
        width, height = native.get("width"), native.get("height")
        for index, (text, box) in enumerate(zip(texts, boxes, strict=True)):
            scores = ocr.get("rec_scores", [])
            add(text, box, f"overall_ocr_res/{index}", width, height,
                scores[index] if index < len(scores) else None)
    else:
        pages = native.get("pages", {})
        page = pages.get("1", pages.get(1, {}))
        size = page.get("size", {})
        width, height = size.get("width"), size.get("height")
        if recognized.get("ocr_cells"):
            for index, cell in enumerate(recognized["ocr_cells"]):
                add(cell["text"], cell.get("bbox"), cell.get("native_ref", f"ocr_cells/{index}"), width, height,
                    cell.get("confidence"))
            return items, width / height if width and height else None
        for table_index, table in enumerate(recognized.get("tables", [])):
            for index, cell in enumerate(table.get("native", {}).get("data", {}).get("table_cells", [])):
                add(cell.get("text", ""), cell.get("bbox"), f"tables/{table_index}/cells/{index}", width, height)
        for index, item in enumerate(native.get("texts", [])):
            # Headers/footers are context, never candidate participant rows.
            if item.get("label") in ("page_header", "page_footer"):
                continue
            prov = item.get("prov", [])
            if prov:
                add(item.get("text", ""), prov[0].get("bbox"), f"texts/{index}", width, height)
    return items, width / height if width and height else None


def roles(text, organization_aliases=()):
    """Fuzzy matching applies only to generic headings, never participant values."""
    found = header_fields(text)
    if organization_aliases:
        from .column_headers import field_roles

        found |= field_roles(text, organization_aliases)
        if key := re.sub(r"\W", "", text.casefold()):
            if key == "signatur":
                found.add("signature")
    key = re.sub(r"\W", "", text.casefold())
    if not found and 6 <= len(key) <= 18 and len(text.split()) == 1:
        aliases = {"benutzername": {"first_name", "last_name"}, "kurzzeichen": {"department"},
                   "personalnummer": {"personnel_number"}, "unterschrift": {"signature"}}
        matches = [fields for alias, fields in aliases.items()
                   if SequenceMatcher(None, key, alias).ratio() >= 0.84]
        if len(matches) == 1:
            found = matches[0]
    if key in ("datum", "date", "unterschrift", "signature"):
        found = {"signature" if key in ("unterschrift", "signature") else "date"}
    return found


def prepare_rows(recognized, method):
    items, aspect = native_items(recognized, method)
    if not items or not any(item["text"] for item in items):
        rows, notes = source_rows("\n".join(table["html"] for table in recognized.get("tables", [])))
        return rows, notes, None
    # Compare baselines on the page, not the OCR engine's unreliable table row indices.
    heights = [item["bbox"]["y1"] - item["bbox"]["y0"] for item in items if item["text"]]
    tolerance = max(0.002, median(heights) * 0.45)
    groups = []
    for item in sorted(items, key=lambda i: (i["bbox"]["y0"] + i["bbox"]["y1"], i["bbox"]["x0"])):
        center = (item["bbox"]["y0"] + item["bbox"]["y1"]) / 2
        if not groups or abs(center - median(g[0] for g in groups[-1])) > tolerance:
            groups.append([])
        groups[-1].append((center, item))
    columns = docling_columns(recognized) if method == "docling" else []
    groups = merge_aligned_fragments(groups, columns, median(heights))
    rows = []
    for index, group in enumerate(groups):
        cells, components, pieces, cursor = [], [], [], 0
        for _, item in sorted(group, key=lambda entry: entry[1]["bbox"]["x0"]):
            cell = dict(item, index=len(cells), column_start=round(item["bbox"]["x0"] * 1000),
                        colspan=1, rowspan=1, kind="native", header_fields=sorted(roles(
                            item["text"], recognized.get("organization_header_aliases", ()))))
            cells.append(cell)
            if item["text"]:
                components.append(dict(start=cursor, stop=cursor + len(item["text"]),
                                       bbox=item["bbox"], native_ref=item["native_ref"]))
                pieces.append(item["text"])
                cursor += len(item["text"]) + 1
        if not pieces:
            continue
        box = union([cell["bbox"] for cell in cells])
        # The transcript permits names split across adjacent OCR boxes. Offsets
        # retain the exact constituent boxes; no correction/completion is allowed.
        transcript = dict(index=0, text=" ".join(pieces), raw_text=" ".join(pieces),
                          column_start=0, colspan=1, rowspan=1, kind="row_transcript", bbox=box, components=components)
        # A single literal row transcript avoids confusing geometric x positions
        # with cell indices. Retain explicitly empty native cells separately.
        visible = [transcript, *(dict(cell, index=i + 1) for i, cell in enumerate(c for c in cells if not c["text"]))]
        readable = []
        for column, (left, right) in enumerate(zip(columns, columns[1:])):
            found = [cell["text"] for cell in cells if left <= (cell["bbox"]["x0"] + cell["bbox"]["x1"]) / 2 < right]
            if found:
                readable.append(dict(column=column, text=" ".join(found)))
        rows.append(dict(id=f"t0r{index}", table_index=0, row_index=index, cells=visible,
                         native_cells=cells, bbox=box, column_texts=readable))
    return rows, ["Zuordnung aus nativen OCR-/Zellpositionen; Tabellenmarkup separat erhalten"], aspect


def merge_aligned_fragments(groups, columns, typical_height):
    """Join fragments in one physical cell despite a flat or unusually tall word box.

    Repeated words at overlapping x positions establish distinct rows. This avoids
    merging neighbouring people merely because handwriting boxes overlap vertically.
    """
    if not columns:
        return groups
    output = []
    def column(cell):
        center = (cell["bbox"]["x0"] + cell["bbox"]["x1"]) / 2
        return next((i for i, (a, b) in enumerate(zip(columns, columns[1:])) if a <= center < b), None)
    for group in groups:
        if not output or abs(median(c for c, _ in group) - median(c for c, _ in output[-1])) > .9 * typical_height:
            output.append(group)
            continue
        pairs = [(a["bbox"], b["bbox"]) for _, a in output[-1] for _, b in group
                 if len(a["text"].strip()) > 1 and len(b["text"].strip()) > 1 and column(a) == column(b)]
        conflicting = any(min(a["x1"], b["x1"]) - max(a["x0"], b["x0"]) > .1 * min(
            a["x1"] - a["x0"], b["x1"] - b["x0"]) for a, b in pairs)
        aligned = any(min(a["y1"], b["y1"]) - max(a["y0"], b["y0"]) >= .5 * min(
            a["y1"] - a["y0"], b["y1"] - b["y0"]) for a, b in pairs)
        if aligned and not conflicting:
            output[-1] = output[-1] + group
        else:
            output.append(group)
    return output


def docling_columns(recognized):
    """Use TableFormer's own column geometry as text grouping, never another engine's output."""
    pages = recognized.get("native", {}).get("pages", {})
    size = pages.get("1", pages.get(1, {})).get("size", {})
    width, height = size.get("width"), size.get("height")
    if not width or not height:
        return []
    starts = {}
    for table in recognized.get("tables", []):
        for cell in table.get("native", {}).get("data", {}).get("table_cells", []):
            left, right = cell.get("start_col_offset_idx"), cell.get("end_col_offset_idx")
            if left is None or right != left + 1 or not cell.get("bbox"):
                continue
            box = rectangle(cell["bbox"], width, height)
            if box:
                starts.setdefault(left, []).append(box["x0"])
    boundaries = [0.0]
    for value in sorted(median(values) for values in starts.values()):
        if value - boundaries[-1] > .008:
            boundaries.append(value)
    boundaries.append(1.0)
    return boundaries if len(boundaries) >= 4 else []


def continue_name_column(rows, boundaries, aspect, previous):
    """Reuse geometry only when the current table still shares its column anchors."""
    if not previous or not aspect or abs(previous["aspect"] / aspect - 1) >= .02:
        return rows, None, None
    matches = sum(any(abs(a - b) < .015 for b in boundaries[1:-1])
                  for a in previous["boundaries"][1:-1])
    if matches < 2:
        return rows, None, None
    left, right = previous["bounds"]
    hint = previous["hint"]
    regrouped = []
    for row in rows:
        grouped = {}
        for cell in row.get("native_cells", []):
            center = (cell["bbox"]["x0"] + cell["bbox"]["x1"]) / 2
            column = hint if left <= center < right else hint - 1 if center < left else hint + 1
            if cell["text"]:
                grouped.setdefault(column, []).append(cell["text"])
        regrouped.append(dict(row, column_texts=[dict(column=key, text=" ".join(values))
                                                 for key, values in sorted(grouped.items())]))
    return regrouped, hint, [left, right]


def union(boxes):
    return {key: operation(box[key] for box in boxes)
            for key, operation in (("x0", min), ("y0", min), ("x1", max), ("y1", max))}


def header_bands(rows):
    """Only a row with multiple recognizable headings establishes column roles."""
    anchors = {}
    for row in rows:
        cells = [(cell, set(cell.get("header_fields", []))) for cell in row.get("native_cells", row["cells"])
                 if cell.get("kind") == "native"]
        found = set().union(*(fields for _, fields in cells)) if cells else set()
        if not (found & {"first_name", "last_name"} and len(found & set(TEXT_FIELDS)) >= 2):
            continue
        for cell, fields in cells:
            for field in fields:
                anchors.setdefault(field, []).append(cell["bbox"]["x0"])
    if not anchors:
        return {}
    starts = {field: median(values) for field, values in anchors.items()
              if max(values) - min(values) < 0.02}
    boundaries = sorted(set(starts.values()))
    return {field: (max(0.0, start - 0.012),
                    min((x - 0.012 for x in boundaries if x > start + 0.002), default=1.0))
            for field, start in starts.items() if field in TEXT_FIELDS}


def ground_positions(people, evidence, rows, bands):
    """Enforce column evidence after literal grounding; do not fill unknown values."""
    by_id = {row["id"]: row for row in rows}
    for person, proof in zip(people, evidence, strict=True):
        row = by_id[proof["source_row"]]
        if row.get("bbox"):
            person.bbox = Box.model_validate(row["bbox"])
        for field, item in proof["fields"].items():
            cell = row["cells"][item["cell_index"]]
            boxes = source_boxes(cell, item["offset"])
            if not boxes:
                continue
            item["bbox"] = union(boxes)
            if field in bands and any(not bands[field][0] <= box["x0"] < bands[field][1] for box in boxes):
                setattr(person, field, TextField(state="failed"))
                item["rejected"] = "outside_header_column"
                person.review_notes.append(f"{field}: Text liegt außerhalb der zugeordneten Spalte; Wert unbekannt")
            else:
                getattr(person, field).bbox = Box.model_validate(item["bbox"])
        person.review_notes.append("Native Positionen geprüft; OCR- und Namenszuordnung weiterhin manuell kontrollieren")


def source_boxes(cell, offset):
    if cell.get("kind") == "row_transcript" and offset:
        start, stop = offset
        return [c["bbox"] for c in cell["components"] if min(stop, c["stop"]) > max(start, c["start"])]
    return [cell["bbox"]] if cell.get("bbox") else []


def position_matches(field, cell, match, bands):
    boxes = source_boxes(cell, match.span() if match else None)
    return field not in bands or all(bands[field][0] <= box["x0"] < bands[field][1] for box in boxes)


def comma_names(response, rows, bands):
    """Explicit supported convention: a combined cell printed as 'Surname, First name'."""
    by_id = {row["id"]: row for row in rows}
    for prediction in response.participants:
        row = by_id.get(prediction.source_row)
        if not row or not row.get("native_cells"):
            continue
        name_band = bands.get("first_name")
        if name_band and name_band == bands.get("last_name"):
            parts = [cell["text"] for cell in row["native_cells"]
                     if name_band[0] <= cell["bbox"]["x0"] < name_band[1]]
            value = " ".join(parts)
        else:
            # Without a recognized combined-name column, only separate a cell
            # that the model already references for both name fields.
            first, last = prediction.first_name, prediction.last_name
            if first[0] != last[0] or first[0] is None or not first[1] or not last[1]:
                continue
            candidates = [cell["text"] for cell in row["native_cells"]
                          if first[1] in cell["text"] and last[1] in cell["text"] and "," in cell["text"]]
            value = candidates[0] if len(candidates) == 1 else ""
        if value.count(",") != 1:
            continue
        last, first = (part.strip() for part in value.split(","))
        if (not first or not last or any(ch.isdigit() for ch in value)
                or not any(ch.isalpha() for ch in first) or not any(ch.isalpha() for ch in last)):
            continue
        transcript = row["cells"][0]["text"]
        if value in transcript:
            prediction.first_name, prediction.last_name = (0, first), (0, last)


def observed_field_bands(people):
    """Position hints only: never carry model values to the next page."""
    output = {}
    for field in TEXT_FIELDS:
        boxes = [getattr(p, field).bbox for p in people
                 if getattr(p, field).state == "read" and getattr(p, field).bbox is not None]
        if len(boxes) < 3 or max(b.x0 for b in boxes) - min(b.x0 for b in boxes) > .04:
            continue
        output[field] = (max(0.0, min(b.x0 for b in boxes) - .012), min(1.0, max(b.x1 for b in boxes) + .025))
    if "first_name" in output and "last_name" in output:
        a, b = output["first_name"], output["last_name"]
        if min(a[1], b[1]) > max(a[0], b[0]):
            output["first_name"] = output["last_name"] = (min(a[0], b[0]), max(a[1], b[1]))
    return output


def continuation_candidates(rows, bands):
    names = [bands[f] for f in ("first_name", "last_name") if f in bands]
    return [row["id"] for row in rows if any(
        len(cell["text"]) >= 3 and any(ch.isalpha() for ch in cell["text"])
        and any(left <= cell["bbox"]["x0"] < right for left, right in names)
        for cell in row.get("native_cells", [])
    )]
