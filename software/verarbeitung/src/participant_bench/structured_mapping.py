"""Deterministic conversion of native TableFormer cells; HTML is an explicit backup.

The original grid, spans, headings and empty/missing distinction remain auditable.
No OCR, language model, fixed pixel columns or reference data enter this module.
"""

import re
from collections import defaultdict

from .column_context import geometry, resolve
from .column_headers import ORGANIZATION_ALIASES, field_roles
from .name_parts import classify_name_pair, infer_column_tiebreaker, split_combined_name
from .schema import TEXT_FIELDS, Box, Participant, TextField
from .structure_assignment import rectangle, union
from .unlimited_assignment import source_rows

VERSION = "tableformer-native-v7-row-observation-trace"


def _is_combined_name_cell(text: str) -> bool:
    if not text or any(c.isdigit() for c in text):
        return False
    if re.fullmatch(r"[^\d,]{2,80},\s*[^\d,]{2,80}", text) and split_combined_name(text):
        return True
    if "," not in text and len(text.split()) == 2:
        return classify_name_pair(*text.split()) is not None
    return False


def _two_column_headerless_fallback(rows):
    """Recover two separate unnamed name columns when >= 2 rows show unambiguous given/surname pairs."""
    pair_support = defaultdict(set)
    id_support = defaultdict(set)
    for row in rows:
        cells = {c["column_start"]: c for c in row["cells"] if c["colspan"] == c["rowspan"] == 1}
        for col, cell in cells.items():
            if re.fullmatch(r"[0-9]{4,16}", cell["text"]):
                id_support[col].add(row["row_index"])
        for col_a in sorted(cells):
            col_b = col_a + 1
            if col_b not in cells:
                continue
            text_a, text_b = cells[col_a]["text"].strip(), cells[col_b]["text"].strip()
            if not text_a or not text_b or any(c.isdigit() for c in text_a + text_b):
                continue
            clean_a, clean_b = text_a.rstrip(",").strip(), text_b.rstrip(",").strip()
            if (text_a.endswith(",") and all(any(c.isalpha() for c in p) for p in (clean_a, clean_b))) or (
                classify_name_pair(clean_a, clean_b) is not None
            ):
                pair_support[(col_a, col_b)].add(row["row_index"])
    valid_pairs = [pair for pair, indices in pair_support.items() if len(indices) >= 2]
    if len(valid_pairs) != 1:
        return [], []
    col_a, col_b = valid_pairs[0]
    id_cols = [col for col, indices in id_support.items() if col not in (col_a, col_b) and len(indices) >= 2]
    id_column = id_cols[0] if len(id_cols) == 1 else None
    start = min(pair_support[(col_a, col_b)])
    counts = {"given_family": 0, "family_given": 0}
    for row in rows:
        if row["row_index"] < start:
            continue
        cells = {c["column_start"]: c for c in row["cells"] if c["colspan"] == c["rowspan"] == 1}
        cell_a, cell_b = cells.get(col_a), cells.get(col_b)
        if not cell_a or not cell_b:
            continue
        text_a, text_b = cell_a["text"].strip(), cell_b["text"].strip()
        if text_a.endswith(","):
            counts["family_given"] += 1
        else:
            cls = classify_name_pair(text_a.rstrip(",").strip(), text_b.rstrip(",").strip())
            if cls is not None:
                counts[cls[0]] += 1
    tiebreaker = "given_family" if counts["given_family"] > counts["family_given"] else "family_given"
    people, proofs = [], []
    for row in rows:
        if row["row_index"] < start:
            continue
        cells = {c["column_start"]: c for c in row["cells"] if c["colspan"] == c["rowspan"] == 1}
        cell_a, cell_b = cells.get(col_a), cells.get(col_b)
        if not cell_a or not cell_b:
            continue
        text_a, text_b = cell_a["text"].strip(), cell_b["text"].strip()
        clean_a, clean_b = text_a.rstrip(",").strip(), text_b.rstrip(",").strip()
        if not clean_a or not clean_b or any(c.isdigit() for c in clean_a + clean_b):
            continue
        if not all(any(c.isalpha() for c in p) for p in (clean_a, clean_b)):
            continue
        if text_a.endswith(","):
            first, last, first_cell, last_cell = clean_b, clean_a, cell_b, cell_a
            rule = "explicit_surname_comma_given_name"
        else:
            cls = classify_name_pair(clean_a, clean_b)
            if cls is not None:
                order, first, last, rule = cls
            else:
                order = tiebreaker
                first, last = (clean_a, clean_b) if order == "given_family" else (clean_b, clean_a)
                rule = "column_majority_tiebreaker"
            first_cell, last_cell = (cell_a, cell_b) if order == "given_family" else (cell_b, cell_a)
        identifier = cells.get(id_column) if id_column is not None else None
        fields = {key: TextField() for key in TEXT_FIELDS}
        evidence = {}
        for key, value, cell, cell_rule in (
            ("first_name", first, first_cell, rule),
            ("last_name", last, last_cell, rule),
            ("personnel_number", identifier["text"] if identifier and re.fullmatch(r"[0-9]{4,16}", identifier["text"]) else None, identifier, "unverified_repeated_identity_cells"),
        ):
            if value and cell:
                fields[key] = TextField(value=value, state="uncertain",
                    bbox=Box.model_validate(cell["bbox"]) if cell.get("bbox") else None)
                evidence[key] = dict(text=value, native_ref=cell.get("native_ref"),
                    column_start=cell["column_start"], assignment_rule=cell_rule)
        people.append(Participant(**fields, review_notes=[
            "Unverified native-cell fallback: repeated name/number columns, printed headings missing; manual review required",
            "Organization and signature columns not inferred"]))
        proofs.append(dict(source_row=row["id"], source_row_index=row["row_index"],
            grid_source="native", fields=evidence, source_cells=row["cells"],
            raw_cells=[c["text"] for c in row["cells"]], fallback=True,
            assignment_rule="unverified_repeated_identity_cells", support_rows=sorted(pair_support[(col_a, col_b)])))
    return people, proofs


