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


def test_gray_shaded_header_band_survives_grid_line_removal():
    image = Image.new("RGB", (720, 320), "white")
    draw = ImageDraw.Draw(image)
    draw.rectangle((40, 60, 680, 96), fill=(169, 169, 169))
    draw.line((40, 60, 680, 60), fill="black", width=2)
    draw.line((40, 96, 680, 96), fill="black", width=2)
    # Short vertical and diagonal letter strokes inside the shaded header band
    draw.line((120, 68, 120, 88), fill=(25, 25, 25), width=3)
    draw.line((120, 68, 132, 78), fill=(25, 25, 25), width=3)
    cleaned = remove_grid_lines(image)
    mask = binary(cleaned)
    assert mask[60, 350] == 0 and mask[96, 350] == 0
    assert mask[78, 120] > 0
    cleaned.close()


def test_mixed_page_and_headerless_continuation_in_ocr_llm_and_docling(monkeypatch):
    from test_document_columns import table
    from test_observation_retention import word

    from participant_bench.models import parse_ocr_response
    from participant_bench.ocr_layout import model_input, with_table_columns
    from participant_bench.structured_mapping import extract_structured

    monkeypatch.setattr(
        "participant_bench.column_context.image_boundaries",
        lambda image: [0.0, 0.25, 0.55, 0.8, 1.0],
    )
    p1_words = [
        word("Benutzer", x=0.05, y=0.10, score=92, line=1),
        word("Benutzemame", x=0.30, y=0.10, score=88, line=1),
        word("Kurzzeichen", x=0.60, y=0.10, score=90, line=1),
        word("Signetur", x=0.84, y=0.10, score=80, line=1),
        *[
            w
            for idx, given in enumerate(("Anna", "Berta", "Clara", "Dora"))
            for w in (
                word(f"10000{idx + 1}", x=0.05, y=0.18 + idx * 0.08, score=95, line=idx + 2),
                word(f"Muster, {given}", x=0.30, y=0.18 + idx * 0.08, score=94, line=idx + 2),
                word(f"AB-{idx + 1}", x=0.60, y=0.18 + idx * 0.08, score=93, line=idx + 2),
            )
        ],
        # Low-confidence handwritten row below the typed block on page 1
        word("100009_", x=0.05, y=0.68, score=12, line=6),
        word("Handschrift, Ben", x=0.30, y=0.68, score=15, line=6),
        word("HC-9", x=0.60, y=0.68, score=18, line=6),
    ]
    p2_words = [
        word("100010", x=0.05, y=0.18, score=14, line=1),
        word("Folgeseite, Clara", x=0.30, y=0.18, score=19, line=1),
        word("FS-1", x=0.60, y=0.18, score=22, line=1),
    ]
    with Image.new("RGB", (100, 100), "white") as image:
        layout1 = with_table_columns(dict(words=p1_words, text="p1"), image, document_id="mix-doc", page_number=1)
        layout2 = with_table_columns(
            dict(words=p2_words, text="p2"), image, layout1, document_id="mix-doc", page_number=2
        )
    assert "Handschrift, Ben" in model_input(layout1)
    assert "selection_hint" in model_input(layout1)
    assert layout2["mapping_provenance"]["status"] == "inherited_from_previous_page"
    p1_people = parse_ocr_response(
        json.dumps(
            dict(
                participants=[
                    dict(
                        source_row="r2",
                        personnel_number="100001",
                        first_name="Anna",
                        last_name="Muster",
                        department="AB-1",
                    ),
                    dict(
                        source_row="r6",
                        personnel_number="100009",
                        first_name="Ben",
                        last_name="Handschrift",
                        department="HC-9",
                    ),
                ]
            )
        ),
        layout1,
        [],
    )
    p2_people = parse_ocr_response(
        json.dumps(
            dict(
                participants=[
                    dict(
                        source_row="r1",
                        personnel_number="100010",
                        first_name="Clara",
                        last_name="Folgeseite",
                        department="FS-1",
                    )
                ]
            )
        ),
        layout2,
        [],
    )
    assert len(p1_people) == 2 and p1_people[0].first_name.state == "read"
    assert p1_people[1].first_name.state == "uncertain" and p1_people[1].personnel_number.value == "100009"
    assert len(p2_people) == 1 and p2_people[0].last_name.value == "Folgeseite"
    assert p2_people[0].last_name.state == "uncertain"

    # Same mixed scenario in Docling (Stage 1 TableFormer + Stage 2 selective geometry fallback)
    doc_p1 = table(
        headers=["Benutzer", "Benutzername", "Kurzzeichen", "Signatur"],
        values=[["100001", "Muster, Anna", "AB-1", ""]],
        edges=[0.0, 0.25, 0.55, 0.8, 1.0],
    )
    doc_p1["ocr_cells"] = [
        dict(text="100009", bbox=dict(x0=0.05, y0=0.50, x1=0.18, y1=0.54), confidence=0.12, index=10),
        dict(text="Handschrift, Ben", bbox=dict(x0=0.28, y0=0.50, x1=0.48, y1=0.54), confidence=0.15, index=11),
        dict(text="HC-9", bbox=dict(x0=0.58, y0=0.50, x1=0.68, y1=0.54), confidence=0.18, index=12),
    ]
    d1_people, _, _, doc_ctx = extract_structured(doc_p1, document_id="mix-doc", page_number=1)
    assert len(d1_people) == 2
    assert d1_people[0].first_name.value == "Anna" and d1_people[0].first_name.state == "read"
    assert d1_people[1].first_name.value == "Ben" and d1_people[1].first_name.state == "uncertain"
    assert d1_people[1].department.value == "HC-9" and d1_people[1].department.state == "uncertain"

    # Continuation page without header where trailing Signatur column is omitted by TableFormer
    doc_p2 = table(
        headers=["", "", ""],
        values=[["100010", "Folgeseite, Clara", ""]],
        edges=[0.0, 0.25, 0.55, 0.8],
        header=False,
    )
    doc_p2["ocr_cells"] = [
        # Stage 2a completes missing department on row 0 (y=0.10..0.14)
        dict(text="FS-1", bbox=dict(x0=0.58, y0=0.105, x1=0.68, y1=0.135), confidence=0.20, index=20),
        # Stage 2b recovers orphaned handwritten row below the table (y=0.35..0.39)
        dict(text="100011", bbox=dict(x0=0.05, y0=0.35, x1=0.18, y1=0.39), confidence=0.14, index=21),
        dict(text="Nachtrag, David", bbox=dict(x0=0.28, y0=0.35, x1=0.48, y1=0.39), confidence=0.16, index=22),
        dict(text="FS-2", bbox=dict(x0=0.58, y0=0.35, x1=0.68, y1=0.39), confidence=0.19, index=23),
    ]
    d2_people, _, _, _ = extract_structured(doc_p2, doc_ctx, document_id="mix-doc", page_number=2)
    assert len(d2_people) == 2
    assert d2_people[0].first_name.value == "Clara" and d2_people[0].first_name.state == "read"
    assert d2_people[0].department.value == "FS-1" and d2_people[0].department.state == "uncertain"
    assert d2_people[1].first_name.value == "David" and d2_people[1].first_name.state == "uncertain"
    assert d2_people[1].department.value == "FS-2" and d2_people[1].department.state == "uncertain"
