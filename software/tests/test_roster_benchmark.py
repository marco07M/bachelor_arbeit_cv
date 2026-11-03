"""Independent test framework: course scope, real edit distances, global assignment and honest denominators."""

import csv
import itertools
import json
import subprocess
import sys

import numpy as np
import pymupdf
import pytest
from openpyxl import Workbook

from participant_bench.excel_reference import ReferencePerson
from participant_bench.io import file_hash, read_json, write_json, write_jsonl
from participant_bench.roster_benchmark.config import BenchmarkConfig, MatchingConfig, ReferenceConfig
from participant_bench.roster_benchmark.evaluation import evaluate_run, identify_course
from participant_bench.roster_benchmark.matching import Prediction, normalize, similarity, solve
from participant_bench.roster_benchmark.metrics import course_metrics
from participant_bench.roster_benchmark.references import read_reference
from participant_bench.roster_benchmark.runner import run_benchmark
from participant_bench.schema import PageResult, VisualParticipant


def ref(row=2, course="123456", user="001234", first="Anna", last="Weber", code="MUC"):
    return ReferencePerson(row, course, user, first, last, code)


def person(user="001234", first="Anna", last="Weber", code="MUC"):
    return VisualParticipant(first_name=first, last_name=last, personnel_number=user,
                             department=code, signature_present=None).participant()


def prediction(index=0, **kwargs):
    return Prediction("document", 1, index, person(**kwargs))


def compare(predictions, references):
    return course_metrics("123456", predictions, references, MatchingConfig(), ReferenceConfig())


def write_reference(path, rows=None, delimiter=";", columns=None):
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.writer(stream, delimiter=delimiter)
        writer.writerow(columns or ["Class ID", "User ID", "First Name", "Last Name", "Organization"])
        writer.writerows(rows or [["123456", "001234", "Anna", "Weber", "MUC"]])


def saved_run(root, pages, inputs=None, summary=None):
    write_json(root / "summary.json", summary or {"vlm": {"status": "partial", "output_kind": "structured"}})
    write_json(root / "manifest.json", {"inputs": inputs or [dict(kind="pdf", sha256="document", path="123456.pdf")]})
    write_jsonl(root / "vlm/extractions.jsonl", [page.model_dump() for page in pages])
    return root


def page(people, document="document", number=1):
    return PageResult(run_id="synthetic", document_id=document, page_id=f"{document}-p{number:04d}",
                      page_number=number, method_id="vlm", status="partial", parse_status="valid", participants=people)


def test_true_levenshtein_and_explicit_normalization():
    assert similarity("kitten", "sitting") == pytest.approx(4 / 7)
    assert similarity("", "") == 1 and similarity("", "text") == 0
    config = MatchingConfig()
    assert normalize(" A\u0308nne  Test ", "first_name", config) == "änne test"
    assert normalize(" 001234 ", "user_id", config) == "001234"
    assert similarity(normalize("Groß", "last_name", config), normalize("Gross", "last_name", config)) < 1


def test_near_correct_word_earns_fractional_credit_without_exact_hit():
    result, _, fields, _ = compare([prediction(first="Anma")], [ref()])
    assert result["score_percent"] == pytest.approx(93.75)
    assert result["overall"]["exact_reference_accuracy"] == 0.75
    first = next(row for row in fields if row["field"] == "first_name")
    assert first["levenshtein_distance"] == 1 and first["similarity"] == 0.75


def test_all_permutations_preserve_assignment_and_scores():
    references = [ref(), ref(row=3, user="000007", first="Ben", last="Meyer"),
                  ref(row=4, user="000008", first="Lea", last="Schmidt")]
    predictions = [prediction(), prediction(user="000007", first="Ben", last="Meyer"),
                   prediction(user="000008", first="Lea", last="Schmidt")]
    for permuted in itertools.permutations(predictions):
        score, rows, *_ = compare(list(permuted), references)
        assert score["score_percent"] == 100 and score["fully_exact_participants"] == 3
        assert len({row["reference_row"] for row in rows if row["status"] == "matched"}) == 3


