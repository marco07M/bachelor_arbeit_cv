"""Data contracts, raw-only semantics, source-page isolation and independent local adapters."""

import importlib.util
import json
import socket
from pathlib import Path

import pymupdf
import pytest
from PIL import Image

from participant_bench.config import METHODS, Config, ModelConfig, StructureConfig, load_config
from participant_bench.io import file_hash, read_json, read_jsonl, write_json
from participant_bench.models import Unavailable
from participant_bench.ocr import raw_transcript
from participant_bench.runner import run
from participant_bench.structure import (
    StructureModel,
    docling_page_pdf,
    lossless_image_pdf,
    model_manifest,
    single_page_pdf,
)

TABLE = """<table><tr><th>Vorname</th><th>Nachname</th><th>Benutzer</th><th>Kurzzeichen</th></tr>
<tr><td>Anna</td><td>Groß-Müller</td><td>001234</td><td>MUC</td></tr>
<tr><td>Jörg</td><td>Weber</td><td></td><td>ABC-12</td></tr></table>"""


def test_six_default_methods_and_legacy_readability():
    config = load_config(Path("configs/benchmark-unlimited.yaml"))
    assert config.methods == list(METHODS)
    assert set(config.structures) == {"paddle_llm", "docling"}
    assert "unlimited_ocr" not in config.methods
    assert load_config(Path("configs/unlimited-ocr-llm.yaml")).models["unlimited_ocr"].options["extraction"] == "llm"
    assert Config(methods=["ocr_rules"]).methods == ["ocr_rules"]


def test_raw_text_retains_engine_line_order_spelling_and_leading_zeros():
    data = {"words": [dict(text=text, line=line) for text, line in [
        ("Jörg", [2, 1, 1]), ("Groß-Müller", [2, 1, 1]), ("001234", [1, 1, 2])]]}
    assert raw_transcript(data) == "Jörg Groß-Müller\n001234"
    assert raw_transcript({"words": []}) == ""


def test_raw_method_skips_models_field_metrics_and_signatures(tmp_path, monkeypatch):
    from participant_bench import runner

    folder = tmp_path / "input"
    folder.mkdir()
    with pymupdf.open() as document:
        document.new_page().insert_text((40, 70), "Synthetic OCR input")
        document.save(folder / "123456.pdf")
    config = Config(methods=["ocr_raw"], output_dir=str(tmp_path / "runs"))
    config.pdf.auto_orient = False

    class LocalOCR:
        identity = {"engine": "synthetic-test-double"}

        def __init__(self, config):
            pass

        def recognize(self, *args, **kwargs):
            return {"words": [{"text": "001234", "line": [1, 1, 1], "ocr_confidence": 90,
                    "bbox": dict(x0=0.1, y0=0.1, x1=0.3, y1=0.2)}],
                    "cache_hit": False, "elapsed_seconds": 0.01}

    def forbidden(*args, **kwargs):
        pytest.fail("Raw OCR must not initialize a model or evaluate participant fields")

    monkeypatch.setattr(runner, "OCR", LocalOCR)
    monkeypatch.setattr(runner, "create_model", forbidden)
    monkeypatch.setattr(runner, "evaluate_groups", forbidden)
    monkeypatch.setattr(runner, "load_truth", lambda *args: [object()])
    monkeypatch.setattr(runner, "environment", lambda *args: {})
    output, summary = run(config, folder, truth_path=Path(__file__), offline=True)
    page = read_jsonl(output / "ocr_raw/extractions.jsonl")[0]
    assert page["output_kind"] == "ocr_text" and page["status"] == "success"
    assert page["participants"] == [] and not page["text_fallback"]
    assert page["page_text"] == "001234"
    assert summary["ocr_raw"]["signature_backend"] == "none"
    assert read_json(output / "metrics.json") == {}
    assert next((output / "ocr_raw/ocr_text").glob("*.txt")).read_text(encoding="utf-8") == "001234"


def test_native_docling_page_isolated_and_rotated_without_modifying_original(tmp_path):
    source = tmp_path / "source.pdf"
    with pymupdf.open() as document:
        document.new_page().insert_text((30, 70), "Cover")
        document.new_page().insert_text((30, 70), "Native table page")
        document[1].set_rotation(90)
        document.save(source)
    original = file_hash(source)
    data = single_page_pdf(dict(source_path=str(source), page_number=2,
                                additional_rotation_clockwise=90, curation_rotation_clockwise=180))
    with pymupdf.open(stream=data, filetype="pdf") as document:
        assert len(document) == 1
        assert "Native table page" in document[0].get_text() and "Cover" not in document[0].get_text()
        assert document[0].rotation == 0
    assert file_hash(source) == original
    assert single_page_pdf({"source_kind": "image"}) is None


