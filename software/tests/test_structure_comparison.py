"""Comparison reports must not reward an ID merely because it is similar."""

import importlib.util
from pathlib import Path

import pytest


@pytest.fixture
def comparison():
    spec = importlib.util.spec_from_file_location("structure_comparison", "scripts/compare_structure_runs.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def field(value, exact="False", assessable="True"):
    return dict(
        method="paddle_llm",
        class_id="123456",
        reference_row="2",
        field="user_id",
        reference_value="000007",
        prediction_value=value,
        exact=exact,
        assessable=assessable,
        page_number="1",
    )


def test_wrong_id_is_corrected_only_after_an_exact_match(comparison):
    counts, rows = comparison.paired_fields([field("000008")], [field("000007", exact="True")])
    assert counts["paddle_llm"]["corrected"] == 1
    assert rows[0]["baseline_value"] == "000008" and rows[0]["transition"] == "corrected"


def test_masked_exclusion_does_not_become_a_fake_correction(comparison):
    counts, rows = comparison.paired_fields(
        [field("XXXXXX", assessable="False")], [field("000007", exact="True")]
    )
    assert counts["paddle_llm"]["not_comparable"] == 1
    assert rows[0]["transition"] == "not_comparable"


def test_reference_change_is_rejected(comparison):
    with pytest.raises(ValueError, match="dieselbe"):
        comparison.paired_fields([field("000007")], [dict(field("000007"), reference_value="000009")])


def test_mismatched_input_images_are_rejected_before_evaluation(comparison, tmp_path):
    from participant_bench.io import write_json

    roots = [tmp_path / "before", tmp_path / "after"]
    for index, root in enumerate(roots):
        write_json(
            root / "manifest.json",
            dict(pages=[dict(document_id="doc", page_number=1, include=True, image_sha256=str(index))]),
        )
    with pytest.raises(ValueError, match="Bild-Hashes"):
        comparison.compare(*roots, Path("not-read.xlsx"), tmp_path / "result")


def test_manual_rotation_mismatch_is_rejected_even_with_same_original_image(comparison, tmp_path):
    from participant_bench.io import write_json

    roots = [tmp_path / "before", tmp_path / "after"]
    for index, root in enumerate(roots):
        page = dict(document_id="doc", page_number=1, include=True, image_sha256="same-original")
        write_json(root / "manifest.json", dict(pages=[page]))
        write_json(root / "effective_pages.json", [dict(page, run_image_sha256=str(index))])
    with pytest.raises(ValueError, match="Laufbilder unterscheiden"):
        comparison.compare(*roots, Path("not-read.xlsx"), tmp_path / "result")
