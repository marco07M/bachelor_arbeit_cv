"""Layout-based rows and columns, conservative signature-field inspection."""

import re
import time

import cv2
import numpy as np

from .ocr import grid_masks
from .schema import TEXT_FIELDS, Box, Participant, TextField
from .signatures import row_regions


def token_key(text):
    return re.sub(r"[^a-zäöüß]", "", text.casefold())


def line_positions(mask, axis, fraction=0.25):
    indices = np.flatnonzero(np.mean(mask > 0, axis=axis) > fraction)
    if not len(indices):
        return []
    groups = np.split(indices, np.flatnonzero(np.diff(indices) > 2) + 1)
    size = mask.shape[0 if axis == 1 else 1]
    return [float(np.mean(group) / size) for group in groups]


def find_headers(words, aliases, row_tolerance):
    """Match exact configured labels, including labels split into adjacent OCR words."""
    normalized = {field: {token_key(alias) for alias in values} for field, values in aliases.items()}
    headers = {}
    for word in words:
        key = token_key(word["text"])
        if not key or not any(label.startswith(key) for values in normalized.values() for label in values):
            continue
        candidates = [word]
        center = (word["bbox"]["y0"] + word["bbox"]["y1"]) / 2
        neighbors = sorted((
            other for other in words
            if other["bbox"]["x0"] >= word["bbox"]["x1"]
            and abs((other["bbox"]["y0"] + other["bbox"]["y1"]) / 2 - center) <= row_tolerance
        ), key=lambda other: other["bbox"]["x0"])
        for other in neighbors[:3]:
            if other["bbox"]["x0"] - candidates[-1]["bbox"]["x1"] > 0.035:
                break
            candidates.append(other)
        for length in range(1, len(candidates) + 1):
            group = candidates[:length]
            combined = "".join(token_key(w["text"]) for w in group)
            for field, values in normalized.items():
                if combined not in values or field in headers:
                    continue
                headers[field] = dict(word, text=" ".join(w["text"] for w in group), bbox={
                    "x0": min(w["bbox"]["x0"] for w in group),
                    "y0": min(w["bbox"]["y0"] for w in group),
                    "x1": max(w["bbox"]["x1"] for w in group),
                    "y1": max(w["bbox"]["y1"] for w in group),
                })
    return headers


def layout(image, data, config):
    _, horizontal, vertical = grid_masks(image)
    hlines = line_positions(horizontal, 1)
    vlines = line_positions(vertical, 0, 0.05)
    words = data["words"]
    headers = find_headers(words, config.rules.header_aliases, config.rules.row_tolerance)
    columns = dict(config.rules.columns)
    anchors = sorted((w["bbox"]["x0"], name, w) for name, w in headers.items())
    for index, (x, name, word) in enumerate(anchors):
        if name in columns:
            continue
        # Use actual vertical separators where possible; otherwise header-derived intervals.
        lefts = [v for v in vlines if v <= x]
        rights = [v for v in vlines if v >= word["bbox"]["x1"]]
        if lefts and rights:
            columns[name] = (max(lefts), min(rights))
        else:
            left = max(0.0, x - 0.012)
            right = anchors[index + 1][0] - 0.012 if index + 1 < len(anchors) else 0.98
            if right > left:
                columns[name] = (left, right)
    top = config.rules.body_top
    if top is None:
        if len(headers) < 3 and len(set(headers).intersection(TEXT_FIELDS)) < 2:
            found = ", ".join(sorted(headers)) or "keine"
            return [], columns, [
                f"Spaltenüberschriften nicht ausreichend erkannt ({found}). "
                "Für diese Vorlage rules.columns und rules.body_top konfigurieren; OCR-Text manuell prüfen."
            ]
        top = max(w["bbox"]["y1"] for w in headers.values()) + 0.002
    bottom = config.rules.body_bottom
    rows = []
    boundaries = [v for v in hlines if v > top and v <= bottom]
    if len(boundaries) >= 2:
        # top can fall just below the first separator (e.g. header glyphs touch
        # that line). Keep the first body band; an empty partial band adds nobody.
        rows = list(zip([top, *boundaries[:-1]], boundaries, strict=True))
    else:
        body_words = sorted(
            (w for w in words if top < w["bbox"]["y0"] < bottom), key=lambda w: w["bbox"]["y0"]
        )
        groups = []
        for word in body_words:
            y = (word["bbox"]["y0"] + word["bbox"]["y1"]) / 2
            if not groups or abs(y - groups[-1][0]) > config.rules.row_tolerance:
                groups.append((y, [word]))
            else:
                groups[-1][1].append(word)
        rows = [
            (
                max(top, min(w["bbox"]["y0"] for w in group) - 0.003),
                min(bottom, max(w["bbox"]["y1"] for w in group) + 0.003),
            )
            for _, group in groups
        ]
    notes = [] if len(boundaries) >= 2 else ["Rows from word baselines; wrapped text may split participants"]
    return rows, columns, notes


