"""Deterministic conversion of native TableFormer cells; HTML is an explicit backup.

The original grid, spans, headings and empty/missing distinction remain auditable.
No OCR, language model, fixed pixel columns or reference data enter this module.
"""

import re
from collections import defaultdict

from .column_context import geometry, resolve
from .column_headers import ORGANIZATION_ALIASES, field_roles
from .name_parts import split_combined_name
from .schema import TEXT_FIELDS, Box, Participant, TextField
from .structure_assignment import rectangle, union
from .unlimited_assignment import source_rows

VERSION = "tableformer-native-v7-row-observation-trace"


def partial_identity_fallback(rows):
    """Recover repeated native identity cells without pretending that missing headers were read.

    Require at least two rows with a comma-delimited name and a separate numeric
    identifier in the same column pair. No organization/signature column is guessed.
    Merged cells and ambiguous competing column pairs are deliberately ineligible.
    """
    support = defaultdict(set)
    for row in rows:
        cells = [c for c in row["cells"] if c["colspan"] == c["rowspan"] == 1]
        names = [c for c in cells if re.fullmatch(r"[^\d,]{2,80},\s*[^\d,]{2,80}", c["text"])
                 and split_combined_name(c["text"])]
        ids = [c for c in cells if re.fullmatch(r"[0-9]{4,16}", c["text"])]
        for name in names:
            for identifier in ids:
                support[name["column_start"], identifier["column_start"]].add(row["row_index"])
    pairs = [pair for pair, indices in support.items() if len(indices) >= 2]
    if len(pairs) != 1:
        return [], []
    name_column, id_column = pairs[0]
    start = min(support[pairs[0]])
    people, proofs = [], []
    for row in rows:
        if row["row_index"] < start:
            continue
        cells = {c["column_start"]: c for c in row["cells"] if c["colspan"] == c["rowspan"] == 1}
        name = cells.get(name_column)
        if not name or not name["text"] or any(c.isdigit() for c in name["text"]):
            continue
        split = split_combined_name(name["text"])
        identifier = cells.get(id_column)
        if not split and not (identifier and re.fullmatch(r"[0-9]{4,16}", identifier["text"])):
            continue
        first, last = split[:2] if split else (None, None)
        fields = {key: TextField() for key in TEXT_FIELDS}
        evidence = {}
        for key, value, cell in (("first_name", first, name), ("last_name", last, name),
                                 ("personnel_number", identifier["text"] if identifier else None, identifier)):
            if value and cell:
                fields[key] = TextField(value=value, state="uncertain",
                    bbox=Box.model_validate(cell["bbox"]) if cell.get("bbox") else None)
                evidence[key] = dict(text=value, native_ref=cell.get("native_ref"),
                    column_start=cell["column_start"], assignment_rule="unverified_repeated_identity_cells")
        people.append(Participant(**fields, review_notes=[
            "Unverified native-cell fallback: repeated name/number columns, printed headings missing; manual review required",
            "Organization and signature columns not inferred"]))
        proofs.append(dict(source_row=row["id"], source_row_index=row["row_index"],
            grid_source="native", fields=evidence, source_cells=row["cells"],
            raw_cells=[c["text"] for c in row["cells"]], fallback=True,
            assignment_rule="unverified_repeated_identity_cells", support_rows=sorted(support[pairs[0]])))
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


def extract_structured(recognized, context=None, *, document_id=None, page_number=None):
    people, proofs, notes = [], [], []
    context = dict(context or {})
    size = recognized.get("native", {}).get("pages", {}).get("1", {}).get("size", {})
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
        current_header_rows = [r["row_index"] for r in rows if (lambda found:
            bool(found & {"first_name", "last_name"}) and len(found & set(TEXT_FIELDS)) >= 2)(
                set().union(*(field_roles(c["text"], aliases) for c in r["cells"])))]
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
            header = (bool(found & {"first_name", "last_name"}) and len(found & set(TEXT_FIELDS)) >= 2
                      or bool(found) and last_header == row["row_index"]-1)
            if header:
                decision.update(status="context", reason="printed_headings")
                has_header, resolved = True, False
                if last_header != row["row_index"]-1:
                    mapping, headings = {}, {}
                last_header = row["row_index"]
                for cell, roles in classified:
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
                split = split_combined_name(value)
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
                    fields["first_name"], fields["last_name"] = TextField(), TextField()
                    warnings.append("Name split unknown; combined cell retained in source evidence")
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
        # Explicit but ambiguous headings must never be bypassed by content inference.
        if not mapping and trace["status"] != "incompatible_table_structure" and source == "native" and not any(
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
            columns={key: sorted(cols) for key, cols in mapping.items()}, headings=headings,
            organization_mapping="unique" if len(mapping.get("department", [])) == 1 else "ambiguous_or_missing"))
        if not mapping:
            notes.append(f"column_mapping_failed: table {table_index} has no identifiable printed column headings")
    recognized["mapping_diagnostics"] = diagnostics
    recognized["row_decisions"] = row_decisions
    if not people:
        notes.append("No reliably assignable participants; native cells and OCR remain available for review")
    return people, proofs, notes, context
