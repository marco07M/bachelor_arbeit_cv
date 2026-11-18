"""Reference-first exclusions use saved row evidence, never OCR confidence or empty text."""

import pytest
from PIL import Image, ImageDraw
from test_roster_benchmark import page, prediction, ref, saved_run, write_reference

from participant_bench.config import Config
from participant_bench.io import file_hash, read_json, write_json
from participant_bench.roster_benchmark.config import BenchmarkConfig, MatchingConfig, ReferenceConfig
from participant_bench.roster_benchmark.evaluation import evaluate_run
from participant_bench.roster_benchmark.matching import page_predictions
from participant_bench.roster_benchmark.metrics import aggregate, course_metrics
from participant_bench.roster_benchmark.references import saved_reference
from participant_bench.rules import signature
from participant_bench.schema import Box


def unsigned(index=1, **kwargs):
    item = prediction(index=index, first="Zora", last="Quast", user="998877", code="XYZ", **kwargs)
    item.person.bbox = Box(x0=0, y0=.4, x1=1, y1=.45)
    item.person.signature_present = False
    item.person.signature_state = "empty"
    item.person.signature_method = "opencv_conservative"
    item.person.signature_bbox = Box(x0=.8, y0=.39, x1=.98, y1=.46)
    return item


def compare(items, references=None, **config):
    return course_metrics("123456", items, [ref()] if references is None else references,
                          MatchingConfig(exclude_probably_unsigned_extras=True, **config), ReferenceConfig())


@pytest.mark.parametrize("state", [True, False, None])
def test_reference_person_always_scored_despite_signature(state):
    item = unsigned()
    item.person.first_name.value, item.person.last_name.value = "Anna", "Weber"
    item.person.personnel_number.value, item.person.department.value = "001234", "MUC"
    item.person.signature_present = state
    item.person.signature_state = "uncertain" if state is None else "read" if state else "empty"
    score, rows, _, _ = compare([item])
    assert score["overall"]["reference_fields"] == score["overall"]["exact_fields"] == 4
    assert score["excluded_probably_unsigned_participants"] == 0
    assert score["participant_quality"]["identity_exact_participants"] == 1
    assert rows[0]["reference_assignment"] == "matched"


def test_probably_unsigned_extra_has_no_false_positives_but_missing_reference_stays():
    score, rows, fields, _ = compare([unsigned()])
    assert score["reference_participants"] == score["missing_participants"] == 1
    assert score["overall"]["reference_fields"] == score["overall"]["missing_fields"] == 4
    assert score["overall"]["predicted_fields"] == score["extra_participants"] == 0
    assert score["predicted_participants"] == 1 and score["evaluated_predicted_participants"] == 0
    assert score["excluded_probably_unsigned_participants"] == 1
    assert score["unsigned_exclusion"]["excluded_field_values"] == 4
    assert all(f["evaluation_status"] == "unassessed" and not f["prediction_contribution"]
               for f in fields if f["excluded_from_quality"])
    assert next(r for r in rows if r["excluded_from_quality"])["manual_review_required"] is False


def test_exclusion_changes_only_extra_precision_penalty_and_is_additive():
    score, *_ = compare([prediction(), unsigned()])
    before = score["unsigned_exclusion"]["before_exclusion"]
    after = score["overall"]
    assert before["exact_f1"] == pytest.approx(2 / 3) and after["exact_f1"] == 1
    for key in ("reference_fields", "exact_fields", "exact_recall", "field_coverage", "detected_similarity"):
        assert before[key] == after[key]
    pooled = aggregate([score, score])
    assert pooled["excluded_probably_unsigned_participants"] == 2
    assert pooled["unsigned_exclusion"]["before_exclusion"]["predicted_fields"] == 16
    assert pooled["schriftart_unassigned"]["participants"] == 0


