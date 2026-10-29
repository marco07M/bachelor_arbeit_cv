"""OCR data contracts and fallback paths; doubles do not measure language-model quality."""

import json
from pathlib import Path

import pymupdf
import pytest
from PIL import Image
from pydantic import ValidationError

from participant_bench import runner
from participant_bench.config import load_config
from participant_bench.doctor import tesseract_command
from participant_bench.io import file_hash, read_jsonl
from participant_bench.models import LocalModel, parse_ocr_response
from participant_bench.ocr_layout import compact_layout, readable_text
from participant_bench.rules import extract_rules, find_headers


def word(text, x, y, line=1):
    return {"text": text, "bbox": {"x0": x, "y0": y, "x1": x + 0.07, "y1": y + 0.015},
            "ocr_confidence": 85.123456, "line": [1, 1, line]}


def ocr_data():
    words = [word("1", 0.01, 0.3), word("Anna", 0.1, 0.3), word("Weber", 0.3, 0.3),
             word("00123", 0.5, 0.3), word("MUC", 0.7, 0.3)]
    return {"words": words, "text": " ".join(w["text"] for w in words), "size": [1000, 1000]}


def model_response():
    return json.dumps({"participants": [{
        "row_ref": "1", "first_name": "Anna", "last_name": "Weber",
        "personnel_number": "00123", "department": "MUC", "word_ids": [4, 3, 2, 1, 0],
    }]})


def test_compact_input_retains_every_word_and_readable_lines_without_float_metadata():
    data = ocr_data()
    original = json.dumps(data)
    packed = compact_layout(data)
    decoded = json.loads(packed)
    assert [w[1] for w in decoded["words"]] == [w["text"] for w in data["words"]]
    assert [w[0] for w in decoded["words"]] == list(range(len(data["words"])))
    assert decoded["coordinate_scale"] == 1000
    assert all(isinstance(v, int) for w in decoded["words"] for v in w[2:])
    assert decoded["lines"] == [{"line_id": 1, "word_ids": [0, 1, 2, 3, 4],
                                 "text": "1 Anna Weber 00123 MUC"}]
    assert len(packed) < len(original) / 2
    assert json.dumps(data) == original  # Run evidence is not rounded or mutated.


def test_compact_model_output_uses_observed_word_positions_and_preserves_zeroes():
    row = parse_ocr_response(model_response(), ocr_data())[0]
    assert row.personnel_number.value == "00123" and row.personnel_number.state == "read"
    assert row.first_name.value == "Anna"
    assert row.bbox.x0 == 0.01 and row.bbox.x1 == 0.77
    assert row.signature_present is None and row.signature_state == "uncertain"


@pytest.mark.parametrize("mutation", ["invented_value", "unknown_id", "duplicate_id", "string_id", "numeric_personnel"])
def test_invalid_or_invented_ocr_model_evidence_is_not_accepted(mutation):
    data = json.loads(model_response())
    row = data["participants"][0]
    if mutation == "invented_value":
        row["first_name"] = "Erfunden"
    elif mutation == "unknown_id":
        row["word_ids"] = [100]
    elif mutation == "duplicate_id":
        row["word_ids"] = [0, 0]
    elif mutation == "string_id":
        row["word_ids"] = ["0"]
    else:
        row["personnel_number"] = 123
    with pytest.raises((ValueError, ValidationError)):
        parse_ocr_response(json.dumps(data), ocr_data())


def test_extraction_actually_sends_compact_input_and_accepts_compact_response():
    model = object.__new__(LocalModel)
    model.method = "ocr_llm"
    model.spec = load_config(Path("configs/local.yaml")).models["ocr_llm"]
    model.calls = 0
    seen = []

    def generation_double(text, image):
        assert image is None
        seen.append(json.loads(text.split("\n", 1)[1]))
        return model_response(), {"output_budget_reached": False, "output_tokens": 100}

    model.generate = generation_double
    with Image.new("RGB", (1000, 1000), "white") as image:
        rows, _, status, _ = model.extract(image, ocr_data())
    assert status == "success" and len(rows) == 1 and model.calls == 1
    assert len(seen[0]["words"]) == 5 and "text" not in seen[0]
    assert seen[0]["lines"][0]["text"] == "1 Anna Weber 00123 MUC"
    assert not any("Model-reported boxes" in note for note in rows[0].review_notes)


