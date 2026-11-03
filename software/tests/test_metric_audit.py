"""Manually calculable information counts, reference exclusions and audited fallback."""

import csv
from copy import deepcopy
from dataclasses import replace

import pytest
from openpyxl import load_workbook
from test_roster_benchmark import page, person, prediction, ref, saved_run, write_reference
from test_structure_diagnostics import native_table

from participant_bench.io import file_hash, read_json, write_json
from participant_bench.roster_benchmark.config import BenchmarkConfig, MatchingConfig, ReferenceConfig
from participant_bench.roster_benchmark.evaluation import evaluate_run
from participant_bench.roster_benchmark.metrics import course_metrics
from participant_bench.roster_benchmark.references import read_reference
from participant_bench.structured_mapping import extract_structured


def measure(predictions, references, **settings):
    return course_metrics("123456", predictions, references, MatchingConfig(**settings), ReferenceConfig())


@pytest.mark.parametrize("mode", ["best_fit", "conservative"])
def test_control_example_24_of_40_fields_is_60_percent_recall_and_75_percent_f1(mode):
    references = [ref(row=i + 2, user=str(1000 + i), first=f"Name{i}", last=f"Family{i}") for i in range(10)]
    predictions = [
        prediction(index=i, user=str(1000 + i), first=f"Name{i}", last=f"Family{i}") for i in range(6)
    ]
    score, *_ = measure(predictions, references, mode=mode)
    count = score["overall"]
    assert (
        count["reference_fields"],
        count["predicted_fields"],
        count["exact_fields"],
        count["missing_fields"],
    ) == (40, 24, 24, 16)
    assert count["exact_precision"] == 1 and count["exact_recall"] == 0.6
    assert count["exact_f1"] == count["soft_f1"] == 0.75
    assert count["field_coverage"] == 0.6 and score["missing_participants"] == 4


@pytest.mark.parametrize("value", [None, "", "***", "unknown", "-"])
def test_model_placeholders_never_remove_a_readable_reference_from_denominator(value):
    score, _, fields, _ = measure([prediction(user=value)], [ref()], mode="best_fit")
    count = score["fields"]["user_id"]
    assert count["reference_fields"] == count["missing_fields"] == 1
    assert count["excluded_reference_fields"] == count["similarity_credit"] == 0
    assert count["fn"] == 1 and count["exact_fields"] == 0
    assert next(row for row in fields if row["field"] == "user_id")["assessable"]


def test_known_empty_is_separate_and_hallucination_is_an_extra_prediction():
    reference = replace(ref(code=""), field_states={"short_code": "empty"})
    score, *_ = measure([prediction(code="")], [reference])
    assert score["overall"]["reference_fields"] == score["overall"]["exact_fields"] == 3
    assert score["overall"]["correct_empty_fields"] == 1
    score, *_ = measure([prediction(code="invented")], [reference])
    assert score["overall"]["reference_fields"] == 3 and score["overall"]["predicted_fields"] == 4
    assert score["overall"]["hallucinated_empty_fields"] == score["overall"]["extra_fields"] == 1
    assert score["overall"]["exact_f1"] == pytest.approx(6 / 7)


def test_unannotated_blank_and_explicit_unknown_are_not_assumed_empty():
    for reference in [ref(code=""), replace(ref(), field_states={"short_code": "unknown"})]:
        score, *_ = measure([prediction(code="anything")], [reference])
        assert score["overall"]["reference_fields"] == 3
        assert score["overall"]["reference_empty_fields"] == 0
        assert score["overall"]["excluded_reference_fields"] == 1


def test_reference_status_columns_are_optional_and_saved_without_changing_values(tmp_path):
    source = tmp_path / "reference.csv"
    write_reference(
        source,
        rows=[["123456", "001234", "Anna", "Weber", "", "empty"]],
        columns=["Class ID", "User ID", "First Name", "Last Name", "Organization", "short_code__state"],
    )
    data = read_reference(source, ReferenceConfig())
    assert data.people[0].short_code == "" and data.people[0].field_states == {"short_code": "empty"}


@pytest.mark.parametrize("mode", ["best_fit", "conservative"])
def test_whole_name_groups_are_compared_both_ways_without_modifying_source(mode):
    p = prediction(first="Muster Schmidt", last="Anna Maria", user=None)
    before = p.person.model_dump()
    score, rows, fields, _ = measure(
        [p],
        [ref(first="Anna Maria", last="Muster Schmidt", user="")],
        mode=mode,
        compare_name_orientations=True,
    )
    assert score["score_percent"] == 100 and score["name_swapped_participants"] == 1
    assert rows[0]["name_swapped"] and p.person.model_dump() == before
    first = next(row for row in fields if row["field"] == "first_name")
    assert (
        first["prediction_value"] == "Anna Maria" and first["original_prediction_value"] == "Muster Schmidt"
    )


