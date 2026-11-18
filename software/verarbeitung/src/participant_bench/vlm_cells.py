"""Assign VLM identity cells by literal headings, never by their appearance or compacted order."""

import json
import re

from .column_headers import field_roles
from .schema import TEXT_FIELDS, TextField, VisualCellPageResponse, VisualPageResponse, VisualParticipant
from .structure_assignment import roles as approximate_header_roles


def header_fields(text):
    return field_roles(text) | approximate_header_roles(text)


def text_column_geometry(profile, mapping, headers=()):
    """Compare measured target columns, excluding page margins and trailing nontext columns.

    The VLM can count repeated signature columns differently. Their count must
    not invalidate unchanged ID/name/organization boundaries. Missing boundaries
    inside that prefix still change its geometry and block inheritance.
    """
    from .column_context import geometry

    width = max((c for field in TEXT_FIELDS for c in mapping.get(field, ())), default=-1) + 1
    if not profile or width < 2 or profile["width"] < width:
        return None
    if headers and profile["width"] != len(headers):
        # Only a suffix explicitly described as nontext may have a different
        # count. Unknown columns inside/beyond the mapped prefix stay ambiguous.
        if any(not header_fields(title or "") for title in headers[:width]):
            return None
        if not headers[width:]:
            return None  # An invented all-text schema is not a counted nontext suffix.
        if any(title and (not header_fields(title) or header_fields(title) - {"signature", "date"})
               for title in headers[width:]):
            return None
    prefix = geometry(width, boundaries=profile["edges"][:width + 1])
    if prefix:
        prefix.update(basis=profile["basis"] + "_text_prefix", full_table_width=profile["width"])
    return prefix


def continuation_context(previous, profile, *, document_id, page_number):
    """Data-free, geometrically verified hint for the next model call."""
    from .column_context import resolve

    previous = previous or {}
    prefix = text_column_geometry(profile, previous.get("mapping", {}))
    mapping, _, trace = resolve({}, {}, prefix, previous,
        document_id=document_id, page_number=page_number)
    if trace["status"] != "inherited_from_previous_page":
        return None
    from .column_context import compatible

    if compatible(previous.get("full_geometry"), profile)[0]:
        mapping.update(previous.get("nontext_columns", {}))
    columns = [dict(column=i, fields=sorted(k for k, cols in mapping.items() if i in cols),
                    x_interval=profile["edges"][i:i+2])
               for i in sorted({c for cols in mapping.values() for c in cols})]
    return dict(source_page=trace["source_page"], physical_columns=columns,
                physical_column_count=profile["width"],
                headerless_identity_headers=[None] * profile["width"],
                geometry_check=trace["geometry_check"],
                instruction="Use these roles only if this page has no visible headings. "
                "Current printed headings take precedence. Return null headings when absent; "
                "never use the first attendee as headings. Fields grouped in one column belong "
                "to ONE physical cell: never split a combined name into two columns. "
                "Keep every empty cell and trailing signature-column position.")


def participant_header_echo(response):
    """Recognize an exact echo of this page's first named person, never infer roles from values."""
    headers = response.identity_headers
    if not response.participants or any(header_fields(title) for title in headers if title):
        return False
    row = response.participants[0]
    if len(row.identity_cells) != len(headers) or not row.first_name or not row.last_name:
        return False
    visible = [(i, title) for i, title in enumerate(headers) if title and title.strip()]
    if len(visible) < 2 or any(row.identity_cells[i] != title for i, title in visible):
        return False
    # Both semantic name parts must occur literally in one echoed name cell.
    return any(row.first_name.casefold() in title.casefold() and row.last_name.casefold() in title.casefold()
               for _, title in visible)


def echoed_row_observation(row, mapping, profile, hints):
    """Anchor one CURRENT native OCR row by literal full name or ID; never by organization."""
    from .column_context import column_intervals

    scale = (hints or {}).get("coordinate_scale", 0)
    if not profile or not isinstance(scale, (int, float)) or scale <= 0:
        return None
    bands = column_intervals(mapping, profile)
    def normalize(value):
        return re.sub(r"\W", "", value.casefold())
    names = {normalize((row.first_name or "") + (row.last_name or "")),
             normalize((row.last_name or "") + (row.first_name or ""))} - {""}
    id_columns = mapping.get("personnel_number", set())
    identifier = (row.identity_cells[next(iter(id_columns))] if len(id_columns) == 1 else None)
    candidates = []
    for source in (hints or {}).get("rows", []):
        native = [dict(text=c[0], bbox=dict(zip(("x0", "y0", "x1", "y1"),
                      [v/scale for v in c[1:5]], strict=True)), native_ref=f"{source['source_row']}/{i}",
                      ocr_confidence=c[5] if len(c) > 5 else None)
                  for i, c in enumerate(source.get("cells", [])) if len(c) >= 5 and isinstance(c[0], str)]
        def text(field):
            left, right = bands.get(field, [0, 0])
            return " ".join(c["text"] for c in sorted(native, key=lambda c: c["bbox"]["x0"])
                            if left - .006 <= c["bbox"]["x0"] < c["bbox"]["x1"] <= right + .006
                            and left <= (c["bbox"]["x0"] + c["bbox"]["x1"]) / 2 < right)
        name = normalize(text("first_name") + (" " + text("last_name")
                         if bands.get("first_name") != bands.get("last_name") else ""))
        if name in names or identifier and normalize(identifier) == normalize(text("personnel_number")):
            candidates.append(dict(id=source["source_row"], native_cells=native))
    return candidates[0] if len(candidates) == 1 else None

