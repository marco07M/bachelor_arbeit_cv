"""Independent synthetic OCR observations survive score, selection and mapping failures."""

import importlib.util
import json
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image

from participant_bench.config import Config, load_config
from participant_bench.models import LocalModel, parse_ocr_response
from participant_bench.ocr import OCR
from participant_bench.ocr_layout import model_input, with_table_columns
from participant_bench.ocr_observations import audit, export, observations
from participant_bench.schema import PageResult, Participant, TextField
from participant_bench.structured_mapping import extract_structured


def page(method="ocr_llm", number=2, people=None):
    return PageResult(run_id="synthetic", document_id="test-doc", page_id=f"test-doc-p{number:04d}",
                      page_number=number, method_id=method, status="partial", participants=people or [])


def word(text, x=.1, y=.2, score=90, line=1):
    return dict(text=text, bbox=dict(x0=x, y0=y, x1=x+.08, y1=y+.02),
                ocr_confidence=score, line=[1, 1, line])


@pytest.mark.parametrize("score", [95., 0., -1., None, "unavailable", "nan"])
def test_actual_ocr_adapter_never_drops_nonempty_words_for_a_score(tmp_path, monkeypatch, score):
    model = object.__new__(OCR)
    model.config, model.identity, model.cache = Config(methods=["ocr_raw"]), {"test": True}, tmp_path
    response = dict(text=["  A/12 ", "007", "…", ""], conf=[score]*4,
        left=[1]*4, top=[1]*4, width=[10]*4, height=[10]*4,
        block_num=[1]*4, par_num=[1]*4, line_num=[1]*4)
    monkeypatch.setattr("participant_bench.ocr.pytesseract.image_to_data", lambda *a, **k: deepcopy(response))
    with Image.new("RGB", (50, 50), "white") as image:
        result = model.recognize(image, "synthetic")
    assert [w["text"] for w in result["words"]] == response["text"][:3]
    assert result["words"][0]["raw_ocr_confidence"] == score
    if score is None or isinstance(score, str):
        assert result["words"][0]["ocr_confidence"] is None


@pytest.mark.parametrize("score", [90., 1., None])
def test_lossless_ledger_includes_text_without_geometry_or_identity(score):
    raw = dict(ocr=dict(words=[dict(text=" A/12\n", ocr_confidence=score)]))
    data = audit(raw, page())
    assert data["counts"]["observations"] == data["counts"]["unassigned"] == 1
    item = data["observations"][0]
    assert item["text"] == " A/12\n" and item["confidence"] == score and item["bbox"] is None
    assert item["assignment_state"] == "unassigned" and item["submitted_to_assignment"] is None


def test_irregular_rows_are_not_filtered_out_of_the_actual_model_input(monkeypatch):
    data = dict(words=[word("Muster, Anna", y=.1+i*.1, line=i+1) for i in range(4)]+
        [word("Beispiel, Ben", y=.85, score=1, line=5)])
    original = deepcopy(data)
    monkeypatch.setattr("participant_bench.column_context.image_boundaries", lambda image: [0., .25, .5, .75, 1.])
    with Image.new("RGB", (100, 100)) as image:
        enriched = with_table_columns(data, image, document_id="test-doc", page_number=2, row_policy="all")
    assert enriched["selection_diagnostics"]["heuristic_rows"] == 4
    assert enriched["selection_diagnostics"]["model_input_rows"] == 5 and not enriched["context_rows"]
    assert "Beispiel, Ben" in model_input(enriched)
    assert enriched["text_rows"][-1]["selection_hint"] == "unclassified_observation"
    assert data == original


def test_regular_policy_is_default_but_omitted_observations_remain_in_the_ledger(monkeypatch):
    data = dict(words=[word("Muster, Anna", y=.1+i*.1, line=i+1) for i in range(4)]+
        [word("Beispiel, Ben", y=.85, score=1, line=5)])
    monkeypatch.setattr("participant_bench.column_context.image_boundaries", lambda image: [0., .25, .5, .75, 1.])
    with Image.new("RGB", (100, 100)) as image:
        layout = with_table_columns(data, image)
    assert layout["selection_diagnostics"]["policy"] == "pattern" and len(layout["text_rows"]) == 4
    assert len(layout["all_text_rows"]) == 5
    info = audit(dict(ocr=data, ocr_layout_analysis=layout), page())
    assert info["counts"]["observations"] == 5 and info["counts"]["not_submitted"] == 1
    assert load_config(Path("configs/benchmark.yaml")).models["ocr_llm"].ocr_row_selection == "pattern"


