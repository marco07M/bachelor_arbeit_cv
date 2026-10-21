"""Signature localization, evidence contracts and real local crop/cache integration."""

import json
from pathlib import Path

import pytest
from participant_bench.config import load_config
from participant_bench.io import file_hash, read_json, read_jsonl, write_json, write_jsonl
from participant_bench.progress import Progress
from participant_bench.rules import attach_signatures
from participant_bench.schema import (
    Box,
    PageResult,
    Participant,
    SignatureLocations,
    SignatureResponse,
    TextField,
    VisualPageResponse,
)
from participant_bench.signatures import apply_observation, inspect_signatures, ocr_row_box, row_regions
from PIL import Image, ImageDraw
from pydantic import ValidationError


def person(y=0.4, present=None):
    return Participant(bbox=Box(x0=0.1, y0=y, x1=0.65, y1=y + 0.02),
                       first_name=TextField(value="Anna", state="read"), last_name=TextField(value="Weber", state="read"),
                       personnel_number=TextField(value="00123", state="read"), department=TextField(value="MUC", state="read"),
                       signature_present=present, signature_state="read" if present else "empty" if present is False else "uncertain")


class DetailDouble:
    def __init__(self, config, payload=None):
        self.spec = config.models["vlm"]
        self.identity = {"fixture": "no-real-inference"}
        self.progress = Progress(enabled=False)
        self.calls = 0
        self.images = []
        self.payload = payload or {"field_located": True, "signature_present": True, "evidence": "handwritten_mark"}

    def generate(self, text, image, **kwargs):
        assert kwargs["response_type"] is SignatureResponse
        assert "Never identify or authenticate" in kwargs["system_prompt"]
        self.images.append(image.copy())
        return json.dumps(self.payload), {"output_tokens": 32, "output_budget_reached": False}


@pytest.mark.parametrize("payload", [
    {"field_located": False, "signature_present": True, "evidence": "handwritten_mark"},
    {"field_located": True, "signature_present": True, "evidence": "printed_text"},
    {"field_located": True, "signature_present": False, "evidence": "unclear"},
    {"field_located": True, "signature_present": None, "evidence": "blank_field"},
])
def test_signature_decisions_require_consistent_visual_evidence(payload):
    with pytest.raises(ValidationError):
        SignatureResponse.model_validate(payload)


def test_unclear_printed_text_never_becomes_a_positive_signature():
    row = person()
    apply_observation(row, SignatureResponse(field_located=True, signature_present=None, evidence="printed_text"))
    assert row.signature_present is None


def test_disagreement_requires_review_and_never_flips_a_known_decision_silently():
    row = person(present=True)
    apply_observation(row, SignatureResponse(field_located=True, signature_present=False, evidence="blank_field"))
    assert row.signature_present is None and row.signature_state == "uncertain"
    assert any("widersprechen" in note for note in row.review_notes)


def test_valid_detail_observation_replaces_obsolete_unknown_note():
    row = person()
    row.review_notes = ["Unterschriftsfeld nicht zugeordnet; Signaturstatus unbekannt", "first_name: prüfen"]
    apply_observation(row, SignatureResponse(field_located=True, signature_present=True, evidence="handwritten_mark"))
    assert row.signature_present is True and row.signature_method == "local_vlm_detail"
    assert not any("nicht zugeordnet" in note for note in row.review_notes)
    assert "first_name: prüfen" in row.review_notes


def test_ocr_text_bands_expand_to_separate_whole_row_regions():
    config = load_config(Path("configs/local.yaml"))
    rows = row_regions([person(0.4), person(0.5), person(0.6)], config)
    assert rows[0].y0 < 0.4 and rows[0].y1 > 0.42
    assert rows[0].y1 <= rows[1].y0 and rows[1].y1 <= rows[2].y0
    assert all(box.x0 == 0 and box.x1 == 1 for box in rows)
    assert row_regions([person(0.4), person(0.4)], config) == [None, None]


def test_missing_and_oversized_row_regions_are_not_inspected():
    config = load_config(Path("configs/local.yaml"))
    first, second = person(), person()
    first.bbox = None
    second.bbox = Box(x0=0, y0=0, x1=1, y1=1)
    assert row_regions([first, second], config) == [None, None]


def test_row_localization_does_not_change_the_primary_participant_response_contract():
    payload = {"participants": [{"first_name": "Anna", "last_name": "Weber", "department": "MUC",
                                  "personnel_number": "00123"}], "page_text": None}
    row = VisualPageResponse.model_validate_json(json.dumps(payload)).participants[0].participant()
    assert row.bbox is None and row.first_name.value == "Anna"
    located = SignatureLocations.model_validate_json('{"rows":[{"output_index":0,"row_y":[400,500]}]}')
    assert located.rows[0].row_y == (400, 500)


