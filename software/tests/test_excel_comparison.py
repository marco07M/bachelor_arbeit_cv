import csv
import json
import subprocess
import sys

import pytest
from openpyxl import Workbook

from participant_bench.excel_comparison import compare_run, course_mapping, evaluate_method
from participant_bench.excel_reference import ExcelConfig, ReferencePerson, read_reference
from participant_bench.io import file_hash, read_json, write_json, write_jsonl
from participant_bench.schema import PageResult, Participant, TextField

HEADERS = ["Class ID", "User ID", "First Name", "Last Name", "Organization", "Email Address"]


def workbook(path, rows):
    book = Workbook()
    sheet = book.active
    sheet.title = "Kurse"
    sheet.append(HEADERS)
    for row in rows:
        sheet.append(row)
    book.save(path)
    return book


def person(first="Anna", last="Weber", user="00007", code="ABC", user_state="read"):
    return Participant(
        first_name=TextField(value=first, state="read"), last_name=TextField(value=last, state="read"),
        personnel_number=TextField(value=user, state=user_state), department=TextField(value=code, state="read"),
    )


def ref(row=2, course="123456", first="Anna", last="Weber", user="00007", code="ABC"):
    return ReferencePerson(row, course, user, first, last, code)


def prediction(person, doc="doc", page=1, index=0):
    return {"person": person, "document_id": doc, "page_number": page, "index": index}


def evaluate(predictions, refs, mapping=None):
    return evaluate_method(predictions, refs, mapping or {"doc": "123456"}, ExcelConfig())


def test_excel_reads_only_mapped_columns_and_preserves_leading_zeros(tmp_path):
    path = tmp_path / "reference.xlsx"
    book = workbook(path, [[12345, 7, "Anna", "Weber", "ABC", "ignored@example.invalid"]])
    book.active["A2"].number_format = "000000"
    book.active["B2"].number_format = "00000"
    book.save(path)
    original = file_hash(path)
    rows, sheet = read_reference(path, ExcelConfig())
    assert sheet == "Kurse"
    assert rows == [ref(course="012345")]
    assert file_hash(path) == original


def test_excel_missing_mapping_and_formula_are_explicit_errors(tmp_path):
    path = tmp_path / "reference.xlsx"
    book = workbook(path, [["123456", "00007", "Anna", "Weber", "ABC"]])
    with pytest.raises(ValueError, match="Excel-Blatt fehlt"):
        read_reference(path, ExcelConfig(sheet="missing"))
    book.active["E1"] = "Other"
    book.save(path)
    with pytest.raises(ValueError, match="Organization"):
        read_reference(path, ExcelConfig())
    book.active["E1"] = "Organization"
    book.active["B2"] = '=TEXT(7,"00000")'
    book.save(path)
    with pytest.raises(ValueError, match="Formel"):
        read_reference(path, ExcelConfig())


@pytest.mark.parametrize("masked", ["", "12***45", "XXXXX", "███", "unkenntlich", "n/a", "-"])
def test_masked_user_ids_are_not_identity_keys(masked):
    assert not ExcelConfig().usable_id(masked)


@pytest.mark.parametrize("user,state", [("12***45", "uncertain"), (None, "illegible")])
def test_masked_pdf_id_uses_names_and_code_and_is_excluded_from_id_metric(user, state):
    scores, rows, details = evaluate([prediction(person(user=user, user_state=state))], [ref()])
    assert scores["participant_assignment"]["tp"] == 1
    assert rows[0]["matching_source"] == "name_short_code"
    assert scores["fields"]["user_id"]["exact_match"]["denominator"] == 0
    assert scores["fields"]["user_id"]["excluded"] == 1
    assert next(row for row in details if row["field"] == "user_id")["exact"] is None


def test_masked_excel_id_is_not_compared():
    scores, _, _ = evaluate([prediction(person())], [ref(user="***")])
    assert scores["participant_assignment"]["tp"] == 1
    assert scores["fields"]["user_id"]["exact_match"]["value"] is None


def test_wrong_user_id_is_detected_via_independent_name_code_assignment():
    scores, rows, _ = evaluate([prediction(person(user="007"))], [ref()])
    assert rows[0]["matching_source"] == "name_short_code"
    assert scores["fields"]["user_id"]["exact_match"] == {"numerator": 0, "denominator": 1, "value": 0.0}
    assert scores["independent_user_id_exact_match"]["value"] == 0


def test_user_id_assignment_scores_name_errors_but_marks_id_metric_conditioned():
    scores, rows, details = evaluate([prediction(person(first="Anma"))], [ref()])
    assert rows[0]["matching_source"] == "user_id"
    assert scores["fields"]["first_name"]["exact_match"]["value"] == 0
    assert scores["independent_user_id_exact_match"]["denominator"] == 0
    assert next(row for row in details if row["field"] == "user_id")["used_for_matching"]


def test_same_name_requires_short_code_when_id_masked():
    references = [ref(row=2, code="ABC"), ref(row=3, user="00008", code="XYZ")]
    scores, rows, _ = evaluate([prediction(person(user="***", code="XYZ"))], references)
    assert scores["participant_assignment"]["tp"] == 1
    assert next(row for row in rows if row["status"] == "matched")["excel_row"] == 3


