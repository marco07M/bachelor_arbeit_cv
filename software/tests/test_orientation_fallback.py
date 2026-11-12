"""Automatic orientation evidence, abstention and shared rendered/native page pixels."""

import json
from pathlib import Path
from types import SimpleNamespace

import pymupdf
import pytest
from PIL import Image

from participant_bench.config import load_config
from participant_bench.io import file_hash, write_json
from participant_bench.ocr import OCR
from participant_bench.orientation import MAX_SIDE, VERSION, choose, detect, text_evidence
from participant_bench.pdf import prepare, validate_manifest
from participant_bench.roster_benchmark.pipeline_trace import page_trace
from participant_bench.schema import PageResult
from participant_bench.structure import single_page_pdf


def evidence(winner=0):
    return [
        dict(
            clockwise=a,
            score=80.0 if a == winner else 4.0,
            words=12 if a == winner else 1,
            letters=100 if a == winner else 5,
        )
        for a in (0, 90, 180, 270)
    ]


def test_score_is_text_only_finite_and_never_returns_recognized_values():
    data = dict(
        text=["Lesbarer", "Text", "123456789", "AB-12", "!", "Blurred", "NaN", "Negative"],
        conf=[90, 80, 99, 99, 99, 20, float("nan"), -1],
    )
    result = text_evidence(data)
    assert result == dict(score=10.4, words=2, letters=12)
    assert "Lesbarer" not in json.dumps(result)


@pytest.mark.parametrize("angle", [0, 90, 180, 270])
def test_selector_accepts_each_clockwise_rotation_only_with_distinct_evidence(angle):
    assert choose(evidence(angle)) == (angle, "distinct_readable_text_evidence")


@pytest.mark.parametrize(
    "kind,reason",
    [
        ("blank", "insufficient_readable_text"),
        ("few_words", "insufficient_readable_text"),
        ("few_letters", "insufficient_readable_text"),
        ("tie", "ambiguous_rotation_comparison"),
        ("small_gap", "ambiguous_rotation_comparison"),
        ("small_ratio", "ambiguous_rotation_comparison"),
        ("failed", "rotation_probe_failed"),
        ("missing", "incomplete_rotation_comparison"),
        ("duplicate", "incomplete_rotation_comparison"),
        ("nan", "invalid_rotation_evidence"),
    ],
)
def test_selector_abstains_instead_of_rotating_uncertain_pages(kind, reason):
    data = evidence()
    if kind == "blank":
        for c in data:
            c.update(score=0, words=0, letters=0)
    elif kind == "few_words":
        data[0]["words"] = 4
    elif kind == "few_letters":
        data[0]["letters"] = 24
    elif kind == "tie":
        data[1].update(data[0], clockwise=90)
    elif kind == "small_gap":
        data[0]["score"] = 16
    elif kind == "small_ratio":
        data[1]["score"] = 70
    elif kind == "failed":
        data[2]["error"] = "RuntimeError"
    elif kind == "missing":
        data.pop()
    elif kind == "duplicate":
        data[1]["clockwise"] = 0
    else:
        data[0]["score"] = float("nan")
    assert choose(data) == (None, reason)


class Detector:
    def __init__(self, angle=0, confidence=0.3, error=None, winner=90):
        self.osd = (angle, confidence, error, 0.1)
        self.winner = winner
        self.probed = False

    def orientation(self, image):
        return self.osd

    def orientation_evidence(self, image):
        self.probed = True
        return evidence(self.winner), 0.4


def test_reliable_osd_is_kept_and_skips_additional_ocr():
    ocr = Detector(angle=180, confidence=10, winner=90)
    decision = detect(None, ocr, 5)
    assert decision["accepted"] and decision["clockwise"] == 180 and decision["method"] == "osd"
    assert not ocr.probed and decision["seconds"] == 0.1


@pytest.mark.parametrize("angle", [0, 90, 180, 270])
@pytest.mark.parametrize("error", [None, "OSD could not identify orientation"])
def test_weak_or_failed_osd_uses_ocr_without_falsifying_osd_confidence(angle, error):
    decision = detect(None, Detector(error=error, winner=angle), 5)
    assert decision["clockwise"] == angle and decision["accepted"]
    assert decision["method"] == "ocr_comparison" and decision["status"] == "accepted_ocr_comparison"
    assert decision["osd_confidence"] == 0.3 and decision["seconds"] == 0.5
    assert decision["osd_rotation_clockwise"] == (None if error else 0)
    assert decision["policy"]["min_words"] == 5 and decision["policy"]["psm"] == 11


def test_inconclusive_comparison_does_not_return_a_zero_degree_confirmation():
    ocr = Detector()
    ocr.orientation_evidence = lambda image: (
        [dict(clockwise=a, score=0.0, words=0, letters=0) for a in (0, 90, 180, 270)],
        0.4,
    )
    decision = detect(None, ocr, 5)
    assert not decision["accepted"] and decision["clockwise"] is None
    assert decision["status"] == "unresolved_ocr_comparison"


def test_probe_is_bounded_preserves_original_image_and_retains_errors(monkeypatch):
    ocr = object.__new__(OCR)
    ocr.config = SimpleNamespace(ocr=SimpleNamespace(languages="deu+eng", timeout_seconds=120))
    calls = []

    def recognize(image, **kwargs):
        calls.append((image.size, kwargs))
        if len(calls) == 2:
            raise RuntimeError("timeout")
        return dict(text=["Readable"], conf=[90])

    monkeypatch.setattr("participant_bench.ocr.pytesseract.image_to_data", recognize)
    with Image.new("RGB", (3000, 4000), "white") as image:
        before = image.tobytes()
        candidates, _ = ocr.orientation_evidence(image)
        assert image.size == (3000, 4000) and image.tobytes() == before
    assert len(calls) == 4 and all(max(size) <= MAX_SIDE for size, _ in calls)
    assert all(k["timeout"] == 15 and k["config"] == "--psm 11" and k["lang"] == "deu+eng" for _, k in calls)
    assert candidates[1]["error"] == "RuntimeError" and "timeout" not in json.dumps(candidates)
    assert choose(candidates) == (None, "rotation_probe_failed")


