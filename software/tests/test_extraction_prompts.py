"""One fixed prompt family: existing contracts, honest evidence and reproducible messages."""

import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image

from participant_bench import extraction_prompts as prompts
from participant_bench.document_names import current_name_order, infer_text_order
from participant_bench.io import digest, read_json
from participant_bench.models import (
    ALL_ROW_INSTRUCTIONS,
    OCR_RECORD_SYSTEM,
    OCR_SYSTEM,
    VLM_SYSTEM,
    LocalModel,
    build_system,
    extraction_prompt_snapshot,
    generation_schema,
    prompt_metadata,
)
from participant_bench.schema import NameOrderDecision, OCRRecordResponse, VisualCellPageResponse
from participant_bench.selection_sample import prompt_identity
from participant_bench.unlimited_assignment import RECORD_SYSTEM, SYSTEM, AssignmentResponse


@pytest.mark.parametrize("template", [VLM_SYSTEM, OCR_SYSTEM, OCR_RECORD_SYSTEM, SYSTEM, RECORD_SYSTEM])
def test_existing_input_contracts_have_one_copy_of_the_six_annotation_sections(template):
    sections = [f"{i}. " for i in range(1, 7)]
    positions = [template.index(section) for section in sections]
    assert positions == sorted(positions)
    assert (
        template.count(prompts.TASK)
        == template.count(prompts.FIELDS)
        == template.count(prompts.ROLE_RULES)
        == 1
    )
    assert "Benutzername" in template and "Kurzzeichen" in template and "leading zeroes" in template
    assert prompts.UNKNOWN in template and prompts.MULTIPAGE in template


def test_record_contract_does_not_request_a_field_absent_from_its_schema():
    assert "name_order" not in generation_schema(OCRRecordResponse)["properties"]
    assert prompts.NAME_REPORT not in OCR_RECORD_SYSTEM and prompts.NAME_REPORT not in RECORD_SYSTEM
    assert prompts.NAME_REPORT in VLM_SYSTEM and prompts.NAME_REPORT in SYSTEM
    assert "identity_headers" in generation_schema(VisualCellPageResponse)["required"]
    assert "page_text" in generation_schema(VisualCellPageResponse)["required"]
    assert "identity_headers" not in generation_schema(OCRRecordResponse)["properties"]


def test_generation_requires_an_explicit_basis_but_historical_parser_is_unchanged():
    for schema in (
        generation_schema(NameOrderDecision),
        generation_schema(VisualCellPageResponse)["$defs"]["NameOrderDecision"],
        generation_schema(AssignmentResponse)["$defs"]["NameOrderDecision"],
    ):
        assert "basis" in schema["required"]
    historical = dict(order="given_family", evidence="Vorname Nachname")
    assert NameOrderDecision.model_validate(historical).basis == "document"
    decision = current_name_order(historical)
    assert decision.basis == decision.order == "unknown"
    explicit = current_name_order(dict(historical, basis="document"))
    assert explicit.order == "given_family" and explicit.basis == "document"


def test_name_order_example_agrees_with_requested_basis_and_schema():
    example = prompts.NAME_REPORT.split("Shape only: ", 1)[1].split(".\n", 1)[0]
    data = json.loads(example)
    decision = NameOrderDecision.model_validate(data["name_order"])
    assert decision.basis == "default" and decision.order == "family_given"
    assert set(generation_schema(NameOrderDecision)["required"]) <= set(data["name_order"])


def test_complete_system_hash_includes_schema_and_all_row_additions():
    text = 'OCR_TEXT_ROWS:\n{"rows":[]}'
    trace = prompt_metadata("ocr_llm", text, OCRRecordResponse, OCR_RECORD_SYSTEM + ALL_ROW_INSTRUCTIONS)
    assert trace["system_prompt_sha256"] == digest(trace["system_prompt"])
    assert trace["text_prompt_sha256"] == digest(text)
    assert trace["generation_schema_sha256"] == digest(generation_schema(OCRRecordResponse))
    assert trace["system_prompt_sha256"] != digest(OCR_RECORD_SYSTEM)
    assert ALL_ROW_INSTRUCTIONS in trace["system_prompt"]
    assert json.loads(trace["system_prompt"].split("\nJSON Schema:\n", 1)[1])["title"] == "OCRRecordResponse"


def test_run_snapshot_and_selection_freeze_capture_the_same_final_family():
    snapshot = extraction_prompt_snapshot()
    assert snapshot == prompt_identity()
    assert snapshot["compiled_systems"]["vlm"] == snapshot["compiled_systems"]["ocr_vlm"]
    for key, value in snapshot["compiled_systems"].items():
        assert snapshot["compiled_system_sha256"][key] == digest(value)
    for key, value in snapshot.items():
        if key != "component_sha256":
            assert snapshot["component_sha256"][key] == digest(value)
    old = read_json(Path("docs/prompt-history/pre-20261111.json"))
    assert old["versions"]["extraction"] != snapshot["version"]
    assert all(old["text_hashes"][key] == digest(value) for key, value in old["texts"].items())


def test_visual_and_hybrid_keep_identical_system_schema_and_only_add_grounded_hints():
    calls, records = [], []
    for method in ("vlm", "ocr_vlm"):
        model = object.__new__(LocalModel)
        model.method, model.calls = method, 0
        model.spec = SimpleNamespace(tile_height=None)

        def generate(text, image=None, **options):
            calls.append(dict(method=model.method, text=text))
            answer = dict(
                name_order=dict(order="unknown", basis="unknown", evidence="No readable headings"),
                identity_headers=[],
                participants=[],
                page_text="",
            )
            return json.dumps(answer), dict(output_budget_reached=False)

        model.generate = generate
        with Image.new("RGB", (30, 30), "white") as image:
            _, raw, _, _ = model.extract(
                image, {"hints": {"text": "synthetic OCR"}} if method == "ocr_vlm" else None
            )
        records.append(raw[0])
    assert (
        records[0]["system_prompt"]
        == records[1]["system_prompt"]
        == build_system("vlm", VisualCellPageResponse)
    )
    assert records[0]["system_prompt_sha256"] == records[1]["system_prompt_sha256"]
    assert calls[1]["text"].startswith(calls[0]["text"])
    assert prompts.HYBRID_RULES in calls[1]["text"]
    assert calls[0]["text"] == prompts.VISION_REQUEST


def test_missing_basis_in_new_helper_answer_cannot_claim_document_evidence():
    class Model:
        calls = 0

        def generate(self, *args, **kwargs):
            return '{"order":"given_family","evidence":"unverified"}', dict(output_budget_reached=False)

    model = Model()
    decision, record = infer_text_order(model, [])
    assert decision.order == decision.basis == "unknown" and model.calls == 1
    assert record["system_prompt_sha256"] == digest(record["system_prompt"])
    assert "JSON Schema" in record["system_prompt"]