def test_non_unique_composite_or_contradictory_id_requires_review():
    references = [ref(row=2), ref(row=3, user="00008")]
    scores, rows, _ = evaluate([prediction(person(user="***"))], references)
    assert scores["participant_assignment"]["tp"] == 0
    assert any(row["status"] == "ambiguous" for row in rows)
    references[1] = ref(row=3, user="00008", first="Ben")
    scores, rows, _ = evaluate([prediction(person(first="Ben"))], references)
    assert scores["participant_assignment"]["tp"] == 0
    assert any(row["status"] == "identity_conflict" for row in rows)


def test_course_scope_prevents_cross_course_matching_and_excludes_unprocessed_courses():
    references = [ref(), ref(row=3, course="654321", user="00008"), ref(row=4, course="999999")]
    scores, _, _ = evaluate([prediction(person(user="00008"))], references)
    assert scores["counts"]["reference_rows"] == 1
    assert scores["counts"]["reference_rows_outside_run"] == 2
    assert scores["fields"]["user_id"]["exact_match"]["value"] == 0


def test_missing_extra_and_duplicate_predictions_keep_denominators():
    predictions = [prediction(person()), prediction(person(), index=1), prediction(person(first="Chris", user="999"), index=2)]
    references = [ref(), ref(row=3, first="Ben", user="00008")]
    scores, rows, _ = evaluate(predictions, references)
    assert scores["participant_assignment"]["tp"] == 1
    assert scores["participant_assignment"]["fp"] == 2
    assert scores["participant_assignment"]["fn"] == 1
    assert scores["fields"]["first_name"]["exact_match"]["value"] == 0.5
    assert any(row["status"] == "duplicate_prediction" for row in rows)


def test_unknown_prediction_id_is_an_error_unless_masking_or_illegibility_is_explicit():
    scores, _, _ = evaluate([prediction(person(user=None, user_state="uncertain"))], [ref()])
    assert scores["fields"]["user_id"]["exact_match"]["value"] == 0
    assert scores["fields"]["user_id"]["excluded"] == 0


def test_duplicate_reference_people_are_not_silently_merged():
    scores, rows, _ = evaluate([prediction(person())], [ref(row=2), ref(row=3)])
    assert scores["participant_assignment"]["tp"] == 0
    assert scores["participant_assignment"]["fn"] == 2
    assert any(row["status"] == "ambiguous" for row in rows)


def test_invalid_workbook_and_regex_have_clear_errors(tmp_path):
    path = tmp_path / "reference.xlsx"
    path.write_bytes(b"not a workbook")
    with pytest.raises(ValueError, match="beschädigt"):
        read_reference(path, ExcelConfig())
    with pytest.raises(ValueError, match="Maskierungs-Muster"):
        ExcelConfig(masked_user_id_pattern="[")


def test_explicit_mapping_supports_non_numeric_filenames_and_detects_conflicts(tmp_path):
    manifest = {"inputs": [{"kind": "pdf", "sha256": "doc", "path": "sample.pdf"}]}
    mapping, rows = course_mapping(manifest, None)
    assert not mapping and rows[0]["status"] == "review_required"
    path = tmp_path / "mapping.csv"
    path.write_text("document_id,class_id\ndoc,001234\n", encoding="utf-8")
    assert course_mapping(manifest, path)[0] == {"doc": "001234"}


def test_existing_run_excel_cli_and_offline_reports(tmp_path, monkeypatch):
    import socket

    def no_network(*args, **kwargs):
        raise AssertionError("Excel comparison attempted network access")

    monkeypatch.setattr(socket, "create_connection", no_network)
    run = tmp_path / "run"
    run.mkdir()
    page = PageResult(run_id="r", document_id="doc", page_id="doc-p0001", page_number=1,
                      method_id="vlm", status="success", parse_status="valid", participants=[person()])
    write_jsonl(run / "vlm" / "extractions.jsonl", [page.model_dump()])
    write_json(run / "manifest.json", {"inputs": [{"kind": "pdf", "sha256": "doc", "path": "123456.pdf"}]})
    write_json(run / "summary.json", {"vlm": {"status": "success"}, "ocr_llm": {"status": "failed"}})
    excel = tmp_path / "reference.xlsx"
    workbook(excel, [["123456", "00007", "Anna", "Weber", "ABC"],
                     ["999999", "00008", "Unprocessed", "Other", "XYZ"]])
    original = {p: file_hash(p) for p in run.rglob("*") if p.is_file()}
    output, metrics = compare_run(run, excel, ExcelConfig(), output=tmp_path / "comparison")
    assert metrics["vlm"]["participant_assignment"]["f1"]["value"] == 1
    assert metrics["ocr_llm"]["participant_assignment"]["fn"] == 1
    assert metrics["ocr_llm"]["extraction_status"] == "failed"
    assert original == {p: file_hash(p) for p in original}
    assert read_json(output / "metrics.json")["methods"]["vlm"]["counts"]["reference_rows_outside_run"] == 1
    with (output / "field_comparison.csv").open(encoding="utf-8-sig", newline="") as stream:
        assert len(list(csv.DictReader(stream))) == 8
    assert "Content-Security-Policy" in (output / "report.html").read_text(encoding="utf-8")
    with pytest.raises(ValueError, match="leer"):
        compare_run(run, excel, ExcelConfig(), output=output)
    result = subprocess.run([
        sys.executable, "-m", "participant_bench.cli", "compare-excel", "--run", str(run),
        "--excel", str(excel), "--method", "vlm", "--output", str(tmp_path / "cli-output"),
    ], capture_output=True)
    assert result.returncode == 0, result.stderr
    saved = json.loads((tmp_path / "cli-output" / "metrics.json").read_text(encoding="utf-8"))
    assert set(saved["methods"]) == {"vlm"}
