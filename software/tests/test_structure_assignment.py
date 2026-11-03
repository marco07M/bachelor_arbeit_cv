"""Synthetic native layout evidence, independent engines and literal field grounding."""

import json
from copy import deepcopy
from pathlib import Path

import pytest

from participant_bench.config import Config, ModelConfig, StructureConfig, load_config
from participant_bench.io import file_hash, read_json, read_jsonl, write_json, write_jsonl
from participant_bench.progress import Progress
from participant_bench.schema import PageResult
from participant_bench.structure_assignment import (
    comma_names,
    ground_positions,
    header_bands,
    observed_field_bands,
    position_matches,
    prepare_rows,
    rectangle,
)
from participant_bench.unlimited_assignment import AssignmentResponse, assign_pages, ground_response


def paddle(*, headings=True, no_table=False):
    items = [
        ("Benutzer", [80, 100, 160, 120]), ("Benutzername", [250, 100, 420, 120]),
        ("Kurzzeichen", [600, 100, 710, 120]), ("Unterschrift", [800, 100, 900, 120]),
        ("001234", [80, 200, 180, 220]), ("von", [250, 200, 280, 220]),
        ("der", [310, 200, 340, 220]), ("Wiese,", [360, 200, 420, 220]),
        ("Anna", [440, 200, 500, 220]), ("MUC-1", [600, 200, 690, 220]),
        ("Weber, Jörg", [250, 250, 490, 270]), ("ABC-12", [600, 250, 700, 270]),
    ]
    if not headings:
        items = items[4:]
    return dict(tables=[] if no_table else [{"html": "<table><tr><td colspan='8'>merged</td></tr></table>"}],
                plain_text="old incomplete layout transcript", markdown="old layout",
                native=dict(width=1000, height=1000, overall_ocr_res=dict(
                    rec_texts=[text for text, _ in items], rec_boxes=[box for _, box in items])))


def answer(rows, *, swapped_id=False):
    body = [row for row in rows if any("Wiese" in c["text"] or "Weber" in c["text"] for c in row["cells"])]
    a, b = body
    return AssignmentResponse.model_validate_json(json.dumps({"participants": [
        dict(source_row=a["id"], first_name=[0, "Anna"],
             last_name=[0, "von der Wiese"], personnel_number=[0, "001234"],
             department=[0, "MUC-1"]),
        dict(source_row=b["id"], first_name=[0, "Jörg"], last_name=[0, "Weber"],
             personnel_number=[0, "ABC-12"] if swapped_id else [None, None], department=[0, "ABC-12"]),
    ]}))


def page(number, document="synthetic"):
    return PageResult(run_id="test", document_id=document, page_id=f"{document}-p{number:04d}",
                      page_number=number, method_id="paddle_structure", status="partial")


def test_spatial_rows_survive_merged_or_missing_tables_without_losing_ocr():
    for no_table in (False, True):
        rows, _, aspect = prepare_rows(paddle(no_table=no_table), "paddle_structure")
        assert aspect == 1 and len(rows) == 3
        assert sum(len(r["native_cells"]) for r in rows) == 12
        assert rows[1]["cells"][-1]["text"] == "001234 von der Wiese, Anna MUC-1"
        bands = header_bands(rows)
        assert bands["first_name"] == bands["last_name"]
        assert bands["personnel_number"][1] < bands["department"][0]


def test_compound_names_use_literal_offsets_and_original_positions():
    rows, _, _ = prepare_rows(paddle(), "paddle_structure")
    people, proofs, _ = ground_response(answer(rows), rows, trusted_headers=False)
    ground_positions(people, proofs, rows, header_bands(rows))
    assert len(people) == 2
    assert people[0].last_name.value == "von der Wiese"
    assert people[0].last_name.bbox.x0 == .25 and people[0].last_name.bbox.x1 == .42
    assert people[0].personnel_number.value == "001234"
    assert people[1].personnel_number.value is None and people[1].department.value == "ABC-12"
    assert people[1].bbox.y0 == .25
    assert all(p.signature_present is None for p in people)