@pytest.mark.parametrize("change", ["signed", "unknown", "no_bbox", "wrong_row", "full_page", "failed"])
def test_unreliable_or_signed_extra_keeps_penalties_and_manual_review(change):
    item = unsigned()
    if change == "signed":
        item.person.signature_present, item.person.signature_state = True, "read"
    elif change == "unknown":
        item.person.signature_present, item.person.signature_state = None, "uncertain"
    elif change == "no_bbox":
        item.person.bbox = None
    elif change == "wrong_row":
        item.person.signature_bbox = Box(x0=.8, y0=.7, x1=.98, y1=.75)
    elif change == "full_page":
        item.person.signature_method = None
    else:
        item.person.signature_state = "failed"
    score, rows, _, _ = compare([prediction(), item])
    assert score["extra_participants"] == score["unassigned_manual_review_participants"] == 1
    assert score["overall"]["predicted_fields"] == 8 and score["overall"]["exact_f1"] == pytest.approx(2 / 3)
    extra = next(r for r in rows if r["reference_row"] is None)
    assert extra["manual_review_required"] and not extra["excluded_from_quality"]


def test_similar_spelling_duplicate_and_id_conflicts_never_disappear():
    item = unsigned()
    item.person.first_name.value, item.person.last_name.value = "Anma", "Weber"
    score, rows, _, _ = compare([prediction(), item])
    extra = next(r for r in rows if r["reference_row"] is None)
    assert score["extra_participants"] == 1 and not extra["excluded_from_quality"]
    assert extra["reference_candidates"][0]["name_similarity"] == .875
    item.person.personnel_number.value = "001234"
    item.person.first_name.value, item.person.last_name.value = "Zora", "Quast"
    score, *_ = compare([prediction(), item])
    assert score["excluded_probably_unsigned_participants"] == 0
    score, *_ = compare([prediction(), prediction()])
    assert score["extra_participants"] == 1 and score["overall"]["exact_f1"] < 1


def test_matching_is_unchanged_and_wrong_spelling_retains_levenshtein():
    item = prediction(last="Muller")
    item.person.signature_present, item.person.signature_state = False, "empty"
    score, _, fields, _ = compare([item], [ref(last="Müller")])
    field = next(f for f in fields if f["field"] == "last_name")
    assert field["evaluation_status"] == "deviating" and field["similarity_percent"] == pytest.approx(100 * 5 / 6)
    assert score["overall"]["exact_recall"] == .75 and score["overall"]["field_coverage"] == 1


def test_name_swap_guard_is_conservative_even_when_swap_scoring_is_disabled():
    item = unsigned()
    item.person.first_name.value, item.person.last_name.value = "Weber", "Anna"
    score, rows, *_ = compare([prediction(), item], compare_name_orientations=False)
    extra = next(r for r in rows if r["reference_row"] is None)
    assert score["extra_participants"] == 1 and score["excluded_probably_unsigned_participants"] == 0
    assert extra["reference_candidates"][0]["name_similarity"] == 1
    assert score["overall"]["exact_fields"] == 4  # no new pair or exact-match credit


def detail_record(item):
    return dict(output_index=0, participant_row=item.person.bbox.model_dump(),
                region=dict(x0=0, y0=.39, x1=1, y1=.46), location_source="ocr_words", parse_status="valid",
                observation=dict(field_located=True, signature_present=False, evidence="blank_field"),
                signature_present=False, prior_signature_present=None)


@pytest.mark.parametrize("change,excluded", [("valid", True), ("guessed", False), ("wrong_person", False),
    ("contradiction", False), ("bad_parse", False), ("overlap", False), ("duplicate_record", False)])
def test_detail_record_must_belong_to_unique_current_row(tmp_path, change, excluded):
    item = unsigned(index=0)
    item.person.signature_method, item.person.signature_bbox = "local_vlm_detail", None
    record = detail_record(item)
    if change == "guessed":
        record["location_source"] = "local_vlm"
    elif change == "wrong_person":
        record["participant_row"]["y0"] = .3
    elif change == "contradiction":
        record["prior_signature_present"] = True
    elif change == "bad_parse":
        record["parse_status"] = "invalid"
    people = [item.person]
    if change == "overlap":
        people.append(item.person.model_copy(deep=True))
    current = page(people)
    write_json(tmp_path / f"raw-{current.page_id}.json", dict(signature_checks=[record] * (2 if change == "duplicate_record" else 1)))
    loaded = page_predictions(current, tmp_path)
    score, *_ = compare([prediction(index=99), *loaded])
    assert bool(score["excluded_probably_unsigned_participants"]) is excluded


def test_legacy_config_and_absent_reference_do_not_exclude():
    score, *_ = course_metrics("123456", [unsigned()], [ref()], MatchingConfig(), ReferenceConfig())
    assert score["extra_participants"] == 1
    assert score["unsigned_exclusion"]["enabled"] is False
    score, *_ = compare([unsigned()], [])
    assert score["excluded_probably_unsigned_participants"] == 0
    assert score["overall"]["exact_recall"] is None