def test_separate_vlm_localization_preserves_people_and_does_not_apply_invalid_positions(tmp_path):
    config = load_config(Path("configs/local.yaml"))
    config.cache_dir = str(tmp_path / "cache")
    rows = [person(0.4), person(0.6)]
    for row in rows:
        row.bbox = None

    class LocationDouble(DetailDouble):
        def generate(self, text, image, **kwargs):
            if kwargs["response_type"] is SignatureLocations:
                assert len(json.loads(text)["participants"]) == 2
                return '{"rows":[{"output_index":0,"row_y":[400,500]},{"output_index":1,"row_y":[800,700]}]}', {}
            return super().generate(text, image, **kwargs)

    model = LocationDouble(config)
    with Image.new("RGB", (1000, 1000), "white") as image:
        records, _, calls = inspect_signatures(rows, image, model, config, tmp_path / "out", "doc-p0001")
    assert len(rows) == 2 and all(row.first_name.value == "Anna" for row in rows)
    assert rows[0].bbox is not None and rows[0].signature_present is True
    assert rows[1].bbox is None and rows[1].signature_present is None
    assert records[0]["row_location"]["raw_response"] and records[1]["error"]
    assert calls == 2 and model.calls == 2


def test_valid_signature_column_works_without_other_ocr_headers(tmp_path):
    config = load_config(Path("configs/local.yaml"))
    config.rules.columns = {"signature": (0.75, 0.98)}
    row = person()
    with Image.new("RGB", (1000, 1000), "white") as image:
        attach_signatures([row], image, {"words": []}, config)
    assert row.signature_bbox is not None and row.signature_bbox.y1 > row.bbox.y1
    assert row.signature_present is False


def test_ocr_geometry_does_not_replace_vlm_values_or_mix_people(tmp_path):
    config = load_config(Path("configs/local.yaml"))
    config.cache_dir = str(tmp_path / "cache")
    data = {"words": [
        {"text": text, "bbox": {"x0": x, "y0": y, "x1": x + 0.08, "y1": y + 0.02},
         "line": [1, 1, line], "ocr_confidence": 90}
        for text, x, y, line in (("Anna", 0.1, 0.4, 1), ("Weber", 0.3, 0.4, 1), ("00123", 0.5, 0.4, 1),
                                ("Nora", 0.1, 0.6, 2), ("Fischer", 0.3, 0.6, 2), ("00456", 0.5, 0.6, 2))
    ]}
    row = person()
    row.bbox, row.first_name.value = None, "ANNA"
    assert ocr_row_box(row, data).y0 == 0.4
    model = DetailDouble(config)  # A model location call would fail this double's response-type assertion.
    with Image.new("RGB", (1000, 1000), "white") as image:
        records, _, calls = inspect_signatures([row], image, model, config, tmp_path / "out", "doc-p0001", data)
    assert calls == 1 and row.signature_present is True and row.first_name.value == "ANNA"
    assert records[0]["location_source"] == "ocr_words"
    cached_row = person()
    cached_row.bbox, cached_row.first_name.value = None, "ANNA"
    with Image.new("RGB", (1000, 1000), "white") as image:
        cached, _, cached_calls = inspect_signatures([cached_row], image, model, config, tmp_path / "cached", "doc-p0001", data)
    assert cached_calls == 0 and cached[0]["location_source"] == "ocr_words"
    assert cached_row.first_name.value == "ANNA" and cached_row.signature_present is True
    row.first_name.value = "Nora"
    assert ocr_row_box(row, data) is None


def test_detail_crop_and_cache_keep_original_pixels_and_do_not_repeat_generation(tmp_path):
    config = load_config(Path("configs/local.yaml"))
    config.cache_dir = str(tmp_path / "cache")
    model = DetailDouble(config)
    rows = [person(0.4), person(0.5)]
    with Image.new("RGB", (1000, 1000), "white") as image:
        ImageDraw.Draw(image).line([(760, 405), (800, 385), (830, 425), (880, 400)], fill="black", width=3)
        records, _, calls = inspect_signatures(rows, image, model, config, tmp_path / "one", "doc-p0001")
        cached_rows = [person(0.4), person(0.5)]
        cached, _, cached_calls = inspect_signatures(cached_rows, image, model, config, tmp_path / "two", "doc-p0001")
    assert calls == 2 and cached_calls == 0 and model.calls == 2
    assert all(row.signature_present is True for row in rows + cached_rows)
    assert all(record["cache_hit"] for record in cached)
    assert model.images[0].width == 1000
    assert all((tmp_path / "one" / record["crop"]).is_file() for record in records)
    assert all((tmp_path / "two" / record["crop"]).is_file() for record in cached)


def test_bad_detail_response_keeps_people_and_is_not_cached(tmp_path):
    config = load_config(Path("configs/local.yaml"))
    config.cache_dir = str(tmp_path / "cache")
    model = DetailDouble(config, {"field_located": True, "signature_present": True, "evidence": "printed_text"})
    row = person()
    with Image.new("RGB", (1000, 1000), "white") as image:
        records, _, _ = inspect_signatures([row], image, model, config, tmp_path / "out", "doc-p0001")
    assert row.first_name.value == "Anna" and row.signature_present is None
    assert records[0]["error"] and not list((tmp_path / "cache/signatures").glob("*.json"))


