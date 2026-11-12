"""Prepare native layout evidence for local, literal-grounded participant assignment.

Use recognized positions even when a table model misses the table or merges its
header. Never add text from another engine or infer a blank cell from missing OCR.
"""

import re
from difflib import SequenceMatcher
from statistics import median

from .schema import TEXT_FIELDS, Box, TextField
from .unlimited_assignment import header_fields, source_rows

VERSION = "structure-spatial-assignment-v10-multiline-column-context"


def heading_rows(rows):
    """Spatial header blocks need no guessed logical grid indices."""
    selected, last = [], {}
    for index, row in enumerate(rows):
        found = {field for cell in row.get("native_cells", row["cells"])
                 if cell.get("kind") == "native" for field in cell.get("header_fields", [])}
        table, number = row.get("table_index", 0), row.get("row_index", index)
        if (len(found & set(TEXT_FIELDS)) >= 2
                or found and last.get(table) == number-1):
            selected.append(row)
            last[table] = number
    return selected


def document_bands(recognized, rows, bands, previous, *, document_id, page_number):
    """Extend existing spatial context with scoped measured layout compatibility."""
    from .column_context import geometry, project_bands, resolve

    edges = recognized.get("image_column_boundaries")
    profile = geometry(len(edges)-1, boundaries=edges) if edges else None
    if profile is None and len(recognized.get("tables", [])) == 1:
        from .structured_mapping import table_rows

        pages = recognized.get("native", {}).get("pages", {})
        size = pages.get("1", pages.get(1, {})).get("size", {})
        grid, _, _ = table_rows(recognized["tables"][0], size=size)
        width = max((r.get("grid_width", 0) for r in grid), default=0)
        profile = geometry(width, grid)
    starts = sorted({band[0] for band in bands.values()})
    mapping = {field: {starts.index(band[0])} for field, band in bands.items()}
    header_rows = heading_rows(rows)
    headings = {field: [dict(text=cell["text"], bbox=cell["bbox"])
                for row in header_rows for cell in row.get("native_cells", []) if field in cell.get("header_fields", [])]
                for field in bands}
    if profile:
        # Rank among recognized labels is not a physical column number: a row
        # number, blank column or signature column may precede a target field.
        mapping = {field: {i for i, (left, right) in enumerate(zip(profile["edges"], profile["edges"][1:]))
                           for cell in labels if left <= (cell["bbox"]["x0"]+cell["bbox"]["x1"])/2 < right}
                   for field, labels in headings.items()}
    for field in ("signature", "date"):
        found = [cell for row in header_rows for cell in row.get("native_cells", []) if field in cell.get("header_fields", [])]
        if found:
            headings[field] = [dict(text=cell["text"], bbox=cell["bbox"]) for cell in found]
            if profile:
                mapping[field] = {i for i, (left, right) in enumerate(zip(profile["edges"], profile["edges"][1:]))
                                  for cell in found if left <= (cell["bbox"]["x0"]+cell["bbox"]["x1"])/2 < right}
    ambiguous = ambiguous_header_fields(rows)
    _, context, trace = resolve(mapping, headings, profile, previous,
        document_id=document_id, page_number=page_number, has_header=bool(bands) or bool(ambiguous), ambiguous=bool(ambiguous))
    inherited = {}
    if trace["status"] in ("detected_on_current_page", "updated_on_current_page"):
        context["field_bands"] = bands
        # Completion needs a physical cell, not the broad text bands used for validation.
        # In particular the last text band can extend through signature columns.
        context["observed_cell_bands"] = observed_cell_bands(rows, profile)
        trace["observed_cell_bands"] = context["observed_cell_bands"]
    elif trace["status"] == "inherited_from_previous_page":
        inherited = project_bands(context.get("field_bands", {}), context["geometry"], profile)
        trace["observed_cell_bands"] = project_bands(context.get("observed_cell_bands", {}), context["geometry"], profile)
    return inherited, context, trace


def observed_cell_bands(rows, profile):
    """Bound two scalar roles by measured grid lines and actual printed headings."""
    if not profile or profile.get("basis") != "measured_grid_lines":
        return {}
    edges, columns = profile["edges"], {}
    for row in heading_rows(rows):
        cells = row.get("native_cells", [])
        for cell in cells:
            box = cell.get("bbox")
            if not box:
                continue
            for field in cell.get("header_fields", []):
                for i, (left, right) in enumerate(zip(edges, edges[1:])):
                    if left <= box["x0"] < box["x1"] <= right:
                        columns.setdefault(field, set()).add(i)
    result = {}
    for field in ("personnel_number", "department"):
        candidates = columns.get(field, set())
        if len(candidates) != 1:
            continue
        index = next(iter(candidates))
        if any(index in cols for other, cols in columns.items() if other != field):
            continue
        result[field] = [edges[index], edges[index+1]]
    return result