def test_unreadable_reference_identity_or_page_sized_geometry_requires_review():
    score, *_ = compare([unsigned()], [ref(first="", last="", user="")])
    assert score["excluded_probably_unsigned_participants"] == 0
    item = unsigned()
    item.person.bbox = Box(x0=0, y0=0, x1=1, y1=1)
    score, *_ = compare([prediction(), item])
    assert score["extra_participants"] == 1 and score["excluded_probably_unsigned_participants"] == 0


def test_signed_detail_is_not_labelled_as_a_blank_field(tmp_path):
    item = unsigned(index=0)
    item.person.signature_present, item.person.signature_state = True, "read"
    item.person.signature_method, item.person.signature_bbox = "local_vlm_detail", None
    record = detail_record(item)
    record["signature_present"] = True
    record["observation"] = dict(field_located=True, signature_present=True, evidence="handwritten_mark")
    current = page([item.person])
    write_json(tmp_path / f"raw-{current.page_id}.json", dict(signature_checks=[record]))
    evidence = page_predictions(current, tmp_path)[0].signature_evidence
    assert evidence["row_evidence"] == "detail_handwritten_mark" and not evidence["probable_absence"]


@pytest.mark.parametrize("ink", [False, True])
def test_existing_blank_threshold_on_synthetic_development_images(ink):
    config = Config(methods=["ocr_rules"])
    with Image.new("RGB", (500, 100), "white") as image:
        if ink:
            ImageDraw.Draw(image).line([(20, 75), (150, 20), (220, 80), (400, 25)], fill="black", width=4)
        present, state, _ = signature(image, Box(x0=0, y0=0, x1=1, y1=1), {}, config)
    assert present is (None if ink else False)
    assert state == ("uncertain" if ink else "read")


@pytest.mark.parametrize("existing_raw", [False, True])
def test_real_report_consistency_exclusions_manual_review_and_historical_preservation(tmp_path, existing_raw):
    unsigned_item = unsigned()
    signed_item = unsigned(index=2)
    signed_item.person.first_name.value, signed_item.person.last_name.value = "Xeno", "Punkt"
    signed_item.person.signature_present, signed_item.person.signature_state = True, "read"
    signed_item.person.bbox = Box(x0=0, y0=.6, x1=1, y1=.65)
    current = page([prediction().person, unsigned_item.person, signed_item.person])
    source = saved_run(tmp_path / "run", [current])
    raw_path = source / "vlm" / f"raw-{current.page_id}.json"
    if existing_raw:
        write_json(raw_path, {})
    reference = tmp_path / "reference.csv"
    write_reference(reference)
    protected = {p: file_hash(p) for p in source.rglob("*") if p.is_file()}
    config = BenchmarkConfig(matching=MatchingConfig(exclude_probably_unsigned_extras=True))
    target, metrics = evaluate_run(source, reference, config, tmp_path, output=tmp_path / "report",
                                 scientific_options=dict(resamples=200, figures=False))
    assert all(file_hash(p) == h for p, h in protected.items())
    assert metrics["vlm"]["overall"]["predicted_fields"] == 8
    checks = read_json(target / "scientific/metric_audit_checks.json")
    assert checks["vlm"]["matches_metrics"]
    audit = read_json(target / "scientific/metric_audit.json")
    assert sum(r["participant_result"] == "excluded" for r in audit["participants"]) == 1
    reviews = read_json(target / "error_analysis/participants.json")
    assert sum(r["excluded_from_quality"] for r in reviews) == 1
    assert sum(r["reference_row"] is None and r["manual_review_required"] for r in reviews) == 1
    html = (target / "extraction_errors.html").read_text(encoding="utf8")
    assert "Manuelle Prüfung erforderlich" in html and "keine visuell bestätigte Tatsache" in html
    assert "Automatisch ausgeschlossen" in html and "Zora Quast" in html
    assert "Signatur / Unsicherheit" in (target / "report.html").read_text(encoding="utf8")
    write_json(raw_path, dict(signature_checks=[]))
    with pytest.raises(ValueError, match="Signaturbelege"):
        saved_reference(target)
