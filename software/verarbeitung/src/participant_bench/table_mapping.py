"""Deterministic, heading-based mapping of TableFormer cells. No generative model."""

import re
from collections import defaultdict

from .schema import TEXT_FIELDS, Box, Participant, TextField
from .structure_assignment import rectangle, union
from .unlimited_assignment import header_fields, source_rows, table_headers

VERSION = "tableformer-heading-mapping-v1"


def extract_docling(recognized: dict, context: dict | None = None):
    people, evidence, notes = [], [], []
    context = dict(context or {})
    pages = recognized.get("native", {}).get("pages", {})
    size = pages.get("1", pages.get(1, {})).get("size", {})
    for table_index, table in enumerate(recognized.get("tables", [])):
        rows, errors = source_rows(table.get("html", ""))
        notes.extend(errors)
        if not rows:
            continue
        headers, mappings = table_headers(rows)
        mapping = mappings.get(0, {})
        width = max((cell["column_start"] + cell["colspan"] for row in rows for cell in row["cells"]), default=0)
        header_end = max((row["row_index"] for row in headers), default=-1)
        if mapping:
            width = max(cell["column_start"] + cell["colspan"] for row in headers for cell in row["cells"])
            context = dict(width=width, mapping={key: sorted(value) for key, value in mapping.items()})
        elif context.get("width") == width:
            mapping = {key: set(value) for key, value in context["mapping"].items()}
            notes.append(f"Tabelle {table_index}: Spaltenüberschriften derselben PDF bei gleicher Tabellenbreite übernommen")
        else:
            notes.append(f"Tabelle {table_index}: keine eindeutigen Namens-/Spaltenüberschriften; manuelle Prüfung erforderlich")
            continue
        native = table.get("native", {}).get("data", {}).get("table_cells", [])
        positions = {}
        for cell in native:
            if cell.get("bbox") and size.get("width") and size.get("height"):
                box = rectangle(cell["bbox"], size["width"], size["height"])
                if box:
                    positions[(cell.get("start_row_offset_idx"), cell.get("start_col_offset_idx"))] = box
        for row in rows:
            if row["row_index"] <= header_end:
                continue
            if sum(bool(header_fields(cell["text"])) for cell in row["cells"]) >= 2:
                continue
            if max((cell["column_start"]+cell["colspan"] for cell in row["cells"]), default=0) != width:
                notes.append(f"Tabelle {table_index}, Zeile {row['row_index']}: abweichende Zellzahl; keine Spaltenverschiebung geraten")
                continue
            by_column = defaultdict(list)
            for cell in row["cells"]:
                cell = dict(cell)
                cell["bbox"] = positions.get((row["row_index"], cell["column_start"]))
                by_column[cell["column_start"]].append(cell)
            fields, proofs, warnings = {}, {}, []
            for field in TEXT_FIELDS:
                candidates = [cell for index in mapping.get(field, []) for cell in by_column[index]]
                if len(candidates) != 1 or candidates[0]["colspan"] != 1:
                    fields[field] = TextField()
                    if candidates:
                        warnings.append(f"{field}: mehrdeutige oder verbundene Quellzelle")
                    continue
                cell = candidates[0]
                text = cell["text"]
                fields[field] = TextField(value=text, state="read" if text else "empty",
                                         bbox=Box.model_validate(cell["bbox"]) if cell["bbox"] else None)
                proofs[field] = dict(column_start=cell["column_start"], text=text, assignment_rule="printed_header_cell")
            first_columns, last_columns = mapping.get("first_name", set()), mapping.get("last_name", set())
            # A combined printed Name/Benutzername cell is split only at an explicit comma.
            combined = bool(first_columns and first_columns == last_columns)
            if not first_columns and last_columns:
                cell = next((c for column in last_columns for c in by_column[column] if "," in c["text"]), None)
                combined = cell is not None
            if combined:
                value = fields["last_name"].value
                if value and value.count(",") == 1 and all(part.strip() for part in value.split(",")):
                    last, first = (part.strip() for part in value.split(",", 1))
                    box = fields["last_name"].bbox
                    fields["first_name"] = TextField(value=first, state="read", bbox=box)
                    fields["last_name"] = TextField(value=last, state="read", bbox=box)
                    for key, text in (("first_name", first), ("last_name", last)):
                        proofs[key] = dict(column_start=next(iter(last_columns)), text=text,
                                           assignment_rule="explicit_surname_comma_given_name")
                else:
                    fields["first_name"], fields["last_name"] = TextField(), TextField()
                    warnings.append("Kombinierte Namenszelle ohne eindeutiges Komma; Vor-/Nachname unbekannt")
            if not any(fields[key].value for key in ("first_name", "last_name", "personnel_number")):
                if any(cell["text"] for cell in row["cells"]):
                    notes.append(f"Tabelle {table_index}, Zeile {row['row_index']}: kein eindeutig zuordenbarer Identitätswert")
                continue
            boxes = [cell["bbox"] for values in by_column.values() for cell in values if cell["bbox"]]
            reference = None
            for cell in row["cells"]:
                if cell["column_start"] in mapping.get("row_ref", set()) and re.fullmatch(r"[0-9]+", cell["text"]):
                    reference = cell["text"]
            people.append(Participant(**fields, row_ref=reference,
                bbox=Box.model_validate(union(boxes)) if boxes else None,
                review_notes=warnings + ["Deterministisches TableFormer-Spaltenmapping; keine LLM-Zuordnung"] ))
            evidence.append(dict(output_index=len(people)-1, source_row=f"t{table_index}r{row['row_index']}",
                table_index=table_index, source_row_index=row["row_index"], fields=proofs,
                raw_cells=[cell["text"] for cell in row["cells"]],
                column_mapping={key: sorted(value) for key, value in mapping.items()},
                source_cells=[cell for values in by_column.values() for cell in values]))
    if not people:
        notes.append("Keine Teilnehmer eindeutig aus der Tabellenstruktur zugeordnet; Originalzellen zur Kontrolle erhalten")
    return people, evidence, notes, context
