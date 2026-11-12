"""Observed loss points and conservative continuation, with no model inference."""

import json
from copy import deepcopy
from pathlib import Path

import pymupdf
import pytest
from PIL import Image
from test_extraction_errors import field, page
from test_vlm_cells import payload

from participant_bench.column_context import geometry, resolve
from participant_bench.config import load_config
from participant_bench.io import file_hash
from participant_bench.models import LocalModel
from participant_bench.pdf import prepare
from participant_bench.roster_benchmark.error_report import diagnose_field
from participant_bench.roster_benchmark.pipeline_trace import field_trace, page_trace, visual_record
from participant_bench.schema import Box
from participant_bench.structure import lossless_image_pdf
from participant_bench.unlimited_assignment import header_fields
from participant_bench.vlm_cells import parse_visual_response


@pytest.mark.parametrize("title", ["User", "User ID", "Benutzer"])
def test_exact_employee_heading_aliases(title):
    assert header_fields(title) == {"personnel_number"}


@pytest.mark.parametrize("title", ["User Name", "Username", "Benutzername"])
def test_full_name_heading_never_becomes_an_employee_id(title):
    assert header_fields(title) == {"first_name", "last_name"}


def visual(headers, cells, context=None, number=1, document="doc", profile=None):
    return parse_visual_response(
        json.dumps(payload(headers, cells)),
        document_context=context,
        document_id=document,
        page_number=number,
        column_geometry=profile,
    )


def test_visual_user_keeps_exact_id_and_department_without_shifting():
    people, _, warnings, _ = visual(["User", "User Name", "Department"], ["000007", "Weber, Anna", "AB-12"])
    assert people[0].personnel_number.value == "000007" and people[0].department.value == "AB-12"
    assert not warnings


def test_visual_continuation_requires_same_measured_grid_and_only_keeps_roles():
    profile = geometry(3, boundaries=[0, 0.2, 0.7, 1])
    _, _, _, audit = visual(
        ["User", "User Name", "Department"], ["000007", "Weber, Anna", "AB-12"], profile=profile
    )
    context = audit["column_context"]
    assert "000007" not in json.dumps(context) and "Anna" not in json.dumps(context)
    people, _, warnings, after = visual(
        [None] * 3, ["000008", "Muster, Nora", "CD-34"], context, 2, profile=profile
    )
    assert people[0].personnel_number.value == "000008" and people[0].department.value == "CD-34"
    assert not warnings and after["mapping_provenance"]["status"] == "inherited_from_previous_page"


@pytest.mark.parametrize(
    "case", ["other_document", "earlier_page", "changed_grid", "missing_grid", "fake_headings", "short_row"]
)
def test_visual_continuation_never_guesses_unsafe_column_roles(case):
    profile = geometry(3, boundaries=[0, 0.2, 0.7, 1])
    _, _, _, first = visual(
        ["User", "User Name", "Department"], ["000007", "Weber, Anna", "AB-12"], profile=profile
    )
    heads, cells, doc, number = [None] * 3, ["000008", "Muster, Nora", "CD-34"], "doc", 2
    if case == "other_document":
        doc = "other"
    elif case == "earlier_page":
        number = 1
    elif case == "changed_grid":
        profile = geometry(3, boundaries=[0, 0.4, 0.8, 1])
    elif case == "missing_grid":
        profile = None
    elif case == "fake_headings":
        heads = ["000008", "Muster, Nora", "CD-34"]
    elif case == "short_row":
        cells = cells[1:]
    people, _, warnings, _ = visual(heads, cells, first["column_context"], number, doc, profile)
    assert people[0].personnel_number.value is None and people[0].department.value is None and warnings


def test_missing_previous_geometry_is_unknown_not_an_attribute_error():
    _, context, _ = resolve(
        {"first_name": {1}, "last_name": {1}, "personnel_number": {0}},
        {},
        None,
        document_id="doc",
        page_number=1,
        has_header=True,
        column_count=2,
    )
    found, _, trace = resolve(
        {}, {}, geometry(2, boundaries=[0, 0.4, 1]), context, document_id="doc", page_number=2
    )
    assert not found and trace["reason"] == "missing_measured_column_geometry"