def test_global_matching_outperforms_greedy_local_choice():
    matrix = np.array([[0.90, 0.85, 0, 0], [0.89, -1e6, 0, 0]])
    pairs, utility = solve(matrix, 2)
    assert set(pairs) == {(0, 1), (1, 0)} and utility == pytest.approx(1.74)


def test_duplicate_predictions_never_reuse_a_reference_for_full_credit():
    result, rows, *_ = compare([prediction(), prediction(index=1)], [ref()])
    assert result["assigned_participants"] == 1 and result["extra_participants"] == 1
    assert result["duplicate_predictions"] == 1
    assert result["overall"]["exact_fields"] == 4
    assert result["score_percent"] == pytest.approx(100 * 2 / 3)
    assert {row["status"] for row in rows} == {"matched", "duplicate_prediction"}


def test_normalized_duplicates_have_order_independent_raw_exact_score():
    for people in ([prediction(first="anna"), prediction(first="Anna")],
                   [prediction(first="Anna"), prediction(first="anna")]):
        result, *_ = compare(people, [ref()])
        assert result["overall"]["raw_exact_reference_accuracy"] == 1
        assert result["extra_participants"] == 1


def test_missing_people_and_missing_fields_remain_in_denominator():
    score, *_ = compare([], [ref()])
    assert score["score_percent"] == 0 and score["overall"]["reference_fields"] == 4
    assert score["missing_participants"] == 1
    score, *_ = compare([prediction(user=None)], [ref()])
    assert score["fields"]["user_id"]["reference_fields"] == 1
    assert score["fields"]["user_id"]["exact_fields"] == 0
    assert score["score_percent"] == pytest.approx(100 * 6 / 7)


@pytest.mark.parametrize("user", ["", "***", "XXXXX", "███"])
def test_reference_id_masking_uses_names_and_short_code(user):
    score, rows, *_ = compare([prediction(user=None, first="Anma")], [ref(user=user)])
    assert score["assigned_participants"] == 1
    assert score["fields"]["user_id"]["reference_fields"] == 0
    assert score["score_percent"] == pytest.approx(100 * 2.75 / 3)
    assert rows[0]["matching_source"] == "name_short_code_levenshtein"


def test_explicitly_masked_prediction_remains_an_error_and_is_reported():
    score, *_ = compare([prediction(user="***")], [ref()])
    assert score["overall"]["excluded_masked_predictions"] == 0
    assert score["overall"]["invalid_prediction_fields"] == 1
    assert score["overall"]["reference_fields"] == 4 and score["score_percent"] == 75
    assert score["review_rows"] == 1


def test_historical_configuration_keeps_original_zero_rule():
    result, *_ = compare([prediction(user="1234")], [ref(user="001234")])
    assert result["fields"]["user_id"]["exact_fields"] == 0
    assert result["fields"]["user_id"]["soft_f1"] == pytest.approx(2 / 3)


def test_ambiguous_names_are_not_arbitrarily_awarded_points():
    result, rows, _, candidates = compare([prediction(user=None)], [ref(), ref(row=3, user="000007")])
    assert result["score_percent"] == 0
    assert result["ambiguous_participants"] == 1 and result["missing_participants"] == 2
    assert len(candidates) == 2 and any(row["status"] == "ambiguous" for row in rows)


def test_conflicting_exact_identity_keys_require_review():
    references = [ref(), ref(row=3, user="000007", first="Ben", last="Meyer")]
    result, *_ = compare([prediction(user="000007")], references)
    assert result["identity_conflicts"] == 1 and result["assigned_participants"] == 0
    assert result["score_percent"] == 0


def test_reference_course_boundary_cannot_be_bypassed():
    with pytest.raises(ValueError, match="verschiedener Schulungen"):
        compare([prediction()], [ref(course="654321")])


