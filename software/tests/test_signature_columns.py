"""Signature columns are given; localization and blank-cell evidence remain necessary."""

from copy import deepcopy
from pathlib import Path

import pytest
from PIL import Image, ImageDraw
from test_roster_benchmark import prediction, ref, write_reference

from participant_bench.column_context import geometry, resolve
from participant_bench.config import load_config
from participant_bench.io import file_hash, read_json, read_jsonl, write_json
from participant_bench.roster_benchmark.config import BenchmarkConfig, MatchingConfig, ReferenceConfig
from participant_bench.roster_benchmark.evaluation import evaluate_run
from participant_bench.roster_benchmark.matching import page_predictions
from participant_bench.roster_benchmark.metrics import course_metrics
from participant_bench.rules import inspect_signature_cells
from participant_bench.schema import TEXT_FIELDS, Box, PageResult
from participant_bench.signatures import detail_image

EDGES = [0.05, .25, .45, .6, .75, .95]


def settings():
    config = load_config(Path("configs/local.yaml"))
    config.signature.backend = "opencv"
    config.rules.columns = {}
    return config


def words(header=True):
    headers = ["Vorname", "Nachname", "Benutzer", "Organisation", "Unterschrift"]
    rows = [(headers, .2, 1)] if header else []
    rows += [(["Zora", "Quast", "998877", "XYZ", "OCR-GEKRITZEL"], .33, 2)]
    return dict(words=[dict(text=text, bbox=dict(x0=EDGES[c]+.01, x1=EDGES[c+1]-.01, y0=y, y1=y+.02),
                           line=[1, 1, line], ocr_confidence=1 if c == 4 else 90)
                       for texts, y, line in rows for c, text in enumerate(texts)])


def grid(ink=False, edges=EDGES):
    image = Image.new("RGB", (1000, 1000), "white")
    draw = ImageDraw.Draw(image)
    for x in edges:
        draw.line((x*1000, 100, x*1000, 800), fill="black", width=2)
    for y in (.3, .4, .5, .6):
        draw.line((50, y*1000, 950, y*1000), fill="black", width=2)
    if ink:
        draw.line([(800, 320), (840, 380), (900, 330)], fill="black", width=4)
    return image


def person():
    item = prediction(first="Zora", last="Quast", user="998877", code="XYZ")
    item.person.bbox = Box(x0=.06, x1=.74, y0=.33, y1=.35)
    return item.person


def inspect(people, image, raw=None, previous=None, document="doc", number=1):
    raw = raw if raw is not None else dict(ocr=words())
    context = inspect_signature_cells(people, image, raw, settings(), previous,
                                     document_id=document, page_number=number)
    return raw, context


def test_header_position_and_compatible_following_page_use_only_image_presence():
    first, second = person(), person()
    before = deepcopy(first.model_dump())
    with grid() as image:
        raw, context = inspect([first], image)
        following, _ = inspect([second], image, dict(ocr=words(False)), context, number=2)
    assert first.signature_present is second.signature_present is False
    assert raw["signature_cell_checks"][0]["row_basis"] == "measured_grid_lines"
    assert raw["signature_cell_checks"][0]["cells"][0]["bbox"]["x0"] == pytest.approx(.75, abs=.002)
    traces = following["signature_column_mapping"]["mapping_provenance"]
    assert any(t["status"] == "inherited_from_previous_page" and t["source_page"] == 1 for t in traces)
    # Even a low-confidence OCR pseudo-transcription in the signature cell is irrelevant.
    assert all(getattr(first, name).model_dump() == before[name] for name in TEXT_FIELDS)
    assert first.bbox.model_dump() == before["bbox"]


@pytest.mark.parametrize("kind", ["other_pdf", "changed_grid", "no_grid", "earlier_page"])
def test_unsafe_signature_column_inheritance_is_not_used(kind):
    with grid() as image:
        _, context = inspect([person()], image)
    image = grid(edges=[.05, .25, .45, .6, .85, .95]) if kind == "changed_grid" else grid()
    if kind == "no_grid":
        image.close()
        image = Image.new("RGB", (1000, 1000), "white")
    row = person()
    try:
        raw, _ = inspect([row], image, dict(ocr=words(False)), context,
                         document="other" if kind == "other_pdf" else "doc",
                         number=1 if kind == "earlier_page" else 2)
    finally:
        image.close()
    assert row.signature_present is None
    assert raw["signature_column_mapping"]["assumed_present"]
    assert not raw["signature_cell_checks"][0]["reliable_blank"]


def test_text_prefix_continuation_does_not_prove_missing_trailing_signature_column():
    mapping = dict(first_name={0}, last_name={1}, signature={2})
    _, context, _ = resolve(mapping, {}, geometry(3, boundaries=[0, .3, .6, 1]),
                             document_id="doc", page_number=1, has_header=True)
    _, _, trace = resolve({}, {}, geometry(2, boundaries=[0, .3, .6]), context, document_id="doc", page_number=2)
    row = person()
    with Image.new("RGB", (1000, 1000), "white") as image:
        raw, _ = inspect([row], image, dict(assignment=dict(document_column_mapping=trace)), number=2)
    assert row.signature_present is None and not raw["signature_column_mapping"]["intervals"]


