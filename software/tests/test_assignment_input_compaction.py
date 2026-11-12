"""Lossless prompt compaction; never truncate evidence to fit an input budget."""

import json
from copy import deepcopy

import pytest
from PIL import Image, ImageDraw
from test_structure_assignment import LLM, config, paddle, page

from participant_bench.config import Config
from participant_bench.io import read_json, write_json
from participant_bench.progress import Progress
from participant_bench.roster_benchmark.error_report import page_events
from participant_bench.rules import extract_rules
from participant_bench.unlimited_assignment import (
    INPUT_COMPACTION_VERSION,
    assign_pages,
    compact_assignment_rows,
)


def row(layout=None):
    return dict(
        id="r1",
        cells=[dict(index=0, text="Nora Beispiel 000123 D-7")],
        bbox=dict(x0=0.1, y0=0.2, x1=0.9, y1=0.24),
        layout_cells=layout
        if layout is not None
        else [
            ["Nora Beispiel", dict(x0=0.1, y0=0.2, x1=0.45, y1=0.24), 0.01, ["first_name", "last_name"]],
            ["000123 D-7", dict(x0=0.5, y0=0.2, x1=0.9, y1=0.24), 0.99, []],
        ],
        column_texts=[dict(column=0, text="Nora Beispiel"), dict(column=1, text="000123 D-7")],
    )


def test_only_exactly_reconstructible_row_bbox_is_omitted_and_all_evidence_survives():
    original = row()
    saved = deepcopy(original)
    result = compact_assignment_rows([original], ["index", "text"])[0]
    assert "bbox" not in result and original == saved
    assert result["layout_cells"] == saved["layout_cells"] and result["column_texts"] == saved["column_texts"]
    assert result["cells"] == [[0, "Nora Beispiel 000123 D-7"]]
    assert len(json.dumps(result)) < len(json.dumps(dict(result, bbox=original["bbox"])))


@pytest.mark.parametrize(
    "case", ["missing_cells", "missing_bbox", "incomplete_bbox", "different_extent", "extra_precision"]
)
def test_row_bbox_is_preserved_when_not_exactly_derivable(case):
    original = row()
    if case == "missing_cells":
        original["layout_cells"] = []
    elif case == "missing_bbox":
        original["layout_cells"][0][1] = None
    elif case == "incomplete_bbox":
        original["layout_cells"][0][1].pop("x1")
    elif case == "different_extent":
        original["bbox"]["x1"] = 0.95
    else:
        original["bbox"]["x1"] = 0.90000001
    result = compact_assignment_rows([original], ["index", "text"])[0]
    assert result["bbox"] == original["bbox"]
    assert result["layout_cells"] == original["layout_cells"]


def test_grid_cell_columns_and_missing_optional_metadata_keep_the_existing_contract():
    source = dict(id="r1", cells=[dict(index=0, text="Nora", column_start=2, colspan=1, rowspan=1)])
    assert compact_assignment_rows([source], ["index", "text", "column_start", "colspan", "rowspan"]) == [
        dict(id="r1", cells=[[0, "Nora", 2, 1, 1]])
    ]


def test_actual_assignment_saves_compact_input_and_keeps_full_precision_for_validation(tmp_path):
    item = page(1)
    settings = config(tmp_path)
    recognized = paddle()
    write_json(tmp_path / f"raw-{item.page_id}.json", dict(structure=recognized))
    prompts = []
    model = LLM(settings.models["ocr_llm"], prompts)
    assign_pages(
        [item], tmp_path, settings, Progress(enabled=False), lambda: model, method="paddle_structure"
    )
    record = read_json(tmp_path / f"raw-{item.page_id}.json")
    audit = record["assignment"]["input_compaction"]
    assert audit["version"] == INPUT_COMPACTION_VERSION and audit["omitted_redundant_row_boxes"] > 0
    assert all(r.get("layout_cells") and "bbox" not in r for r in prompts[0]["current_rows"])
    assert record["structure"]["native"] == recognized["native"]


@pytest.mark.parametrize("typed", [True, False])
def test_input_budget_failure_is_not_misreported_as_a_generated_invalid_answer(typed):
    item = page(1)
    item.parse_status = "invalid"
    assignment = (
        dict(error_stage="input_budget", model_inference_started=False)
        if typed
        else dict(error="ValueError: Input budget exceeded (13298); no silent truncation")
    )
    events = page_events(item, dict(assignment=assignment), {})
    assert [e["event"] for e in events] == ["input_budget_exceeded"]
    assert events[0]["stage"] == "model_input"


def test_generated_invalid_json_keeps_its_response_parsing_diagnosis():
    item = page(1)
    item.parse_status = "invalid"
    assert (
        page_events(item, dict(assignment=dict(raw_response="{bad", error="JSONDecodeError")), {})[0]["event"]
        == "invalid_structured_response"
    )


def test_actual_pre_generation_budget_exception_is_saved_as_model_input_failure(tmp_path):
    item = page(1)
    settings = config(tmp_path)
    write_json(tmp_path / f"raw-{item.page_id}.json", dict(structure=paddle()))

    class TooLarge(LLM):
        def generate(self, prompt, **kwargs):
            raise ValueError("Input budget exceeded (13000); no silent truncation")

    model = TooLarge(settings.models["ocr_llm"], [])
    assign_pages([item], tmp_path, settings, Progress(enabled=False), lambda: model, method="paddle_structure")
    raw = read_json(tmp_path / f"raw-{item.page_id}.json")
    assert raw["assignment"]["error_stage"] == "input_budget"
    assert raw["assignment"]["model_inference_started"] is False
    assert "raw_response" not in raw["assignment"] and not item.participants


@pytest.mark.parametrize("body_top", [0.2, 0.203])
def test_rule_layout_does_not_skip_first_body_row_when_header_boundary_is_at_or_before_top(body_top):
    settings = Config(methods=["ocr_rules"])
    settings.rules.columns = dict(first_name=(0.1, 0.4), last_name=(0.4, 0.8))
    settings.rules.body_top = body_top
    words = [
        dict(text=text, bbox=dict(x0=x, y0=y, x1=x + 0.1, y1=y + 0.02), ocr_confidence=90)
        for text, x, y in [
            ("Nora", 0.15, 0.25),
            ("Beispiel", 0.5, 0.25),
            ("Anna", 0.15, 0.35),
            ("Testfall", 0.5, 0.35),
        ]
    ]
    with Image.new("RGB", (1000, 1000), "white") as image:
        draw = ImageDraw.Draw(image)
        for y in (200, 300, 400):
            draw.line((100, y, 800, y), fill="black", width=3)
        people, _, _ = extract_rules(image, dict(words=words), settings)
    assert [p.first_name.value for p in people] == ["Nora", "Anna"]
