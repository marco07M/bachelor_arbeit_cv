"""Model-decided document name order, literal provenance and document boundaries."""

import csv
import json
from pathlib import Path

import pymupdf
import pytest

from participant_bench import runner
from participant_bench.config import load_config
from participant_bench.document_names import REVIEW, DocumentNameOrders
from participant_bench.io import file_hash, read_json, read_jsonl, write_json
from participant_bench.models import LocalModel, generation_schema
from participant_bench.progress import Progress
from participant_bench.schema import (
    Box,
    OCRPageResponse,
    PageResult,
    VisualCellPageResponse,
    VisualParticipant,
)
from participant_bench.unlimited_assignment import AssignmentResponse, ground_response, source_rows
from participant_bench.vlm_cells import parse_visual_response


def visual(first="Weber", last="Anna", cell="Weber, Anna", order="family_given", number=1, document="doc"):
    payload = dict(name_order=dict(order=order, evidence="Gedruckte Reihenfolge Nachname, Vorname"),
                   identity_headers=["Benutzername", "Benutzer", "Kurzzeichen"], page_text=None,
                   participants=[dict(row_ref=str(number), first_name=first, last_name=last,
                                      identity_cells=[cell, "", "MUC"])])
    raw_response = json.dumps(payload)
    people, _, _, _ = parse_visual_response(raw_response)
    page = PageResult(run_id="fixture", document_id=document, page_id=f"{document}-p{number:04d}",
                      page_number=number, method_id="vlm", status="success", parse_status="valid", participants=people)
    return page, dict(responses=[dict(raw_response=raw_response, name_order=payload["name_order"], parse_status="valid")])


def test_one_document_convention_handles_both_swapped_and_already_correct_rows():
    resolver = DocumentNameOrders()
    first, raw = visual()
    resolver.apply(first, raw)
    assert first.participants[0].first_name.value == "Anna" and first.participants[0].last_name.value == "Weber"
    second, other_raw = visual(first="Ben", last="Schmidt", cell="Schmidt, Ben", order="unknown", number=2)
    resolver.apply(second, other_raw)
    assert second.participants[0].first_name.value == "Ben" and second.participants[0].last_name.value == "Schmidt"
    assert other_raw["document_name_order"]["origin_page"] == 1
    assert resolver.context("doc")["order"] == "family_given"
    assert raw["document_name_order"]["actions"][0]["action"] == "swap"
    assert other_raw["document_name_order"]["actions"][0]["action"] == "keep"


def test_decisions_never_transfer_to_a_different_pdf():
    resolver = DocumentNameOrders()
    a, raw_a = visual()
    resolver.apply(a, raw_a)
    assert resolver.context("other") is None
    b, raw_b = visual(first="Berg", last="Lina", cell="Lina Berg", order="given_family", document="other")
    resolver.apply(b, raw_b)
    assert b.participants[0].first_name.value == "Lina" and b.participants[0].last_name.value == "Berg"
    assert resolver.context("other")["order"] == "given_family"


def test_compound_names_and_empty_user_cells_remain_literal():
    page, raw = visual(first="von der Wiese", last="Anna Maria", cell="von der Wiese, Anna Maria")
    before = raw["responses"][0]["raw_response"]
    DocumentNameOrders().apply(page, raw)
    person = page.participants[0]
    assert person.first_name.value == "Anna Maria" and person.last_name.value == "von der Wiese"
    assert person.personnel_number.state == "empty" and person.department.value == "MUC"
    assert raw["responses"][0]["raw_response"] == before


def test_separate_ocr_name_boxes_are_swapped_as_whole_fields_with_their_positions():
    person = VisualParticipant(first_name="Weber", last_name="Anna", personnel_number="000007", department="MUC").participant()
    person.first_name.bbox = Box(x0=0.1, y0=0.3, x1=0.2, y1=0.32)
    person.last_name.bbox = Box(x0=0.4, y0=0.3, x1=0.5, y1=0.32)
    page = PageResult(run_id="fixture", document_id="doc", page_id="doc-p0001", page_number=1,
                      method_id="ocr_llm", status="success", participants=[person])
    raw = dict(responses=[dict(name_order=dict(order="family_given", evidence="Nachname Vorname"))])
    DocumentNameOrders().apply(page, raw)
    assert person.first_name.value == "Anna" and person.first_name.bbox.x0 == .4
    assert person.last_name.value == "Weber" and person.last_name.bbox.x0 == .1
    assert person.personnel_number.value == "000007"