def test_uncertain_literal_values_can_be_scored_without_being_accepted():
    predicted = prediction()
    predicted.person.first_name.state = "uncertain"
    score, rows, *_ = compare([predicted], [ref()])
    assert score["score_percent"] == 100 and rows[0]["review_required"]
    score, *_ = course_metrics("123456", [predicted], [ref()],
                              MatchingConfig(score_uncertain_values=False), ReferenceConfig())
    assert score["overall"]["exact_fields"] == 3


@pytest.mark.parametrize("delimiter", [",", ";", "\t"])
def test_csv_accepts_excel_delimiters_bom_and_string_ids(tmp_path, delimiter):
    path = tmp_path / "roster.csv"
    write_reference(path, [["001234", "000007", "Jörg", "Groß-Müller", "MUC", "unused"]], delimiter,
                    ["Class ID", "User ID", "First Name", "Last Name", "Organization", "Ignored"])
    before = file_hash(path)
    data = read_reference(path, ReferenceConfig())
    assert data.people == [ref(course="001234", user="000007", first="Jörg", last="Groß-Müller")]
    assert file_hash(path) == before


def test_csv_without_user_id_and_duplicate_reference_policy(tmp_path):
    path = tmp_path / "roster.csv"
    write_reference(path, [["123456", "Anna", "Weber", "MUC"]] * 2,
                    columns=["Class ID", "First Name", "Last Name", "Organization"])
    with pytest.raises(ValueError, match="Identische Referenzzeilen"):
        read_reference(path, ReferenceConfig())
    data = read_reference(path, ReferenceConfig(merge_identical_duplicates=True))
    assert len(data.people) == 1 and data.people[0].user_id == ""
    assert not data.user_id_column_present and data.duplicate_rows[0]["source_rows"] == [2, 3]


def test_all_masked_identity_without_names_is_rejected(tmp_path):
    path = tmp_path / "reference.csv"
    write_reference(path, [["123456", "***", "", "", "MUC"]])
    with pytest.raises(ValueError, match="Keine lesbare Teilnehmeridentität"):
        read_reference(path, ReferenceConfig())


def test_xlsx_identifier_formats_and_formula_rejection(tmp_path):
    path = tmp_path / "reference.xlsx"
    book = Workbook()
    sheet = book.active
    sheet.append(["Class ID", "User ID", "First Name", "Last Name", "Organization"])
    sheet.append([1234, 7, "Anna", "Weber", "MUC"])
    sheet["A2"].number_format = "000000"
    sheet["B2"].number_format = "000000"
    book.save(path)
    assert read_reference(path, ReferenceConfig()).people == [ref(course="001234", user="000007")]
    sheet["B2"] = "=7"
    book.save(path)
    with pytest.raises(ValueError, match="Formel"):
        read_reference(path, ReferenceConfig())


@pytest.mark.parametrize("name,expected", [
    ("123456.pdf", "123456"), ("123456__2.pdf", "123456"),
    ("12473.123456_12.23.1456_Muc.pdf", "123456"), ("COURSE-A.pdf", "COURSE-A")])
def test_pdf_filename_identifies_training_id(name, expected):
    assert identify_course(name, {expected}) == expected