def test_signature_only_recheck_preserves_source_and_never_runs_participant_extraction(tmp_path, monkeypatch):
    from participant_bench import signature_review

    config = load_config(Path("configs/local.yaml"))
    config.cache_dir = str(tmp_path / "cache")
    source = tmp_path / "source"
    source.mkdir()
    page = PageResult(run_id="old", document_id="doc", page_id="doc-p0001", page_number=1,
                      method_id="ocr_llm", status="partial", parse_status="valid", participants=[person()])
    write_json(source / "summary.json", {"ocr_llm": {"status": "partial"}})
    write_jsonl(source / "ocr_llm/extractions.jsonl", [page.model_dump()])
    write_json(source / "manifest.json", {"automatic_page_selection": False, "pages": [{
        "page_id": page.page_id, "source_path": "123456.pdf", "page_number": 1,
        "status": "ready", "include": True, "review_required": False,
    }]})
    (source / "pages").mkdir()
    Image.new("RGB", (1000, 1000), "white").save(source / "pages/doc-p0001.png")
    hashes = {path: file_hash(path) for path in source.rglob("*") if path.is_file()}

    class ReviewDouble(DetailDouble):
        def __init__(self, method, config, progress=None):
            super().__init__(config)
            assert method == "vlm"

        def resources(self):
            return {"calls": self.calls}

        def close(self):
            pass

        def extract(self, *args):
            raise AssertionError("Participant inference must never run in a signature-only recheck")

    monkeypatch.setattr(signature_review, "LocalModel", ReviewDouble)
    output = signature_review.recheck_run(source, config, ["ocr_llm"], tmp_path / "review")
    assert all(file_hash(path) == old for path, old in hashes.items())
    saved = read_jsonl(output / "ocr_llm/extractions.jsonl")[0]
    assert saved["participants"][0]["first_name"] == page.participants[0].first_name.model_dump()
    assert saved["participants"][0]["signature_present"] is True
    assert saved["calls"] == 1
    assert read_json(output / "signature_recheck.json")["new_participant_inference"] is False
    assert read_json(output / "metrics.json") == {}
    content = (output / "report.html").read_text(encoding="utf-8")
    assert "Unterschriften im Detail" in content and "signatures/doc-p0001-row001.png" in content
    assert (output / "signature_checks.csv").is_file()


@pytest.mark.parametrize("method", ["ocr_llm", "vlm"])
def test_runner_records_separate_signature_calls_and_unloads_ocr_model_first(tmp_path, monkeypatch, method):
    import pymupdf
    from participant_bench import runner

    config = load_config(Path("configs/local.yaml"))
    config.methods = [method]
    config.pdf.auto_orient = False
    config.output_dir, config.cache_dir = str(tmp_path / "runs"), str(tmp_path / "cache")
    for spec in config.models.values():
        spec.path = str(tmp_path / "weights-not-used-by-unit-test")
    raw = tmp_path / "raw"
    raw.mkdir()
    with pymupdf.open() as pdf:
        pdf.new_page().insert_text((50, 50), "Synthetic participant fixture")
        pdf.save(raw / "123456.pdf")
    events = []

    class ModelDouble(DetailDouble):
        def __init__(self, selected, config, progress=None):
            if selected == "vlm" and method == "ocr_llm":
                assert "closed:ocr_llm" in events
            super().__init__(config)
            self.selected = selected
            events.append("loaded:" + selected)

        def extract(self, image, data):
            return [person()], [{"parse_status": "valid"}], "success", 0.01

        def resources(self):
            return {"load_seconds": 0.0, "warmup_calls": 0, "calls": self.calls}

        def close(self):
            events.append("closed:" + self.selected)

    class OCRDouble:
        def __init__(self, config):
            self.identity = {"fixture": True}

        def recognize(self, image, image_hash):
            return {"words": [], "text": "", "cache_hit": False, "elapsed_seconds": 0.01}

    monkeypatch.setattr(runner, "LocalModel", ModelDouble)
    monkeypatch.setattr(runner, "OCR", OCRDouble)
    monkeypatch.setattr(runner, "environment", lambda *args: {})
    output, summary = runner.run(config, raw)
    saved = read_jsonl(output / method / "extractions.jsonl")[0]
    assert saved["participants"][0]["signature_present"] is True
    assert saved["participants"][0]["personnel_number"]["value"] == "00123"
    assert saved["calls"] == summary[method]["generation_calls"] == 2
    assert saved["timings"]["signature_seconds"] >= 0
    assert summary[method]["signature_backend"] == "local_vlm"
    assert len(read_json(output / method / ("raw-" + saved["page_id"] + ".json"))["signature_checks"]) == 1
    if method == "ocr_llm":
        assert events == ["loaded:ocr_llm", "closed:ocr_llm", "loaded:vlm", "closed:vlm"]
    else:
        assert events == ["loaded:vlm", "closed:vlm"]