def test_wrong_department_as_id_is_rejected_by_heading_position():
    rows, _, _ = prepare_rows(paddle(), "paddle_structure")
    bands = header_bands(rows)
    people, proofs, _ = ground_response(answer(rows, swapped_id=True), rows, trusted_headers=False,
                                       field_validator=lambda field, cell, match: position_matches(field, cell, match, bands))
    ground_positions(people, proofs, rows, bands)
    assert people[1].personnel_number.value is None
    assert people[1].department.value == "ABC-12"
    assert "personnel_number" not in proofs[1]["fields"]


def test_explicit_comma_name_order_overrides_overlapping_llm_fields_without_changing_spelling():
    rows, _, _ = prepare_rows(paddle(), "paddle_structure")
    response = answer(rows)
    response.participants[0].first_name = (0, "von der Wiese, Anna")
    response.participants[0].last_name = (0, "von der Wiese, Anna")
    comma_names(response, rows, header_bands(rows))
    assert response.participants[0].first_name == (0, "Anna")
    assert response.participants[0].last_name == (0, "von der Wiese")
    # No comma/order evidence: do not guess which word is the surname.
    source = paddle()
    source["native"]["overall_ocr_res"]["rec_texts"][10] = "Weber Jörg"
    rows, _, _ = prepare_rows(source, "paddle_structure")
    before = response.participants[1].model_dump()
    comma_names(response, rows, header_bands(rows))
    assert response.participants[1].model_dump() == before


def test_docling_native_cells_and_text_outside_table_are_both_preserved():
    cell = dict(text="001234", bbox=dict(l=80, t=200, r=180, b=220, coord_origin="TOPLEFT"))
    source = dict(tables=[dict(html="<table></table>", native={"data": {"table_cells": [cell]}})],
                  native=dict(pages={"1": {"size": {"width": 1000, "height": 1000}}}, texts=[
                      dict(text="von der Wiese, Anna", label="text", prov=[dict(
                          bbox=dict(l=250, t=800, r=500, b=780, coord_origin="BOTTOMLEFT"))]),
                      dict(text="footer", label="page_footer", prov=[dict(
                          bbox=dict(l=100, t=50, r=500, b=20, coord_origin="BOTTOMLEFT"))]),
                  ]))
    rows, _, _ = prepare_rows(source, "docling")
    assert len(rows) == 1 and len(rows[0]["native_cells"]) == 2
    assert rows[0]["cells"][-1]["text"] == "001234 von der Wiese, Anna"
    assert rows[0]["native_cells"][1]["bbox"]["y0"] == .2
    assert rectangle([[1, 2], [4, 1], [5, 8], [2, 9]], 10, 10)["y0"] == .1


def test_docling_uses_pre_table_ocr_boxes_instead_of_duplicating_merged_cells():
    source = dict(native={"pages": {"1": {"size": {"width": 1000, "height": 1000}}}},
                  tables=[dict(html="", native={"data": {"table_cells": [dict(text="merged bad header")]}})],
                  ocr_cells=[dict(text=text, bbox=dict(l=x, t=100, r=x + 90, b=120, coord_origin="TOPLEFT"))
                             for text, x in (("Benutzer", 80), ("Benutzername", 250), ("Kurzzeichen", 600))])
    rows, _, _ = prepare_rows(source, "docling")
    assert len(rows) == 1 and len(rows[0]["native_cells"]) == 3
    assert set(header_bands(rows)) == {"first_name", "last_name", "personnel_number", "department"}


def test_explicit_empty_cells_are_distinct_from_missing_ocr():
    source = dict(native={}, tables=[dict(html="""<table><tr><th>Vorname</th><th>Benutzer</th>
        <th>Kurzzeichen</th></tr><tr><td>Anna</td><td></td><td>MUC</td></tr></table>""")])
    rows, _, aspect = prepare_rows(source, "docling")
    assert aspect is None
    response = AssignmentResponse.model_validate_json(json.dumps({"participants": [dict(
        source_row="t0r1", first_name=[0, "Anna"], last_name=[None, None], personnel_number=[1, ""],
        department=[2, "MUC"])]}))
    people, _, _ = ground_response(response, rows, trusted_headers=False)
    assert people[0].personnel_number.state == "empty" and people[0].personnel_number.value == ""