def test_saved_run_groups_all_pages_and_files_but_keeps_courses_separate(tmp_path):
    source = saved_run(tmp_path / "source", [page([person(first="Lea", user="000007", last="Meyer")], "doc2"),
                      page([person()], "document", 2), page([person(first="Ben", user="000008", last="Schmidt")])],
                       inputs=[dict(kind="pdf", sha256="document", path="123456.pdf"),
                               dict(kind="pdf", sha256="doc2", path="654321.pdf")])
    reference = tmp_path / "reference.csv"
    write_reference(reference, [["123456", "000008", "Ben", "Schmidt", "MUC"],
                               ["654321", "000007", "Lea", "Meyer", "MUC"],
                               ["123456", "001234", "Anna", "Weber", "MUC"],
                               ["999999", "999999", "Not", "Processed", "BER"]])
    originals = {path: file_hash(path) for path in source.rglob("*") if path.is_file()}
    originals[reference] = file_hash(reference)
    output, metrics = evaluate_run(source, reference, BenchmarkConfig(), tmp_path / "results")
    assert metrics["vlm"]["score_percent"] == 100
    assert metrics["vlm"]["reference_participants"] == 3
    assert read_json(output / "metrics.json")["scope"]["reference_rows_outside_input"] == 1
    assert all(file_hash(path) == expected for path, expected in originals.items())
    assert (output / "fields.csv").is_file() and (output / "matching_candidates.csv").is_file()
    assert "Content-Security-Policy" in (output / "report.html").read_text(encoding="utf-8")
    with pytest.raises(FileExistsError):
        evaluate_run(source, reference, BenchmarkConfig(), tmp_path, output=output)


@pytest.mark.parametrize("mode", ["conservative", "best_fit"])
def test_same_person_in_other_course_is_not_used_as_a_reference(tmp_path, mode):
    source = saved_run(tmp_path / "source", [page([person(first="Boris", last="Xylophon", user="999999", code="XYZ")])])
    reference = tmp_path / "reference.csv"
    write_reference(reference, [["123456", "001234", "Anna", "Weber", "MUC"],
                               ["654321", "999999", "Boris", "Xylophon", "XYZ"]])
    config = BenchmarkConfig(matching=MatchingConfig(mode=mode))
    _, metrics = evaluate_run(source, reference, config, tmp_path / "results")
    assert metrics["vlm"]["score_percent"] == 0
    assert metrics["vlm"]["reference_participants"] == 1


@pytest.mark.parametrize("mode", ["conservative", "best_fit"])
@pytest.mark.parametrize("extension", ["csv", "xlsx"])
def test_exact_names_and_ids_in_another_active_course_never_become_candidates(tmp_path, mode, extension):
    source = saved_run(tmp_path / "source", [
        page([person(first="Anna", user="009999")], "course-a"),
        page([person(first="Anma", user="000007")], "course-b")],
        inputs=[dict(kind="pdf", sha256="course-a", path="001234.pdf"),
                dict(kind="pdf", sha256="course-b", path="654321.pdf")])
    rows = [["654321", "009999", "Anna", "Weber", "MUC"],
            ["001234", "000007", "Anma", "Weber", "MUC"],
            ["999999", "", "OUTSIDE_NO_PDF", "Excluded", "BER"]]
    reference = tmp_path / f"reference.{extension}"
    if extension == "xlsx":
        book = Workbook()
        book.active.append(["Class ID", "User ID", "First Name", "Last Name", "Organization"])
        for row in rows:
            book.active.append(row)
        book.save(reference)
        book.close()
    else:
        write_reference(reference, rows)
    config = BenchmarkConfig(matching=MatchingConfig(mode=mode))
    output, metrics = evaluate_run(source, reference, config, tmp_path / "results")
    score = metrics["vlm"]
    assert score["assigned_participants"] == 2 and score["score_percent"] < 100
    scope = read_json(output / "metrics.json")["scope"]
    assert scope["reference_rows_in_scope"] == 2 and scope["reference_rows_outside_input"] == 1
    reference_classes = {str(index): row[0] for index, row in enumerate(rows, 2)}
    document_classes = {"course-a": "001234", "course-b": "654321"}
    for filename in ("participants.csv", "fields.csv", "matching_candidates.csv"):
        with (output / filename).open(encoding="utf-8-sig", newline="") as stream:
            saved = list(csv.DictReader(stream))
        assert saved
        assert all(row["class_id"] == document_classes[row["document_id"]] == reference_classes[row["reference_row"]]
                   for row in saved)
    names = (output / "zuordnungen.html").read_text(encoding="utf-8")
    assert "Kandidatenfilter: Class ID = 001234" in names
    assert "Kandidatenfilter: Class ID = 654321" in names
    assert "OUTSIDE_NO_PDF" not in names
    assert names.count("Alle 1 Referenzkandidaten dieser Schulung") == 2
    for details in (output / "details").glob("*.html"):
        text = details.read_text(encoding="utf-8")
        assert "Alle 1 Referenzkandidaten dieser Schulung" in text
        assert "Einträge anderer Klassen sind vor dem Vergleich ausgeschlossen" in text


