"""Deterministic conversion of native TableFormer cells; HTML is an explicit backup.

The original grid, spans, headings and empty/missing distinction remain auditable.
No OCR, language model, fixed pixel columns or reference data enter this module.
"""

import re
from collections import defaultdict

from .column_headers import ORGANIZATION_ALIASES, field_roles
from .schema import TEXT_FIELDS, Box, Participant, TextField
from .structure_assignment import rectangle, union
from .unlimited_assignment import source_rows

VERSION = "tableformer-native-headings-v2"


def table_rows(table, table_index=0, size=None):
    data = table.get("native", {}).get("data", {})
    native = data.get("table_cells", [])
    height, width = data.get("num_rows"), data.get("num_cols")
    if not native:
        rows, notes = source_rows(table.get("html", ""))
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


def extract_structured(recognized, context=None):
    people, proofs, notes = [], [], []
    context = dict(context or {})
    size = recognized.get("native", {}).get("pages", {}).get("1", {}).get("size", {})
    aliases = recognized.get("organization_header_aliases") or ORGANIZATION_ALIASES
    diagnostics = []
    for table_index, table in enumerate(recognized.get("tables", [])):
        rows, source, errors = table_rows(table, table_index, size)
        notes.extend(errors)
        mapping, headings = {}, {}
        width = max((row.get("grid_width", max((c["column_start"]+c["colspan"] for c in row["cells"]), default=0))
                     for row in rows), default=0)
        inherited = context.get("width") == width
        if inherited:
            mapping = {key: set(value) for key, value in context.get("mapping", {}).items()}
            headings = context.get("headings", {})
        last_header = -2
        for row in rows:
            classified = [(cell, field_roles(cell["text"], aliases)) for cell in row["cells"]]
            found = set().union(*(roles for _, roles in classified)) if classified else set()
            header = (bool(found & {"first_name", "last_name"}) and len(found & set(TEXT_FIELDS)) >= 2
                      or bool(found) and last_header == row["row_index"]-1)
            if header:
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
                context = dict(width=width, mapping={key: sorted(cols) for key, cols in mapping.items()},
                               headings=headings)
                inherited = False
                continue
            if not mapping:
                continue
            if row["row_index"] <= last_header:
                continue
            # HTML may omit cells. Native grids distinguish missing from explicitly empty cells.
            if source == "html" and max((c["column_start"]+c["colspan"] for c in row["cells"]), default=0) != width:
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
                fields[field] = TextField(value=cell["text"], state="read" if cell["text"] else "empty",
                    bbox=Box.model_validate(cell["bbox"]) if cell.get("bbox") else None)
                evidence[field] = dict(text=cell["text"], column_start=cell["column_start"],
                    native_ref=cell.get("native_ref"), heading=headings.get(field, []),
                    assignment_rule="native_printed_header_cell" if source == "native" else "html_printed_header_cell")
            combined = (mapping.get("first_name") and mapping.get("first_name") == mapping.get("last_name"))
            value = fields["last_name"].value
            if combined or (not mapping.get("first_name") and value and "," in value):
                if value and value.count(",") == 1 and all(part.strip() for part in value.split(",")):
                    last, first = (part.strip() for part in value.split(","))
                    box = fields["last_name"].bbox
                    fields["first_name"] = TextField(value=first, state="read", bbox=box)
                    fields["last_name"] = TextField(value=last, state="read", bbox=box)
                    for key, text in (("first_name", first), ("last_name", last)):
                        evidence[key] = dict(evidence.get("last_name", {}), text=text,
                                             assignment_rule="explicit_surname_comma_given_name")
                else:
                    fields["first_name"], fields["last_name"] = TextField(), TextField()
                    warnings.append("Name split unknown; combined cell retained in source evidence")
            if not any(fields[f].value for f in ("first_name", "last_name", "personnel_number")):
                continue
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
                column_mapping={key: sorted(cols) for key, cols in mapping.items()}, original_headings=headings))
        diagnostics.append(dict(table_index=table_index, grid_source=source, rows=len(rows), width=width,
            columns={key: sorted(cols) for key, cols in mapping.items()}, headings=headings,
            organization_mapping="unique" if len(mapping.get("department", [])) == 1 else "ambiguous_or_missing"))
        if not mapping:
            notes.append(f"column_mapping_failed: table {table_index} has no identifiable printed column headings")
    recognized["mapping_diagnostics"] = diagnostics
    if not people:
        notes.append("No reliably assignable participants; native cells and OCR remain available for review")
    return people, proofs, notes, context