def test_unsubstantiated_row_does_not_discard_other_supported_rows():
    model = object.__new__(LocalModel)
    model.method = "ocr_llm"
    model.spec = load_config(Path("configs/local.yaml")).models["ocr_llm"]
    model.spec.preserve_partial_fields = False
    model.calls = 0
    payload = json.loads(model_response())
    invalid = dict(payload["participants"][0], first_name="NichtImOCR")
    payload["participants"].append(invalid)
    model.generate = lambda *args: (json.dumps(payload), {"output_budget_reached": False, "output_tokens": 200})
    with Image.new("RGB", (1000, 1000), "white") as image:
        rows, records, status, _ = model.extract(image, ocr_data())
    assert status == "partial" and len(rows) == 1
    assert rows[0].first_name.value == "Anna"
    assert records[0]["parse_status"] == "valid"  # JSON schema is valid; evidence failure is explicitly separate.
    assert records[0]["rejected_rows"][0]["output_index"] == 1
    assert "verworfen" in records[0]["review_notes"][0]
    assert model.calls == 1


def test_all_unsubstantiated_rows_are_excluded_and_reported():
    payload = json.loads(model_response())
    payload["participants"][0]["first_name"] = "NichtImOCR"
    rejected = []
    assert parse_ocr_response(json.dumps(payload), ocr_data(), rejected_rows=rejected) == []
    assert len(rejected) == 1 and rejected[0]["output_index"] == 0


@pytest.mark.parametrize("malformed", ["missing_field", "numeric_id", "not_an_object"])
def test_one_malformed_model_row_does_not_discard_supported_rows(malformed):
    payload = json.loads(model_response())
    invalid = dict(payload["participants"][0])
    if malformed == "missing_field":
        invalid.pop("last_name")
    elif malformed == "numeric_id":
        invalid["personnel_number"] = 123
    else:
        invalid = "not a participant object"
    payload["participants"].append(invalid)
    raw = json.dumps(payload)
    rejected = []
    people = parse_ocr_response(raw, ocr_data(), rejected_rows=rejected, preserve_partial_fields=True)
    assert len(people) == 1 and people[0].personnel_number.value == "00123"
    assert rejected[0]["output_index"] == 1 and rejected[0]["stage"] == "schema"
    assert json.loads(raw) == payload


@pytest.mark.parametrize("payload", ['{"participants": []', '{"participants": [], "unexpected": true}',
                                    '{"participants": "wrong type"}'])
def test_row_isolation_does_not_repair_invalid_json_or_top_level_schema(payload):
    with pytest.raises(ValueError):
        parse_ocr_response(payload, ocr_data(), rejected_rows=[])


def test_fallback_preserves_reading_order_and_line_breaks():
    data = ocr_data()
    data["words"].append(word("Hinweise", 0.1, 0.5, line=2))
    assert readable_text(data) == "1 Anna Weber 00123 MUC\nHinweise"
    lines = json.loads(compact_layout(data))["lines"]
    assert [line["line_id"] for line in lines] == [1, 2]
    assert "\n".join(line["text"] for line in lines) == readable_text(data)
    assert lines[1]["word_ids"] == [5]
    assert readable_text({"text": "Original ohne Wortpositionen"}) == "Original ohne Wortpositionen"
    assert readable_text({"words": [], "text": ""}) == ""


