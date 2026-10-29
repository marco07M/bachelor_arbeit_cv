"""Original reference headings survive parsing and remain separate from internal field identifiers."""

import csv

import pytest
from openpyxl import Workbook, load_workbook

from participant_bench.excel_columns import field_labels, resolve_columns, write_participants_xlsx
from participant_bench.excel_reference import ExcelColumns, ExcelConfig
from participant_bench.excel_reference import read_reference as strict_read
from participant_bench.io import file_hash, read_json, write_json, write_jsonl
from participant_bench.report import refresh_report, report
from participant_bench.roster_benchmark.config import BenchmarkConfig, ReferenceConfig
from participant_bench.roster_benchmark.evaluation import evaluate_run
from participant_bench.roster_benchmark.references import read_reference
from participant_bench.schema import PageResult, VisualParticipant


def test_original_heading_case_spacing_and_order_are_preserved():
    headings = ["LAST NAME", " Class ID ", "Organization", "First Name", "User ID"]
    indices, labels = resolve_columns(headings, ExcelColumns().model_dump())
    assert indices["class_id"] == 1
    assert list(labels.values()) == headings
    assert field_labels(labels)["last_name"] == "LAST NAME"
    assert field_labels(labels)["personnel_number"] == "User ID"
    assert field_labels(labels)["department"] == "Organization"


@pytest.mark.parametrize("headings", [
    ["Class ID", "User ID", "First Name", "Last Name", "Organization", "FIRST NAME"],
    ["Class ID", "User ID", "Last Name", "Organization"],
])
def test_missing_or_ambiguous_required_headers_are_rejected(headings):
    with pytest.raises(ValueError, match="genau einmal"):
        resolve_columns(headings, ExcelColumns().model_dump())


def test_two_fields_cannot_silently_share_one_reference_column():
    with pytest.raises(ValueError, match="eigene Spalte"):
        resolve_columns(["Name"], {"first_name": "Name", "last_name": "Name"})


def test_xlsx_readers_capture_actual_headings_without_modifying_reference(tmp_path):
    path = tmp_path / "reference.xlsx"
    book = Workbook()
    book.active.append(["Class ID", "USER ID", "FIRST NAME", "Last Name", "Organization"])
    book.active.append(["123456", "000007", "Anna", "Weber", "MUC"])
    book.save(path)
    before = file_hash(path)
    data = read_reference(path, ReferenceConfig())
    actual = {}
    people, _ = strict_read(path, ExcelConfig(), column_names=actual)
    assert data.columns == actual
    assert actual["first_name"] == "FIRST NAME" and actual["user_id"] == "USER ID"
    assert people == data.people and people[0].user_id == "000007"
    assert file_hash(path) == before


def test_excel_export_preserves_ids_blanks_and_formula_like_text(tmp_path):
    path = tmp_path / "participants.xlsx"
    write_participants_xlsx(path, {"vlm": [dict(class_id="001234", user_id="", first_name="=1+1",
        last_name="Weber", short_code="ABC-12", page_number=2, output_index=0)]})
    book = load_workbook(path, data_only=False)
    try:
        sheet = book["vlm"]
        assert [c.value for c in sheet[1]] == ["Class ID", "User ID", "First Name", "Last Name", "Organization"]
        assert sheet["A2"].value == "001234" and sheet["A2"].data_type == "s"
        assert sheet["B2"].value is None and sheet["E2"].value == "ABC-12"
        assert sheet["C2"].value == "=1+1" and sheet["C2"].data_type == "s"
        assert book["Quellen"]["E2"].value == 2
    finally:
        book.close()