@pytest.mark.parametrize("ink,prior,expected", [(False, None, False), (True, None, None),
    (True, True, True), (False, True, None), (True, False, None)])
def test_blank_ink_and_conflicting_presence_keep_distinct_decisions(tmp_path, ink, prior, expected):
    row = person()
    row.signature_present, row.signature_state = prior, "uncertain" if prior is None else "read" if prior else "empty"
    with grid(ink) as image:
        raw, _ = inspect([row], image)
    assert row.signature_present is expected
    page = PageResult(run_id="test", document_id="doc", page_id="doc-p0001", page_number=1,
                      method_id="vlm", status="success", parse_status="valid", participants=[row])
    write_json(tmp_path / "raw-doc-p0001.json", raw)
    predictions = page_predictions(page, tmp_path)
    result, cases, *_ = course_metrics("123456", predictions, [ref()],
        MatchingConfig(exclude_probably_unsigned_extras=True), ReferenceConfig())
    assert result["excluded_probably_unsigned_participants"] == int(expected is False)
    assert result["overall"]["reference_fields"] == result["overall"]["missing_fields"] == 4
    if expected is not False:
        assert next(r for r in cases if r["reference_row"] is None)["manual_review_required"]


@pytest.mark.parametrize("kind", ["no_position", "unknown_row", "text_band_only", "overlap", "guessed_row"])
def test_missing_signature_localization_never_means_unsigned(kind):
    row = person()
    raw = dict(ocr=words()) if kind != "no_position" else {}
    people = [row]
    if kind == "unknown_row":
        row.bbox = None
    elif kind == "overlap":
        people.append(row.model_copy(deep=True))
    elif kind == "guessed_row":
        raw["signature_checks"] = [dict(output_index=0, location_source="local_vlm")]
    image = grid() if kind != "text_band_only" else Image.new("RGB", (1000, 1000), "white")
    try:
        raw, _ = inspect(people, image, raw)
    finally:
        image.close()
    assert all(p.signature_present is None for p in people)
    assert not any(r["reliable_blank"] for r in raw["signature_cell_checks"])


def test_signature_column_cannot_overlap_a_text_target():
    mapping = dict(first_name={0}, last_name={1}, signature={1})
    _, _, trace = resolve(mapping, {}, geometry(2, boundaries=[0, .5, 1]),
                           document_id="doc", page_number=1, has_header=True)
    row = person()
    row.bbox = Box(x0=0, y0=.3, x1=1, y1=.4)
    with Image.new("RGB", (1000, 1000), "white") as image:
        raw, _ = inspect([row], image, dict(assignment=dict(document_column_mapping=trace)))
    assert row.signature_present is None
    assert raw["signature_column_mapping"]["status"] == "ambiguous_column_position"


def test_long_signature_stroke_is_not_used_as_a_row_boundary():
    mapping = dict(first_name={0}, last_name={1}, signature={2})
    _, _, trace = resolve(mapping, {}, geometry(3, boundaries=[0, .2, .4, 1]),
                           document_id="doc", page_number=1, has_header=True)
    row = person()
    row.bbox = Box(x0=.05, x1=.35, y0=.33, y1=.35)
    raw = dict(assignment=dict(document_column_mapping=trace))
    with Image.new("RGB", (1000, 1000), "white") as image:
        draw = ImageDraw.Draw(image)
        for y in (.3, .4):
            draw.line((0, y*1000, 999, y*1000), fill="black", width=2)
        draw.line((500, 360, 950, 360), fill="black", width=4)
        inspect([row], image, raw)
    assert row.signature_present is None
    assert raw["signature_cell_checks"][0]["cells"][0]["bbox"]["y1"] == pytest.approx(.4, abs=.003)


def test_contradiction_survives_another_negative_detail_response(tmp_path):
    from test_signature_details import DetailDouble

    from participant_bench.runner import signature_details

    config = settings()
    config.cache_dir = str(tmp_path / "cache")
    row = person()
    row.signature_present, row.signature_state = True, "read"
    current = PageResult(run_id="test", document_id="doc", page_id="doc-p0001", page_number=1,
                         method_id="vlm", status="success", parse_status="valid", participants=[row])
    raw = dict(ocr=words())
    model = DetailDouble(config, dict(field_located=True, signature_present=False, evidence="blank_field"))
    with grid() as image:
        signature_details(current, raw, image, model, config, tmp_path)
    assert raw["signature_cell_checks"][0]["conflict"]
    assert row.signature_present is None and row.signature_state == "uncertain"
    write_json(tmp_path / "raw-doc-p0001.json", raw)
    loaded = page_predictions(current, tmp_path)[0]
    assert not loaded.signature_evidence["probable_absence"]


