"""Read-only stage evidence from saved artifacts, never a second extraction path."""

import json

from ..column_context import mapping_diagnostics
from ..io import file_hash


def source_index(raw, index):
    role = raw.get("person_role_filter", {})
    if not role.get("excluded"):
        return index
    found = [
        r["source_output_index"] for r in role.get("output_index_mapping", []) if r["output_index"] == index
    ]
    return found[0] if len(found) == 1 else None


def visual_record(raw, index):
    """Only validated physical-cell answers have a provable concatenated row order."""
    index = source_index(raw, index)
    if index is None:
        return None
    offset = 0
    for response in raw.get("responses", []):
        if response.get("parse_status") != "valid":
            continue
        try:
            data = json.loads(response.get("raw_response", ""))
        except (ValueError, TypeError):
            continue
        if not isinstance(data, dict) or "identity_headers" not in data:
            continue
        rows = data.get("participants", [])
        if (
            not isinstance(rows, list)
            or not isinstance(data["identity_headers"], list)
            or any(not isinstance(r, dict) or not isinstance(r.get("identity_cells"), list) for r in rows)
        ):
            continue
        if offset <= index < offset + len(rows):
            return response, data, rows[index - offset], index - offset
        offset += len(rows)
    return None


def page_trace(source, page, raw, manifest, effective):
    """Distinguish requested, accepted and unavailable historical rotation evidence."""
    saved = next((p for p in manifest.get("pages", []) if p.get("page_id") == page.page_id), {})
    used = next((p for p in effective if p.get("page_id") == page.page_id), {})
    image = source / "pages" / (page.page_id + ".png")
    actual = file_hash(image) if image.is_file() else None
    claimed = raw.get("run_image_sha256")
    orientation = saved.get("orientation_status")
    if orientation is None:
        orientation = (
            "legacy_osd_error"
            if saved.get("orientation_error")
            else ("legacy_review_required" if saved.get("review_required") else "not_recorded")
        )
    return dict(
        source_path=saved.get("source_path"),
        source_sha256=saved.get("source_sha256"),
        page_number=page.page_number,
        pdf_rotation_metadata=saved.get("pdf_rotation_metadata"),
        orientation_status=orientation,
        orientation_method=saved.get("orientation_method"),
        orientation_evidence=saved.get("orientation_evidence"),
        orientation_confidence=saved.get("orientation_confidence"),
        orientation_proposed_clockwise=saved.get("orientation_proposed_clockwise"),
        orientation_min_confidence=saved.get(
            "orientation_min_confidence",
            manifest.get("preprocessing_config", {}).get("pdf", {}).get("osd_min_confidence"),
        ),
        additional_rotation_clockwise=saved.get("additional_rotation_clockwise"),
        curation_rotation_clockwise=used.get(
            "curation_rotation_clockwise", saved.get("curation_rotation_clockwise")
        ),
        curation_note=used.get("curation_note", saved.get("curation_note")),
        curation_reviewed=saved.get("curation_reviewed"),
        orientation_error=saved.get("orientation_error"),
        review_required=saved.get("review_required"),
        image_sha256=actual,
        raw_image_sha256=claimed,
        image_matches_raw=(actual == claimed) if actual and claimed else None,
        image_matches_effective=(actual == used["run_image_sha256"])
        if actual and used.get("run_image_sha256")
        else None,
        mapping_provenance=raw.get("ocr_layout_analysis", {}).get("mapping_provenance")
        or raw.get("assignment", {}).get("document_column_mapping"),
        visual_mapping=[
            r["identity_column_assignment"]
            for r in raw.get("responses", [])
            if "identity_column_assignment" in r
        ],
        column_mappings=mapping_diagnostics(raw),
    )


def value_of(value):
    if isinstance(value, dict):
        return value.get("value")
    if isinstance(value, (list, tuple)) and len(value) == 2:
        return value[1]
    return value if isinstance(value, str) or value is None else None


