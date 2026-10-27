"""Manually authored synthetic references, leakage guards, analytical metrics and local end-to-end."""

import json
import shutil
import socket
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pymupdf
import pytest
import yaml
from PIL import Image

from participant_bench.calibration.confidence import (
    evaluate_policy,
    fit,
    predict,
    reliability,
    threshold_curve,
)
from participant_bench.calibration.dataset import (
    assign_groups,
    initialize,
    load_dataset,
    partitions,
    rows,
    split_dataset,
)
from participant_bench.calibration.experiment import better_on_audit, experiment, final_test, load_experiment
from participant_bench.calibration.metrics import text_metrics
from participant_bench.config import ImageConfig, load_config
from participant_bench.doctor import tesseract_command
from participant_bench.image_preprocessing import preprocess, rotate_box
from participant_bench.io import file_hash, read_json, write_csv
from participant_bench.synthetic import ROWS, add_table


def references(tmp_path, count=5):
    raw = tmp_path / "pdf"
    raw.mkdir()
    for index in range(count):
        with pymupdf.open() as doc:
            page = doc.new_page(width=595, height=842)
            add_table(page)
            page.insert_text((30, 400), f"Independent synthetic example {index}")
            doc.save(raw / f"{index}.pdf")
    target = initialize(raw, tmp_path / "ref")
    docs = rows(target / "documents.csv")
    for doc in docs:
        doc["grouping_reviewed"] = "true"
        doc["stratum"] = "synthetic"
    write_csv(target / "documents.csv", docs)
    pages = rows(target / "pages.csv")
    people = []
    for page in pages:
        page["reviewed"] = "true"
        for row in ROWS:
            person = dict(
                document_id=page["document_id"],
                page_number=page["page_number"],
                row_ref=row[0],
                bbox="",
                signature_present="unknown",
            )
            for name, value in zip(("first_name", "last_name", "personnel_number", "department"), row[1:]):
                person[name] = value
                person[name + "_state"] = "read"
            people.append(person)
    write_csv(target / "pages.csv", pages)
    write_csv(target / "participants.csv", people)
    split_dataset(target)
    return target


def test_manual_references_preserve_ids_and_group_splits(tmp_path):
    target = references(tmp_path, 10)
    dataset = load_dataset(target)
    assert all(p.participants[0].personnel_number.value == "00123" for p in dataset["pages"])
    parts = partitions(dataset)
    group_sets = {
        name: {p.dependency_group for p in parts[name]}
        for name in ("development", "validation_fit", "validation_audit", "test")
    }
    assert all(
        not left & right
        for i, left in enumerate(group_sets.values())
        for right in list(group_sets.values())[i + 1 :]
    )
    assert sum(len(group) for group in group_sets.values()) == 10
    before = file_hash(target / "participants.csv")
    with pytest.raises(ValueError, match="eingefroren"):
        split_dataset(target)
    assert file_hash(target / "participants.csv") == before


def test_groups_and_near_duplicate_metadata_never_cross_splits():
    documents = [
        dict(dependency_group=f"family-{i // 2}", stratum="scan" if i % 4 else "digital") for i in range(30)
    ]
    first = assign_groups(documents, seed=7)
    assert first == assign_groups(list(reversed(documents)), seed=7)
    assert set(first.values()) == {"development", "validation", "test"}
    with pytest.raises(ValueError):
        assign_groups(documents[:4])


def test_init_deduplicates_and_requires_human_group_approval(tmp_path):
    raw = tmp_path / "raw"
    raw.mkdir()
    with pymupdf.open() as doc:
        doc.new_page()
        doc.save(raw / "a.pdf")
    shutil.copy2(raw / "a.pdf", raw / "b.pdf")
    (raw / "bad.pdf").write_bytes(b"invalid")
    folder = initialize(raw, tmp_path / "refs")
    metadata = read_json(folder / "dataset.json")
    assert len(metadata["documents"]) == 1 and len(metadata["documents"][0]["duplicates"]) == 1
    assert metadata["errors"] and not rows(folder / "participants.csv")
    with pytest.raises(ValueError, match="grouping_reviewed"):
        split_dataset(folder)
    with pytest.raises(ValueError, match="überschreiben"):
        initialize(raw, folder)


def test_changed_groups_and_missing_page_review_are_rejected(tmp_path):
    target = references(tmp_path)
    pages = rows(target / "pages.csv")
    pages[0]["reviewed"] = "false"
    write_csv(target / "pages.csv", pages)
    with pytest.raises(ValueError, match="reviewed"):
        load_dataset(target)
    (target / "documents.csv").write_text("changed", encoding="utf-8")
    with pytest.raises(ValueError, match="verändert"):
        load_dataset(target)


def test_cer_wer_and_empty_references_do_not_invent_zero_error():
    scores = text_metrics("abc def", "abc deg")
    assert scores["cer"]["numerator"] == 1 and scores["cer"]["denominator"] == 7
    assert scores["wer"]["value"] == 0.5
    assert text_metrics("", "extra")["cer"] == {"numerator": 5, "denominator": 0, "value": None}