def signature(image, box: Box | None, data, config):
    if box is None:
        return None, "uncertain", "Unterschriftsfeld nicht zugeordnet; Signaturstatus unbekannt"
    width, height = image.size
    crop = image.crop((int(box.x0 * width), int(box.y0 * height), int(box.x1 * width), int(box.y1 * height)))
    ink, horizontal, vertical = grid_masks(crop)
    # Only remove geometric cell edges. An interior straight stroke may be content,
    # so deleting every long horizontal component could create a false blank decision.
    edge_h = max(2, int(ink.shape[0] * 0.10))
    edge_w = max(2, int(ink.shape[1] * 0.05))
    horizontal[edge_h:-edge_h, :] = 0
    vertical[:, edge_w:-edge_w] = 0
    cleaned = cv2.subtract(ink, cv2.dilate(cv2.bitwise_or(horizontal, vertical), np.ones((3, 3), np.uint8)))
    # Remove edge remnants, never erase OCR words: unexpected printed text requires review too.
    border = max(2, int(min(cleaned.shape) * 0.04))
    cleaned[:border] = cleaned[-border:] = 0
    cleaned[:, :border] = cleaned[:, -border:] = 0
    count, labels, stats, _ = cv2.connectedComponentsWithStats(cleaned)
    area = sum(
        int(stats[i, cv2.CC_STAT_AREA])
        for i in range(1, count)
        if stats[i, cv2.CC_STAT_AREA] >= config.signature.component_min_area
    )
    fraction = area / max(1, cleaned.size)
    if fraction <= config.signature.blank_ink_fraction:
        return False, "read", "Localized field blank after grid removal; inspect threshold on real scans"
    return None, "uncertain", "Ink/printed marks present; no validated positive signature classifier"


def extract_rules(image, data, config):
    start = time.perf_counter()
    rows, columns, notes = layout(image, data, config)
    participants, signature_seconds = [], 0.0
    for y0, y1 in rows:
        fields = {}
        for name in TEXT_FIELDS:
            if name not in columns:
                fields[name] = TextField(state="uncertain")
                continue
            x0, x1 = columns[name]
            box = Box(x0=x0, y0=y0, x1=x1, y1=y1)
            words = [
                w
                for w in data["words"]
                if x0 <= (w["bbox"]["x0"] + w["bbox"]["x1"]) / 2 < x1
                and y0 <= (w["bbox"]["y0"] + w["bbox"]["y1"]) / 2 < y1
            ]
            words.sort(key=lambda w: (round(w["bbox"]["y0"], 2), w["bbox"]["x0"]))
            value = " ".join(w["text"] for w in words)
            state = "read" if value else "empty"
            if words and any(w["ocr_confidence"] is not None and w["ocr_confidence"] < 30 for w in words):
                state = "uncertain"
            fields[name] = TextField(value=value if value else None, state=state, bbox=box)
        if not any(f.value for f in fields.values()):
            continue
        row_ref = None
        if "row_ref" in columns:
            left, right = columns["row_ref"]
            candidates = [
                w["text"]
                for w in data["words"]
                if left <= w["bbox"]["x0"] < right
                and y0 <= w["bbox"]["y0"] < y1
                and re.fullmatch(r"\d+", w["text"])
            ]
            if len(candidates) == 1:
                row_ref = candidates[0]
        sig_box = None
        if "signature" in columns and not notes:
            sig_box = Box(x0=columns["signature"][0], y0=y0, x1=columns["signature"][1], y1=y1)
        sig_start = time.perf_counter()
        present, state, note = signature(image, sig_box, data, config)
        signature_seconds += time.perf_counter() - sig_start
        participants.append(
            Participant(
                row_ref=row_ref,
                bbox=Box(x0=0.0, y0=y0, x1=1.0, y1=y1),
                **fields,
                signature_present=present,
                signature_state=state,
                signature_bbox=sig_box,
                signature_method="opencv_conservative",
                review_notes=notes + [note],
            )
        )
    return (
        participants,
        notes,
        {
            "structure_seconds": time.perf_counter() - start - signature_seconds,
            "signature_seconds": signature_seconds,
        },
    )