def partial_identity_fallback(rows):
    """Recover repeated native identity cells without pretending that missing headers were read.

    Require at least two rows with a recognizable combined name (comma-delimited or
    unambiguous given/surname pair) or two adjacent unnamed name columns.
    Merged cells and ambiguous competing column pairs are deliberately ineligible.
    """
    support = defaultdict(set)
    name_only_support = defaultdict(set)
    for row in rows:
        cells = [c for c in row["cells"] if c["colspan"] == c["rowspan"] == 1]
        names = [c for c in cells if _is_combined_name_cell(c["text"])]
        ids = [c for c in cells if re.fullmatch(r"[0-9]{4,16}", c["text"])]
        for name in names:
            name_only_support[name["column_start"]].add(row["row_index"])
            for identifier in ids:
                support[name["column_start"], identifier["column_start"]].add(row["row_index"])
    pairs = [pair for pair, indices in support.items() if len(indices) >= 2]
    if len(pairs) == 1:
        name_column, id_column = pairs[0]
        support_indices = support[pairs[0]]
    elif len(pairs) == 0:
        name_cols = [col for col, indices in name_only_support.items() if len(indices) >= 2]
        if len(name_cols) == 1:
            name_column, id_column = name_cols[0], None
            support_indices = name_only_support[name_column]
        else:
            return _two_column_headerless_fallback(rows)
    else:
        return [], []
    start = min(support_indices)
    col_values = [
        c["text"]
        for r in rows
        if r["row_index"] >= start
        for c in r["cells"]
        if c["colspan"] == c["rowspan"] == 1 and c["column_start"] == name_column
    ]
    tiebreaker = infer_column_tiebreaker(col_values)
    people, proofs = [], []
    for row in rows:
        if row["row_index"] < start:
            continue
        cells = {c["column_start"]: c for c in row["cells"] if c["colspan"] == c["rowspan"] == 1}
        name = cells.get(name_column)
        if not name or not name["text"] or any(c.isdigit() for c in name["text"]):
            continue
        split = split_combined_name(name["text"], default_order=tiebreaker)
        identifier = cells.get(id_column) if id_column is not None else None
        if not split and not (identifier and re.fullmatch(r"[0-9]{4,16}", identifier["text"])):
            continue
        first, last, name_rule = split if split else (None, None, "unverified_repeated_identity_cells")
        fields = {key: TextField() for key in TEXT_FIELDS}
        evidence = {}
        for key, value, cell, cell_rule in (
            ("first_name", first, name, name_rule),
            ("last_name", last, name, name_rule),
            ("personnel_number", identifier["text"] if identifier else None, identifier, "unverified_repeated_identity_cells"),
        ):
            if value and cell:
                fields[key] = TextField(value=value, state="uncertain",
                    bbox=Box.model_validate(cell["bbox"]) if cell.get("bbox") else None)
                evidence[key] = dict(text=value, native_ref=cell.get("native_ref"),
                    column_start=cell["column_start"], assignment_rule=cell_rule)
        people.append(Participant(**fields, review_notes=[
            "Unverified native-cell fallback: repeated name/number columns, printed headings missing; manual review required",
            "Organization and signature columns not inferred"]))
        proofs.append(dict(source_row=row["id"], source_row_index=row["row_index"],
            grid_source="native", fields=evidence, source_cells=row["cells"],
            raw_cells=[c["text"] for c in row["cells"]], fallback=True,
            assignment_rule="unverified_repeated_identity_cells", support_rows=sorted(support_indices)))
    return people, proofs