def test_reliability_ece_brier_and_one_boundary():
    report = reliability([0, 0.5, 1], [0, 1, 1])
    assert report["ece"] == pytest.approx(1 / 6)
    assert report["brier"] == pytest.approx(1 / 12)
    assert report["bins"][-1]["count"] == 1
    assert reliability([], [])["ece"] is None
    with pytest.raises(ValueError):
        reliability([1.1], [1])


def events():
    return [
        dict(
            document_id=f"d{i % 4}",
            field="first_name",
            correct=int(i >= 10),
            raw_score=i / 19,
            has_value=True,
        )
        for i in range(20)
    ]


@pytest.mark.parametrize("method", ["sigmoid", "isotonic"])
def test_calibrators_fit_monotonically_and_serialize(method):
    model = fit(events(), method, min_samples=10, min_class=2, min_documents=2)
    assert model["status"] == "fitted"
    probabilities = [predict(json.loads(json.dumps(model)), value) for value in np.linspace(0, 1, 20)]
    assert probabilities == sorted(probabilities) and probabilities[-1] > probabilities[0]
    assert fit(events()[:5], method)["status"] == "insufficient_data"
    assert predict(model, None) is None


def test_thresholds_require_independent_audit_and_preserve_failed_fields():
    model = dict(status="fitted", method="isotonic", x=[0, 1], y=[0, 1])
    samples = [
        dict(document_id="d", field="first_name", raw_score=score, correct=label, has_value=True)
        for score, label in ((0.1, 0), (0.9, 1), (1.0, 1))
    ]
    samples += [dict(document_id="d", field="first_name", raw_score=None, correct=0, has_value=False)]
    curve = threshold_curve(samples, model)
    row = next(row for row in curve if row["threshold"] == 0.9)
    assert row["accepted"] == 2 and row["precision"]["value"] == 1 and row["review"] == 2
    policy = {
        name: dict(model=model, threshold=0.9, status="pending_audit", target_precision=0.9)
        for name in ("first_name", "last_name", "personnel_number", "department")
    }
    assert all(row["decision"] != "accepted" for row in evaluate_policy(samples, policy)["decisions"])
    result = evaluate_policy(samples, policy, audit=True, min_accepted=2)
    assert sum(row["decision"] == "accepted" for row in result["decisions"]) == 2
    assert sum(row["decision"] == "failed" for row in result["decisions"]) == 1
    assert policy["last_name"]["status"] == "review_only"


def test_image_crop_and_scale_return_original_coordinates():
    with Image.new("RGB", (1000, 800), "white") as image:
        transformed, mapper, metadata = preprocess(image, ImageConfig(crop=(0.1, 0.25, 0.9, 0.75), scale=2))
        assert transformed.size == (1600, 800)
        assert mapper(0, 0, 1600, 800) == pytest.approx(dict(x0=0.1, y0=0.25, x1=0.9, y1=0.75))
        assert metadata["deskew_degrees"] == 0
        transformed.close()
    box = dict(x0=0.1, y0=0.2, x1=0.3, y1=0.4)
    assert rotate_box(rotate_box(box, 90), 270) == pytest.approx(box)


def test_external_configuration_is_rejected_without_loading_credentials(tmp_path):
    external = tmp_path / "external.yaml"
    external.write_text(
        yaml.safe_dump(
            dict(
                methods=["vlm"],
                models={"vlm": dict(backend="external_test", options={"setting": "synthetic"})},
            )
        ),
        encoding="utf-8",
    )
    config = tmp_path / "experiment.yaml"
    config.write_text(yaml.safe_dump(dict(base_config=str(external))), encoding="utf-8")
    with pytest.raises(ValueError, match="lokal"):
        load_experiment(config)


def test_no_quality_improvement_cannot_be_promoted():
    base = dict(
        structured={
            "fields": {},
            "signature": {"prf": {"recall": {"value": None}}},
            "counts": {"technical_failure_pages": 0},
            "field_prf": {"f1": {"value": 0.8}},
            "assignment": {"complete_row_coverage": {"value": 0.7}},
        },
        runtime={"full_pipeline_charged_seconds": 10},
    )
    options = SimpleNamespace(minimum_quality_gain=0, minimum_runtime_gain=0.05)
    assert better_on_audit(base, base, options) == (False, "no_independent_improvement")
    candidate = json.loads(json.dumps(base))
    candidate["structured"]["field_prf"]["f1"]["value"] = 0.9
    assert better_on_audit(candidate, base, options)[0]