def field_trace(row, page, raw, proof, observations, field):
    """Explain only uniquely linked rows; unknown stages are kept explicit."""
    stages = []

    def add(stage, status, value=None, **extra):
        stages.append(dict(stage=stage, status=status, value=value, **extra))

    if not page or row.get("output_index") in (None, ""):
        add("localization", "unavailable_course_reference_has_no_page")
        return dict(stages=stages, loss_stage="unknown", certainty="unknown")
    index = int(row["output_index"])
    if index >= len(page.participants):
        add("localization", "invalid_saved_output_index")
        return dict(stages=stages, loss_stage="unknown", certainty="unknown")
    target = getattr(page.participants[index], field)
    deterministic = raw.get("structure", {}).get(
        "assignment_backend"
    ) == "deterministic_headers" and not raw.get("assignment")
    add(
        "recognition",
        "observed_row" if observations else "no_localized_ocr_evidence",
        [o["text"] for o in observations],
        source_row=proof.get("source_row"),
    )
    submitted = [o.get("submitted_to_assignment") for o in observations]
    submission_status = (
        "recorded_submission"
        if any(v is True for v in submitted)
        else "not_submitted"
        if submitted and all(v is False for v in submitted)
        else "submission_unknown"
        if observations
        else "not_localized"
    )
    add(
        "model_input",
        "not_applicable_deterministic_mapper" if deterministic else submission_status,
        [o["text"] for o in observations if o.get("submitted_to_assignment") is True],
    )
    found = visual_record(raw, index)
    loss, certainty = "unknown", "unknown"
    if found:
        response, payload, proposal, original_index = found
        cells, headers = proposal["identity_cells"], payload["identity_headers"]
        assignment = response.get("identity_column_assignment", {})
        saved_mapping = {**assignment.get("field_columns", {}), **assignment.get("name_field_columns", {})}
        column = saved_mapping.get(field)
        aligned = len(cells) == len(headers)
        scalar = cells[column] if aligned and isinstance(column, int) and 0 <= column < len(cells) else None
        add(
            "model_response",
            "physical_cells",
            scalar,
            cells=cells,
            headers=headers,
            saved_column=column,
            aligned=aligned,
        )
        warnings = [
            w
            for w in response.get("field_warnings", [])
            if w.get("output_index") == original_index and w.get("field") == field
        ]
        add(
            "column_mapping",
            "blocked" if warnings else "recorded",
            scalar,
            warnings=warnings,
            mapping=response.get("identity_column_assignment"),
        )
        if warnings and target.value is None:
            loss, certainty = "response_alignment" if not aligned else "column_mapping", "proven"
    else:
        source_row = proof.get("source_row")
        assignment = raw.get("assignment", {})
        proposals = assignment.get("participants_before_validation", [])
        for response in raw.get("responses", []):
            try:
                data = json.loads(response.get("raw_response", ""))
            except (ValueError, TypeError):
                continue
            if isinstance(data, dict) and isinstance(data.get("participants", []), list):
                proposals = [*proposals, *data.get("participants", [])]
        matches = [
            p
            for p in proposals
            if isinstance(p, dict) and source_row is not None and p.get("source_row") == source_row
        ]
        # Never choose one of several model proposals merely because it fits GT.
        if len(matches) == 1 and field in matches[0]:
            scalar = value_of(matches[0][field])
            add("model_response", "linked_source_row", scalar)
            if scalar is None and target.value is None:
                loss, certainty = "model_response", "proven"
        else:
            scalar = None
            add(
                "model_response",
                "not_applicable_deterministic_mapper" if deterministic else "not_uniquely_linked",
            )
        origin = source_index(raw, index)
        proofs = raw.get("structure", {}).get("row_evidence", [])
        for key, stage in (
            ("participants_after_literal_grounding", "literal_validation"),
            ("participants_after_position_validation", "position_validation"),
            ("participants_after_observed_cell_completion", "observed_cell_completion"),
        ):
            people = assignment.get(key)
            if (
                people is not None
                and proofs
                and len(people) == len(proofs)
                and origin is not None
                and origin < len(people)
            ):
                after = value_of(people[origin].get(field))
                add(stage, "recorded", after)
                if scalar not in (None, "") and after is None:
                    loss, certainty = stage, "proven"
                scalar = after
        if proof.get("fields", {}).get(field, {}).get("rejected"):
            loss, certainty = "validation", "proven"
    if target.state == "failed":
        add("validation", "recorded_failed_field", None)
        if loss == "unknown":
            loss, certainty = "validation", "proven"
    add("final_output", target.state, target.value)
    if target.value not in (None, ""):
        loss, certainty = "no_missing_output", "proven"
    elif target.value == "":
        loss, certainty = "explicit_empty_output", "proven"
    return dict(
        stages=stages,
        loss_stage=loss,
        certainty=certainty,
        note="Saved stage transitions are evidence of output loss, not independent proof of correct OCR, identity or reference localization.",
    )