@pytest.mark.parametrize("mode", ["conservative", "best_fit"])
def test_pdf_without_reference_class_is_unassessed_even_when_name_and_id_match(tmp_path, mode):
    source = saved_run(tmp_path / "source", [page([person()]), page([person()], "no-reference")],
                       inputs=[dict(kind="pdf", sha256="document", path="123456.pdf"),
                               dict(kind="pdf", sha256="no-reference", path="777777.pdf")])
    reference = tmp_path / "reference.csv"
    write_reference(reference)
    config = BenchmarkConfig(matching=MatchingConfig(mode=mode))
    output, metrics = evaluate_run(source, reference, config, tmp_path / "results")
    assert metrics["vlm"]["assigned_participants"] == 1
    assert metrics["vlm"]["predicted_participants"] == 1
    with (output / "unassessed_pages.csv").open(encoding="utf-8-sig", newline="") as stream:
        unassessed = list(csv.DictReader(stream))
    assert len(unassessed) == 1
    assert unassessed[0]["document_id"] == "no-reference"
    assert unassessed[0]["reason"] == "no_reference_course"


def test_same_course_across_different_pdf_files_and_duplicate_pages(tmp_path):
    source = saved_run(tmp_path / "source", [page([person()]), page([person()], number=2),
                      page([person(user="000007", first="Ben", last="Meyer")], "doc2")],
                      inputs=[dict(kind="pdf", sha256="document", path="123456.pdf"),
                              dict(kind="pdf", sha256="doc2", path="123456__2.pdf")])
    reference = tmp_path / "reference.csv"
    write_reference(reference, [["123456", "001234", "Anna", "Weber", "MUC"],
                               ["123456", "000007", "Ben", "Meyer", "MUC"]])
    _, metrics = evaluate_run(source, reference, BenchmarkConfig(), tmp_path / "results")
    assert metrics["vlm"]["reference_participants"] == 2
    assert metrics["vlm"]["assigned_participants"] == 2 and metrics["vlm"]["duplicate_predictions"] == 1
    assert metrics["vlm"]["score_percent"] == 80


def test_identical_pdf_hash_under_two_course_names_requires_review(tmp_path):
    source = saved_run(tmp_path / "source", [page([person()])],
                      inputs=[dict(kind="pdf", sha256="document", path="123456.pdf"),
                              dict(kind="pdf", sha256="document", path="654321.pdf")])
    reference = tmp_path / "reference.csv"
    write_reference(reference, [["123456", "001234", "Anna", "Weber", "MUC"],
                               ["654321", "001234", "Anna", "Weber", "MUC"]])
    output, metrics = evaluate_run(source, reference, BenchmarkConfig(), tmp_path / "results")
    assert metrics["vlm"]["score_percent"] == 0
    assert read_json(output / "metrics.json")["scope"]["ambiguous_documents"] == 1


def test_comparison_is_network_free(tmp_path, monkeypatch):
    import socket

    def forbidden(*args, **kwargs):
        pytest.fail("Roster comparison must remain offline")

    source = saved_run(tmp_path / "source", [page([person()])])
    reference = tmp_path / "reference.csv"
    write_reference(reference)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    _, metrics = evaluate_run(source, reference, BenchmarkConfig(), tmp_path / "results")
    assert metrics["vlm"]["score_percent"] == 100