def test_local_pdf_text_experiment_freeze_resume_and_one_final_test(tmp_path, monkeypatch):
    target = references(tmp_path)
    baseline = load_config(Path("configs/smoke.yaml"))
    try:
        tesseract_command(baseline)
    except FileNotFoundError:
        pytest.skip("Local Tesseract setup required")
    baseline.pdf.auto_orient = False
    baseline.ocr.source = "prefer_pdf"
    baseline.cache_dir = str(tmp_path / "cache")
    base_path = tmp_path / "base.yaml"
    base_path.write_text(yaml.safe_dump(baseline.model_dump()), encoding="utf-8")
    experiment_config = tmp_path / "experiment.yaml"
    experiment_config.write_text(yaml.safe_dump(dict(base_config=str(base_path))), encoding="utf-8")
    monkeypatch.setattr("participant_bench.runner.environment", lambda *args: {})

    def no_network(*args, **kwargs):
        raise AssertionError("Calibration attempted network access")

    def no_image_ocr(*args, **kwargs):
        raise AssertionError("Pure digital table should use PDF text")

    monkeypatch.setattr(socket, "create_connection", no_network)
    monkeypatch.setattr("participant_bench.ocr.pytesseract.image_to_data", no_image_ocr)
    original = file_hash(target / "participants.csv")
    output = experiment(target, experiment_config, tmp_path / "c")
    frozen = read_json(output / "frozen.json")
    assert frozen["selected"] == "baseline" and not frozen["test_used"]
    assert experiment(target, experiment_config, output, resume=True) == output
    assert (output / "report.html").exists() and (output / "reliability-baseline.png").exists()
    assert all(field["status"] == "review_only" for field in frozen["policy"].values())
    assert not {p.stem for p in (output / "i").rglob("*.pdf")} & set(frozen["partition_documents"]["test"])
    assert (
        read_json(output / "comparison.json")["development"]["baseline"]["structured"]["overall_exact_match"][
            "value"
        ]
        == 1
    )
    test = final_test(output)
    assert (test / "final_metrics.json").exists() and (test / "decisions.csv").exists()
    assert "test" in read_json(test / "final_metrics.json")
    with pytest.raises(FileExistsError):
        final_test(output)
    assert file_hash(target / "participants.csv") == original
    # Applying the policy to fresh inputs must not read any reference files.
    from participant_bench.calibration.apply import apply_frozen

    (target / "participants.csv").rename(target / "held-back.csv")
    applied = apply_frozen(output, tmp_path / "pdf", tmp_path / "applied")
    assert read_json(applied / "application.json")["quality_measured"] is False
    frozen["selected"] = "tampered"
    (output / "frozen.json").write_text(json.dumps(frozen), encoding="utf-8")
    with pytest.raises(ValueError, match="verändert"):
        final_test(output)


def test_calibration_does_not_learn_from_duplicate_families():
    samples = [event | {"dependency_group": "one-template"} for event in events()]
    assert fit(samples, min_samples=10, min_class=2, min_documents=2)["status"] == "insufficient_data"


def test_calibrator_with_worse_holdout_brier_remains_review_only():
    model = dict(status="fitted", method="isotonic", x=[0, 1], y=[0.8, 0.8])
    samples = [
        dict(document_id="d", field="first_name", raw_score=0.99, correct=1, has_value=True) for _ in range(3)
    ]
    policy = {
        name: dict(model=model, threshold=0.7, status="pending_audit", target_precision=0.7)
        for name in ("first_name", "last_name", "personnel_number", "department")
    }
    audit = evaluate_policy(samples, policy, audit=True, min_accepted=2)
    assert policy["first_name"]["status"] == "review_only"
    assert not any(row["decision"] == "accepted" for row in audit["decisions"])


@pytest.mark.parametrize("threshold", ["none", "otsu", "adaptive"])
def test_experimental_image_options_preserve_coordinate_frame(threshold):
    from PIL import ImageDraw

    with Image.new("RGB", (300, 200), "white") as image:
        ImageDraw.Draw(image).text((50, 70), "Synthetic sample", fill="black")
        processed, mapper, metadata = preprocess(
            image, ImageConfig(grayscale=True, contrast=1.2, denoise=3, deskew=True, threshold=threshold)
        )
        assert processed.size == image.size and abs(metadata["deskew_degrees"]) <= 7
        box = mapper(40, 60, 120, 40)
        assert 0 <= box["x0"] < box["x1"] <= 1 and 0 <= box["y0"] < box["y1"] <= 1
        processed.close()


def test_hybrid_pdf_heading_does_not_hide_scanned_body(tmp_path):
    import io

    from participant_bench.pdf import prepare

    config = load_config(Path("configs/smoke.yaml"))
    config.pdf.auto_orient = False
    config.ocr.source = "prefer_pdf"
    raw = tmp_path / "raw"
    raw.mkdir()
    stream = io.BytesIO()
    with Image.new("RGB", (500, 500), "white") as image:
        image.save(stream, format="PNG")
    with pymupdf.open() as document:
        page = document.new_page()
        page.insert_text((50, 50), "A digital heading only")
        page.insert_image(pymupdf.Rect(20, 100, 550, 700), stream=stream.getvalue())
        document.save(raw / "hybrid.pdf")
    manifest = prepare(raw, config, tmp_path / "prepared")
    assert manifest["pages"][0]["embedded_text_layer"]
    assert not manifest["pages"][0]["embedded_words"]
    assert manifest["pages"][0]["embedded_text_rejection"] == "substantial_raster_content"