def test_missing_line_metadata_remains_visible_without_an_invented_person_row():
    data = dict(words=[dict(text="Musterma…", bbox=None, ocr_confidence=None)])
    with Image.new("RGB", (100, 100)) as image:
        enriched = with_table_columns(data, image)
    packed = json.loads(model_input(enriched).split("\n", 1)[1])
    assert not packed["rows"] and packed["unassigned_observations"][0]["text"] == "Musterma…"
    info = audit(dict(ocr=data, ocr_layout_analysis=enriched), page())
    assert info["observations"][0]["submitted_to_assignment"] is True
    assert info["observations"][0]["reason"] == "no_reliable_ocr_row"


def test_llm_omission_and_failed_literal_validation_do_not_delete_observations():
    data = dict(words=[word("Musterma…"), word("12345", x=.4), word("A/12", x=.7)])
    with Image.new("RGB", (100, 100)) as image:
        layout = with_table_columns(data, image)
    rejected, proofs = [], []
    body = dict(participants=[dict(source_row="r1", last_name="Erfunden", personnel_number="12345")])
    people = parse_ocr_response(json.dumps(body), layout, rejected, field_evidence=proofs)
    assert len(people) == 1 and people[0].last_name.state == "failed"
    assert people[0].personnel_number.value == "12345"
    raw = dict(ocr=data, ocr_layout_analysis=layout,
               responses=[dict(raw_response=json.dumps(body), ocr_field_evidence=proofs, rejected_rows=rejected)])
    info = audit(raw, page(people=people))
    assert info["counts"]["observations"] == 3
    assert info["observations"][0]["assignment_state"] == "unassigned"
    assert info["observations"][2]["assignment_state"] == "unassigned"


def test_rejected_source_row_is_explicitly_traced_and_original_words_survive():
    data = dict(words=[word("Anna")])
    with Image.new("RGB", (100, 100)) as image:
        layout = with_table_columns(data, image)
    rejected = []
    assert not parse_ocr_response(json.dumps(dict(participants=[dict(source_row="missing", first_name="Anna")])), layout, rejected)
    assert rejected[0]["stage"] == "evidence" and rejected[0]["source_row"] == "missing"
    assert observations(dict(ocr=data))[0][0]["text"] == "Anna"


def test_rejected_record_does_not_break_the_actual_model_response_reporting():
    model = object.__new__(LocalModel)
    model.method, model.calls = "ocr_llm", 0
    model.spec = load_config(Path("configs/benchmark.yaml")).models["ocr_llm"]
    payload = json.dumps(dict(participants=[dict(source_row="missing", first_name="Anna")]))
    model.generate = lambda *a, **k: (payload, dict(output_budget_reached=False, output_tokens=20))
    data = dict(words=[word("Anna")], text="Anna")
    with Image.new("RGB", (100, 100), "white") as image:
        layout = with_table_columns(data, image)
        people, records, _, _ = model.extract(image, layout)
    assert not people and records[0]["parse_status"] == "valid"
    assert records[0]["row_validation"]["evidence_rejections"] == 1


def test_single_identity_field_is_enough_with_known_current_columns():
    from test_document_columns import table

    source = table(values=[["An…", "", "", ""]])
    people, _, _, _ = extract_structured(source, document_id="test-doc", page_number=2)
    assert len(people) == 1 and people[0].first_name.value == "An…" and people[0].first_name.state == "uncertain"
    assert source["row_decisions"][-1]["status"] == "participant"


def test_id_only_record_needs_a_verified_id_column_when_a_name_hint_exists(monkeypatch):
    data = dict(words=[word("Benutzername", x=.05, y=.1), word("Benutzer", x=.4, y=.1),
                      word("001234", x=.4, y=.3, line=2)])
    monkeypatch.setattr("participant_bench.column_context.image_boundaries", lambda image: [0., .25, .5, .75, 1.])
    with Image.new("RGB", (100, 100)) as image:
        layout = with_table_columns(data, image)
    payload = json.dumps(dict(participants=[dict(source_row="r2", personnel_number="001234")]))
    people = parse_ocr_response(payload, layout, [])
    assert len(people) == 1 and people[0].personnel_number.value == "001234"
    assert people[0].first_name.value is None and people[0].last_name.value is None
    layout["column_mapping"] = {}
    assert not parse_ocr_response(payload, layout, [])


