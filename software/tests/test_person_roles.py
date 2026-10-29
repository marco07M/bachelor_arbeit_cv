"""Only explicit course staff are excluded; doubles verify routing, not recognition accuracy."""

import csv
import json
from pathlib import Path

import pymupdf
import pytest
from test_ocr_fixes import model_response, ocr_data, word

from participant_bench import runner
from participant_bench.config import load_config
from participant_bench.excel_reference import ReferencePerson
from participant_bench.io import file_hash, read_json, read_jsonl
from participant_bench.models import parse_ocr_response
from participant_bench.person_roles import filter_page_people
from participant_bench.roster_benchmark.config import BenchmarkConfig, MatchingConfig, ReferenceConfig
from participant_bench.roster_benchmark.evaluation import evaluate_run
from participant_bench.roster_benchmark.matching import Prediction
from participant_bench.roster_benchmark.metrics import course_metrics
from participant_bench.schema import Box, PageResult, VisualParticipant
from participant_bench.unlimited_assignment import AssignmentResponse, ground_response, source_rows
from participant_bench.vlm_cells import parse_visual_response


def person(first="Anna", last="Weber", role="participant", evidence=None):
    return VisualParticipant(first_name=first, last_name=last, personnel_number="", department="MUC",
                             person_role=role, role_evidence=evidence).participant()


def page(people, method="vlm"):
    return PageResult(run_id="synthetic", document_id="doc", page_id="doc-p0001", page_number=1,
                      method_id=method, status="success", parse_status="valid", participants=people)


@pytest.mark.parametrize("label", ["Kursleiter", "Kursleiterin", "Kursleitung", "Trainer", "Dozent", "Instructor"])
def test_visual_instructor_is_separate_and_attendee_without_user_id_stays(label):
    result = page([person(), person("Max", "Muster", "instructor", label)])
    raw = {}
    filter_page_people(result, raw)
    assert [p.first_name.value for p in result.participants] == ["Anna"]
    assert result.participants[0].personnel_number.state == "empty"
    assert len(result.excluded_instructors) == 1 and result.excluded_instructors[0].role_evidence == label
    assert raw["person_role_filter"]["excluded"][0]["source_output_index"] == 1
    filter_page_people(result, raw)
    assert len(result.excluded_instructors) == len(raw["person_role_filter"]["excluded"]) == 1


@pytest.mark.parametrize("label", [None, "wahrscheinlich der erste Eintrag", "nicht Kursleiter", "Trainer"])
def test_no_exclusion_without_a_role_label_and_surname_trainer_is_preserved(label):
    result = page([person("Anna", "Trainer", "instructor", label)])
    filter_page_people(result, {})
    assert len(result.participants) == 1 and not result.excluded_instructors
    assert result.participants[0].person_role == "unknown" and result.status == "partial"
    assert result.participants[0].review_notes


@pytest.mark.parametrize("partial", [False, True])
def test_ocr_role_has_to_be_grounded_in_own_line_and_is_preserved_by_parser(partial):
    data = ocr_data()
    data["words"].append(word("Kursleiter:", 0.8, 0.3))
    payload = json.loads(model_response())
    payload["participants"][0].update(person_role="instructor", role_evidence="Kursleiter")
    people = parse_ocr_response(json.dumps(payload), data, preserve_partial_fields=partial)
    assert people[0].person_role == "instructor"
    result = page(people, "ocr_llm")
    filter_page_people(result, {"ocr": data})
    assert not result.participants and len(result.excluded_instructors) == 1


def test_same_name_in_another_ocr_line_does_not_remove_attendee():
    data = ocr_data()
    data["words"].extend([word("Kursleiter:", 0.01, 0.8, 2), word("Anna", 0.2, 0.8, 2),
                          word("Weber", 0.4, 0.8, 2)])
    payload = json.loads(model_response())
    payload["participants"][0].update(person_role="instructor", role_evidence="Kursleiter")
    result = page(parse_ocr_response(json.dumps(payload), data), "ocr_llm")
    filter_page_people(result, {"ocr": data})
    assert len(result.participants) == 1 and not result.excluded_instructors
    assert result.participants[0].person_role == "unknown"


@pytest.mark.parametrize("mode", ["best_fit", "conservative"])
def test_unconfirmed_instructor_role_remains_review_required_even_with_exact_excel_match(mode):
    result = page([person(role="instructor")])
    filter_page_people(result, {})
    reference = ReferencePerson(2, "123456", "", "Anna", "Weber", "MUC")
    metrics, rows, fields, _ = course_metrics("123456", [Prediction("doc", 1, 0, result.participants[0])],
                                            [reference], MatchingConfig(mode=mode), ReferenceConfig())
    assert metrics["score_percent"] == 100 and metrics["review_rows"] == 1
    assert rows[0]["review_required"] and "role_unconfirmed" in rows[0]["matching_review_reasons"]
    assert all(field["review_required"] for field in fields)