def attach_signatures(participants, image, data, config):
    """B uses its own participant locations; do not silently transfer A's participant assignment."""
    start = time.perf_counter()
    _, columns, _ = layout(image, data, config)
    regions = row_regions(participants, config)
    for participant, region in zip(participants, regions, strict=True):
        box = participant.bbox
        sig_box = None
        if box and region and "signature" in columns:
            left, right = columns["signature"]
            sig_box = Box(x0=left, y0=region.y0, x1=right, y1=region.y1)
        present, state, note = signature(image, sig_box, data, config)
        participant.signature_present = present
        participant.signature_state = state
        participant.signature_bbox = sig_box
        participant.signature_method = "opencv_conservative"
        participant.review_notes.append(note)
    return time.perf_counter() - start


def signature_columns(image, raw, config, previous=None, *, document_id, page_number):
    """Locate the assumed signature column using existing scoped heading/geometry checks."""
    from .column_context import compatible, mapping_diagnostics
    from .ocr_layout import with_table_columns

    traces = mapping_diagnostics(raw)
    data = raw.get("ocr") or raw.get("signature_ocr") or {}
    context = previous or {}
    if data.get("words"):
        layout_data = with_table_columns(data, image, dict(column_mapping_context=context),
                                        document_id=document_id, page_number=page_number)
        context = layout_data["column_mapping_context"]
        traces = [*traces, layout_data["mapping_provenance"]]
    intervals, accepted = [], []
    for trace in traces:
        if trace.get("document_id") != document_id or trace.get("page_number") != page_number:
            continue
        profile = trace.get("geometry") or {}
        columns = trace.get("column_mapping", {}).get("signature", [])
        text_columns = {c for f in TEXT_FIELDS for c in trace.get("column_mapping", {}).get(f, [])}
        if set(columns) & text_columns:
            return [], context, dict(assumed_present=True, status="ambiguous_column_position", intervals=[])
        edges = profile.get("edges", [])
        inherited = trace.get("status") == "inherited_from_previous_page"
        if inherited and not compatible((trace.get("geometry_check") or {}).get("source_geometry"), profile)[0]:
            continue  # Text-prefix compatibility does not prove a trailing signature cell.
        if trace.get("status") not in ("detected_on_current_page", "updated_on_current_page", "inherited_from_previous_page"):
            continue
        if columns and all(isinstance(c, int) and 0 <= c < len(edges) - 1 for c in columns):
            current = [(edges[c], edges[c+1]) for c in sorted(set(columns))]
            if intervals and current != intervals:
                return [], context, dict(assumed_present=True, status="ambiguous_column_position")
            intervals, accepted = current, [*accepted, trace]
    if not intervals and "signature" in config.rules.columns:
        intervals = [config.rules.columns["signature"]]
        return intervals, context, dict(assumed_present=True, status="configured_column_position", intervals=intervals)
    return intervals, context, dict(assumed_present=True, status="localized" if intervals else "column_position_unknown",
                                   intervals=intervals, mapping_provenance=accepted)


