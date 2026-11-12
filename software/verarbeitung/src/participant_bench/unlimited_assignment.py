"""Local LLM assignment with references to literal cells, separate from OCR inference."""

import json
import re
import time
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path

from pydantic import Field, ValidationError

from .config import structure_settings
from .document_names import DocumentNameOrders, infer_text_order
from .extraction_prompts import ASSIGNMENT_VERSION, POSITIONED_ASSIGNMENT_VERSION, extraction_prompt
from .io import digest, read_json, write_json
from .person_roles import filter_page_people
from .person_rows import select_person_rows
from .schema import (
    TEXT_FIELDS,
    NameOrderDecision,
    OCRRecordResponse,
    Participant,
    PersonRole,
    StrictModel,
    TextField,
)
from .unlimited_tables import HEADERS, tables

PROMPT_VERSION = ASSIGNMENT_VERSION
POSITIONED_PROMPT_VERSION = POSITIONED_ASSIGNMENT_VERSION
SYSTEM = extraction_prompt("ocr_cells")
RECORD_SYSTEM = extraction_prompt("ocr_cells", document_order=False)



class AssignedRow(PersonRole):
    is_participant: bool = True
    source_row: str
    first_name: tuple[int | None, str | None] = (None, None)
    last_name: tuple[int | None, str | None] = (None, None)
    personnel_number: tuple[int | None, str | None] = (None, None)
    department: tuple[int | None, str | None] = (None, None)


class AssignmentResponse(StrictModel):
    name_order: NameOrderDecision | None = None
    participants: list[AssignedRow] = Field(default_factory=list)


class ValueAssignedRow(PersonRole):
    source_row: str
    is_participant: bool = True
    first_name: str | None = None
    last_name: str | None = None
    personnel_number: str | None = None
    department: str | None = None


def parse_assignment_response(raw: str, rejected_rows: list, source_rows=None) -> AssignmentResponse:
    """New value-only protocol plus historical cell references, without JSON repair or coercion."""
    payload = json.loads(raw)
    if isinstance(payload, list) and source_rows is not None:
        payload = dict(participants=payload)
    if not isinstance(payload, dict) or not isinstance(payload.get("participants"), list):
        return AssignmentResponse.model_validate_json(raw)
    envelope = AssignmentResponse.model_validate_json(json.dumps(dict(payload, participants=[])))
    sources = {row["id"]: row for row in source_rows or []}
    for index, original in enumerate(payload["participants"]):
        row = dict(original) if isinstance(original, dict) else original
        if isinstance(row, dict) and "cells" in row and row.get("source_row") in sources:
            source = sources[row["source_row"]]
            permitted = [source.get("column_texts", []), [[cell["index"], cell["text"]] for cell in source["cells"]]]
            if row["cells"] in permitted:
                row.pop("cells")  # Verified input echo, not a participant field or a JSON repair.
        if isinstance(row, dict) and row.get("source_row") in sources:
            source = sources[row["source_row"]]
            if row.get("id") == source["id"]:
                row.pop("id")
            if "column_texts" in row and row["column_texts"] == source.get("column_texts"):
                row.pop("column_texts")
            for key in ("bbox", "layout_cells"):
                if key in row and source.get(key) is not None and row[key] == source[key]:
                    row.pop(key)
        try:
            if isinstance(row, dict) and all(row.get(field) is None or isinstance(row.get(field), str) for field in TEXT_FIELDS):
                value = ValueAssignedRow.model_validate(row)
                reference = value.model_dump(exclude=set(TEXT_FIELDS))
                for field in TEXT_FIELDS:
                    observed = getattr(value, field)
                    reference[field] = (None, observed if observed else None)
                person = AssignedRow.model_validate(reference)
            else:
                person = AssignedRow.model_validate_json(json.dumps(row))
            envelope.participants.append(person)
        except ValidationError as exc:
            rejected_rows.append(dict(output_index=index, stage="schema", errors=[
                dict(type=error["type"], loc=list(error["loc"]))
                for error in exc.errors(include_input=False, include_context=False, include_url=False)]))
    return envelope