def source_run(root):
    person = VisualParticipant(first_name="Anna", last_name="Weber", personnel_number="000007", department="MUC").participant()
    page = PageResult(run_id="fixture", document_id="document", page_id="document-p0001", page_number=1,
                      method_id="vlm", status="partial", parse_status="valid", participants=[person])
    summary = {"vlm": {"status": "partial", "output_kind": "structured"}}
    manifest = dict(inputs=[dict(kind="pdf", sha256="document", path="123456.pdf")],
                    pages=[dict(page_id=page.page_id, source_path="123456.pdf", page_number=1,
                                status="ready", review_required=False)])
    write_json(root / "summary.json", summary)
    write_json(root / "manifest.json", manifest)
    write_json(root / "metrics.json", {})
    write_json(root / "costs.json", {})
    write_jsonl(root / "vlm/extractions.jsonl", [page.model_dump()])
    return page, summary, manifest


def test_report_uses_excel_titles_and_refresh_keeps_them_without_new_inference(tmp_path):
    page, summary, manifest = source_run(tmp_path)
    columns = {"first_name": "First <Name>", "class_id": "CLASS ID", "user_id": "USER ID",
               "last_name": "Last Name", "short_code": "Organization"}
    prediction_hash = file_hash(tmp_path / "vlm/extractions.jsonl")
    report(tmp_path, summary, {"vlm": [page]}, {}, manifest, {}, columns=columns)
    refresh_report(tmp_path)
    text = (tmp_path / "report.html").read_text(encoding="utf-8")
    assert "<th>First &lt;Name&gt;</th>" in text and "<th>USER ID</th>" in text
    assert "participants.xlsx" in text
    assert file_hash(tmp_path / "vlm/extractions.jsonl") == prediction_hash
    book = load_workbook(tmp_path / "participants.xlsx", read_only=True)
    try:
        rows = list(book["vlm"].values)
        assert list(rows[0]) == list(columns.values())
        assert rows[1] == ("Anna", "123456", "000007", "Weber", "MUC")
    finally:
        book.close()


@pytest.mark.parametrize("filename, expected", [("1.pdf", None), ("123456__2.pdf", "123456")])
def test_export_class_id_is_not_guessed_from_arbitrary_filenames(tmp_path, filename, expected):
    page, summary, manifest = source_run(tmp_path)
    manifest["pages"][0]["source_path"] = filename
    report(tmp_path, summary, {"vlm": [page]}, {}, manifest, {})
    book = load_workbook(tmp_path / "participants.xlsx", read_only=True)
    try:
        assert list(book["vlm"].values)[1][0] == expected
    finally:
        book.close()


@pytest.mark.parametrize("comparison", ["benchmark", "strict"])
def test_reference_comparisons_copy_actual_headers_and_keep_source_files(tmp_path, comparison):
    source = tmp_path / "source"
    source_run(source)
    reference = tmp_path / "reference.xlsx"
    book = Workbook()
    book.active.append(["LAST NAME", "Class ID", "USER ID", "First Name", "Organization"])
    book.active.append(["Weber", "123456", "000007", "Anna", "MUC"])
    book.save(reference)
    before = {p: file_hash(p) for p in source.rglob("*") if p.is_file()}
    before[reference] = file_hash(reference)
    if comparison == "benchmark":
        output, scores = evaluate_run(source, reference, BenchmarkConfig(), tmp_path / "outputs")
        assert scores["vlm"]["score_percent"] == 100
        with (output / "fields.csv").open(encoding="utf-8-sig", newline="") as stream:
            assert {row["field_label"] for row in csv.DictReader(stream)} == {
                "USER ID", "First Name", "LAST NAME", "Organization"}
    else:
        from participant_bench.excel_comparison import compare_run

        output, scores = compare_run(source, reference, ExcelConfig(), output=tmp_path / "comparison")
        assert scores["vlm"]["participant_assignment"]["f1"]["value"] == 1
    assert all(file_hash(p) == digest for p, digest in before.items())
    assert read_json(output / "identity.json")["reference_columns"]["last_name"] == "LAST NAME"
    book = load_workbook(output / "participants.xlsx", read_only=True)
    try:
        assert list(next(book["vlm"].values)) == ["LAST NAME", "Class ID", "USER ID", "First Name", "Organization"]
        assert list(book["Referenz"].values)[1] == ("Weber", "123456", "000007", "Anna", "MUC")
    finally:
        book.close()