def test_visual_physical_cells_retain_role_before_filtering():
    payload = dict(identity_headers=["Name", "Kurzzeichen"], page_text=None, participants=[dict(
        first_name="Max", last_name="Muster", identity_cells=["Muster, Max", "MUC"],
        person_role="instructor", role_evidence="Kursleiter")])
    people, _, _, _ = parse_visual_response(json.dumps(payload))
    result = page(people)
    filter_page_people(result, {})
    assert not result.participants and result.excluded_instructors[0].last_name.value == "Muster"


@pytest.mark.parametrize("method", ["unlimited_ocr", "paddle_structure", "docling"])
def test_literal_cell_role_requires_own_source_row(method):
    text = "<table><tr><td>Vorname</td><td>Nachname</td><td>Rolle</td></tr>" + (
        "<tr><td>Anna</td><td>Weber</td><td>Teilnehmer</td></tr>"
        "<tr><td>Max</td><td>Muster</td><td>Trainer</td></tr></table>")
    rows, _ = source_rows(text)
    response = AssignmentResponse.model_validate_json(json.dumps(dict(participants=[dict(
        source_row=f"t0r{index}", first_name=[0, first], last_name=[1, last],
        personnel_number=[None, None], department=[None, None], person_role=role, role_evidence=evidence)
        for index, first, last, role, evidence in [(1, "Anna", "Weber", "participant", None),
                                                  (2, "Max", "Muster", "instructor", "Trainer")]])))
    people, proofs, _ = ground_response(response, rows)
    result = page(people, method)
    filter_page_people(result, {"unlimited_ocr" if method == "unlimited_ocr" else "structure": dict(row_evidence=proofs)})
    assert len(result.participants) == len(result.excluded_instructors) == 1
    assert result.participants[0].first_name.value == "Anna"


def test_legacy_rules_can_exclude_a_labelled_row_without_model_role_metadata():
    result = page([person(role="unknown")], "ocr_rules")
    result.participants[0].bbox = Box(x0=0.1, y0=0.3, x1=0.8, y1=0.32)
    data = ocr_data()
    data["words"].append(word("Dozent", 0.8, 0.3))
    filter_page_people(result, {"ocr": data})
    assert not result.participants and result.excluded_instructors[0].person_role == "instructor"


def test_pipeline_filters_before_signatures_export_and_excel_matching(tmp_path, monkeypatch):
    inputs = tmp_path / "pdfs"
    inputs.mkdir()
    pdf = inputs / "123456.pdf"
    with pymupdf.open() as document:
        document.new_page().insert_text((30, 70), "Anna Weber - Teilnehmer; Max Muster - Kursleiter")
        document.save(pdf)
    original_hash = file_hash(pdf)
    calls = []

    class Model:
        def __init__(self, *args, **kwargs):
            pass

        def extract(self, *args):
            return [person(), person("Max", "Muster", "instructor", "Kursleiter")], [dict(parse_status="valid")], "success", 0.0

        def resources(self):
            return {}

        def close(self):
            pass

    def signatures(result, *args):
        calls.append([p.first_name.value for p in result.participants])

    config = load_config(Path("configs/vlm-smoke.yaml"))
    config.pdf.auto_orient = False
    config.signature.backend, config.signature.use_ocr_positions = "local_vlm", False
    config.output_dir, config.cache_dir = str(tmp_path / "runs"), str(tmp_path / "cache")
    monkeypatch.setattr(runner, "LocalModel", Model)
    monkeypatch.setattr(runner, "signature_details", signatures)
    monkeypatch.setattr(runner, "environment", lambda *args: {})
    output, _ = runner.run(config, inputs, offline=True)
    assert calls == [["Anna"]]
    saved = read_jsonl(output / "vlm/extractions.jsonl")[0]
    assert len(saved["participants"]) == len(saved["excluded_instructors"]) == 1
    assert read_json(output / "vlm" / f"raw-{saved['page_id']}.json")["person_role_filter"]["excluded_instructors"] == 1
    with (output / "extractions.csv").open(encoding="utf-8-sig", newline="") as stream:
        extracted = list(csv.DictReader(stream))
    with (output / "excluded_instructors.csv").open(encoding="utf-8-sig", newline="") as stream:
        excluded = list(csv.DictReader(stream))
    assert [p["first_name"] for p in extracted] == ["Anna"]
    assert [p["first_name"] for p in excluded] == ["Max"]
    assert "1 Kursleiter-/Trainereinträge ausgeschlossen" in (output / "report.html").read_text(encoding="utf-8")
    reference = tmp_path / "reference.csv"
    reference.write_text("Class ID;First Name;Last Name;Organization\n123456;Anna;Weber;MUC\n", encoding="utf-8")
    _, metrics = evaluate_run(output, reference, BenchmarkConfig(), tmp_path / "benchmarks")
    assert metrics["vlm"]["score_percent"] == 100 and metrics["vlm"]["predicted_participants"] == 1
    assert metrics["vlm"]["excluded_instructors"] == 1
    assert file_hash(pdf) == original_hash