def table_rows(table, table_index=0, size=None):
    data = table.get("native", {}).get("data", {})
    native = data.get("table_cells", [])
    height, width = data.get("num_rows"), data.get("num_cols")
    if not native:
        rows, notes = source_rows(table.get("html", ""))
        for row in rows:
            row.update(id=f"t{table_index}r{row['row_index']}", table_index=table_index)
        return rows, "html", notes
    if not isinstance(height, int) or not isinstance(width, int) or not (0 < height <= 10000 and 0 < width <= 256):
        return [], "native", ["table_structure_failed: invalid native grid dimensions"]
    rows, occupied = defaultdict(list), set()
    for index, cell in enumerate(native):
        r, c = cell.get("start_row_offset_idx"), cell.get("start_col_offset_idx")
        end_r, end_c = cell.get("end_row_offset_idx"), cell.get("end_col_offset_idx")
        if not all(isinstance(v, int) for v in (r, c, end_r, end_c)) or not (
                0 <= r < end_r <= height and 0 <= c < end_c <= width):
            return [], "native", ["table_structure_failed: invalid native cell offsets; no grid guessed"]
        slots = {(i, j) for i in range(r, end_r) for j in range(c, end_c)}
        if occupied & slots:
            return [], "native", ["table_structure_failed: overlapping native cells; no grid guessed"]
        occupied |= slots
        raw_text = cell.get("text", "")
        box = None
        if size and size.get("width") and size.get("height") and cell.get("bbox"):
            box = rectangle(cell["bbox"], size["width"], size["height"])
        rows[r].append(dict(index=index, text=" ".join(raw_text.split()), raw_text=raw_text,
            column_start=c, rowspan=end_r-r, colspan=end_c-c, bbox=box,
            native_ref=f"tables/{table_index}/cells/{index}", column_header=cell.get("column_header", False)))
    return [dict(id=f"t{table_index}r{r}", table_index=table_index, row_index=r,
                 grid_width=width, cells=sorted(rows[r], key=lambda cell: cell["column_start"]))
            for r in sorted(rows)], "native", []


def _page_size(recognized):
    pages = recognized.get("native", {}).get("pages", {})
    if isinstance(pages, dict):
        for key in ("1", 1, *pages.keys()):
            size = pages.get(key, {}).get("size", {}) if isinstance(pages.get(key), dict) else {}
            if size.get("width") and size.get("height"):
                return size
    return {}


def _normalized_ocr_observations(recognized, size):
    raw_cells = recognized.get("ocr_cells") or recognized.get("engine_ocr_observations") or []
    observations = []
    for idx, obs in enumerate(raw_cells):
        if not isinstance(obs, dict):
            continue
        raw_text = str(obs.get("text", ""))
        text = " ".join(raw_text.split())
        if not text:
            continue
        raw_box = obs.get("bbox")
        box = None
        if isinstance(raw_box, dict):
            if all(k in raw_box for k in ("x0", "y0", "x1", "y1")):
                box = {k: float(raw_box[k]) for k in ("x0", "y0", "x1", "y1")}
            elif size and size.get("width") and size.get("height"):
                box = rectangle(raw_box, size["width"], size["height"])
        if not box or box["x1"] <= box["x0"] or box["y1"] <= box["y0"]:
            continue
        observations.append(
            dict(
                index=obs.get("index", idx),
                text=text,
                raw_text=raw_text,
                bbox=box,
                confidence=obs.get("confidence", obs.get("ocr_confidence")),
                native_ref=f"ocr_cells/{obs.get('index', idx)}",
            )
        )
    return observations


def _field_for_x(cx, intervals, margin=0.015):
    sig = intervals.get("signature")
    if sig and sig[0] <= cx <= sig[1]:
        # Do not pull signature ink into text fields unless it is inside a text field interval.
        if not any(
            intervals.get(f) and intervals[f][0] <= cx <= intervals[f][1]
            for f in TEXT_FIELDS
        ):
            return []
    matched = []
    for field in TEXT_FIELDS:
        band = intervals.get(field)
        if band and (band[0] - margin) <= cx <= (band[1] + margin):
            matched.append(field)
    return matched