def header_fields(text):
    words = re.sub(r"[^\w]", "", text.casefold())
    title = re.sub(r"[^\w]", "", re.split(r"[\n(]", text.casefold(), maxsplit=1)[0])
    if title in {"benutzername", "benutzemame", "username", "fullname", "namevorname", "nachnamevorname", "teilnehmername", "teilnehmemame"}:
        return {"first_name", "last_name"}
    for name in ("first_name", "last_name"):
        if title in HEADERS[name]:
            return {name}
    found = set()
    patterns = {
        "first_name": r"\bvorname[n]?\b|\bfirst[\s_-]*name\b",
        "last_name": r"\b(?:name|nachname|familienname|surname)\b|\blast[\s_-]*name\b",
        "personnel_number": r"\b(?:benutzer|personalnummer|personalnr)\b|\buser[\s_-]*id\b",
        "department": r"\b(?:kurzzeichen|abteilung|department|organization|organisation)\b",
    }
    found.update(field for field, pattern in patterns.items() if re.search(pattern, text, re.IGNORECASE))
    for field, aliases in HEADERS.items():
        if words in aliases:
            found.add(field)
        # Parenthesized instructions often follow printed column headings.
        for part in re.split(r"[,/\n()]", text.casefold()):
            if re.sub(r"[^\w]", "", part.strip()) in aliases:
                found.add(field)
    return found