@pytest.mark.parametrize("order,cell", [("unknown", "Weber, Anna"), ("family_given", "Unreadable name")])
def test_uncertain_order_or_missing_physical_evidence_is_reviewed_without_changing_names(order, cell):
    page, raw = visual(order=order, cell=cell)
    DocumentNameOrders().apply(page, raw)
    assert page.participants[0].first_name.value == "Weber" and page.participants[0].last_name.value == "Anna"
    assert page.participants[0].first_name.state == "uncertain"
    assert REVIEW in page.participants[0].review_notes


def test_later_headings_resolve_earlier_pages_without_another_model_call(tmp_path):
    resolver = DocumentNameOrders()
    first, raw = visual(order="unknown")
    resolver.apply(first, raw)
    assert first.participants[0].first_name.state == "uncertain"
    write_json(tmp_path / f"raw-{first.page_id}.json", raw)
    second, second_raw = visual(number=2)
    resolver.apply(second, second_raw)
    write_json(tmp_path / f"raw-{second.page_id}.json", second_raw)
    resolver.finalize([first, second], tmp_path)
    assert first.participants[0].first_name.value == "Anna" and first.participants[0].first_name.state == "read"
    assert first.participants[0].last_name.value == "Weber"
    assert REVIEW not in first.participants[0].review_notes
    resolver.finalize([first, second], tmp_path)
    assert first.participants[0].first_name.value == "Anna"  # Never toggle a previously resolved mapping.


def test_conflicting_page_decisions_mark_the_entire_document_for_review(tmp_path):
    resolver = DocumentNameOrders()
    first, a = visual()
    resolver.apply(first, a)
    write_json(tmp_path / f"raw-{first.page_id}.json", a)
    second, b = visual(number=2, order="given_family")
    resolver.apply(second, b)
    write_json(tmp_path / f"raw-{second.page_id}.json", b)
    resolver.finalize([first, second], tmp_path)
    assert all(REVIEW in p.participants[0].review_notes for p in (first, second))
    assert all(read_json(tmp_path / f"raw-{p.page_id}.json")["document_name_order"]["conflicting_page_decision"] for p in (first, second))


def test_old_response_without_a_document_decision_is_not_reinterpreted():
    page, raw = visual()
    del raw["responses"][0]["name_order"]
    DocumentNameOrders().apply(page, raw)
    assert page.participants[0].first_name.value == "Weber"
    assert "document_name_order" not in raw


def test_new_model_answer_missing_the_required_order_is_preserved_for_manual_review():
    page, raw = visual()
    payload = json.loads(raw["responses"][0]["raw_response"])
    del payload["name_order"]
    model = object.__new__(LocalModel)
    model.method, model.calls = "vlm", 0
    model.spec = load_config(Path("configs/vlm-smoke.yaml")).models["vlm"]
    model.progress = Progress(enabled=False)
    model.generate = lambda *a: (json.dumps(payload), dict(output_budget_reached=False))
    from PIL import Image

    with Image.new("RGB", (256, 256)) as image:
        people, responses, _, _ = model.extract(image)
    assert responses[0]["name_order"]["order"] == "unknown"
    page.participants = people
    DocumentNameOrders().apply(page, dict(responses=responses))
    assert page.participants[0].first_name.value == "Weber"
    assert REVIEW in page.participants[0].review_notes