def _apply_stage2_geometry_fallback(
    recognized,
    size,
    intervals,
    people,
    proofs,
    row_decisions,
    notes,
    *,
    table_index=0,
    header_bottom=0.0,
    aliases=ORGANIZATION_ALIASES,
    trace=None,
):
    if not intervals or (trace and trace.get("status") not in (
            "detected_on_current_page", "updated_on_current_page", "inherited_from_previous_page")):
        return 0
    observations = _normalized_ocr_observations(recognized, size)
    if not observations:
        return 0
    used_indices = set()
    row_bands = []
    # Mark observations that already overlap Stage 1 participant cells.
    for person, proof in zip(people, proofs):
        if proof.get("table_index", 0) != table_index:
            continue
        cell_boxes = [c["bbox"] for c in proof.get("source_cells", []) if isinstance(c.get("bbox"), dict)]
        if not cell_boxes and person.bbox:
            cell_boxes = [person.bbox.model_dump()]
        if not cell_boxes:
            continue
        rbox = union(cell_boxes)
        row_bands.append((rbox["y0"], rbox["y1"], person, proof))
        for obs in observations:
            obox = obs["bbox"]
            ov_y = min(rbox["y1"], obox["y1"]) - max(rbox["y0"], obox["y0"])
            min_h = max(min(rbox["y1"] - rbox["y0"], obox["y1"] - obox["y0"]), 1e-4)
            if ov_y / min_h > 0.35:
                # Check if any existing Stage 1 non-empty field already covers this X-band or text
                cx = (obox["x0"] + obox["x1"]) / 2
                fields_here = _field_for_x(cx, intervals)
                if any(getattr(person, f).value for f in fields_here):
                    used_indices.add(obs["index"])

    combined_name = (
        intervals.get("first_name") is not None
        and intervals.get("first_name") == intervals.get("last_name")
    )

    # Stage 2a: Complete missing/empty fields on existing Stage 1 rows from unassigned OCR observations.
    for ry0, ry1, person, proof in row_bands:
        row_obs = [
            obs
            for obs in observations
            if obs["index"] not in used_indices
            and obs["bbox"]["y0"] >= max(0.0, header_bottom - 0.005)
            and (min(ry1, obs["bbox"]["y1"]) - max(ry0, obs["bbox"]["y0"]))
            / max(min(ry1 - ry0, obs["bbox"]["y1"] - obs["bbox"]["y0"]), 1e-4)
            > 0.35
        ]
        if not row_obs:
            continue
        by_field = defaultdict(list)
        for obs in sorted(row_obs, key=lambda item: item["bbox"]["x0"]):
            cx = (obs["bbox"]["x0"] + obs["bbox"]["x1"]) / 2
            for field in _field_for_x(cx, intervals):
                by_field[field].append(obs)
        if combined_name and not person.first_name.value and not person.last_name.value and by_field.get("last_name"):
            items = by_field["last_name"]
            raw_val = " ".join(item["text"] for item in items).strip(" |_")
            if raw_val and any(c.isalpha() for c in raw_val) and not any(c.isdigit() for c in raw_val):
                box = Box.model_validate(union([item["bbox"] for item in items]))
                split = split_combined_name(raw_val)
                if split:
                    first, last, _ = split
                    person.first_name = TextField(value=first, state="uncertain", bbox=box)
                    person.last_name = TextField(value=last, state="uncertain", bbox=box)
                    for k, v in (("first_name", first), ("last_name", last)):
                        proof["fields"][k] = dict(
                            text=v,
                            native_ref=items[0]["native_ref"],
                            assignment_rule="geometry_fallback_ocr_observation",
                            observation_state="uncertain",
                            mapping_provenance=trace or {},
                        )
                else:
                    person.last_name = TextField(value=raw_val, state="uncertain", bbox=box)
                    proof["fields"]["last_name"] = dict(
                        text=raw_val,
                        native_ref=items[0]["native_ref"],
                        assignment_rule="geometry_fallback_ocr_observation",
                        observation_state="uncertain",
                        mapping_provenance=trace or {},
                    )
                for item in items:
                    used_indices.add(item["index"])
                person.review_notes.append("Stage 2 geometry fallback: name completed from raw OCR observation")
        for field in TEXT_FIELDS:
            if combined_name and field in ("first_name", "last_name"):
                continue
            if getattr(person, field).value or not by_field.get(field):
                continue
            items = by_field[field]
            raw_val = " ".join(item["text"] for item in items).strip(" |_")
            if not raw_val:
                continue
            if field == "personnel_number" and not any(c.isdigit() for c in raw_val):
                continue
            box = Box.model_validate(union([item["bbox"] for item in items]))
            setattr(person, field, TextField(value=raw_val, state="uncertain", bbox=box))
            proof["fields"][field] = dict(
                text=raw_val,
                native_ref=items[0]["native_ref"],
                assignment_rule="geometry_fallback_ocr_observation",
                observation_state="uncertain",
                mapping_provenance=trace or {},
            )
            for item in items:
                used_indices.add(item["index"])
            person.review_notes.append(f"Stage 2 geometry fallback: {field} completed from raw OCR observation")

    # Stage 2b: Group remaining orphaned OCR observations below header_bottom into continuation/orphan rows.
    orphans = []
    for obs in observations:
        if obs["index"] in used_indices:
            continue
        obox = obs["bbox"]
        cy = (obox["y0"] + obox["y1"]) / 2
        if cy <= header_bottom + 0.004:
            continue
        if any(
            (min(ry1, obox["y1"]) - max(ry0, obox["y0"]))
            / max(min(ry1 - ry0, obox["y1"] - obox["y0"]), 1e-4)
            > 0.3
            for ry0, ry1, _, _ in row_bands
        ):
            continue
        cx = (obox["x0"] + obox["x1"]) / 2
        if not _field_for_x(cx, intervals):
            continue
        orphans.append(obs)

    if not orphans:
        return 0

    orphans.sort(key=lambda item: ((item["bbox"]["y0"] + item["bbox"]["y1"]) / 2, item["bbox"]["x0"]))
    clusters = []
    for obs in orphans:
        obox = obs["bbox"]
        cy = (obox["y0"] + obox["y1"]) / 2
        placed = False
        for cluster in clusters:
            cbox = union([item["bbox"] for item in cluster])
            ccy = (cbox["y0"] + cbox["y1"]) / 2
            ov_y = min(cbox["y1"], obox["y1"]) - max(cbox["y0"], obox["y0"])
            min_h = max(min(cbox["y1"] - cbox["y0"], obox["y1"] - obox["y0"]), 1e-4)
            if ov_y / min_h > 0.25 or abs(cy - ccy) <= 0.014:
                cluster.append(obs)
                placed = True
                break
        if not placed:
            clusters.append([obs])

    added = 0
    for cluster_idx, cluster in enumerate(clusters):
        cluster.sort(key=lambda item: item["bbox"]["x0"])
        roles_found = set().union(*(field_roles(item["text"], aliases) for item in cluster))
        if bool(roles_found & {"first_name", "last_name"}) and len(roles_found & set(TEXT_FIELDS)) >= 2:
            continue
        by_field = defaultdict(list)
        for item in cluster:
            cx = (item["bbox"]["x0"] + item["bbox"]["x1"]) / 2
            for field in _field_for_x(cx, intervals):
                by_field[field].append(item)
        fields = {key: TextField() for key in TEXT_FIELDS}
        evidence = {}
        if combined_name and by_field.get("last_name"):
            items = by_field["last_name"]
            raw_val = " ".join(item["text"] for item in items).strip(" |_")
            if raw_val and any(c.isalpha() for c in raw_val) and not any(c.isdigit() for c in raw_val):
                box = Box.model_validate(union([item["bbox"] for item in items]))
                split = split_combined_name(raw_val)
                if split:
                    first, last, _ = split
                    fields["first_name"] = TextField(value=first, state="uncertain", bbox=box)
                    fields["last_name"] = TextField(value=last, state="uncertain", bbox=box)
                    for k, v in (("first_name", first), ("last_name", last)):
                        evidence[k] = dict(
                            text=v,
                            native_ref=items[0]["native_ref"],
                            assignment_rule="geometry_fallback_ocr_observation",
                            observation_state="uncertain",
                            mapping_provenance=trace or {},
                        )
                else:
                    fields["last_name"] = TextField(value=raw_val, state="uncertain", bbox=box)
                    evidence["last_name"] = dict(
                        text=raw_val,
                        native_ref=items[0]["native_ref"],
                        assignment_rule="geometry_fallback_ocr_observation",
                        observation_state="uncertain",
                        mapping_provenance=trace or {},
                    )
        for field in TEXT_FIELDS:
            if combined_name and field in ("first_name", "last_name"):
                continue
            items = by_field.get(field, [])
            if not items:
                continue
            raw_val = " ".join(item["text"] for item in items).strip(" |_")
            if not raw_val:
                continue
            if field == "personnel_number" and not any(c.isdigit() for c in raw_val):
                continue
            if field in ("first_name", "last_name") and (
                not any(c.isalpha() for c in raw_val) or any(c.isdigit() for c in raw_val)
            ):
                continue
            box = Box.model_validate(union([item["bbox"] for item in items]))
            fields[field] = TextField(value=raw_val, state="uncertain", bbox=box)
            evidence[field] = dict(
                text=raw_val,
                native_ref=items[0]["native_ref"],
                assignment_rule="geometry_fallback_ocr_observation",
                observation_state="uncertain",
                mapping_provenance=trace or {},
            )
        has_name = bool(fields["first_name"].value or fields["last_name"].value)
        has_id = bool(fields["personnel_number"].value)
        # Require a name, or both personnel_number and department, to prevent noisy numbers from becoming people.
        if not has_name and not (has_id and fields["department"].value):
            continue
        row_id = f"t{table_index}_ocr_r{cluster_idx}"
        rbox = Box.model_validate(union([item["bbox"] for item in cluster]))
        people.append(
            Participant(
                **fields,
                bbox=rbox,
                review_notes=[
                    "Stage 2 geometry fallback from raw OCR observations using fixed column context; manual review required"
                ],
            )
        )
        proofs.append(
            dict(
                output_index=len(people) - 1,
                source_row=row_id,
                table_index=table_index,
                source_row_index=cluster_idx,
                grid_source="ocr_geometry_fallback",
                fields=evidence,
                source_cells=cluster,
                raw_cells=[item["text"] for item in cluster],
                fallback=True,
                assignment_rule="geometry_fallback_ocr_observation",
                mapping_provenance=trace or {},
            )
        )
        row_decisions.append(
            dict(
                source_row=row_id,
                table_index=table_index,
                row_index=cluster_idx,
                native_refs=[item["native_ref"] for item in cluster],
                status="uncertain_participant",
                reason="geometry_fallback_ocr_observation",
                output_index=len(people) - 1,
            )
        )
        added += 1
    if added:
        notes.append("Stage 2 geometry fallback assigned orphaned OCR observations via fixed column X-intervals")
    return added