def test_failed_method_is_not_silently_removed_and_raw_ocr_is_not_field_scored(tmp_path):
    source = saved_run(tmp_path / "source", [], summary={"vlm": {"status": "failed"},
                                                       "ocr_raw": {"status": "success", "output_kind": "ocr_text"}})
    reference = tmp_path / "reference.csv"
    write_reference(reference)
    _, metrics = evaluate_run(source, reference, BenchmarkConfig(), tmp_path / "results")
    assert metrics["vlm"]["score_percent"] == 0 and metrics["vlm"]["missing_participants"] == 1
    assert metrics["vlm"]["extraction_status"] == "failed"
    assert metrics["ocr_raw"]["score_percent"] is None and metrics["ocr_raw"]["status"] == "not_applicable"


@pytest.mark.parametrize("allow_api", [False, True])
def test_framework_reuses_extraction_without_passing_any_reference_values(tmp_path, monkeypatch, allow_api):
    from participant_bench.roster_benchmark import runner

    inputs = tmp_path / "pdfs"
    inputs.mkdir()
    with pymupdf.open() as document:
        document.new_page().insert_text((30, 70), "Synthetic PDF")
        document.save(inputs / "123456.pdf")
    reference = tmp_path / "reference.csv"
    write_reference(reference)
    model_config = tmp_path / "models.yaml"
    model_config.write_text("methods: [ocr_raw]\n", encoding="utf-8")
    source = saved_run(tmp_path / "source", [page([person()])])
    calls = []

    def fake_extract(config, folder, **kwargs):
        calls.append((config, folder, kwargs))
        assert "truth_path" not in kwargs and kwargs == {"resume": None, "offline": not allow_api}
        assert folder == inputs and config.signature.backend == "opencv"
        # The reference is frozen before inference, even if the source is edited during the model run.
        write_reference(reference, [["123456", "001234", "Changed", "Reference", "XYZ"]])
        return source, {}

    monkeypatch.setattr(runner, "extract", fake_extract)
    config = BenchmarkConfig(input_dir="pdfs", reference_file="reference.csv", extraction_config="models.yaml", output_dir="results")
    output, metrics = run_benchmark(config, tmp_path, allow_api=allow_api)
    assert len(calls) == 1 and metrics["vlm"]["score_percent"] == 100
    assert read_json(output / "identity.json")["source_reference_changed"]


def test_local_framework_rejects_an_api_profile_before_inference(tmp_path, monkeypatch):
    from participant_bench.roster_benchmark import runner

    inputs = tmp_path / "pdfs"
    inputs.mkdir()
    with pymupdf.open() as document:
        document.new_page().insert_text((30, 70), "Synthetic PDF")
        document.save(inputs / "123456.pdf")
    write_reference(tmp_path / "reference.csv")
    (tmp_path / "models.yaml").write_text(
        'methods: [vlm]\nmodels:\n  vlm:\n    backend: api\n'
        '    options: {base_url: "http://127.0.0.1:9", model: synthetic}\n', encoding="utf-8")
    monkeypatch.setattr(runner, "extract", lambda *args, **kwargs: pytest.fail("API inference was not authorized"))
    config = BenchmarkConfig(input_dir="pdfs", reference_file="reference.csv", extraction_config="models.yaml")
    with pytest.raises(ValueError, match="offline"):
        runner.run_benchmark(config, tmp_path)


def test_compare_cli_needs_no_models_and_prints_no_person_values(tmp_path):
    source = saved_run(tmp_path / "source", [page([person(first="Anma")])])
    reference = tmp_path / "reference.csv"
    write_reference(reference)
    output = tmp_path / "output"
    result = subprocess.run([sys.executable, "testframework/main.py", "compare", "--run", str(source),
                             "--reference", str(reference), "--output", str(output)],
                            capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, result.stderr
    assert "93.75%" in result.stdout and "Anna" not in result.stdout and "Weber" not in result.stdout
    assert json.loads((output / "metrics.json").read_text(encoding="utf-8"))["methods"]["vlm"]["score_percent"] == 93.75