def test_name_orientation_tie_preserves_original_roles():
    score, rows, *_ = measure(
        [prediction(first="Alex", last="Alex")],
        [ref(first="Alex", last="Alex")],
        compare_name_orientations=True,
    )
    assert score["name_swapped_participants"] == 0 and not rows[0]["name_swapped"]


def test_failed_page_stays_in_end_to_end_and_excel_csv_json_html_reconcile(tmp_path):
    source = tmp_path / "source"
    good = page([person()])
    failed = page([], document="second")
    failed.status, failed.parse_status = "failed", "invalid"
    inputs = [
        dict(kind="pdf", sha256="document", path="123456.pdf"),
        dict(kind="pdf", sha256="second", path="456789.pdf"),
    ]
    saved_run(source, [good, failed], inputs=inputs)
    reference = tmp_path / "reference.csv"
    write_reference(
        reference,
        rows=[["123456", "001234", "Anna", "Weber", "MUC"], ["456789", "009999", "Ben", "Kurz", "ABC"]],
    )
    original = file_hash(source / "vlm/extractions.jsonl")
    output, metrics = evaluate_run(source, reference, BenchmarkConfig(), tmp_path / "out")
    score = metrics["vlm"]
    assert score["overall"]["reference_fields"] == 8 and score["overall"]["missing_fields"] == 4
    assert score["technical"]["page_success_rate"] == 0.5
    assert score["conditional_successful_courses"]["overall"]["reference_fields"] == 4
    assert score["conditional_successful_courses"]["score_percent"] == 100
    with (output / "field_scores.csv").open(encoding="utf-8-sig", newline="") as stream:
        counts = list(csv.DictReader(stream))
    assert sum(int(r["missing_fields"]) for r in counts) == 4
    book = load_workbook(output / "participants.xlsx", read_only=True)
    try:
        headers, *rows = list(book["Metriken"].values)
        assert dict(zip(headers, rows[0]))["missing_fields"] == 4
    finally:
        book.close()
    text = (output / "report.html").read_text(encoding="utf8")
    assert "Fehlende Felder" in text and "Exakter Feld-Recall" in text
    assert "Exakt Originalschreibweise" not in text
    details = "".join(p.read_text(encoding="utf8") for p in (output / "details").glob("*.html"))
    assert "Fehlend" in details and "<th>Ausgabe normalisiert</th>" not in details
    assert read_json(output / "details/calculation_checks.json")["vlm"]["contributions_match_saved_metrics"]
    assert file_hash(source / "vlm/extractions.jsonl") == original


def test_docling_missing_headers_recovers_only_repeated_identity_evidence_as_uncertain():
    source = native_table(["", "", ""], [["000007", "Muster, Anna", "ABC"], ["000008", "Kurz, Ben", ""]])
    original = deepcopy(source["tables"])
    people, proofs, notes, _ = extract_structured(source)
    assert len(people) == 2
    assert people[0].first_name.value == "Anna" and people[0].first_name.state == "uncertain"
    assert people[1].personnel_number.value == "000008" and people[1].department.value is None
    assert proofs[0]["fallback"] and "Unverified" in " ".join(notes)
    assert source["tables"] == original


def test_docling_does_not_invent_people_from_isolated_metadata_or_unrelated_text():
    source = native_table(["", ""], [["123456", "Trainer, Example"], ["", "Notes"]])
    assert not extract_structured(source)[0]


def test_docling_missing_native_cell_does_not_shift_a_neighbor_into_it():
    source = native_table(
        ["First Name", "Last Name", "User ID", "Organization"], [["Anna", "Muster", "", "ABC"]]
    )
    source["tables"][0]["native"]["data"]["table_cells"].pop(6)
    people, *_ = extract_structured(source)
    assert len(people) == 1 and people[0].personnel_number.value is None
    assert people[0].department.value == "ABC"


@pytest.mark.parametrize("tamper", [False, True])
def test_audit_rejects_different_or_modified_run_images_before_writing_output(tmp_path, tamper):
    import importlib.util
    from pathlib import Path

    spec = importlib.util.spec_from_file_location("audit_metrics_docling", Path("scripts/audit_metrics_docling.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    source, repaired, old = (tmp_path / name for name in ("source", "repaired", "old"))
    for root in (source, repaired):
        (root / "pages").mkdir(parents=True)
        (root / "pages/doc-p0001.png").write_bytes(b"fixed pixels")
        write_json(root / "effective_pages.json", [dict(document_id="doc", page_number=1, page_id="doc-p0001",
            include=True, run_image_sha256=file_hash(root / "pages/doc-p0001.png"))])
    write_json(old / "identity.json", dict(source_run=str(source)))
    if tamper:
        (repaired / "pages/doc-p0001.png").write_bytes(b"changed pixels")
    else:
        write_json(repaired / "effective_pages.json", [dict(document_id="doc", page_number=1,
            page_id="doc-p0001", include=True, run_image_sha256="different")])
    with pytest.raises(ValueError, match="Laufbild"):
        module.audit(old, repaired, tmp_path / "output")
    assert not (tmp_path / "output").exists()