@pytest.mark.parametrize("score,state", [(90., "read"), (1., "uncertain"), (None, "read")])
def test_compact_record_protocol_keeps_word_confidence_and_precise_field_boxes(score, state):
    data = dict(words=[word("Musterma…", score=score), word("12345", x=.4, score=score)])
    with Image.new("RGB", (100, 100)) as image:
        layout = with_table_columns(data, image)
    payload = dict(participants=[dict(source_row="r1", personnel_number="12345")])
    evidence = []
    people = parse_ocr_response(json.dumps(payload), layout, [], field_evidence=evidence)
    assert people[0].personnel_number.value == "12345" and people[0].personnel_number.state == state
    assert people[0].personnel_number.bbox.x0 == .4
    assert evidence[0]["fields"]["personnel_number"]["ocr_observations"][0]["ocr_confidence"] == score


def test_unmapped_docling_text_and_unknown_confidence_survive_the_mapper():
    from test_document_columns import table

    source = table(headers=["", ""], values=[["Musterma…", "A/12"]], header=False)
    source["ocr_cells"] = [dict(text="Musterma…", bbox=dict(l=0, t=100, r=490, b=140), confidence=.01)]
    before = deepcopy(source["ocr_cells"])
    assert not extract_structured(source, document_id="test-doc", page_number=2)[0]
    info = audit(dict(structure=source), page("docling"))
    assert info["counts"]["observations"] == 1 and info["counts"]["unassigned"] == 1
    assert info["counts"]["native_mapper_rows"] == 1 and info["counts"]["native_mapper_cells"] == 2
    assert info["mapper_row_decisions"][0]["status"] == "unassigned"
    assert source["ocr_cells"] == before


def test_docling_capture_precedes_sdk_deletion_and_mutation():
    spec = importlib.util.spec_from_file_location("capture_test_backend", Path("structure_runtime/docling_backend.py"))
    backend = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(backend)
    box = SimpleNamespace(model_dump=lambda **k: dict(l=1, t=1, r=3, b=3))
    cells = [SimpleNamespace(text="An…", confidence=.01, index=0,
                             rect=SimpleNamespace(to_bounding_box=lambda: box))]

    class Engine:
        def post_process_cells(self, cells, page, conversion):
            cells[0].text = "modified by SDK"
            cells.clear()

    captured = []
    backend.configure_ocr_capture(Engine, captured.append)
    Engine().post_process_cells(cells, SimpleNamespace(page_no=1), None)
    assert not cells and captured[0]["text"] == "An…" and captured[0]["confidence"] == .01
    raw = dict(structure=dict(engine_ocr_observations=captured, ocr_cells=[],
               native=dict(pages={"1": dict(size=dict(width=100, height=100))})))
    info = audit(raw, page("docling"))
    assert info["counts"]["sdk_merge_removed"] == 1 and info["counts"]["observations"] == 1


def test_empty_engine_output_never_creates_a_participant_or_fake_observation():
    assert not observations(dict(ocr=dict(words=[])))[0]
    assert audit(dict(structure=dict(ocr_cells=[])), page("docling"))["counts"]["observations"] == 0


def test_report_exports_all_original_text_and_escapes_document_markup(tmp_path):
    raw = dict(ocr=dict(words=[word("<script>"), word(" A/12 ", x=.4, score=None)]))
    before = deepcopy(raw)
    text = export(tmp_path, "ocr_llm", page(), raw)
    assert "&lt;script&gt;" in text and "<script>" not in text and raw == before
    record = json.loads(next((tmp_path / "ocr_llm/observations").glob("*.json")).read_text(encoding="utf-8"))
    assert [r["text"] for r in record["observations"]] == ["<script>", " A/12 "]


def test_successful_typed_field_stays_unchanged_and_links_to_observed_word():
    value = TextField(value="Anna", state="read", bbox=word("Anna")["bbox"])
    person = Participant(first_name=value, last_name=TextField(), personnel_number=TextField(), department=TextField())
    raw = dict(ocr=dict(words=[word("Anna")]))
    before = person.model_dump()
    info = audit(raw, page(people=[person]))
    assert info["counts"]["structured_observed"] == 1 and person.model_dump() == before