FIELDS = ("personnel_number", "department")


def parse_visual_response(raw: str, *, document_context=None, document_id=None,
                          page_number=None, column_geometry=None, cell_observations=None):
    payload = json.loads(raw)
    if not isinstance(payload, dict) or "identity_headers" not in payload:
        response = VisualPageResponse.model_validate_json(raw)
        participants = [row.participant() for row in response.participants]
        warnings = []
        for index, person in enumerate(participants):
            candidate = person.personnel_number.value
            if (candidate and not person.department.value and
                    re.fullmatch(r"[A-Za-zÄÖÜäöü]{1,10}[\s/-]+\d{2,}(?:[\s/-]\w+)*", candidate.strip())):
                reason = "Benutzer/Organization ohne Spaltenbeleg möglicherweise verschoben; Originalwert in Rohantwort"
                person.personnel_number = TextField(value=None, state="uncertain")
                person.review_notes.append(reason)
                warnings.append(dict(output_index=index, field="personnel_number", reason=reason))
        return participants, response.page_text, warnings, dict(kind="legacy_semantic_fields")

    response = VisualCellPageResponse.model_validate_json(raw)
    # Match only generic printed headings. No ID or department format is used to assign a value.
    roles = [header_fields(title) if title is not None else set() for title in response.identity_headers]
    from .column_context import resolve

    current = {field: {i for i, found in enumerate(roles) if field in found}
               for field in ("first_name", "last_name", *FIELDS)}
    current = {field: cols for field, cols in current.items() if cols}
    # A full physical grid is required for continuation. Never trust the number
    # or apparent format of returned values as geometry, nor treat fake headings
    # copied from participants as a headerless page.
    echoed = bool(document_context and participant_header_echo(response))
    if echoed:
        current = {}
    profile = text_column_geometry(column_geometry,
        current or (document_context or {}).get("mapping", {}),
        () if echoed or not any(response.identity_headers) else response.identity_headers)
    if profile and len(response.identity_headers) < profile["width"]:
        profile = None  # Even the text prefix is truncated. Slot indices are unsafe.
    grid_conflict = bool(column_geometry and column_geometry["width"] != len(response.identity_headers)
                         and profile is None)
    headings = {field: [dict(text=response.identity_headers[i], column=i) for i in sorted(cols)]
                for field, cols in current.items()}
    mapping, snapshot, trace = resolve(current, headings, profile,
        document_context, document_id=document_id, page_number=page_number,
        has_header=not echoed and any(title is not None and title.strip() for title in response.identity_headers),
        column_count=len(response.identity_headers))
    if (trace["status"] in ("detected_on_current_page", "updated_on_current_page")
            and profile and column_geometry["width"] == len(roles)):
        snapshot["full_geometry"] = column_geometry
        snapshot["nontext_columns"] = {field: [i for i, found in enumerate(roles) if found == {field}]
                                       for field in ("signature", "date")}
    if snapshot.get("nontext_columns") and column_geometry:
        from .column_context import compatible

        if compatible(snapshot.get("full_geometry"), column_geometry)[0] and trace["column_mapping"]:
            trace["column_mapping"].update({k: v for k, v in snapshot["nontext_columns"].items() if v})
    interpretation = ("current_participant_row_echo" if echoed else
                      "reported_headings" if any(response.identity_headers) else "absent")
    trace["header_interpretation"] = interpretation
    if trace["status"] == "inherited_from_previous_page":
        roles = [{field for field, cols in mapping.items() if i in cols}
                 for i in range(len(response.identity_headers))]
    columns = {field: [index for index, found in enumerate(roles) if field in found] for field in FIELDS}
    name_columns = {field: [i for i, found in enumerate(roles) if found == {field}]
                    for field in ("first_name", "last_name")}
    separate_names = all(len(cols) == 1 for cols in name_columns.values())
    participants, warnings, corroboration = [], [], []
    for index, row in enumerate(response.participants):
        person = VisualParticipant(row_ref=row.row_ref, first_name=row.first_name, last_name=row.last_name,
                                   person_role=row.person_role, role_evidence=row.role_evidence,
                                   personnel_number=None, department=None,
                                   signature_present=row.signature_present).participant()
        aligned = len(row.identity_cells) == len(response.identity_headers) and not grid_conflict
        # Separate, explicit or verified inherited name columns outrank semantic
        # model fields too. Only this row's literal cells may supply these values.
        for field, choices in name_columns.items():
            if aligned and separate_names:
                value = row.identity_cells[choices[0]]
                value = "" if isinstance(value, str) and not value.strip() else value
                setattr(person, field, TextField(value=value, state=(
                    "uncertain" if value is None else "empty" if value == "" else "read")))
        for field in FIELDS:
            choices = columns[field]
            reason = None
            if grid_conflict:
                reason = "Gemessene Tabellenspalten widersprechen den ausgegebenen Spalten; keine Feldzuordnung geraten"
            elif not aligned:
                reason = "Anzahl der Identitätszellen passt nicht zu den festen Spalten; keine Verschiebung geraten"
            elif len(choices) != 1 or roles[choices[0]] != {field}:
                reason = "Gedruckte Spaltenüberschrift fehlt oder ist mehrdeutig; Feld nicht automatisch zugeordnet"
            else:
                value = row.identity_cells[choices[0]]
                if isinstance(value, str) and not value.strip():
                    value = ""
                if (field == "department" and isinstance(value, str) and value
                        and mapping.get("first_name") and mapping.get("first_name") == mapping.get("last_name")
                        and value.strip().casefold() in {
                            (row.first_name or "").strip().casefold(),
                            (row.last_name or "").strip().casefold(),
                        } - {""}):
                    reason = "Namensbestandteil bei kombinierter Namensspalte in Organisationsspalte verschoben; nicht als Abteilung übernommen"
                    setattr(person, field, TextField(value=None, state="uncertain"))
                else:
                    setattr(person, field, TextField(value=value, state=(
                        "uncertain" if value is None else "empty" if value == "" else "read")))
            if reason:
                person.review_notes.append(f"{field}: {reason}")
                warnings.append(dict(output_index=index, field=field, reason=reason))
        if trace["status"] == "inherited_from_previous_page" and aligned and (
                echoed or (cell_observations and any(getattr(person, f).value is None for f in FIELDS))):
            # A contract-violating header echo does not establish each cell's
            # position. Require independent, already available native positions.
            from .column_context import column_intervals
            from .structure_assignment import complete_observed_cells

            observed = echoed_row_observation(row, mapping, profile, cell_observations)
            if echoed:
                for field in FIELDS:
                    if getattr(person, field).value != "":
                        setattr(person, field, TextField())
            proof = dict(source_row=observed["id"] if observed else "", fields={})
            changes = complete_observed_cells([person], [proof], [observed] if observed else [],
                dict(trace, observed_cell_bands={f: b for f, b in column_intervals(mapping, profile).items() if f in FIELDS}))
            corroboration.append(dict(output_index=index, source_row=proof["source_row"], fields=proof["fields"]))
            if echoed:
                for field in FIELDS:
                    reason = ("Aktuelle native OCR-Zelle in geprüfter Folgeseitenspalte übernommen; manuell prüfen"
                              if any(c["field"] == field for c in changes) else
                              "Fehlerhafte Modellüberschriften ohne eindeutige aktuelle räumliche Feldbestätigung; Wert unbekannt")
                    if getattr(person, field).value != "":
                        person.review_notes.append(f"{field}: {reason}")
                        warnings.append(dict(output_index=index, field=field, reason=reason))
        participants.append(person)
    audit = dict(kind="physical_identity_cells", identity_headers=response.identity_headers,
                 header_interpretation=interpretation,
                 measured_column_conflict=grid_conflict,
                 echo_corroboration=corroboration,
                 field_columns={field: indices[0] if len(indices) == 1 and roles[indices[0]] == {field} else None
                                for field, indices in columns.items()},
                 name_field_columns={field: cols[0] for field, cols in name_columns.items()} if separate_names else {},
                 participant_rows=len(response.participants),
                 name_mapping_applied_rows=[i for i, row in enumerate(response.participants)
                     if separate_names and not grid_conflict and len(row.identity_cells) == len(response.identity_headers)],
                 mapping_provenance=trace, column_context=snapshot)
    return participants, response.page_text, warnings, audit