def test_resume_only_restores_scoped_column_metadata():
    model = object.__new__(LocalModel)
    profile = geometry(3, boundaries=[0, 0.2, 0.7, 1])
    _, _, _, first = visual(
        ["User", "User Name", "Department"], ["000007", "Weber, Anna", "AB-12"], profile=profile
    )
    raw = dict(responses=[dict(identity_column_assignment=first)])
    model.restore_mapping(dict(document_id="other", page_number=2), raw)
    assert not model.visual_column_context
    model.restore_mapping(dict(document_id="doc", page_number=1), raw)
    assert model.visual_column_context["doc"] == first["column_context"]
    model.restore_mapping(
        dict(document_id="doc", page_number=2),
        dict(responses=[dict(identity_column_assignment=dict(column_context={}))]),
    )
    assert not model.visual_column_context


@pytest.mark.parametrize("angle", [0, 90, 180, 270])
def test_osd_clockwise_preparation_is_applied_once_and_records_decision(tmp_path, angle):
    config = load_config(Path("configs/smoke.yaml"))
    config.pdf.auto_orient = True
    raw = tmp_path / "input"
    raw.mkdir()
    with pymupdf.open() as doc:
        p = doc.new_page(width=100, height=70)
        p.draw_rect(pymupdf.Rect(0, 0, 20, 12), color=(1, 0, 0), fill=(1, 0, 0))
        doc.save(raw / "synthetic.pdf")

    class OSD:
        def orientation(self, image):
            return angle, 10.0, None, 0.01

    manifest = prepare(raw, config, tmp_path / "prepared", OSD())
    p = manifest["pages"][0]
    assert p["orientation_proposed_clockwise"] == p["additional_rotation_clockwise"] == angle
    assert p["orientation_status"] == "accepted" and not p["review_required"]
    with Image.open(tmp_path / "prepared" / p["image"]) as image:
        assert (image.width > image.height) == (angle in (0, 180))
        point = {
            0: (3, 3),
            90: (image.width - 4, 3),
            180: (image.width - 4, image.height - 4),
            270: (3, image.height - 4),
        }[angle]
        assert image.getpixel(point)[0] > 240 and image.getpixel(point)[1] < 20
        # The Docling scan adapter packages precisely these same oriented pixels.
        packed = lossless_image_pdf(image, config.pdf.dpi)
        with pymupdf.open(stream=packed, filetype="pdf") as d:
            pix = d[0].get_pixmap(dpi=config.pdf.dpi, alpha=False)
            assert abs(pix.width - image.width) <= 1 and abs(pix.height - image.height) <= 1


def test_low_confidence_rotation_is_preserved_as_proposal_without_silently_rotating(tmp_path):
    config = load_config(Path("configs/smoke.yaml"))
    config.pdf.auto_orient = True
    raw = tmp_path / "input"
    raw.mkdir()
    with pymupdf.open() as doc:
        doc.new_page()
        doc.save(raw / "synthetic.pdf")

    class OSD:
        def orientation(self, image):
            return 270, 0.4, None, 0.01

    p = prepare(raw, config, tmp_path / "prepared", OSD())["pages"][0]
    assert p["orientation_proposed_clockwise"] == 270 and p["additional_rotation_clockwise"] == 0
    assert p["review_required"] and p["orientation_status"] == "below_confidence_threshold"


