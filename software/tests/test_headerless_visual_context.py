"""Real pipeline contracts for headerless pages, independent missing scalar fields and safe context."""

import json
from pathlib import Path

import pytest
from PIL import Image, ImageDraw

from participant_bench.column_context import geometry, image_boundaries
from participant_bench.config import load_config
from participant_bench.io import digest
from participant_bench.models import LocalModel
from participant_bench.vlm_cells import continuation_context, parse_visual_response

EDGES = [0.1, 0.25, 0.5, 0.65, 0.8, 0.9]
HEADINGS = ["Benutzer", "Benutzename", "Kurzzeichen", "Signatur"]


def payload(headings=HEADINGS, cells=None):
    return dict(
        identity_headers=headings,
        participants=[
            dict(
                first_name="Anna",
                last_name="Beispiel",
                identity_cells=cells or ["00123", "Beispiel, Anna", "AB-12", None],
                signature_present=None,
            )
        ],
        page_text=None,
    )


def parse(data, previous=None, page=1, doc="doc", edges=EDGES, observations=None):
    return parse_visual_response(
        json.dumps(data),
        document_context=previous,
        document_id=doc,
        page_number=page,
        column_geometry=geometry(len(edges) - 1, boundaries=edges),
        cell_observations=observations,
    )


def grid():
    image = Image.new("RGB", (800, 600), "white")
    draw = ImageDraw.Draw(image)
    for x in EDGES:
        draw.line((round(x * 800), 100, round(x * 800), 500), fill="black", width=3)
    for y in (100, 200, 300, 400, 500):
        draw.line((80, y, 720, y), fill="black", width=3)
    return image


def test_white_margins_are_not_physical_vlm_columns():
    with grid() as image:
        physical = image_boundaries(image, include_page_margins=False)
        padded = image_boundaries(image)
    assert physical == pytest.approx(EDGES, abs=0.006)
    assert padded == pytest.approx([0, *EDGES, 1], abs=0.006)


@pytest.mark.parametrize("missing", ["", None])
def test_exact_current_participant_header_echo_can_use_verified_previous_structure(missing):
    _, _, _, first = parse(payload())
    data = payload(["00123", "Beispiel, Anna", "AB-12", None])
    data["participants"].append(
        dict(
            first_name="Lina",
            last_name="Muster",
            identity_cells=[missing, "Muster, Lina", "CD-34", None],
            signature_present=None,
        )
    )
    original = json.dumps(data)
    observations = dict(
        coordinate_scale=1000,
        rows=[
            dict(
                source_row=f"current-{i}",
                cells=[
                    [name, 280, 300 + i * 100, 480, 350 + i * 100, 0.9],
                    [organization, 520, 300 + i * 100, 620, 350 + i * 100, 0.9],
                    *([[identifier, 120, 300 + i * 100, 220, 350 + i * 100, 0.9]] if identifier else []),
                ],
            )
            for i, (name, organization, identifier) in enumerate(
                [("Beispiel, Anna", "AB-12", "00123"), ("Muster, Lina", "CD-34", missing)]
            )
        ],
    )
    people, _, warnings, audit = parse(data, first["column_context"], 2, observations=observations)
    assert warnings  # Native recovery remains explicitly reviewable.
    assert people[0].personnel_number.value == "00123"
    assert people[1].personnel_number.value == missing
    assert people[1].department.value == "CD-34"
    assert audit["mapping_provenance"]["status"] == "inherited_from_previous_page"
    assert audit["header_interpretation"] == "current_participant_row_echo"
    assert json.dumps(data) == original
    assert "Beispiel" not in json.dumps(audit["column_context"])
    assert "00123" not in json.dumps(audit["column_context"])


@pytest.mark.parametrize(
    "unsafe", ["other_document", "earlier_page", "changed_prefix", "no_context", "not_exact_echo"]
)
def test_participant_header_echo_never_bypasses_context_and_geometry_checks(unsafe):
    _, _, _, first = parse(payload())
    data = payload(["00123", "Beispiel, Anna", "AB-12", None])
    context, doc, page, edges = first["column_context"], "doc", 2, EDGES
    if unsafe == "other_document":
        doc = "different"
    elif unsafe == "earlier_page":
        page = 1
    elif unsafe == "changed_prefix":
        edges = [0.1, 0.25, 0.5, 0.78, 0.85, 0.95]
    elif unsafe == "no_context":
        context = None
    else:
        data["identity_headers"][2] = "Unrelated current title"
    people, _, _, audit = parse(data, context, page, doc, edges)
    assert people[0].personnel_number.value is None and people[0].department.value is None
    assert audit["mapping_provenance"]["status"] != "inherited_from_previous_page"


def test_unknown_suffix_is_not_assumed_to_be_a_signature_column():
    _, _, _, first = parse(payload([*HEADINGS[:3], "Unrelated title"]))
    assert first["column_context"]["geometry"] is None