def test_split_header_words_match_only_when_adjacent_on_the_same_line():
    words = [word("Personal", 0.1, 0.1), word("Nr.", 0.18, 0.1),
             word("First", 0.4, 0.1), word("Name", 0.48, 0.1)]
    headers = find_headers(words, {"personnel_number": ["Personal-Nr."], "first_name": ["First Name"]}, 0.008)
    assert set(headers) == {"personnel_number", "first_name"}
    assert headers["personnel_number"]["bbox"]["x1"] == 0.25
    words[1]["bbox"]["y0"], words[1]["bbox"]["y1"] = 0.3, 0.315
    assert "personnel_number" not in find_headers(words, {"personnel_number": ["Personal-Nr."]}, 0.008)


def test_two_reliable_field_headers_are_enough_to_extract_names():
    config = load_config(Path("configs/local.yaml"))
    words = [word("Vorname", 0.1, 0.1), word("Nachname", 0.4, 0.1),
             word("Anna", 0.1, 0.3, 2), word("Weber", 0.4, 0.3, 2)]
    with Image.new("RGB", (1000, 1000), "white") as image:
        rows, _, _ = extract_rules(image, {"words": words}, config)
    assert len(rows) == 1
    assert rows[0].first_name.value == "Anna" and rows[0].last_name.value == "Weber"
    assert rows[0].personnel_number.value is None


def test_explicit_template_extracts_without_headers_while_unknown_layout_remains_unassigned():
    config = load_config(Path("configs/local.yaml"))
    data = {"words": [word("Anna", 0.1, 0.3), word("Weber", 0.4, 0.3)]}
    with Image.new("RGB", (1000, 1000), "white") as image:
        rows, notes, _ = extract_rules(image, data, config)
        assert not rows and "rules.columns" in notes[0]
        config.rules.columns = {"first_name": (0.08, 0.3), "last_name": (0.3, 0.7)}
        config.rules.body_top = 0.2
        rows, _, _ = extract_rules(image, data, config)
    assert len(rows) == 1 and rows[0].last_name.value == "Weber"


@pytest.mark.parametrize("model_fails", [False, True])
def test_both_ocr_methods_keep_real_ocr_text_when_structuring_returns_nothing(tmp_path, monkeypatch, model_fails):
    class ResponseDouble:
        def __init__(self, *args, **kwargs):
            pass

        def extract(self, image, data):
            response = {"parse_status": "not_attempted", "error": "Test input budget error"} if model_fails else {
                "parse_status": "valid", "raw_response": '{"participants":[]}',
            }
            return [], [response], "failed" if model_fails else "success", 0.0

        def resources(self):
            return {}

        def close(self):
            pass

    config = load_config(Path("configs/local.yaml"))
    try:
        tesseract_command(config)
    except FileNotFoundError:
        pytest.skip("Real Tesseract required for fallback integration test")
    config.methods = ["ocr_rules", "ocr_llm"]
    config.pdf.auto_orient = False
    config.cache_dir = str(tmp_path / "cache")
    config.output_dir = str(tmp_path / "runs")
    config.models["ocr_llm"].path = str(tmp_path / "not-loaded-by-test")
    raw = tmp_path / "raw"
    raw.mkdir()
    with pymupdf.open() as doc:
        doc.new_page().insert_text((50, 100), "Hinweise zur Schulung", fontsize=16)
        doc.save(raw / "123456.pdf")
    original = file_hash(raw / "123456.pdf")
    monkeypatch.setattr(runner, "LocalModel", ResponseDouble)
    monkeypatch.setattr(runner, "environment", lambda *args: {"fixture": True})
    output, summaries = runner.run(config, raw)
    for method in config.methods:
        result = read_jsonl(output / method / "extractions.jsonl")[0]
        assert result["text_fallback"] and "Hinweise" in result["page_text"]
        assert not result["participants"] and summaries[method]["text_fallback_pages"] == 1
        assert list((output / method / "texts").glob("*.txt"))
    if model_fails:
        result = read_jsonl(output / "ocr_llm/extractions.jsonl")[0]
        assert result["error"] == "Test input budget error" and result["status"] == "failed"
    assert file_hash(raw / "123456.pdf") == original
    assert "OCR-Rohdaten mit Wortpositionen" in (output / "report.html").read_text(encoding="utf-8")
