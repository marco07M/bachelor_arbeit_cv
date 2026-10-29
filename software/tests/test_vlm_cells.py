"""Physical VLM cell alignment, including wholly blank employee-ID columns."""

import json
from pathlib import Path

import pytest
from openpyxl import load_workbook
from PIL import Image
from pydantic import ValidationError

from participant_bench.config import load_config
from participant_bench.models import LocalModel
from participant_bench.report import report
from participant_bench.schema import PageResult, VisualCellPageResponse
from participant_bench.vlm_cells import parse_visual_response


def payload(headers=None, cells=None):
    return dict(identity_headers=headers if headers is not None else ["Benutzer", "Kurzzeichen"],
                participants=[dict(row_ref="1", first_name="Anna", last_name="Weber",
                                   identity_cells=cells if cells is not None else ["", "AB 123"],
                                   signature_present=False)], page_text=None)


@pytest.mark.parametrize("missing", ["", "   ", None])
def test_blank_or_unknown_employee_id_does_not_consume_short_code(missing):
    people, _, warnings, audit = parse_visual_response(json.dumps(payload(cells=[missing, "AB 123"])))
    assert len(people) == 1 and not warnings
    assert people[0].personnel_number.value == (None if missing is None else "")
    assert people[0].personnel_number.state == ("uncertain" if missing is None else "empty")
    assert people[0].department.value == "AB 123" and people[0].department.state == "read"
    assert audit["field_columns"] == dict(personnel_number=0, department=1)


def test_column_roles_follow_headers_even_in_reverse_order():
    people, _, warnings, _ = parse_visual_response(json.dumps(
        payload(headers=["Organization", "User ID"], cells=["AB-123", "000007"])))
    assert not warnings
    assert people[0].personnel_number.value == "000007"
    assert people[0].department.value == "AB-123"


def test_whole_empty_id_column_is_retained_for_every_person():
    data = payload()
    data["participants"].append(dict(row_ref="2", first_name="Lina", last_name="Klein",
                                     identity_cells=["", "CD/456"], signature_present=None))
    people, _, warnings, _ = parse_visual_response(json.dumps(data))
    assert not warnings and len(people) == 2
    assert all(person.personnel_number.state == "empty" for person in people)
    assert [person.department.value for person in people] == ["AB 123", "CD/456"]


@pytest.mark.parametrize("headers,cells", [
    (["Benutzer", "Kurzzeichen"], ["AB 123"]),
    (["Benutzer", "Kurzzeichen"], ["", "AB 123", "extra"]),
    ([None, None], ["", "AB 123"]),
    (["Benutzer Kurzzeichen"], ["AB 123"]),
])
def test_compacted_or_ambiguous_cells_require_review_without_inventing_roles(headers, cells):
    people, _, warnings, _ = parse_visual_response(json.dumps(payload(headers=headers, cells=cells)))
    assert len(people) == 1 and people[0].first_name.value == "Anna"
    assert people[0].personnel_number.value is None and people[0].department.value is None
    assert len(warnings) == 2


def test_duplicate_id_headers_do_not_disable_a_separate_clear_organization_column():
    people, _, warnings, _ = parse_visual_response(json.dumps(payload(
        headers=["Benutzer", "User ID", "Kurzzeichen"], cells=["001", "002", "AB 123"])))
    assert people[0].personnel_number.value is None
    assert people[0].department.value == "AB 123"
    assert [warning["field"] for warning in warnings] == ["personnel_number"]


def test_identifier_and_department_formats_are_not_used_to_swap_cells():
    people, _, warnings, _ = parse_visual_response(json.dumps(payload(cells=["AB 123", "000007"])))
    assert not warnings
    assert people[0].personnel_number.value == "AB 123"  # An actual ID can be alphanumeric.
    assert people[0].department.value == "000007"  # Department codes can be numeric.


