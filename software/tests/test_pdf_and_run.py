import json
import shutil
import socket
from pathlib import Path

import pymupdf
import pytest

from participant_bench.config import load_config
from participant_bench.doctor import tesseract_command
from participant_bench.io import file_hash, read_json, write_json
from participant_bench.ocr import OCR
from participant_bench.pdf import prepare, validate_manifest
from participant_bench.runner import load_truth, run
from participant_bench.synthetic import HEIGHT, WIDTH, add_table, generate


@pytest.fixture
def fixture(tmp_path):
    config = load_config(Path("configs/smoke.yaml"))
    config.output_dir = str(tmp_path / "runs")
    config.cache_dir = str(tmp_path / "cache")
    try:
        tesseract_command(config)
    except FileNotFoundError:
        pytest.skip("Real Tesseract with deu+eng required; no OCR mock used")
    generate(tmp_path / "synthetic")
    raw = tmp_path / "synthetic/raw"
    destination = tmp_path / "prepared"
    manifest = prepare(raw, config, destination, OCR(config))
    return config, raw, destination, manifest


def curated_manifest(destination, manifest):
    notes = read_json(destination.parent / "synthetic/fixture_notes.json")
    for page in manifest["pages"]:
        annotation = notes["curation"][str(page["page_number"])]
        page["include"] = annotation["include"]
        page["curation_rotation_clockwise"] = (
            annotation["total_additional_clockwise"] - page["additional_rotation_clockwise"]
        ) % 360
    manifest["curated"] = True
    path = destination / "curated.json"
    write_json(path, manifest)
    return path


def test_real_offline_ocr_curated_end_to_end(fixture, monkeypatch):
    config, raw, destination, manifest = fixture
    originals = {p.name: file_hash(p) for p in raw.iterdir()}
    path = curated_manifest(destination, manifest)

    def no_network(*args, **kwargs):
        raise AssertionError("Offline run attempted network access")

    monkeypatch.setattr(socket, "create_connection", no_network)
    output, summaries = run(config, raw, path, destination.parent / "synthetic/ground_truth.jsonl", "curated")
    assert summaries["ocr_rules"]["status"] == "success"
    metrics = read_json(output / "metrics.json")["ocr_rules"]["aggregate"]
    assert metrics["overall_exact_match"]["numerator"] == 24
    assert metrics["overall_exact_match"]["denominator"] == 24
    assert metrics["counts"]["gt_rows"] == 6
    assert metrics["counts"]["extra_rows"] == metrics["counts"]["missing_rows"] == 0
    assert (output / "report.html").is_file()
    assert "00123" in (output / "extractions.csv").read_text(encoding="utf-8-sig")
    assert originals == {p.name: file_hash(p) for p in raw.iterdir()}
    resumed, stats = run(
        config, raw, path, destination.parent / "synthetic/ground_truth.jsonl", "curated", resume=output
    )
    assert resumed == output
    assert stats["ocr_rules"]["resume_reused_pages"] == 4


def test_pdf_metadata_rotation_not_applied_twice(fixture):
    _, _, _, manifest = fixture
    rotated = manifest["pages"][4]
    assert rotated["pdf_rotation_metadata"] == 90
    assert rotated["additional_rotation_clockwise"] in (0, 270)
    assert manifest["pages"][1]["page_type"] == "blank"
    assert manifest["pages"][2]["include"] is True  # uncertain title is retained
    assert any(e["status"] == "skipped" for e in manifest["errors"])


def test_manifest_rejects_changed_input_and_images(fixture):
    config, raw, destination, manifest = fixture
    path = destination / "manifest.json"
    image_path = destination / manifest["pages"][0]["image"]
    old = image_path.read_bytes()
    image_path.write_bytes(b"changed")
    with pytest.raises(ValueError, match="Rendered image changed"):
        validate_manifest(path, raw, config)
    image_path.write_bytes(old)
    (raw / "new.pdf").write_bytes(b"invalid")
    with pytest.raises(ValueError, match="Input paths/hashes changed"):
        validate_manifest(path, raw, config)


def test_corrupt_encrypted_and_duplicate_pdf_logged(tmp_path):
    config = load_config(Path("configs/smoke.yaml"))
    raw = tmp_path / "raw"
    raw.mkdir()
    (raw / "bad.pdf").write_bytes(b"not a pdf")
    document = pymupdf.open()
    document.new_page()
    document.save(
        raw / "locked.pdf", encryption=pymupdf.PDF_ENCRYPT_AES_256, owner_pw="owner", user_pw="secret"
    )
    document.close()
    shutil.copy(raw / "locked.pdf", raw / "duplicate.pdf")
    manifest = prepare(raw, config, tmp_path / "prepared")
    assert sum(e["status"] == "failed" for e in manifest["errors"]) == 2
    assert sum(e["status"] == "duplicate" for e in manifest["errors"]) == 1


def test_manual_180_degree_correction_with_real_ocr(tmp_path):
    config = load_config(Path("configs/smoke.yaml"))
    try:
        tesseract_command(config)
    except FileNotFoundError:
        pytest.skip("Real Tesseract required")
    config.pdf.auto_orient = False
    config.cache_dir = str(tmp_path / "cache")
    config.output_dir = str(tmp_path / "runs")
    raw = tmp_path / "raw"
    raw.mkdir()
    doc = pymupdf.open()
    page = doc.new_page(width=WIDTH, height=HEIGHT)
    add_table(page)
    page.set_rotation(180)
    doc.save(raw / "upside-down.pdf")
    doc.close()
    destination = tmp_path / "prepared"
    manifest = prepare(raw, config, destination, OCR(config))
    assert manifest["pages"][0]["pdf_rotation_metadata"] == 180
    manifest["pages"][0]["curation_rotation_clockwise"] = 180
    manifest["curated"] = True
    write_json(destination / "curated.json", manifest)
    output, summaries = run(config, raw, destination / "curated.json", scope="curated")
    assert summaries["ocr_rules"]["status"] == "success"
    data = (output / "ocr_rules/extractions.jsonl").read_text(encoding="utf-8")
    assert '"value": "00123"' in data and '"value": "00007"' in data


def test_ground_truth_split_leakage_rejected(fixture):
    _, _, destination, manifest = fixture
    truths = [
        json.loads(line)
        for line in (destination.parent / "synthetic/ground_truth.jsonl").read_text().splitlines()
    ]
    truths[1]["split"] = "test"
    path = destination.parent / "bad_truth.jsonl"
    path.write_text("\n".join(json.dumps(t) for t in truths))
    with pytest.raises(ValueError, match="crosses development/test"):
        load_truth(path, manifest, "all", "end-to-end")


def test_missing_models_explicit_and_no_quality_without_truth(fixture):
    config, raw, destination, manifest = fixture
    config.methods = ["ocr_rules", "ocr_llm", "vlm"]
    for method in ("ocr_llm", "vlm"):
        config.models[method].path = str(destination.parent / "missing-model" / method)
    path = curated_manifest(destination, manifest)
    output, summaries = run(config, raw, path, scope="curated")
    assert summaries["ocr_rules"]["status"] == "success"
    assert summaries["ocr_llm"]["status"] == summaries["vlm"]["status"] == "unavailable"
    assert read_json(output / "metrics.json") == {}
    assert "Qualität: nicht gemessen" in (output / "report.html").read_text(encoding="utf-8")