@pytest.mark.parametrize("method", ["unlimited_ocr", "paddle_structure", "docling"])
def test_name_roles_are_resolved_before_strict_source_cell_validation(method):
    rows, _ = source_rows("<table><tr><td>Nachname</td><td>Vorname</td><td>Benutzer</td></tr>"
                          "<tr><td>Weber</td><td>Anna</td><td>000007</td></tr></table>")
    response = AssignmentResponse.model_validate_json(json.dumps(dict(
        name_order=dict(order="family_given", evidence="Nachname | Vorname"), participants=[dict(
            source_row="t0r1", first_name=[0, "Weber"], last_name=[1, "Anna"],
            personnel_number=[2, "000007"], department=[None, None])])))
    resolver = DocumentNameOrders()
    changes = resolver.prepare_assignment(response, rows, "doc", 1)
    assert changes[0]["action"] == "swap_before_cell_validation"
    people, _, _ = ground_response(response, rows, source_label=method)
    assert people[0].first_name.value == "Anna" and people[0].last_name.value == "Weber"
    assert people[0].personnel_number.value == "000007"


def test_resume_restores_document_context_and_origin():
    page, raw = visual()
    resolver = DocumentNameOrders()
    resolver.apply(page, raw)
    restored = DocumentNameOrders()
    restored.restore(page, raw)
    assert restored.context("doc") == resolver.context("doc")
    assert restored.origins == {"doc": 1}


@pytest.mark.parametrize("response", [OCRPageResponse, VisualCellPageResponse, AssignmentResponse])
def test_model_generation_requires_document_decision_while_old_saved_responses_remain_readable(response):
    schema = generation_schema(response)
    assert "name_order" in schema["required"]
    assert schema["properties"]["name_order"] == {"$ref": "#/$defs/NameOrderDecision"}
    assert "name_order" not in response.model_json_schema().get("required", [])


def test_real_parser_pipeline_passes_only_same_document_context_and_exports_decisions(tmp_path, monkeypatch):
    folder = tmp_path / "pdfs"
    folder.mkdir()
    for name, count in (("123456", 2), ("654321", 1)):
        with pymupdf.open() as document:
            for number in range(count):
                document.new_page().insert_text((30, 70), f"Synthetic name-order fixture {name}, page {number + 1}")
            document.save(folder / f"{name}.pdf")
    hashes = {path: file_hash(path) for path in folder.iterdir()}
    fixtures = [visual(), visual(first="Schmidt", last="Ben", cell="Schmidt, Ben", order="unknown", number=2),
                visual(first="Berg", last="Lina", cell="Lina Berg", order="given_family", document="other")]
    requests = []
    config = load_config(Path("configs/vlm-smoke.yaml"))
    config.pdf.auto_orient = False
    config.output_dir, config.cache_dir = str(tmp_path / "runs"), str(tmp_path / "cache")
    model = object.__new__(LocalModel)
    model.method, model.spec, model.calls = "vlm", config.models["vlm"], 0
    model.progress = Progress(enabled=False)

    def generate(text, image):
        index = len(requests)
        requests.append(text)
        return fixtures[index][1]["responses"][0]["raw_response"], dict(output_budget_reached=False, output_tokens=150)

    model.generate = generate
    model.resources, model.close = lambda: {}, lambda: None
    monkeypatch.setattr(runner, "create_model", lambda *a, **k: model)
    monkeypatch.setattr(runner, "environment", lambda *a: {})
    output, _ = runner.run(config, folder, offline=True)
    assert len(requests) == 3
    assert "DOCUMENT_NAME_ORDER_CONTEXT" not in requests[0]
    assert "DOCUMENT_NAME_ORDER_CONTEXT" in requests[1]
    assert "DOCUMENT_NAME_ORDER_CONTEXT" not in requests[2]
    pages = read_jsonl(output / "vlm/extractions.jsonl")
    assert [(p["participants"][0]["first_name"]["value"], p["participants"][0]["last_name"]["value"])
            for p in pages] == [("Anna", "Weber"), ("Ben", "Schmidt"), ("Lina", "Berg")]
    with (output / "document_name_orders.csv").open(encoding="utf-8-sig", newline="") as stream:
        decisions = list(csv.DictReader(stream))
    assert len(decisions) == 3 and decisions[0]["name_order"] == "family_given"
    assert "Dokumentweite Zuordnung von Vor- und Nachname" in (output / "report.html").read_text(encoding="utf-8")
    assert all(file_hash(path) == expected for path, expected in hashes.items())