def test_visual_trace_uses_saved_rejection_and_role_index_not_the_repaired_alias():
    current = page()
    current.method_id = "vlm"
    data = payload(["User", "User Name", "Department"], ["000007", "Weber, Anna", "AB-12"])
    data["participants"].insert(0, deepcopy(data["participants"][0]))
    raw = dict(
        responses=[
            dict(
                parse_status="valid",
                raw_response=json.dumps(data),
                identity_column_assignment=dict(field_columns=dict(personnel_number=None, department=2)),
                field_warnings=[
                    dict(output_index=1, field="personnel_number", reason="saved heading rejected")
                ],
            )
        ],
        person_role_filter=dict(
            excluded=[{}], output_index_mapping=[dict(output_index=0, source_output_index=1)]
        ),
    )
    finding = diagnose_field(field(field="user_id", reference_value="000007"), current, raw, {})
    assert finding["category"] == "column_mapping" and finding["certainty"] == "proven"
    response = next(s for s in finding["pipeline_trace"]["stages"] if s["stage"] == "model_response")
    assert response["saved_column"] is None and response["cells"][0] == "000007"
    raw["person_role_filter"]["output_index_mapping"] = []
    assert visual_record(raw, 0) is None


def test_missing_field_uses_complete_proven_source_row_not_only_the_name_box():
    current = page()
    current.participants[0].bbox = Box(x0=0.4, x1=0.7, y0=0.2, y1=0.3)
    raw = dict(
        responses=[
            dict(
                ocr_field_evidence=[
                    dict(
                        output_index=0,
                        source_row="r1",
                        fields={},
                        source_cells=[dict(bbox=dict(x0=0.1, x1=0.8, y0=0.2, y1=0.3))],
                    )
                ]
            )
        ]
    )
    observations = dict(
        observations=[
            dict(
                id="id",
                text="000007",
                bbox=dict(x0=0.1, x1=0.2, y0=0.2, y1=0.3),
                submitted_to_assignment=True,
            )
        ]
    )
    finding = diagnose_field(field(field="user_id", reference_value="000007"), current, raw, observations)
    assert finding["category"] == "model_omission" and finding["observations"]


def test_trace_retains_recorded_literal_and_position_validation_snapshots():
    current = page()
    proof = dict(output_index=0, source_row="r1", fields={})
    original = current.participants[0].model_dump()
    original["department"]["value"] = "AB-12"
    after = deepcopy(original)
    after["department"]["value"] = None
    raw = dict(
        structure=dict(row_evidence=[proof]),
        assignment=dict(
            participants_before_validation=[dict(source_row="r1", department=[1, "AB-12"])],
            participants_after_literal_grounding=[original],
            participants_after_position_validation=[after],
        ),
    )
    trace = field_trace(field(), current, raw, proof, [], "department")
    assert trace["loss_stage"] == "position_validation"
    assert [
        s["value"]
        for s in trace["stages"]
        if s["stage"] in ("model_response", "literal_validation", "position_validation")
    ] == ["AB-12", "AB-12", None]


def test_page_chain_never_invents_a_missing_historical_osd_proposal(tmp_path):
    current = page()
    (tmp_path / "pages").mkdir()
    image = tmp_path / "pages" / (current.page_id + ".png")
    Image.new("RGB", (30, 30)).save(image)
    manifest = dict(
        pages=[
            dict(
                page_id=current.page_id,
                review_required=True,
                orientation_confidence=0.4,
                additional_rotation_clockwise=0,
            )
        ]
    )
    chain = page_trace(tmp_path, current, dict(run_image_sha256=file_hash(image)), manifest, [])
    assert chain["image_matches_raw"] is True and chain["orientation_proposed_clockwise"] is None
    assert chain["orientation_status"] == "legacy_review_required"


def test_empty_cell_and_deterministic_mapping_are_not_an_omitted_model_value():
    current = page()
    current.participants[0].department.value = ""
    trace = field_trace(
        field(),
        current,
        dict(structure=dict(assignment_backend="deterministic_headers")),
        {},
        [],
        "department",
    )
    assert trace["loss_stage"] == "explicit_empty_output"
    assert (
        next(s for s in trace["stages"] if s["stage"] == "model_response")["status"]
        == "not_applicable_deterministic_mapper"
    )


def test_unrecorded_submission_is_not_presented_as_a_measured_model_input():
    trace = field_trace(
        field(), page(), {}, {}, [dict(text="AB-12", submitted_to_assignment=None)], "department"
    )
    assert next(s for s in trace["stages"] if s["stage"] == "model_input")["status"] == "submission_unknown"
    assert (
        visual_record(
            dict(
                responses=[
                    dict(parse_status="valid", raw_response='{"identity_headers":[],"participants":null}')
                ]
            ),
            0,
        )
        is None
    )