def config(tmp_path):
    return Config(methods=["paddle_structure"], cache_dir=str(tmp_path / "cache"),
                  structures={"paddle_structure": StructureConfig(models_dir="unused", extraction="llm")},
                  models={"ocr_llm": ModelConfig(repo="synthetic/not-loaded", revision="a" * 40,
                                                 path="unused", warmup=False)})


class LLM:
    calls = 0
    identity = {"test": "synthetic-only"}

    def __init__(self, settings, prompts):
        self.spec, self.prompts, self.closed = settings, prompts, False

    def generate(self, prompt, **kwargs):
        self.prompts.append(json.loads(prompt))
        return '{"participants":[]}', {}

    def resources(self):
        return {}

    def close(self):
        self.closed = True


def test_following_page_context_is_geometry_only_and_never_crosses_document(tmp_path):
    settings = config(tmp_path)
    pages = [page(1), page(2), page(1, "zzz-other")]
    for item in pages:
        recognized = paddle(headings=item == pages[0])
        recognized["image_column_boundaries"] = [0., .2, .55, .75, 1.]
        write_json(tmp_path / f"raw-{item.page_id}.json", {"structure": recognized})
    prompts = []
    model = LLM(settings.models["ocr_llm"], prompts)
    assign_pages(pages, tmp_path, settings, Progress(enabled=False), lambda: model, method="paddle_structure")
    assert len(prompts) == 3 and model.closed
    assert prompts[1]["previous_field_bands"] and not prompts[2]["previous_field_bands"]
    previous = json.dumps(prompts[1]["previous_headers"])
    assert "Wiese" not in previous and "001234" not in previous
    assert not prompts[2]["previous_headers"]
    assert "ABC-12" in pages[1].page_text  # Repair the older incomplete Paddle transcript.
    assert all(read_json(tmp_path / f"raw-{p.page_id}.json")["assignment"]["complete"] for p in pages)


def test_learned_position_hints_contain_no_previous_participant_text():
    rows, _, _ = prepare_rows(paddle(), "paddle_structure")
    people, proofs, _ = ground_response(answer(rows), rows, trusted_headers=False)
    ground_positions(people, proofs, rows, {})
    assert observed_field_bands(people) == {}  # Insufficient independent row evidence.
    people.append(deepcopy(people[0]))
    bands = observed_field_bands(people)
    assert "last_name" in bands
    assert "first_name" not in bands  # Different within-cell positions are not a stable column anchor.
    text = json.dumps(bands)
    assert all(value not in text for value in ("Anna", "Wiese", "001234", "MUC"))


def test_resume_does_not_treat_previous_people_as_printed_column_headings(tmp_path):
    from participant_bench.unlimited_assignment import PROMPT_VERSION

    settings = config(tmp_path)
    rows, _, _ = prepare_rows(paddle(), "paddle_structure")
    people, proofs, _ = ground_response(answer(rows), rows, trusted_headers=False)
    ground_positions(people, proofs, rows, {})
    people.append(deepcopy(people[0]))
    first, second = page(1), page(2)
    first.participants = people
    write_json(tmp_path / f"raw-{first.page_id}.json", dict(structure=paddle(headings=False),
               assignment={"complete": True, "prompt_version": PROMPT_VERSION}))
    write_json(tmp_path / f"raw-{second.page_id}.json", dict(structure=paddle(headings=False)))
    prompts = []
    model = LLM(settings.models["ocr_llm"], prompts)
    assign_pages([first, second], tmp_path, settings, Progress(enabled=False), lambda: model, method="paddle_structure")
    assert len(prompts) == 1 and not prompts[0]["previous_field_bands"]
    assert not prompts[0]["continuation_candidates"]
    assert prompts[0]["document_column_mapping"]["status"] == "no_reliable_mapping"


def test_empty_native_result_keeps_review_text_without_loading_llm(tmp_path):
    item = page(1)
    write_json(tmp_path / f"raw-{item.page_id}.json", {"structure": dict(
        tables=[], plain_text="Unstructured OCR must remain visible", markdown="", native={})})
    assign_pages([item], tmp_path, config(tmp_path), Progress(enabled=False),
                 lambda: pytest.fail("No inference for empty evidence"), method="paddle_structure")
    assert item.page_text == "Unstructured OCR must remain visible" and item.text_fallback
    assert item.parse_status == "not_attempted" and item.status == "partial"