@pytest.mark.parametrize("invalid", ["missing", "tampered", "escape"])
def test_structure_manifest_rejects_missing_tampered_or_escaping_models(tmp_path, invalid):
    root = tmp_path / "models"
    root.mkdir()
    weights = root / "weights.bin"
    weights.write_bytes(b"synthetic")
    relative = "../outside.bin" if invalid == "escape" else "weights.bin"
    write_json(root / "models-manifest.json", {"files": {relative: file_hash(weights)}})
    if invalid == "missing":
        weights.unlink()
    elif invalid == "tampered":
        weights.write_bytes(b"changed")
    with pytest.raises(Unavailable):
        model_manifest(root, verify=True)


@pytest.mark.parametrize("method", ["paddle_structure", "docling"])
def test_table_output_keeps_empty_id_and_cache_prevents_repeated_inference(tmp_path, method):
    # Exercise the actual adapter postprocessor/cache contract, not a real engine accuracy claim.
    model = object.__new__(StructureModel)
    model.method = method
    model.identity = {"engine": "synthetic-adapter-double"}
    model.settings = StructureConfig(models_dir="unused", device="cpu")
    model.config = Config(methods=[method])
    model.cache = tmp_path
    model.calls = 0
    model._resources = {}
    model.mapping_context = {}
    from participant_bench.progress import Progress

    model.progress = Progress(enabled=False)
    calls = []

    def recognize(request):
        calls.append(request)
        return {"tables": [{"html": TABLE}], "markdown": TABLE, "plain_text": "observed text",
                "native": {}, "resources": {}}

    model.request = recognize
    page = dict(document_id="synthetic", page_number=1, run_image_sha256="synthetic", source_kind="image")
    image = Image.new("RGB", (200, 200), "white")
    people, evidence, status, _ = model.extract_page(image, page)
    assert len(people) == 2 and status == "partial"
    assert people[0].personnel_number.value == "001234"
    assert people[1].personnel_number.state == "empty" and people[1].department.value == "ABC-12"
    assert all(person.signature_present is None for person in people)
    assert evidence["tables"][0]["html"] == TABLE and evidence["row_evidence"][1]["raw_cells"][2] == ""
    _, evidence, _, _ = model.extract_page(image, page)
    assert len(calls) == 1 and evidence["cache_hit"]
    # Malformed JSON and a valid-but-wrong payload must not poison future page runs.
    cache_path = next(tmp_path.glob("*.json"))
    cache_path.write_text("null", encoding="utf-8")
    model.extract_page(image, page)
    assert len(calls) == 2
    image.close()


def test_runner_structure_failure_retains_later_pages_and_native_exports(tmp_path, monkeypatch):
    from participant_bench import runner
    from participant_bench.unlimited_tables import extract_tables

    folder = tmp_path / "input"
    folder.mkdir()
    with pymupdf.open() as source:
        source.new_page()
        source.new_page()
        source.save(folder / "123456.pdf")
    config = Config(methods=["paddle_structure"], output_dir=str(tmp_path / "runs"),
                    structures={"paddle_structure": StructureConfig(models_dir="synthetic-not-used")})
    config.pdf.auto_orient = False

    class SimulatedStructure:
        def extract_page(self, image, page):
            if page["page_number"] == 1:
                raise RuntimeError("Synthetic page failure")
            people, evidence, notes = extract_tables(TABLE)
            return people, {"tables": [{"html": TABLE}], "markdown": TABLE, "plain_text": "Synthetic text",
                            "native": {}, "row_evidence": evidence, "review_notes": notes}, "partial", 0.01

        def resources(self):
            return {}

        def close(self):
            pass

    monkeypatch.setattr(runner, "create_model", lambda *args, **kwargs: SimulatedStructure())
    monkeypatch.setattr(runner, "environment", lambda *args: {})
    output, summary = run(config, folder, offline=True)
    pages = read_jsonl(output / "paddle_structure/extractions.jsonl")
    assert [page["status"] for page in pages] == ["failed", "partial"]
    assert len(pages[1]["participants"]) == 2
    assert next((output / "paddle_structure/tables").glob("*.html.txt")).read_text(encoding="utf-8") == TABLE
    assert (output / "report.html").is_file() and summary["paddle_structure"]["failed_pages"] == 1


def test_structure_cache_limit_preserves_sdk_files_and_logs(tmp_path):
    model = object.__new__(StructureModel)
    model.cache = tmp_path
    model.config = Config(methods=["paddle_structure"], cache_max_gb=0)
    generated = tmp_path / ("a" * 64 + ".json")
    generated.write_text("{}")
    sdk = tmp_path / "settings.json"
    sdk.write_text("{}")
    log = tmp_path / "worker.log"
    log.write_text("local diagnostics")
    model.enforce_limit()
    assert not generated.exists() and sdk.is_file() and log.is_file()