def complete_observed_cells(people, proofs, rows, mapping_trace):
    """Fill omitted scalar fields only for existing, grounded people in measured header columns.

    No reference, previous participant value, confidence cutoff, name guess or
    missing-OCR-as-empty inference is involved. Ambiguous or split cells stay unknown.
    """
    if mapping_trace.get("status") not in (
            "detected_on_current_page", "updated_on_current_page", "inherited_from_previous_page"):
        return []
    by_id, changes = {row["id"]: row for row in rows}, []
    for index, (person, proof) in enumerate(zip(people, proofs, strict=True)):
        row = by_id.get(proof.get("source_row"), {})
        if not any(getattr(person, f).value for f in ("first_name", "last_name", "personnel_number")):
            continue
        for field, (left, right) in mapping_trace.get("observed_cell_bands", {}).items():
            if field not in ("personnel_number", "department") or getattr(person, field).value is not None:
                continue  # Explicit empty or a surviving model answer remains authoritative.
            candidates = [cell for cell in row.get("native_cells", []) if cell.get("text", "").strip()
                and cell.get("bbox") and not cell.get("header_fields") and
                left <= (cell["bbox"]["x0"]+cell["bbox"]["x1"])/2 < right]
            if len(candidates) != 1:
                continue
            cell = candidates[0]
            if cell["bbox"]["x0"] < left or cell["bbox"]["x1"] > right:
                continue
            # A masked identifier is not a readable identifier; its OCR observation stays in the ledger.
            if field == "personnel_number" and re.search(r"[*█■]{2,}|[xX]{3,}", cell["text"]):
                continue
            prior = getattr(person, field).model_dump()
            setattr(person, field, TextField(value=cell["text"], state="uncertain", bbox=Box.model_validate(cell["bbox"])))
            item = dict(text=cell["text"], bbox=cell["bbox"], native_ref=cell.get("native_ref"),
                ocr_confidence=cell.get("ocr_confidence"))
            proof["fields"][field] = dict(text=cell["text"], bbox=cell["bbox"],
                native_ref=cell.get("native_ref"), ocr_observations=[item],
                assignment_rule="unique_observed_cell_in_measured_header_column", observation_state="uncertain",
                mapping_provenance=mapping_trace, replaced_field=prior)
            person.review_notes.append(f"{field}: eindeutige OCR-Zelle in gemessener Überschriftenspalte ergänzt; manuell prüfen")
            changes.append(dict(output_index=index, field=field, source_row=proof["source_row"],
                                **proof["fields"][field]))
    return changes


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
    """Recognize a heading block, including its adjacent continuation lines."""
    anchors = {}
    for row in heading_rows(rows):
        cells = [(cell, set(cell.get("header_fields", []))) for cell in row.get("native_cells", row["cells"])
                 if cell.get("kind") == "native"]
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


def ambiguous_header_fields(rows):
    """Distinct columns with the same role are not resolved by an LLM guess."""
    ambiguous = set()
    anchors = {}
    for row in heading_rows(rows):
        cells = [(c, set(c.get("header_fields", []))) for c in row.get("native_cells", [])]
        for field in TEXT_FIELDS:
            anchors.setdefault(field, []).extend(cell["bbox"]["x0"] for cell, fields in cells if field in fields)
            if anchors[field] and max(anchors[field])-min(anchors[field])>.02:
                ambiguous.add(field)
    return sorted(ambiguous)


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
            observed = [c for c in row.get("native_cells", []) if c.get("bbox") in boxes]
            item["ocr_observations"] = [dict(text=c.get("raw_text", c["text"]), bbox=c["bbox"],
                ocr_confidence=c.get("ocr_confidence"), native_ref=c.get("native_ref")) for c in observed]
            if field in bands and any(not bands[field][0] <= box["x0"] < bands[field][1] for box in boxes):
                setattr(person, field, TextField(state="failed"))
                item["rejected"] = "outside_header_column"
                person.review_notes.append(f"{field}: Text liegt außerhalb der zugeordneten Spalte; Wert unbekannt")
            else:
                getattr(person, field).bbox = Box.model_validate(item["bbox"])
                scores = [c.get("ocr_confidence") for c in observed if c.get("ocr_confidence") is not None]
                # Native Paddle/Docling scores are on 0..1; this is a review flag, never a correctness probability.
                low = any(0 <= score < .5 for score in scores)
                partial = bool(re.search(r"\.\.\.|…", getattr(person, field).value or ""))
                item["observation_state"] = "partial" if partial else "uncertain" if low else "observed"
                if low or partial:
                    getattr(person, field).state = "uncertain"
                    person.review_notes.append(f"{field}: beobachteter Teiltext oder niedrige OCR-Engine-Konfidenz; Originalwert erhalten")
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