def test_benutzername_heading_cannot_supply_an_employee_id():
    people, _, warnings, _ = parse_visual_response(json.dumps(payload(
        headers=["Benutzername", "Kurzzeichen"], cells=["Weber, Anna", "AB 123"])))
    assert people[0].personnel_number.value is None and people[0].department.value == "AB 123"
    assert warnings[0]["field"] == "personnel_number"


def test_complete_table_row_preserves_name_and_empty_id_as_separate_physical_cells():
    people, _, warnings, audit = parse_visual_response(json.dumps(payload(
        headers=["Nr", "Benutzername", "Benutzer", "Kurzzeichen", "Unterschrift"],
        cells=["1", "Weber, Anna", "", "AB 123", None])))
    assert not warnings and people[0].personnel_number.state == "empty"
    assert people[0].department.value == "AB 123"
    assert audit["field_columns"] == dict(personnel_number=2, department=3)


def test_table_without_id_column_keeps_name_out_of_user_id_and_reads_organization():
    people, _, warnings, _ = parse_visual_response(json.dumps(payload(
        headers=["Nr", "Name", "Kurzzeichen", "Unterschrift"],
        cells=["1", "Weber, Anna", "AB 123", None])))
    assert people[0].personnel_number.value is None and people[0].personnel_number.state == "uncertain"
    assert people[0].department.value == "AB 123"
    assert [warning["field"] for warning in warnings] == ["personnel_number"]


def test_legacy_suspicious_code_is_flagged_without_guessing_a_department():
    legacy = dict(participants=[dict(row_ref="1", first_name="Anna", last_name="Weber",
                                    personnel_number="AB 123", department="", signature_present=None)], page_text=None)
    raw = json.dumps(legacy)
    people, _, warnings, audit = parse_visual_response(raw)
    assert people[0].personnel_number.value is None and people[0].personnel_number.state == "uncertain"
    assert people[0].department.value == "" and warnings
    assert audit["kind"] == "legacy_semantic_fields"
    assert json.loads(raw) == legacy


def test_cells_remain_strict_strings_and_fallback_does_not_filter_pages():
    with pytest.raises(ValidationError):
        VisualCellPageResponse.model_validate(payload(cells=[123, "AB 123"]))
    people, text, warnings, _ = parse_visual_response(json.dumps(
        dict(identity_headers=[], participants=[], page_text="Visible page text")))
    assert not people and not warnings and text == "Visible page text"


def test_model_and_excel_export_keep_a_blank_cell_in_the_user_id_column(tmp_path):
    model = object.__new__(LocalModel)
    model.method, model.calls = "vlm", 0
    model.spec = load_config(Path("configs/local.yaml")).models["vlm"]
    raw = json.dumps(payload())
    model.generate = lambda *args: (raw, dict(output_budget_reached=False))
    with Image.new("RGB", (256, 256)) as image:
        people, responses, status, _ = model.extract(image)
    assert status == "success" and model.calls == 1 and responses[0]["raw_response"] == raw
    assert responses[0]["identity_column_assignment"]["kind"] == "physical_identity_cells"
    page = PageResult(run_id="fixture", document_id="doc", page_id="doc-p0001", page_number=1,
                      method_id="vlm", status=status, parse_status="valid", participants=people)
    report(tmp_path, {"vlm": {"status": status}}, {"vlm": [page]}, {}, {"pages": []}, {})
    book = load_workbook(tmp_path / "participants.xlsx", read_only=True)
    try:
        exported = list(book["vlm"].values)[1]
        assert exported[1] is None and exported[4] == "AB 123"
    finally:
        book.close()


def test_invalid_column_alignment_marks_model_result_partial_without_dropping_person():
    model = object.__new__(LocalModel)
    model.method, model.calls = "vlm", 0
    model.spec = load_config(Path("configs/local.yaml")).models["vlm"]
    model.generate = lambda *args: (json.dumps(payload(cells=["AB 123"])), dict(output_budget_reached=False))
    with Image.new("RGB", (256, 256)) as image:
        people, responses, status, _ = model.extract(image)
    assert len(people) == 1 and status == "partial"
    assert responses[0]["parse_status"] == "valid" and responses[0]["field_warnings"]