def test_docling_uses_full_page_image_for_textless_tiled_scans_and_retains_native_text(tmp_path):
    import io

    image = Image.new("RGB", (100, 80), "white")
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    source = tmp_path / "synthetic-mosaic.pdf"
    with pymupdf.open() as document:
        native = document.new_page()
        native.insert_text((30, 60), "Vorname Nachname Benutzer Kurzzeichen")
        scan = document.new_page()
        for y in range(3):
            for x in range(4):
                scan.insert_image(pymupdf.Rect(20 + x * 100, 20 + y * 80, 120 + x * 100, 100 + y * 80),
                                  stream=buffer.getvalue())
        document.save(source)
    before = file_hash(source)
    page = dict(source_path=str(source), source_kind="pdf", page_number=1)
    data = docling_page_pdf(page)
    with pymupdf.open(stream=data, filetype="pdf") as document:
        assert "Benutzer" in document[0].get_text()
    page["page_number"] = 2
    assert docling_page_pdf(page) is None
    assert docling_page_pdf(page, "native") is not None
    assert file_hash(source) == before


def test_flattened_scan_keeps_exact_analysis_pixels():
    image = Image.new("RGB", (100, 80), "white")
    for x in range(image.width):
        image.putpixel((x, 40), (x, 255 - x, x // 2))
    with pymupdf.open(stream=lossless_image_pdf(image, 200), filetype="pdf") as document:
        xref = document[0].get_images()[0][0]
        pixels = pymupdf.Pixmap(document, xref)
        assert pixels.samples == image.tobytes()
        assert abs(document[0].rect.width - 36) < .001


def test_docling_grid_cleanup_changes_only_temporary_ocr_image(tmp_path):
    from PIL import ImageDraw

    from participant_bench.image_preprocessing import remove_grid_lines

    spec = importlib.util.spec_from_file_location("docling_adapter_test", Path("structure_runtime/docling_backend.py"))
    backend = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(backend)
    image = Image.new("RGB", (500, 300), "white")
    ImageDraw.Draw(image).line((10, 150, 490, 150), fill="black", width=2)
    original = image.tobytes()
    path = tmp_path / "docling-temporary-ocr.png"
    image.save(path, dpi=(216, 216))

    class Engine:
        def _run_tesseract(self, filename, osd):
            with Image.open(filename) as transformed:
                return transformed.convert("RGB").tobytes(), transformed.size, osd

    backend.configure_ocr_images(Engine, remove_grid_lines)
    pixels, size, orientation = Engine()._run_tesseract(str(path), "unchanged-orientation")
    assert pixels != original and size == image.size
    assert image.tobytes() == original and orientation == "unchanged-orientation"


@pytest.mark.parametrize("methods", [None, ["ocr_raw"]])
def test_raw_only_run_cannot_trigger_posthoc_signature_model(tmp_path, methods):
    from participant_bench.signature_review import recheck_run

    write_json(tmp_path / "summary.json", {"ocr_raw": {"output_kind": "ocr_text"}})
    config = Config(methods=["ocr_raw"], models={"vlm": ModelConfig(
        repo="synthetic/not-loaded", revision="a" * 40, path="synthetic/not-read")})
    with pytest.raises(ValueError, match="strukturierte Teilnehmer"):
        recheck_run(tmp_path, config, methods=methods, offline=True)
    assert not (tmp_path / "signature-review").exists()


def test_worker_network_guard_blocks_explicit_and_implicit_connections(monkeypatch):
    script = Path("structure_runtime/offline.py")
    spec = importlib.util.spec_from_file_location("structure_offline_guard", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    # Restore patched globals/environment after exercising the actual guard.
    monkeypatch.setattr(socket, "create_connection", socket.create_connection)
    monkeypatch.setattr(socket.socket, "connect", socket.socket.connect)
    monkeypatch.setattr(socket.socket, "connect_ex", socket.socket.connect_ex)
    for name in ("HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE", "HF_HUB_DISABLE_TELEMETRY",
                 "PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK", "PADDLE_PDX_DISABLE_TELEMETRY", "DO_NOT_TRACK",
                 "FLAGS_enable_pir_api"):
        monkeypatch.setenv(name, "original-synthetic-setting")
    module.disable_network()
    with pytest.raises(OSError, match="Network disabled"):
        socket.create_connection(("example.invalid", 443))
    with socket.socket() as sock, pytest.raises(OSError, match="Network disabled"):
        sock.connect(("127.0.0.1", 1))


def test_sources_are_pinned_and_do_not_download_python_code():
    for name in ("paddle_sources.json", "docling_sources.json"):
        sources = json.loads((Path("structure_runtime") / name).read_text(encoding="utf-8"))
        assert sources
        assert all(len(spec["revision"]) == 40 for spec in sources.values())