def inspect_signature_cells(participants, image, raw, config, previous=None, *, document_id, page_number):
    """Image-only presence checks on actual cells; never consume signature OCR as text."""
    columns, context, trace = signature_columns(image, raw, config, previous,
                                               document_id=document_id, page_number=page_number)
    regions = row_regions(participants, config)
    _, horizontal, _ = grid_masks(image)
    boundaries = line_positions(horizontal, 1)
    records = []
    for index, (person, region) in enumerate(zip(participants, regions, strict=True)):
        box = person.bbox
        basis = "unknown"
        if box and region:
            text_anchors = set()
            for mapping_trace in trace.get("mapping_provenance", []):
                edges = (mapping_trace.get("geometry") or {}).get("edges", [])
                text_anchors.update((edges[c]+edges[c+1])/2 for field in TEXT_FIELDS
                    for c in mapping_trace.get("column_mapping", {}).get(field, []) if 0 <= c < len(edges)-1)
            text_anchors.update((left+right)/2 for field, (left, right) in config.rules.columns.items() if field in TEXT_FIELDS)
            if not text_anchors and box.x0 != 0 and box.x1 != 1:
                text_anchors.add((box.x0+box.x1)/2)
            text_anchors = {x for x in text_anchors if not any(left <= x <= right for left, right in columns)}
            anchors = [*text_anchors, *((left+right)/2 for left, right in columns)]
            # A signature stroke alone must never shorten its own cell and then be erased as a border.
            height, width = horizontal.shape
            verified = [y for y in boundaries if text_anchors and all(np.any(horizontal[
                max(0, int(y*height)-2):min(height, int(y*height)+3),
                max(0, int(x*width)-2):min(width, int(x*width)+3)]) for x in anchors)]
            center = (box.y0 + box.y1) / 2
            before, after = [y for y in verified if y < box.y0], [y for y in verified if y > box.y1]
            if before and after and max(before) <= center <= min(after) and min(after)-max(before) <= config.signature.max_row_height:
                region = Box(x0=0, x1=1, y0=max(before), y1=min(after))
                basis = "measured_grid_lines"
            elif box.x0 == 0 and box.x1 == 1:
                region, basis = box, "explicit_row_box"
            else:
                basis = "interpolated_text_band"
            if any(other is not person and other.bbox and
                   min(region.y1, other.bbox.y1) > max(region.y0, other.bbox.y0) for other in participants):
                region, basis = None, "overlapping_participant_rows"
            if any(r.get("output_index") == index and r.get("location_source") == "local_vlm"
                   for r in raw.get("signature_checks", [])):
                basis = "estimated_row_position"
        cells = []
        if region:
            for left, right in columns:
                cell = Box(x0=left, x1=right, y0=region.y0, y1=region.y1)
                present, _, note = signature(image, cell, {}, config)
                cells.append(dict(bbox=cell.model_dump(), blank=present is False, reason=note))
        reliable = bool(cells and basis in ("measured_grid_lines", "explicit_row_box"))
        blank = reliable and all(cell["blank"] for cell in cells)
        prior = person.signature_present
        conflict = bool(blank and prior is True)
        present = False if blank and not conflict else True if prior is True and cells and not conflict else None
        person.signature_present = present
        person.signature_state = "empty" if present is False else "read" if present else "uncertain"
        person.signature_method = "opencv_cells"
        person.signature_bbox = (Box(x0=min(c["bbox"]["x0"] for c in cells), x1=max(c["bbox"]["x1"] for c in cells),
                                     y0=region.y0, y1=region.y1) if cells else None)
        reason = ("Bildbefund: alle lokalisierten Signaturzellen wahrscheinlich leer; nicht manuell bestätigt." if present is False else
                  "Widerspruch zwischen erkannter Signatur und leerer Bildzelle; manuell prüfen." if conflict else
                  "Signatur als vorhanden erkannt; keine Transkription." if present is True else
                  "Signaturpräsenz unklar: Zellposition, Zeilengrenzen oder Bildinhalt nicht hinreichend sicher.")
        person.review_notes.append(reason)
        records.append(dict(output_index=index, participant_row=box.model_dump() if box else None,
                            region=region.model_dump() if region else None, row_basis=basis, cells=cells,
                            reliable_blank=blank and not conflict, signature_present=present,
                            prior_signature_present=prior, conflict=conflict, reason=reason))
    raw["signature_column_mapping"], raw["signature_cell_checks"] = trace, records
    raw["signature_column_context"] = context
    return context