def test_echo_without_independent_native_positions_never_promotes_signature_text_to_organization():
    _, _, _, first = parse(payload())
    people, _, _, audit = parse(
        payload(
            ["00123", "Beispiel, Anna", "Signature text", None],
            ["00123", "Beispiel, Anna", "Signature text", None],
        ),
        first["column_context"],
        2,
    )
    assert people[0].department.value is None and people[0].personnel_number.value is None
    assert not audit["echo_corroboration"][0]["fields"]


def test_native_completion_is_visible_in_the_saved_field_chain():
    from participant_bench.roster_benchmark.pipeline_trace import field_trace
    from participant_bench.schema import PageResult

    _, _, _, first = parse(payload())
    data = payload(
        ["", "Beispiel, Anna", "Signature text", None], ["", "Beispiel, Anna", "Signature text", None]
    )
    hints = dict(
        coordinate_scale=1000,
        rows=[
            dict(
                source_row="current-1",
                cells=[["Beispiel, Anna", 280, 300, 480, 350, 0.9], ["CD-34", 520, 300, 620, 350, 0.9]],
            )
        ],
    )
    people, _, warnings, audit = parse(data, first["column_context"], 2, observations=hints)
    assert people[0].personnel_number.value == "" and people[0].department.value == "CD-34"
    page = PageResult(
        run_id="fixture",
        document_id="doc",
        page_id="doc-p0002",
        page_number=2,
        method_id="ocr_vlm",
        status="partial",
        parse_status="valid",
        participants=people,
    )
    raw = dict(
        responses=[
            dict(
                raw_response=json.dumps(data),
                parse_status="valid",
                identity_column_assignment=audit,
                field_warnings=warnings,
            )
        ]
    )
    trace = field_trace(dict(output_index=0), page, raw, {}, [], "department")
    recovered = next(s for s in trace["stages"] if s["stage"] == "observed_cell_completion")
    assert recovered["value"] == "CD-34" and recovered["evidence"]["native_ref"] == "current-1/1"


def test_new_explicit_headings_override_old_roles():
    _, _, _, first = parse(payload())
    people, _, _, audit = parse(
        payload(
            ["Organisation", "Benutzername", "Benutzer", "Signatur"],
            ["CD-34", "Beispiel, Anna", "00987", None],
        ),
        first["column_context"],
        2,
    )
    assert people[0].personnel_number.value == "00987" and people[0].department.value == "CD-34"
    assert audit["mapping_provenance"]["status"] == "updated_on_current_page"


def test_invented_separate_name_columns_cannot_override_a_conflicting_measured_grid():
    data = payload(
        ["Benutzer", "Vorname", "Nachname", "Organisation"], ["00123", "Anna", "Beispiel", "CD-34"]
    )
    people, _, warnings, audit = parse(data)
    assert people[0].personnel_number.value is None and people[0].department.value is None
    assert audit["measured_column_conflict"] and len(warnings) == 2


def test_structural_hint_groups_combined_name_parts_in_one_physical_column():
    _, _, _, first = parse(payload())
    hint = continuation_context(
        first["column_context"], geometry(5, boundaries=EDGES), document_id="doc", page_number=2
    )
    assert hint["physical_column_count"] == 5
    assert hint["headerless_identity_headers"] == [None] * 5
    assert len(hint["physical_columns"]) == 3
    assert hint["physical_columns"][1]["fields"] == ["first_name", "last_name"]


@pytest.mark.parametrize("method", ["vlm", "ocr_vlm"])
def test_model_receives_only_verified_structure_and_records_actual_prompt_hash(method):
    model = object.__new__(LocalModel)
    model.method, model.calls = method, 0
    model.spec = load_config(Path("configs/benchmark-five.yaml")).models[method]
    texts = []
    answers = iter([payload(), payload([None] * 4, ["", "Beispiel, Anna", "CD-34", None])])

    def generate(text, *args, **kwargs):
        texts.append(text)
        return json.dumps(next(answers)), dict(output_budget_reached=False)

    model.generate = generate
    with grid() as image:
        for page in (1, 2):
            model.document_page_context = dict(document_id="doc", page_number=page)
            people, records, _, _ = model.extract(image, dict(hints={}) if method == "ocr_vlm" else None)
    assert "DOCUMENT_COLUMN_CONTEXT" not in texts[0] and "DOCUMENT_COLUMN_CONTEXT" in texts[1]
    assert all(value not in texts[1] for value in ("00123", "Beispiel", "Anna", "AB-12"))
    assert people[0].personnel_number.state == "empty" and people[0].department.value == "CD-34"
    assert records[0]["text_prompt_sha256"] == digest(texts[1])
    assert records[0]["document_column_context"]["source_page"] == 1


def test_failed_geometry_sends_no_old_context_to_model():
    _, _, _, first = parse(payload())
    hint = continuation_context(
        first["column_context"],
        geometry(3, boundaries=[0.1, 0.25, 0.5, 0.8]),
        document_id="doc",
        page_number=2,
    )
    assert hint is None
