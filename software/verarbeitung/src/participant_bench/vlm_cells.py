"""Assign VLM identity cells by literal headings, never by their appearance or compacted order."""

import json
import re

from .schema import TextField, VisualCellPageResponse, VisualPageResponse, VisualParticipant
from .unlimited_assignment import header_fields

FIELDS = ("personnel_number", "department")


def parse_visual_response(raw: str):
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
    columns = {field: [index for index, found in enumerate(roles) if field in found] for field in FIELDS}
    participants, warnings = [], []
    for index, row in enumerate(response.participants):
        person = VisualParticipant(row_ref=row.row_ref, first_name=row.first_name, last_name=row.last_name,
                                   person_role=row.person_role, role_evidence=row.role_evidence,
                                   personnel_number=None, department=None,
                                   signature_present=row.signature_present).participant()
        aligned = len(row.identity_cells) == len(response.identity_headers)
        for field in FIELDS:
            choices = columns[field]
            reason = None
            if not aligned:
                reason = "Anzahl der Identitätszellen passt nicht zu den festen Spalten; keine Verschiebung geraten"
            elif len(choices) != 1 or roles[choices[0]] != {field}:
                reason = "Gedruckte Spaltenüberschrift fehlt oder ist mehrdeutig; Feld nicht automatisch zugeordnet"
            else:
                value = row.identity_cells[choices[0]]
                if isinstance(value, str) and not value.strip():
                    value = ""
                setattr(person, field, TextField(value=value, state=(
                    "uncertain" if value is None else "empty" if value == "" else "read")))
            if reason:
                person.review_notes.append(f"{field}: {reason}")
                warnings.append(dict(output_index=index, field=field, reason=reason))
        participants.append(person)
    audit = dict(kind="physical_identity_cells", identity_headers=response.identity_headers,
                 field_columns={field: indices[0] if len(indices) == 1 and roles[indices[0]] == {field} else None
                                for field, indices in columns.items()})
    return participants, response.page_text, warnings, audit