class CellTables(HTMLParser):
    """Preserve physical cells and explicit spans without duplicating merged text."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.output, self.rows, self.row, self.cell = [], None, None, None
        self.depth, self.invalid = 0, False

    def handle_starttag(self, tag, attrs):
        if tag == "table":
            if self.depth:
                self.invalid = True
            else:
                self.rows, self.invalid = [], False
            self.depth += 1
        elif self.depth == 1:
            if tag == "tr":
                if self.row is not None:
                    self.invalid = True
                self.row = []
            elif tag in ("td", "th") and self.row is not None:
                values = dict(attrs)
                try:
                    spans = [int(values.get(key, "1")) for key in ("rowspan", "colspan")]
                    if any(not 1 <= number <= 64 for number in spans):
                        raise ValueError
                except (ValueError, TypeError):
                    self.invalid, spans = True, [1, 1]
                self.cell = dict(raw_text="", rowspan=spans[0], colspan=spans[1])
            elif tag == "br" and self.cell is not None:
                self.cell["raw_text"] += "\n"

    def handle_data(self, text):
        if self.depth == 1 and self.cell is not None:
            self.cell["raw_text"] += text

    def handle_endtag(self, tag):
        if tag == "table":
            if self.depth == 1:
                self.output.append((self.rows, self.invalid or self.row is not None))
                self.rows, self.row, self.cell = None, None, None
            self.depth = max(0, self.depth - 1)
        elif self.depth == 1:
            if tag in ("td", "th") and self.cell is not None:
                self.row.append(self.cell)
                self.cell = None
            elif tag == "tr" and self.row is not None:
                self.rows.append(self.row)
                self.row = None


def source_rows(text):
    if "<table" in text.casefold():
        parser = CellTables()
        parser.feed(text)
        parsed = parser.output
    else:
        parsed = [([[dict(raw_text=cell, rowspan=1, colspan=1) for cell in row] for row in rows], bad)
                  for rows, bad in tables(text)]
        if not parsed:
            parsed = [([[dict(raw_text=line, rowspan=1, colspan=1)] for line in text.splitlines()], False)]
    output, notes = [], []
    for table_index, (rows, invalid) in enumerate(parsed):
        if invalid:
            notes.append(f"Tabelle {table_index}: verschachtelt oder beschädigt; keine Zellzuordnung geraten")
            continue
        occupied = {}
        for row_index, cells in enumerate(rows):
            column = 0
            for index, cell in enumerate(cells):
                while any(occupied.get(slot, -1) >= row_index
                          for slot in range(column, column + cell["colspan"])):
                    column += 1
                cell.update(index=index, text=" ".join(cell["raw_text"].split()), column_start=column)
                for slot in range(column, column + cell["colspan"]):
                    occupied[slot] = row_index + cell["rowspan"] - 1
                column += cell["colspan"]
            output.append(dict(id=f"t{table_index}r{row_index}", table_index=table_index,
                               row_index=row_index, cells=cells))
    return output, notes


def table_headers(rows):
    selected, mappings, last = [], {}, {}
    for row in rows:
        fields = [(cell, header_fields(cell["text"]) | set(cell.get("header_fields", [])))
                  for cell in row.get("native_cells", row["cells"]) if cell.get("kind") != "row_transcript"]
        found = set().union(*(names for _, names in fields)) if fields else set()
        table = row["table_index"]
        if (len(found & set(TEXT_FIELDS)) >= 2
                or found and last.get(table) == row["row_index"] - 1):
            selected.append(row)
            last[table] = row["row_index"]
            for cell, names in fields:
                for name in names:
                    mappings.setdefault(table, {}).setdefault(name, set()).add(cell["column_start"])
    for fields in mappings.values():
        for column in set().union(*fields.values()):
            roles = {name for name, columns in fields.items() if column in columns}
            if len(roles) > 1 and roles != {"first_name", "last_name"}:
                for name in roles:
                    fields[name].discard(column)
    return selected, mappings


def ground_response(response, rows, *, trusted_headers=True, source_label="Unlimited-OCR", field_validator=None,
                    require_name=False):
    headers, mappings = table_headers(rows)
    if not trusted_headers:
        mappings = {}  # Spatial positions are validated separately, never treated as grid-column indices.
    last_header = {row["table_index"]: row["row_index"] for row in headers}
    by_id, counts = {row["id"]: row for row in rows}, Counter(p.source_row for p in response.participants if p.is_participant)
    people, evidence, notes = [], [], []
    def literal(value, cell):
        pattern = re.escape(value).replace(r"\.\.\.", r"(?:\.\.\.|…)").replace("…", r"(?:\.\.\.|…)")
        return re.search(r"(?<![^\W_])(?<!['/’–-])" + pattern + r"(?![^\W_])(?!['/’–-])", cell["text"])

    for index, predicted in enumerate(response.participants):
        if not predicted.is_participant:
            continue
        source = by_id.get(predicted.source_row)
        if (source is None or counts[predicted.source_row] != 1
                or source["row_index"] <= last_header.get(source["table_index"], -1)):
            notes.append(f"Modellzeile {index}: unbekannte, doppelte oder nicht personenbezogene Quellzeile")
            continue
        fields, proofs, warnings, used = {}, {}, [], {}
        cells = source["cells"]
        for name in TEXT_FIELDS:
            cell_index, value = getattr(predicted, name)
            rule = "llm_literal_cell"
            columns = mappings.get(source["table_index"], {}).get(name, set())
            expected = [cell for cell in cells if len(columns) == 1 and cell["column_start"] in columns]
            combined_name = (name in ("first_name", "last_name") and columns and columns ==
                             mappings.get(source["table_index"], {}).get(
                                 "last_name" if name == "first_name" else "first_name", set()))
            combined_name = combined_name or (name in ("first_name", "last_name") and
                predicted.first_name[0] is not None and predicted.first_name[0] == predicted.last_name[0] and
                predicted.first_name[1] and predicted.last_name[1])
            if len(expected) == 1 and expected[0]["colspan"] == 1 and not combined_name:
                # An unambiguous printed header permits copying the whole observed cell.
                rule = "printed_header_cell"
                if (cell_index, value) != (expected[0]["index"], expected[0]["text"]):
                    warnings.append(f"{name}: vollständige Quellzelle anhand eindeutiger Überschrift übernommen")
                cell_index, value = expected[0]["index"], expected[0]["text"]
            elif value:
                matches = [cell for cell in (expected or cells) if literal(value, cell)]
                if len(matches) == 1 and cell_index != matches[0]["index"]:
                    had_reference = cell_index is not None
                    cell_index = matches[0]["index"]
                    rule = "unique_same_row_cell_reference" if had_reference else "literal_value_same_row"
                    if had_reference:
                        warnings.append(f"{name}: falschen Zellindex anhand eindeutigen Textbelegs derselben Zeile berichtigt")
            if cell_index is None and value is None:
                fields[name] = TextField()
                continue
            valid = (cell_index is not None and 0 <= cell_index < len(cells) and value is not None)
            if value is not None and value != "" and not value.strip():
                valid = False
            cell = cells[cell_index] if valid else None
            match = None
            if valid and value:
                match = literal(value, cell)
            if valid and columns and len(columns) == 1 and cell["column_start"] not in columns:
                valid = False
            if valid and field_validator is not None and not field_validator(name, cell, match):
                valid = False
            if not valid or (value == "" and cell["text"] != "") or (value and not match):
                fields[name] = TextField(state="failed")
                warnings.append(f"{name}: Wert oder Spalte nicht durch die angegebene Quellzelle belegt")
                continue
            if value and name == "personnel_number" and re.search(r"[*█■]{2,}|[xX]{3,}", value):
                fields[name] = TextField()
                warnings.append(f"{name}: maskierter Zellinhalt bleibt unbekannt")
                continue
            partial = bool(value and re.search(r"\.\.\.|…", value))
            fields[name] = TextField(value=value, state="uncertain" if partial else "read" if value else "empty")
            proofs[name] = dict(cell_index=cell_index, column_start=cell["column_start"],
                                text=value, offset=match.span() if match else None, assignment_rule=rule,
                                observation_state="partial" if partial else "observed")
            if match:
                for other, (other_cell, start, stop) in used.items():
                    if other_cell == cell_index and min(stop, match.end()) > max(start, match.start()):
                        fields[name], fields[other] = TextField(state="failed"), TextField(state="failed")
                        warnings.append(f"{name}/{other}: überlappender Textbeleg; Feldzuordnung unklar")
                used[name] = (cell_index, *match.span())
        if require_name and not any(fields[name].value for name in ("first_name", "last_name")):
            notes.append(f"Modellzeile {index}: kein belegter Namensbestandteil in der Namensspalte; nur Rohbeleg erhalten")
            continue
        if not any(fields[name].value for name in ("first_name", "last_name", "personnel_number")):
            notes.append(f"Modellzeile {index}: keine belegte Namensangabe oder Benutzer-ID")
            continue
        people.append(Participant(**fields, person_role=predicted.person_role, role_evidence=predicted.role_evidence,
                                 review_notes=warnings + [
            f"Lokale LLM-Zuordnung aus {source_label}; Zellbeleg bestätigt Textvorkommen, nicht semantische Richtigkeit."
        ]))
        evidence.append(dict(output_index=len(people) - 1, source_row=source["id"], fields=proofs,
                             source_cells=cells, warnings=warnings))
    assigned = {item["source_row"] for item in evidence}
    unassigned = [row["id"] for row in rows if row["id"] not in assigned and
                  row["row_index"] > last_header.get(row["table_index"], -1) and
                  any(cell["text"] for cell in row["cells"])]
    if unassigned:
        notes.append("Nicht zugeordnete OCR-Zeilen zur Kontrolle: " + ", ".join(unassigned))
    return people, evidence, notes


INPUT_COMPACTION_VERSION = "assignment-input-v1-derived-row-box"


def compact_assignment_rows(source, cell_columns):
    """Omit only row boxes exactly reconstructible from unchanged cell boxes.

    Text, cell order, indices, confidence and geometry precision are preserved.
    Original rows remain available to literal/position validation unchanged.
    """
    output = []
    for row in source:
        item = dict(id=row["id"], cells=[[cell.get(key) for key in cell_columns] for cell in row["cells"]])
        if row.get("bbox"):
            layout = row.get("layout_cells", [])
            item["layout_cells"] = layout
            boxes = [cell[1] for cell in layout if len(cell) > 1 and isinstance(cell[1], dict)
                     and all(axis in cell[1] for axis in ("x0", "y0", "x1", "y1"))]
            reconstructed = ({key: op(box[key] for box in boxes)
                              for key, op in (("x0", min), ("y0", min), ("x1", max), ("y1", max))}
                             if boxes and len(boxes) == len(layout) else None)
            if reconstructed != row["bbox"]:
                item["bbox"] = row["bbox"]
        if row.get("column_texts"):
            item["column_texts"] = row["column_texts"]
        output.append(item)
    return output


def assign_pages(pages, method_dir, config, progress, factory, persist=lambda: None, *, method="unlimited_ocr"):
    """Called after the OCR/structure worker has exited, before the optional signature VLM."""
    from .models import Unavailable, generation_schema
    from .unlimited import UnlimitedOptions

    structure = method in ("paddle_structure", "paddle_llm", "docling")
    positioned = structure and structure_settings(config, method).assignment_format == "positioned_v14"
    prompt_version = POSITIONED_PROMPT_VERSION if positioned else PROMPT_VERSION
    name_orders = DocumentNameOrders()
    token_budget = (structure_settings(config, method).assignment_max_new_tokens if structure else
                    UnlimitedOptions.model_validate(config.models["unlimited_ocr"].options).assignment_max_new_tokens)
    if "ocr_llm" not in config.models or config.models["ocr_llm"].backend != "local":
        raise ValueError("OCR-Zuordnung benötigt ein ausdrücklich lokales models.ocr_llm")
    model, context, column_context, spatial_context, resources = None, {}, {}, {}, {}
    name_columns = {}
    load_error = None
    load_wall = 0.0
    try:
        for page in sorted(pages, key=lambda p: (p.document_id, p.page_number)):
            path = method_dir / f"raw-{page.page_id}.json"
            raw = read_json(path)
            source_key = "structure" if structure else "unlimited_ocr"
            if source_key not in raw:
                continue
            recognized = raw[source_key]
            if method in ("paddle_structure", "paddle_llm"):
                text = "\n".join(recognized.get("native", {}).get("overall_ocr_res", {}).get("rec_texts", []))
                if text:
                    recognized["plain_text"] = text  # Also repair incomplete transcripts in older saved runs.
            page.page_text = recognized["plain_text"]
            bands, previous_bands = {}, {}
            candidates, validation_bands, ambiguous_fields = [], {}, []
            if structure:
                from .structure_assignment import (
                    VERSION,
                    ambiguous_header_fields,
                    comma_names,
                    continuation_candidates,
                    document_bands,
                    ground_positions,
                    header_bands,
                    position_matches,
                    prepare_rows,
                )

                rows, source_notes, aspect = prepare_rows(recognized, "paddle_structure" if method == "paddle_llm" else method)
                bands = header_bands(rows)
                previous_bands, updated_context, mapping_trace = document_bands(recognized, rows, bands,
                    spatial_context.get(page.document_id), document_id=page.document_id, page_number=page.page_number)
                spatial_context[page.document_id] = updated_context
                recognized["document_column_mapping"] = mapping_trace
                ambiguous_fields = ambiguous_header_fields(rows)
                validation_bands = bands or previous_bands
                candidates = continuation_candidates(rows, previous_bands) if not bands else []
                recognized["assignment_source_version"] = VERSION
            else:
                rows, source_notes = source_rows(recognized["clean_text"])
            headers, column_mapping = table_headers(rows)
            previous = context.get(page.document_id, []) if not structure or previous_bands else []
            previous_columns = column_context.get(page.document_id, {})
            # Carry labels and positions only. Even an apparent heading cell can
            # contain appended participant text on a noisy OCR baseline.
            from .column_context import heading_structure

            safe_headers = []
            for header_row in headers:
                cells = []
                for i, cell in enumerate(header_row.get("native_cells", header_row["cells"])):
                    roles = header_fields(cell["text"]) | set(cell.get("header_fields", []))
                    if cell.get("kind") == "row_transcript" or not roles:
                        continue
                    role = " / ".join(sorted(roles))
                    label = heading_structure({role: [cell]})[role][0]["text"]
                    cells.append(dict({key: cell[key] for key in ("column_start", "colspan", "rowspan", "bbox")
                                       if key in cell}, index=i, text=label))
                if cells:
                    safe_headers.append(dict(id=header_row["id"], cells=cells))
            context[page.document_id] = safe_headers or previous
            current_columns = {str(table): {field: sorted(indices) for field, indices in fields.items()}
                               for table, fields in column_mapping.items()}
            column_context[page.document_id] = current_columns or previous_columns
            name_hint, omitted_rows, name_bounds, inherited_column = None, [], None, False
            if structure:
                selected, name_hint = select_person_rows(rows)
                omitted_rows = [row["id"] for row in rows if row not in selected]
                if name_hint is not None:
                    rows = [dict(row, id=f"r{index+1}", original_source_row=row["id"])
                            for index, row in enumerate(selected)]
                    if method == "docling":
                        from .structure_assignment import docling_columns

                        boundaries = docling_columns(recognized)
                        if name_hint + 1 < len(boundaries):
                            name_bounds = boundaries[name_hint:name_hint + 2]
                            name_columns[page.document_id] = dict(boundaries=boundaries, aspect=aspect,
                                                                  bounds=name_bounds, hint=name_hint)
                elif method == "docling":
                    from .structure_assignment import continue_name_column, docling_columns

                    rows, name_hint, name_bounds = continue_name_column(
                        rows, docling_columns(recognized), aspect, name_columns.get(page.document_id))
                    inherited_column = name_hint is not None
                for row in rows:
                    row["layout_cells"] = [[cell["text"], cell["bbox"], *(
                        [cell.get("ocr_confidence"), cell.get("header_fields", [])] if positioned else [])]
                        for cell in row.get("native_cells", [])]
            if (raw.get("assignment", {}).get("complete") and
                    raw["assignment"].get("prompt_version") == prompt_version):
                name_orders.restore(page, raw)
                continue
            started = time.perf_counter()
            def compact(source):
                return compact_assignment_rows(source, cell_columns)

            cell_columns = (["index", "text"] if structure else
                            ["index", "text", "column_start", "colspan", "rowspan"])
            table_structure = []
            if structure:
                for table in recognized.get("tables", []):
                    grid, _ = source_rows(table["html"])
                    table_structure.append([[row["row_index"], [[cell["column_start"], cell["text"],
                        cell["rowspan"], cell["colspan"]] for cell in row["cells"]]] for row in grid])
            prompt = json.dumps(dict(cell_columns=["cell_index", *cell_columns[1:]],
                **(dict(document_column_mapping=mapping_trace) if structure else {}),
                **(dict(layout_cell_columns=["text", "bbox", "ocr_confidence", "heading_roles"],
                        ambiguous_fields=ambiguous_fields) if positioned else {}),
                table_structure=table_structure,
                name_column_hint=name_hint,
                current_columns={} if structure else current_columns,
                previous_columns={} if structure else previous_columns,
                current_field_bands=bands, previous_field_bands=previous_bands,
                continuation_candidates=candidates,
                previous_headers=compact(previous), current_rows=compact(rows),
                DOCUMENT_NAME_ORDER_CONTEXT=name_orders.context(page.document_id)), ensure_ascii=False, separators=(",", ":"))
            record = dict(prompt_version=prompt_version, text_prompt=prompt, text_prompt_sha256=digest(prompt),
                          input_compaction=dict(version=INPUT_COMPACTION_VERSION,
                              omitted_redundant_row_boxes=sum(bool(row.get("bbox")) and "bbox" not in compacted
                                  for row, compacted in zip(rows, compact(rows), strict=True)),
                              policy="row_bbox_is_exact_union_of_preserved_layout_cell_boxes"),
                          **(dict(document_column_mapping=mapping_trace) if structure else {}),
                          system_prompt_sha256=digest(SYSTEM), complete=False,
                          name_column_hint=name_hint, context_rows=omitted_rows,
                          inherited_name_column=inherited_column, name_column_bounds=name_bounds)
            try:
                if not rows:
                    page.participants, page.status, page.parse_status = [], "partial", "not_attempted"
                    page.text_fallback = True
                    page.review_notes = source_notes + ["Keine zuordenbaren OCR-/Tabellenbelege; Rohdaten manuell prüfen"]
                    record.update(complete=True, parse_status="not_attempted", review_notes=page.review_notes)
                    raw.update(assignment=record, status=page.status, parse_status=page.parse_status)
                    write_json(path, raw)
                    persist()
                    continue
                if model is None:
                    if load_error:
                        raise Unavailable(load_error)
                    progress.log(f"{method}: OCR entladen; lokales LLM für die Zellzuordnung laden")
                    loading = time.perf_counter()
                    try:
                        model = factory()
                    except Unavailable as exc:
                        load_error = str(exc)
                        load_wall = time.perf_counter() - loading
                        raise
                    load_wall = time.perf_counter() - loading
                    started = time.perf_counter()
                name_context = name_orders.context(page.document_id)
                if structure and name_hint is not None and not name_context:
                    progress.log(f"{method}: dokumentweite Namensreihenfolge aus OCR-Text bestimmen")
                    order, stage = infer_text_order(model, rows, name_hint)
                    record["name_order_stage"] = stage
                    page.calls += 1
                    name_context = order.model_dump()
                response_type = OCRRecordResponse if structure and name_hint is not None else AssignmentResponse
                system = RECORD_SYSTEM if response_type is OCRRecordResponse else SYSTEM
                if name_context:
                    prompt_data = json.loads(prompt)
                    prompt_data["DOCUMENT_NAME_ORDER_CONTEXT"] = name_context
                    prompt = json.dumps(prompt_data, ensure_ascii=False, separators=(",", ":"))
                    record.update(text_prompt=prompt, text_prompt_sha256=digest(prompt))
                record["system_prompt_sha256"] = digest(system)
                fingerprint = digest(dict(prompt=prompt, identity=model.identity, spec=model.spec.model_dump(),
                                          prompt_version=prompt_version, system=system,
                                          schema=generation_schema(response_type),
                                          max_new_tokens=token_budget, method=method))
                cache = Path(config.cache_dir) / f"{method}_assignment" / f"{fingerprint}.json"
                try:
                    cached = read_json(cache) if cache.is_file() else None
                except (OSError, ValueError):
                    cached = None
                if not (isinstance(cached, dict) and isinstance(cached.get("answer"), str)
                        and isinstance(cached.get("metadata"), dict)):
                    cached = None
                if cached:
                    answer, metadata = cached["answer"], cached["metadata"]
                else:
                    progress.log(f"{method}-Zuordnung: PDF-Seite {page.page_number}, {len(rows)} OCR-Zeilen")
                    answer, metadata = model.generate(prompt, max_new_tokens=token_budget,
                                                      response_type=response_type, system_prompt=system)
                    model.calls += 1
                    page.calls += 1
                record.update(raw_response=answer, metadata=metadata, cache_hit=cached is not None)
                if metadata.get("output_budget_reached"):
                    raise ValueError("LLM-Zuordnung am Tokenlimit abgeschnitten; Rohantwort erhalten")
                rejected_rows = []
                parsed = parse_assignment_response(answer, rejected_rows, rows)
                record["participants_before_validation"] = [p.model_dump() for p in parsed.participants]
                if parsed.name_order is None and name_context:
                    parsed.name_order = NameOrderDecision.model_validate(name_context)
                record["rejected_rows"] = rejected_rows
                record["filtered_non_participants"] = sum(not row.is_participant for row in parsed.participants)
                name_changes = name_orders.prepare_assignment(parsed, rows, page.document_id, page.page_number)
                if structure and parsed.name_order is None:
                    comma_names(parsed, rows, bands or previous_bands)
                def validator(field, cell, match):
                    if not structure:
                        return True
                    if field in ambiguous_fields:
                        return False
                    if not position_matches(field, cell, match, validation_bands):
                        return False
                    if name_bounds and field in ("first_name", "last_name") and match:
                        from .structure_assignment import source_boxes

                        return all(name_bounds[0] <= (box["x0"] + box["x1"]) / 2 < name_bounds[1]
                                   for box in source_boxes(cell, match.span()))
                    return True
                people, proofs, notes = ground_response(parsed, rows, trusted_headers=not structure,
                                                        source_label=method, field_validator=validator,
                                                        require_name=name_hint is not None)
                record["participants_after_literal_grounding"] = [p.model_dump() for p in people]
                if structure:
                    ground_positions(people, proofs, rows, validation_bands)
                    for proof in proofs:
                        proof["mapping_provenance"] = mapping_trace
                    if previous_bands:
                        for person in people:
                            person.review_notes.append("Spaltenüberschriften von PDF-Seite " + str(
                                mapping_trace["source_page"]) + " bei kompatibler Geometrie übernommen")
                record["participants_after_position_validation"] = [p.model_dump() for p in people]
                if structure:
                    from .structure_assignment import complete_observed_cells

                    record["observed_cell_completions"] = complete_observed_cells(people, proofs, rows, mapping_trace)
                    record["participants_after_observed_cell_completion"] = [p.model_dump() for p in people]
                record.update(complete=True, parse_status="valid", model_identity=model.identity,
                              name_order=parsed.name_order.model_dump() if parsed.name_order else None,
                              name_changes_before_validation=name_changes,
                              row_evidence=proofs, review_notes=source_notes + notes,
                              current_field_bands=bands, previous_field_bands=previous_bands,
                              position_context_origin="headings" if previous_bands else None,
                              continuation_candidates=candidates)
                record["ambiguous_fields"] = ambiguous_fields
                if not cached:
                    write_json(cache, dict(answer=answer, metadata=metadata))
                page.participants, page.parse_status, page.error = people, "valid", None
                page.output_kind, page.status = "structured", "partial"
                page.text_fallback = not people
                page.page_text = recognized["plain_text"]
                page.review_notes = source_notes + notes + ["LLM-Feldzuordnung manuell prüfen; keine kalibrierte Sicherheit"]
                if not people:
                    page.review_notes.append("Keine belegbaren Teilnehmer; vollständiger OCR-Text erhalten")
                recognized["row_evidence"] = proofs
                name_orders.apply(page, raw, parsed.name_order)
                filter_page_people(page, raw)
            except Exception as exc:
                record.update(error=f"{type(exc).__name__}: {exc}", parse_status="invalid")
                if isinstance(exc, ValueError) and str(exc).startswith("Input budget exceeded ("):
                    record.update(error_stage="input_budget", model_inference_started=False)
                page.participants = []
                page.parse_status, page.status = ("not_attempted", "unavailable") if isinstance(exc, Unavailable) else ("invalid", "partial")
                page.error = "LLM-Zuordnung fehlgeschlagen; technische Details in assignment.error"
                page.review_notes.append("LLM-Zuordnung fehlgeschlagen; OCR-Text vollständig erhalten")
            page.timings["assignment_seconds"] = time.perf_counter() - started
            page.timings["page_wall_seconds"] = page.timings.get("page_wall_seconds", 0) + page.timings["assignment_seconds"]
            raw.update(assignment=record, status=page.status, parse_status=page.parse_status)
            write_json(path, raw)
            persist()
            progress.log(f"{method}-Zuordnung: Seite {page.page_number} gesichert; {len(page.participants)} Einträge")
        name_orders.finalize(pages, method_dir)
        persist()
        if model:
            resources = dict(model.resources(), load_attempt_wall_seconds=load_wall)
        elif load_error:
            resources = dict(status="unavailable", reason=load_error, load_attempt_wall_seconds=load_wall)
    finally:
        if model:
            model.close()
    return resources