@pytest.mark.parametrize("mark_second", [False, True])
def test_multiple_signature_columns_require_all_cells_blank(mark_second):
    mapping = dict(first_name={0}, last_name={1}, signature={2, 4})
    _, _, trace = resolve(mapping, {}, geometry(5, boundaries=[0, .2, .4, .6, .8, 1]),
                           document_id="doc", page_number=1, has_header=True)
    row = person()
    row.bbox = Box(x0=0, y0=.3, x1=1, y1=.4)
    raw = dict(assignment=dict(document_column_mapping=trace))
    with Image.new("RGB", (1000, 1000), "white") as image:
        if mark_second:
            ImageDraw.Draw(image).line([(830, 320), (900, 380)], fill="black", width=4)
        inspect([row], image, raw)
    assert len(raw["signature_cell_checks"][0]["cells"]) == 2
    assert row.signature_present is (None if mark_second else False)


def test_detail_crop_uses_only_signature_cells_and_keeps_original_pixels():
    config = settings()
    with Image.new("RGB", (1000, 1000), "white") as image:
        draw = ImageDraw.Draw(image)
        draw.rectangle((100, 310, 500, 390), fill="black")  # Text column: must not enter selected cells.
        draw.rectangle((800, 320, 900, 380), fill="red")
        region = Box(x0=0, x1=1, y0=.3, y1=.4)
        cells = [dict(bbox=dict(x0=.75, x1=.95, y0=.3, y1=.4))]
        with detail_image(image, region, .3, config, cells=cells) as crop:
            assert crop.getpixel((60, crop.height-50)) == (255, 0, 0)
            assert crop.getpixel((300, crop.height-50)) == (255, 255, 255)


def test_runner_checks_compatible_following_signature_cells_without_vlm(tmp_path, monkeypatch):
    import pymupdf

    from participant_bench import runner

    config = settings()
    config.methods = ["ocr_llm"]
    config.pdf.auto_orient = False
    config.output_dir, config.cache_dir = str(tmp_path / "runs"), str(tmp_path / "cache")
    raw_dir = tmp_path / "input"
    raw_dir.mkdir()
    with pymupdf.open() as pdf:
        for _ in range(2):
            sheet = pdf.new_page(width=1000, height=1000)
            for x in EDGES:
                sheet.draw_line((x*1000, 100), (x*1000, 800), color=(0, 0, 0), width=2)
            for y in (.3, .4, .5, .6):
                sheet.draw_line((50, y*1000), (950, y*1000), color=(0, 0, 0), width=2)
        pdf.save(raw_dir / "123456.pdf")

    class OCRDouble:
        def __init__(self, config):
            self.identity, self.calls = {}, 0

        def recognize(self, image, image_hash, **kwargs):
            self.calls += 1
            return dict(words(header=self.calls == 1), cache_hit=False, elapsed_seconds=.01, text="")

    class ModelDouble:
        def __init__(self, method, config, progress=None):
            self.calls = 0

        def extract(self, image, data):
            self.calls += 1
            row = person()
            row.personnel_number.value = str(998876+self.calls)
            return [row], [dict(parse_status="valid")], "success", .01

        def resources(self):
            return dict(calls=self.calls, load_seconds=0, warmup_calls=0)

        def close(self):
            pass

    monkeypatch.setattr(runner, "OCR", OCRDouble)
    monkeypatch.setattr(runner, "LocalModel", ModelDouble)
    monkeypatch.setattr(runner, "environment", lambda *args: {})
    output, _ = runner.run(config, raw_dir)
    pages = read_jsonl(output / "ocr_llm/extractions.jsonl")
    assert len(pages) == 2 and all(p["participants"][0]["signature_present"] is False for p in pages)
    following = read_json(output / "ocr_llm" / f"raw-{pages[1]['page_id']}.json")
    assert any(t["status"] == "inherited_from_previous_page" for t in following["signature_column_mapping"]["mapping_provenance"])
    assert all(p["calls"] == 1 for p in pages)  # No additional VLM/existence detection calls.
    protected = {p: file_hash(p) for p in output.rglob("*") if p.is_file()}
    reference = tmp_path / "reference.csv"
    write_reference(reference)
    target, metrics = evaluate_run(output, reference,
        BenchmarkConfig(matching=MatchingConfig(exclude_probably_unsigned_extras=True)), tmp_path,
        output=tmp_path / "comparison", scientific_options=dict(resamples=200, figures=False))
    score = metrics["ocr_llm"]
    assert score["excluded_probably_unsigned_participants"] == 2 and score["extra_participants"] == 0
    assert score["overall"]["predicted_fields"] == 0 and score["overall"]["missing_fields"] == 4
    assert all(file_hash(p) == h for p, h in protected.items())
    checks = read_json(target / "scientific/metric_audit_checks.json")
    assert checks["ocr_llm"]["matches_metrics"]
    html = (target / "extraction_errors.html").read_text(encoding="utf8")
    assert "Originale Signaturzelle 1" in html and "Manuelle Prüfung erforderlich" in html
    assert "Keine Signaturtranskription" in html
