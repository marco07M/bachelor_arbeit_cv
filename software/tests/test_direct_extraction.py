from pathlib import Path

import pymupdf
import pytest

from participant_bench import runner
from participant_bench.config import load_config
from participant_bench.io import file_hash, read_json, read_jsonl, write_json
from participant_bench.pdf import prepare, validate_manifest
from participant_bench.synthetic import add_table


def mixed_input(tmp_path):
    raw = tmp_path / "raw"
    raw.mkdir()
    with pymupdf.open() as document:
        document.new_page().insert_text((50, 50), "Teilnehmerliste - Deckblatt")
        document.new_page()  # Even an empty page must reach extraction when supplied by the user.
        add_table(document.new_page())
        document.save(raw / "123456.pdf")
    return raw


def test_preparation_does_not_run_text_recognition_or_classify_pages(tmp_path):
    class OrientationOnly:
        calls = 0

        def orientation(self, image):
            self.calls += 1
            return 0, 20.0, None, 0.0

        def recognize(self, *args):
            raise AssertionError("No OCR recognition may be used to select or classify input pages")

    raw = mixed_input(tmp_path)
    config = load_config(Path("configs/smoke.yaml"))
    ocr = OrientationOnly()
    manifest = prepare(raw, config, tmp_path / "prepared", ocr)
    assert ocr.calls == 3
    assert len(manifest["pages"]) == 3
    assert all(page["include"] for page in manifest["pages"])
    assert all(page["page_type"] == "input_page" for page in manifest["pages"])
    assert all("classification_ocr_seconds" not in page for page in manifest["pages"])


def test_vlm_routes_every_page_to_extraction_without_ocr_when_orientation_is_disabled(tmp_path, monkeypatch):
    # This test verifies orchestration only. The double does not simulate model quality.
    calls, closed = [], []

    class RoutingOnlyModel:
        def __init__(self, method, config, progress=None):
            assert method == "vlm"

        def extract(self, image, ocr_data=None):
            assert ocr_data is None
            calls.append(image.size)
            return [], [{"parse_status": "valid", "page_text": f"Seitentext {len(calls)}",
                         "text_fallback": True}], "success", 0.0

        def resources(self):
            return {"calls": len(calls)}

        def close(self):
            closed.append(True)

    def no_ocr(*args, **kwargs):
        raise AssertionError("Direct VLM extraction must not initialize an unnecessary OCR stage")

    raw = mixed_input(tmp_path)
    original_hash = file_hash(raw / "123456.pdf")
    config = load_config(Path("configs/vlm-smoke.yaml"))
    config.pdf.auto_orient = False
    config.output_dir = str(tmp_path / "runs")
    config.models["vlm"].path = str(tmp_path / "not-loaded-in-routing-test")
    monkeypatch.setattr(runner, "OCR", no_ocr)
    monkeypatch.setattr(runner, "LocalModel", RoutingOnlyModel)
    monkeypatch.setattr(runner, "environment", lambda *args: {"test_fixture": True})
    output, summaries = runner.run(config, raw)
    assert len(calls) == 3 and closed == [True]
    assert summaries["vlm"]["selected_pages"] == 3
    assert summaries["vlm"]["valid_pages"] == 3
    assert summaries["vlm"]["text_fallback_pages"] == 3
    assert [p["page_number"] for p in read_jsonl(output / "vlm" / "extractions.jsonl")] == [1, 2, 3]
    assert all(page["include"] for page in read_json(output / "manifest.json")["pages"])
    assert [p["page_text"] for p in read_jsonl(output / "page_text.jsonl")] == [
        "Seitentext 1", "Seitentext 2", "Seitentext 3",
    ]
    assert len(list((output / "vlm/texts").glob("*.txt"))) == 3
    assert "OCR für Seitenauswahl" not in (output / "progress.log").read_text(encoding="utf-8")
    assert file_hash(raw / "123456.pdf") == original_hash


def test_legacy_automatic_exclusions_are_not_silently_reused(tmp_path):
    raw = mixed_input(tmp_path)
    config = load_config(Path("configs/vlm-smoke.yaml"))
    config.pdf.auto_orient = False
    destination = tmp_path / "prepared"
    manifest = prepare(raw, config, destination)
    manifest["version"] = 1
    manifest.pop("automatic_page_selection")
    manifest["pages"][1]["include"] = False
    write_json(destination / "manifest.json", manifest)
    with pytest.raises(ValueError, match="neu erzeugen"):
        validate_manifest(destination / "manifest.json", raw, config)


def test_only_explicit_manual_curation_can_exclude_a_page(tmp_path):
    raw = mixed_input(tmp_path)
    config = load_config(Path("configs/vlm-smoke.yaml"))
    config.pdf.auto_orient = False
    destination = tmp_path / "prepared"
    manifest = prepare(raw, config, destination)
    manifest["pages"][1]["include"] = False
    write_json(destination / "manifest.json", manifest)
    with pytest.raises(ValueError, match="curated=true"):
        validate_manifest(destination / "manifest.json", raw, config)
    manifest["curated"] = True
    write_json(destination / "manifest.json", manifest)
    assert validate_manifest(destination / "manifest.json", raw, config)["pages"][1]["include"] is False