def source_pdf(folder, metadata=0):
    folder.mkdir()
    with pymupdf.open() as doc:
        p = doc.new_page(width=120, height=80)
        p.draw_rect(pymupdf.Rect(0, 0, 24, 16), color=(1, 0, 0), fill=(1, 0, 0))
        p.set_rotation(metadata)
        doc.save(folder / "synthetic.pdf")


@pytest.mark.parametrize("metadata", [0, 90, 180, 270])
@pytest.mark.parametrize("angle", [0, 90, 180, 270])
def test_common_image_and_docling_native_pdf_apply_metadata_and_fallback_once(tmp_path, metadata, angle):
    config = load_config(Path("configs/smoke.yaml"))
    config.pdf.auto_orient = True
    inputs = tmp_path / "input"
    source_pdf(inputs, metadata)
    original = file_hash(inputs / "synthetic.pdf")
    manifest = prepare(inputs, config, tmp_path / "prepared", Detector(winner=angle))
    p = manifest["pages"][0]
    assert p["pdf_rotation_metadata"] == metadata and p["additional_rotation_clockwise"] == angle
    assert p["orientation_method"] == "ocr_comparison" and not p["review_required"]
    assert p["orientation_confidence"] == 0.3 and p["orientation_evidence"]["accepted"]
    total = (metadata + angle) % 360
    with Image.open(tmp_path / "prepared" / p["image"]) as image:
        assert (image.width > image.height) == (total in (0, 180))
        point = {
            0: (4, 4),
            90: (image.width - 5, 4),
            180: (image.width - 5, image.height - 5),
            270: (4, image.height - 5),
        }[total]
        assert image.getpixel(point)[0] > 240 and image.getpixel(point)[1] < 20
        with pymupdf.open(stream=single_page_pdf(p), filetype="pdf") as doc:
            pix = doc[0].get_pixmap(dpi=config.pdf.dpi, alpha=False, colorspace=pymupdf.csRGB)
            assert (pix.width, pix.height) == image.size
            # Rerendering native vector content changes fractional edge pixels;
            # compare the directional marker, not antialiasing byte identity.
            with Image.frombytes("RGB", (pix.width, pix.height), pix.samples) as native:
                assert native.getpixel(point)[0] > 240 and native.getpixel(point)[1] < 20
    assert file_hash(inputs / "synthetic.pdf") == original
    assert manifest["orientation_implementation"] == VERSION


def test_old_unreviewed_manifest_cannot_silently_reuse_uncorrected_images(tmp_path):
    config = load_config(Path("configs/smoke.yaml"))
    config.pdf.auto_orient = True
    inputs = tmp_path / "input"
    source_pdf(inputs)
    manifest = prepare(inputs, config, tmp_path / "prepared", Detector())
    path = tmp_path / "prepared/manifest.json"
    assert validate_manifest(path, inputs, config)
    manifest.pop("orientation_implementation")
    write_json(path, manifest)
    with pytest.raises(ValueError, match="Ausrichtungsprüfung geändert"):
        validate_manifest(path, inputs, config)
    manifest["curated"] = True
    write_json(path, manifest)
    assert validate_manifest(path, inputs, config)["curated"]


def test_page_trace_separates_accepted_fallback_from_weak_osd(tmp_path):
    config = load_config(Path("configs/smoke.yaml"))
    config.pdf.auto_orient = True
    inputs = tmp_path / "input"
    source_pdf(inputs)
    manifest = prepare(inputs, config, tmp_path / "prepared", Detector())
    p = manifest["pages"][0]
    page = PageResult(
        run_id="test",
        document_id=p["document_id"],
        page_id=p["page_id"],
        page_number=1,
        method_id="vlm",
        status="success",
    )
    trace = page_trace(tmp_path, page, {}, manifest, [])
    assert trace["orientation_method"] == "ocr_comparison"
    assert trace["orientation_confidence"] == 0.3 and trace["orientation_evidence"]["accepted"]
    assert trace["additional_rotation_clockwise"] == 90


@pytest.mark.parametrize("angle", [0, 90, 180, 270])
def test_real_ocr_fallback_reads_synthetic_text_after_controlled_osd_failure(tmp_path, monkeypatch, angle):
    config = load_config(Path("configs/smoke.yaml"))
    config.cache_dir = str(tmp_path / "cache")
    try:
        ocr = OCR(config)
    except FileNotFoundError:
        pytest.skip("Real local Tesseract with the configured languages required")
    monkeypatch.setattr(ocr, "orientation", lambda image: (0, 0.0, "controlled OSD failure", 0.0))
    with pymupdf.open() as doc:
        page = doc.new_page(width=500, height=260)
        for i, line in enumerate(
            [
                "Readable printed information supports the orientation check.",
                "All four right angle positions use the same synthetic document.",
                "No participant names or reference values enter the decision.",
                "Insufficient evidence requires manual review of the page.",
            ]
        ):
            page.insert_text((20, 40 + i * 45), line, fontsize=12)
        pixels = page.get_pixmap(dpi=180, alpha=False)
    with Image.frombytes("RGB", (pixels.width, pixels.height), pixels.samples) as image:
        with image.rotate(-angle, expand=True) as rotated:
            decision = detect(rotated, ocr, 5)
    assert decision["method"] == "ocr_comparison" and decision["accepted"]
    assert decision["clockwise"] == (-angle) % 360