def extract_structured(recognized, context=None, *, document_id=None, page_number=None):
    people, proofs, notes = [], [], []
    context = dict(context or {})
    size = _page_size(recognized)
    aliases = recognized.get("organization_header_aliases") or ORGANIZATION_ALIASES
    diagnostics = []
    row_decisions = []
    for table_index, table in enumerate(recognized.get("tables", [])):
        rows, source, errors = table_rows(table, table_index, size)
        notes.extend(errors)
        mapping, headings = {}, {}
        width = max((row.get("grid_width", max((c["column_start"]+c["colspan"] for c in row["cells"]), default=0))
                     for row in rows), default=0)
        profile = geometry(width, rows)
        inherited, has_header, resolved = False, False, False
        trace = {}
        header_bottom = 0.0
        current_header_rows = [r["row_index"] for r in rows if (lambda found:
            len(found & set(TEXT_FIELDS)) >= 2)(
                set().union(*(field_roles(c["text"], aliases) for c in r["cells"])))
            or any(c.get("column_header") and field_roles(c["text"], aliases) for c in r["cells"])]
        last_header = -2
        for row in rows:
            decision = dict(source_row=row["id"], table_index=table_index, row_index=row["row_index"],
                native_refs=[c.get("native_ref") for c in row["cells"]])
            row_decisions.append(decision)
            if current_header_rows and row["row_index"] < min(current_header_rows):
                decision.update(status="context", reason="before_current_printed_headings")
                continue  # Current headings take precedence over an older layout, including metadata above them.
            classified = [(cell, field_roles(cell["text"], aliases)) for cell in row["cells"]]
            found = set().union(*(roles for _, roles in classified)) if classified else set()
            header = (len(found & set(TEXT_FIELDS)) >= 2
                      or any(cell.get("column_header") and roles for cell, roles in classified)
                      or bool(found) and last_header == row["row_index"]-1)
            if header:
                decision.update(status="context", reason="printed_headings")
                has_header, resolved = True, False
                if last_header != row["row_index"]-1:
                    mapping, headings = {}, {}
                last_header = row["row_index"]
                for cell, roles in classified:
                    if cell.get("bbox"):
                        header_bottom = max(header_bottom, cell["bbox"]["y1"])
                    for field in roles:
                        # A merged heading does not define which of its columns owns the field.
                        if cell["colspan"] == 1:
                            mapping.setdefault(field, set()).add(cell["column_start"])
                            headings.setdefault(field, []).append(dict(text=cell["raw_text"],
                                column=cell["column_start"], row=row["row_index"], bbox=cell.get("bbox")))
                for column in {c for cols in mapping.values() for c in cols}:
                    roles = {field for field, cols in mapping.items() if column in cols}
                    if len(roles) > 1 and roles != {"first_name", "last_name"}:
                        for field in roles:
                            mapping[field].discard(column)
                inherited = False
                continue
            if not resolved:
                mapping, context, trace = resolve(mapping, headings, profile, context,
                    document_id=document_id, page_number=page_number, has_header=has_header, column_count=width)
                resolved = True
                inherited = trace["status"] == "inherited_from_previous_page"
                if inherited:
                    headings = context["headings"]
            if not mapping:
                decision.update(status="unassigned", reason=trace.get("reason", "no_reliable_column_mapping"))
                continue
            if row["row_index"] <= last_header:
                decision.update(status="context", reason="at_or_before_current_headings")
                continue
            # HTML may omit cells. Native grids distinguish missing from explicitly empty cells.
            if source == "html" and max((c["column_start"]+c["colspan"] for c in row["cells"]), default=0) != width:
                decision.update(status="unassigned", reason="incomplete_html_grid")
                notes.append(f"cell_assignment_failed: table {table_index} row {row['row_index']} incomplete HTML grid")
                continue
            fields, evidence, warnings = {}, {}, []
            for field in TEXT_FIELDS:
                columns = mapping.get(field, set())
                candidates = [cell for cell in row["cells"] if cell["column_start"] in columns]
                if len(columns) != 1 or len(candidates) != 1 or candidates[0]["colspan"] != 1 or candidates[0]["rowspan"] != 1:
                    fields[field] = TextField()
                    warnings.append(f"{field}: column_mapping_failed" if len(columns) != 1 else f"{field}: cell_assignment_failed")
                    continue
                cell = candidates[0]
                partial = bool(re.search(r"\.\.\.|…", cell["text"]))
                fields[field] = TextField(value=cell["text"], state="uncertain" if partial else "read" if cell["text"] else "empty",
                    bbox=Box.model_validate(cell["bbox"]) if cell.get("bbox") else None)
                evidence[field] = dict(text=cell["text"], column_start=cell["column_start"],
                    native_ref=cell.get("native_ref"), heading=headings.get(field, []),
                    assignment_rule=("inherited_printed_header_cell" if inherited else
                                     "native_printed_header_cell" if source == "native" else "html_printed_header_cell"),
                    mapping_provenance=trace)
                evidence[field]["observation_state"] = "partial" if partial else "observed"
            combined = (mapping.get("first_name") and mapping.get("first_name") == mapping.get("last_name"))
            value = fields["last_name"].value
            if combined or (not mapping.get("first_name") and value and "," in value):
                col_values = [
                    c["text"]
                    for r in rows
                    if r["row_index"] > last_header
                    for c in r["cells"]
                    if c["column_start"] in mapping.get("last_name", set())
                ]
                tiebreaker = infer_column_tiebreaker(col_values)
                split = split_combined_name(value, default_order=tiebreaker)
                if split:
                    first, last, rule = split
                    box = fields["last_name"].bbox
                    fields["first_name"] = TextField(value=first, state="uncertain" if re.search(r"\.\.\.|…", first) else "read", bbox=box)
                    fields["last_name"] = TextField(value=last, state="uncertain" if re.search(r"\.\.\.|…", last) else "read", bbox=box)
                    for key, text in (("first_name", first), ("last_name", last)):
                        evidence[key] = dict(evidence.get("last_name", {}), text=text,
                                             assignment_rule=rule)
                    if rule == "default_name_group_order":
                        warnings.append("Namenszelle ohne Komma gemäß Vorgabe Nachname → Vorname zugeordnet")
                else:
                    words = [w for w in (value or "").split() if any(c.isalpha() for c in w)]
                    if len(words) == 1 and not any(c.isdigit() for c in (value or "")):
                        box = fields["last_name"].bbox
                        fields["first_name"] = TextField()
                        fields["last_name"] = TextField(value=value, state="uncertain", bbox=box)
                        evidence["last_name"] = dict(
                            evidence.get("last_name", {}),
                            text=value,
                            assignment_rule="single_token_combined_name_fallback",
                            observation_state="partial",
                        )
                        warnings.append("Single-token combined name retained as uncertain last_name")
                    else:
                        fields["first_name"], fields["last_name"] = TextField(), TextField()
                        warnings.append("Name split unknown; combined cell retained in source evidence")
            elif fields["first_name"].value and fields["last_name"].value:
                raw_first, raw_last = fields["first_name"].value.strip(), fields["last_name"].value.strip()
                clean_first, clean_last = raw_first.rstrip(",").strip(), raw_last.rstrip(",").strip()
                cls = classify_name_pair(clean_first, clean_last)
                if raw_first.endswith(",") or (cls is not None and cls[0] == "family_given"):
                    rule = "explicit_surname_comma_given_name" if raw_first.endswith(",") else cls[3]
                    fields["first_name"], fields["last_name"] = fields["last_name"], fields["first_name"]
                    fields["first_name"].value, fields["last_name"].value = clean_last, clean_first
                    if "first_name" in evidence and "last_name" in evidence:
                        evidence["first_name"], evidence["last_name"] = evidence["last_name"], evidence["first_name"]
                        evidence["first_name"]["text"] = clean_last
                        evidence["last_name"]["text"] = clean_first
                        evidence["first_name"]["assignment_rule"] = rule
                        evidence["last_name"]["assignment_rule"] = rule
            observed_unsplit = combined and value and any(c.isalpha() for c in value) and not any(c.isdigit() for c in value)
            if not any(fields[f].value for f in ("first_name", "last_name", "personnel_number")) and not observed_unsplit:
                decision.update(status="unassigned", reason="no_grounded_identity_field", field_warnings=warnings)
                continue
            decision.update(status="participant", reason="current_cells_in_mapped_columns", field_warnings=warnings,
                            output_index=len(people))
            boxes = [c["bbox"] for c in row["cells"] if c.get("bbox")]
            row_ref = next((c["text"] for c in row["cells"] if c["column_start"] in mapping.get("row_ref", set())
                            and re.fullmatch(r"[0-9]+", c["text"])), None)
            people.append(Participant(**fields, row_ref=row_ref,
                bbox=Box.model_validate(union(boxes)) if boxes else None,
                review_notes=warnings + ["Native TableFormer header mapping; no LLM"] +
                             (["Inherited headings of the same PDF; verify continuation layout"] if inherited else [])))
            proofs.append(dict(output_index=len(people)-1, source_row=row["id"], table_index=table_index,
                source_row_index=row["row_index"], grid_source=source, fields=evidence,
                source_cells=row["cells"], raw_cells=[c["text"] for c in row["cells"]],
                column_mapping={key: sorted(cols) for key, cols in mapping.items()}, original_headings=headings,
                mapping_provenance=trace))
        if not resolved:
            mapping, context, trace = resolve(mapping, headings, profile, context,
                document_id=document_id, page_number=page_number, has_header=has_header, column_count=width)
        fallback_count = 0
        intervals = trace.get("column_intervals") or trace.get("inherited_column_intervals") or {}
        if intervals:
            fallback_count += _apply_stage2_geometry_fallback(
                recognized,
                size,
                intervals,
                people,
                proofs,
                row_decisions,
                notes,
                table_index=table_index,
                header_bottom=header_bottom,
                aliases=aliases,
                trace=trace,
            )
        # Explicit but ambiguous headings must never be bypassed by content inference.
        if not mapping and not fallback_count and trace["status"] != "incompatible_table_structure" and source == "native" and not any(
                field_roles(c["text"], aliases) for row in rows for c in row["cells"]):
            recovered, recovered_proofs = partial_identity_fallback(rows)
            for person, proof in zip(recovered, recovered_proofs):
                proof.update(output_index=len(people), table_index=table_index)
                people.append(person)
                proofs.append(proof)
                for item in row_decisions:
                    if item["source_row"] == proof["source_row"]:
                        item.update(status="uncertain_participant", reason="repeated_native_identity_fallback",
                                    output_index=proof["output_index"])
            fallback_count = len(recovered)
            if recovered:
                notes.append("Unverified partial identity fallback; headings missing, organization remains unknown")
        diagnostics.append(dict(table_index=table_index, grid_source=source, rows=len(rows), width=width,
            **trace,
            fallback_participants=fallback_count,
            text_cells=sum(bool(c["text"]) for row in rows for c in row["cells"]),
            columns={key: sorted(cols) for key, cols in mapping.items()},
            organization_mapping="unique" if len(mapping.get("department", [])) == 1 else "ambiguous_or_missing"))
        if not mapping and not fallback_count:
            notes.append(f"column_mapping_failed: table {table_index} has no identifiable printed column headings")
    if not recognized.get("tables") and context and document_id is not None and isinstance(page_number, int):
        _, context, trace = resolve(
            {},
            {},
            None,
            context,
            document_id=document_id,
            page_number=page_number,
            has_header=False,
            column_count=0,
        )
        # No measured table means no inherited interval may drive field values.
        # Keep the rejection visible even when no participant could be assigned.
        diagnostics.append(dict(table_index=None, grid_source="unavailable", rows=0, width=0,
            **trace, fallback_participants=0, text_cells=0, columns={}, organization_mapping="ambiguous_or_missing"))
    recognized["mapping_diagnostics"] = diagnostics
    recognized["row_decisions"] = row_decisions
    for proof in proofs:
        proof.setdefault("provenance", "docling")
        for fp in proof.get("fields", {}).values():
            if isinstance(fp, dict):
                fp.setdefault("provenance", "docling")
    if not people:
        notes.append("No reliably assignable participants; native cells and OCR remain available for review")
    return people, proofs, notes, context
