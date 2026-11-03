"""Synthetic observed fragments; these fixtures are not a real handwriting-quality benchmark."""

import importlib.util
import json
from copy import deepcopy
from pathlib import Path

import numpy as np
import pytest
from PIL import Image, ImageDraw
from test_structure_assignment import answer, paddle

from participant_bench.config import ImageConfig
from participant_bench.image_preprocessing import binary, preprocess, remove_grid_lines
from participant_bench.structure_assignment import (
    ground_positions,
    header_bands,
    position_matches,
    prepare_rows,
)
from participant_bench.structure_diagnostics import analyze_page
from participant_bench.unlimited_assignment import ground_response, parse_assignment_response


def grounded(source, payload):
    rows, _, _ = prepare_rows(source, "paddle_structure")
    rejected = []
    response = parse_assignment_response(json.dumps(payload), rejected, rows)
    bands = header_bands(rows)
    people, proofs, notes = ground_response(
        response,
        rows,
        trusted_headers=False,
        field_validator=lambda f, c, m: position_matches(f, c, m, bands),
    )
    ground_positions(people, proofs, rows, bands)
    return people, proofs, rejected, notes


@pytest.mark.parametrize("missing", ["first_name", "last_name", "personnel_number", "department"])
def test_omitted_optional_field_does_not_discard_other_observed_values(missing):
    source = paddle()
    rows, _, _ = prepare_rows(source, "paddle_structure")
    row = answer(rows).participants[0].model_dump(mode="json")
    del row[missing]
    people, proofs, rejected, _ = grounded(source, dict(participants=[row]))
    assert len(people) == 1 and not rejected
    assert getattr(people[0], missing).value is None
    assert any(getattr(people[0], field).value for field in ("first_name", "last_name", "personnel_number"))
    assert missing not in proofs[0]["fields"]


def test_compact_partial_value_protocol_preserves_literal_fragments_and_rejects_invention():
    source = paddle()
    texts = source["native"]["overall_ocr_res"]["rec_texts"]
    texts[5:9] = ["von", "der", "Wiese,", "An..."]
    rows, _, _ = prepare_rows(source, "paddle_structure")
    people, proofs, rejected, _ = grounded(
        source,
        dict(participants=[dict(source_row=rows[1]["id"], first_name="An...", last_name="von der Wiese")]),
    )
    assert len(people) == 1 and not rejected
    assert people[0].first_name.value == "An..." and people[0].first_name.state == "uncertain"
    assert proofs[0]["fields"]["first_name"]["observation_state"] == "partial"
    people, *_ = grounded(source, dict(participants=[dict(source_row=rows[1]["id"], first_name="Invented")]))
    assert not people


@pytest.mark.parametrize(
    "score,expected", [(0.1, "uncertain"), (0.49, "uncertain"), (0.9, "read"), (None, "read")]
)
def test_confidence_flags_uncertainty_without_deleting_or_changing_text(score, expected):
    source = paddle()
    if score is None:
        source["native"]["overall_ocr_res"].pop("rec_scores", None)
    else:
        source["native"]["overall_ocr_res"]["rec_scores"] = [score] * len(
            source["native"]["overall_ocr_res"]["rec_texts"]
        )
    rows, _, _ = prepare_rows(source, "paddle_structure")
    payload = answer(rows).model_dump(mode="json")
    people, proofs, _, _ = grounded(source, payload)
    assert people[0].first_name.value == "Anna" and people[0].first_name.state == expected
    observations = proofs[0]["fields"]["first_name"]["ocr_observations"]
    assert observations and all(x["ocr_confidence"] == score for x in observations)


def test_no_recognition_and_unmapped_words_do_not_create_person_fields():
    people, *_ = grounded(paddle(), dict(participants=[dict(source_row="t0r1")]))
    assert not people
    source = paddle(no_table=True)
    raw = dict(method_id="paddle_llm", page_id="test", structure=source)
    before = deepcopy(source)
    analysis = analyze_page(raw, dict(participants=[]))
    assert analysis["unassigned_ocr_cells"] and source == before
    assert not analysis["final_participants"]


def test_wrong_position_and_department_in_id_column_are_not_recovered_as_id():
    source = paddle()
    rows, _, _ = prepare_rows(source, "paddle_structure")
    row = answer(rows).participants[0].model_dump(mode="json")
    row["personnel_number"] = [0, "MUC-1"]
    people, _, _, _ = grounded(source, dict(participants=[row]))
    assert len(people) == 1 and people[0].personnel_number.value is None
    assert people[0].department.value == "MUC-1"


def test_line_removal_can_remove_a_hand_drawn_stroke_and_does_not_change_original():
    image = Image.new("RGB", (720, 320), "white")
    draw = ImageDraw.Draw(image)
    draw.line((20, 120, 700, 120), fill="black", width=2)
    draw.line((80, 240, 280, 240), fill="black", width=2)  # Long pen stroke, not a table-line label.
    before = np.asarray(image).copy()
    cleaned = remove_grid_lines(image)
    assert np.array_equal(np.asarray(image), before)
    assert binary(image)[240, 150] > 0 and binary(cleaned)[240, 150] == 0
    cleaned.close()


@pytest.mark.parametrize("scale", [1, 1.5, 2])
def test_resolution_and_crop_preserve_inverse_source_positions(scale):
    image = Image.new("RGB", (600, 400), "white")
    transformed, original_box, _ = preprocess(image, ImageConfig(scale=scale, crop=(0.1, 0.2, 0.9, 0.8)))
    box = original_box(0, 0, transformed.width, transformed.height)
    assert box == pytest.approx(dict(x0=0.1, y0=0.2, x1=0.9, y1=0.8))
    transformed.close()


def test_probe_does_not_equate_removed_ink_with_recognition_accuracy():
    spec = importlib.util.spec_from_file_location("handwriting_probe", Path("scripts/handwriting_probe.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    image = Image.new("RGB", (100, 100), "white")
    assert module.changed_ink(image) == dict(ink_before=0, removed_ink=0)


def test_docling_separate_partial_cell_remains_uncertain_and_keeps_empty_neighbor():
    from test_structure_diagnostics import native_table

    from participant_bench.structured_mapping import extract_structured

    source = native_table(
        ["First Name", "Last Name", "User ID", "Organization"], [["An...", "Muster", "", "ABC"]]
    )
    people, proofs, _, _ = extract_structured(source)
    assert len(people) == 1 and people[0].first_name.value == "An..."
    assert people[0].first_name.state == "uncertain"
    assert people[0].personnel_number.state == "empty" and people[0].department.value == "ABC"
    assert proofs[0]["fields"]["first_name"]["observation_state"] == "partial"


def test_missing_fields_do_not_relax_invalid_types_or_unknown_source_rows():
    source = paddle()
    people, _, rejected, _ = grounded(
        source,
        dict(
            participants=[
                dict(source_row="unknown", first_name="Anna"),
                dict(source_row="t0r1", first_name=123),
            ]
        ),
    )
    assert not people and rejected