@pytest.mark.parametrize("method", ["paddle_structure", "paddle_llm"])
def test_runner_closes_structure_worker_before_local_assignment(tmp_path, monkeypatch, method):
    import pymupdf

    from participant_bench import runner

    folder = tmp_path / "input"
    folder.mkdir()
    with pymupdf.open() as pdf:
        pdf.new_page()
        pdf.save(folder / "123456.pdf")
    settings = config(tmp_path)
    settings.methods = [method]
    if method == "paddle_llm":
        settings.structures[method] = settings.structures.pop("paddle_structure")
    settings.pdf.auto_orient = False
    settings.output_dir = str(tmp_path / "runs")
    events = []

    class Structure:
        def extract_page(self, *args):
            events.append("ocr")
            return [], paddle(), "partial", 0.01

        def resources(self):
            return {}

        def close(self):
            events.append("closed")

    model = LLM(settings.models["ocr_llm"], [])

    def factory(method, *args, **kwargs):
        if method in ("paddle_structure", "paddle_llm"):
            return Structure()
        assert method == "ocr_llm" and events == ["ocr", "closed"]
        events.append("llm")
        return model

    monkeypatch.setattr(runner, "create_model", factory)
    monkeypatch.setattr(runner, "environment", lambda *args: {})
    output, summary = runner.run(settings, folder, offline=True)
    assert events == ["ocr", "closed", "llm"] and model.closed
    assert (output / "report.html").is_file()
    assert summary[method]["assignment_backend"] == "local_llm"


@pytest.mark.parametrize("method", ["paddle_structure", "docling"])
def test_structure_assignment_requires_explicitly_local_llm(method):
    with pytest.raises(ValueError, match="lokales"):
        Config(methods=[method], structures={method: StructureConfig(models_dir="unused", extraction="llm")})
    settings = load_config(Path("configs/benchmark-unlimited.yaml"))
    assert settings.structures["paddle_llm"].extraction == "llm"
    assert settings.structures["docling"].extraction == "table"


def test_posthoc_structure_assignment_preserves_source_and_does_not_load_ocr(tmp_path, monkeypatch):
    from participant_bench import unlimited_reassign

    source = tmp_path / "source"
    method = source / "paddle_structure"
    method.mkdir(parents=True)
    item = page(1)
    write_jsonl(method / "extractions.jsonl", [item.model_dump()])
    write_json(method / f"raw-{item.page_id}.json", {"structure": paddle(),
        "document_name_order": {"actions": [{"source_output_index": 0, "action": "review",
            "original_states": {"first_name": "failed", "last_name": "failed"}}]},
        "person_role_filter": {"output_index_mapping": [{"output_index": 0, "source_output_index": 999}]}})
    write_json(source / "manifest.json", {"pages": []})
    hashes = {p: file_hash(p) for p in source.rglob('*') if p.is_file()}
    settings = config(tmp_path)
    model = LLM(settings.models["ocr_llm"], [])
    monkeypatch.setattr(unlimited_reassign, "create_model", lambda method, *a, **k: model if method == "ocr_llm" else
                        pytest.fail("OCR/vision model must not load"))
    output = unlimited_reassign.reassign_run(source, settings, tmp_path / "result", methods=["paddle_structure"])
    assert (output / "report.html").is_file()
    assert read_json(output / "summary.json")["paddle_structure"]["new_ocr_inference"] is False
    raw = read_json(output / "paddle_structure" / f"raw-{item.page_id}.json")
    assert raw["historical_postprocessing"]["document_name_order"]["actions"][0]["action"] == "review"
    assert raw.get("document_name_order", {}).get("actions", []) != raw["historical_postprocessing"]["document_name_order"]["actions"]
    assert len(read_jsonl(output / "paddle_structure/extractions.jsonl")) == 1
    assert all(file_hash(p) == old for p, old in hashes.items())