def test_framework_cli_forwards_an_explicit_curated_manifest(tmp_path, monkeypatch):
    from participant_bench.roster_benchmark import cli

    config = tmp_path / "framework.yaml"
    config.write_text("input_dir: pdfs\n", encoding="utf-8")
    manifest = tmp_path / "curated.json"
    calls = []

    def fake_run(config, base, **kwargs):
        calls.append(kwargs)
        return tmp_path / "report", {}

    monkeypatch.setattr(cli, "run_benchmark", fake_run)
    assert cli.main(["run", "--config", str(config), "--manifest", str(manifest)]) == 0
    assert calls[0]["manifest_path"] == manifest


def test_framework_passes_manifest_to_existing_extractor_without_reference(tmp_path, monkeypatch):
    from participant_bench.roster_benchmark import runner
    from participant_bench.roster_benchmark.config import BenchmarkConfig

    config = BenchmarkConfig()
    extraction = load_config(Path("configs/smoke.yaml"))
    inputs = tmp_path / "input"
    reference = tmp_path / "private.csv"
    manifest = tmp_path / "curated.json"
    monkeypatch.setattr(
        runner,
        "preflight",
        lambda *a: (inputs, reference, ({}, "hash"), dict(input_pdfs=1, courses_compared=1)),
    )
    monkeypatch.setattr(runner, "load_extraction_config", lambda *a: extraction)
    calls = []

    def extract(config, folder, **kwargs):
        calls.append(kwargs)
        return tmp_path / "source", {}

    monkeypatch.setattr(runner, "extract", extract)
    monkeypatch.setattr(runner, "evaluate_run", lambda *a, **kw: (tmp_path / "report", {}))
    runner.run_benchmark(config, tmp_path, manifest_path=manifest)
    assert calls == [dict(resume=None, offline=True, manifest_path=manifest.resolve())]


def test_visual_prompt_and_schema_agree_on_roster_only_and_headerless_columns():
    from participant_bench.extraction_prompts import VERSION, extraction_prompt
    from participant_bench.models import extraction_prompt_snapshot
    from participant_bench.schema import VisualCellPageResponse

    text = extraction_prompt("image")
    description = VisualCellPageResponse.model_json_schema()["properties"]["identity_headers"]["description"]
    assert "participant-row table" in text and "PARTICIPANT-ROW TABLE ONLY" in description
    assert "course-metadata tables" in text and "course metadata tables" in description
    assert "one null heading per physical" in text and "headerless columns use null" in description
    assert extraction_prompt_snapshot()["version"] == VERSION == "participant-json-v26-roster-header-scope"


def test_local_visual_extractor_threads_only_verified_column_context_between_pages(monkeypatch):
    model = object.__new__(LocalModel)
    model.method, model.calls = "vlm", 0
    model.spec = load_config(Path("configs/benchmark-five.yaml")).models["vlm"]
    answers = iter(
        [
            payload(["User", "User Name", "Department"], ["000007", "Weber, Anna", "AB-12"]),
            payload([None] * 3, ["000008", "Muster, Nora", "CD-34"]),
        ]
    )
    model.generate = lambda *a: (json.dumps(next(answers)), dict(output_budget_reached=False))
    monkeypatch.setattr("participant_bench.column_context.image_boundaries", lambda image: [0, 0.2, 0.7, 1])
    with Image.new("RGB", (200, 200)) as image:
        model.document_page_context = dict(document_id="doc", page_number=1)
        model.extract(image)
        model.document_page_context = dict(document_id="doc", page_number=2)
        people, responses, _, _ = model.extract(image)
    assert people[0].personnel_number.value == "000008" and people[0].department.value == "CD-34"
    assert responses[0]["identity_column_assignment"]["mapping_provenance"]["source_page"] == 1
