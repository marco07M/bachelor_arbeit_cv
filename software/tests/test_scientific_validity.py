"""Supplementary metrics must not change baseline scores or hide false negatives/extras."""

from copy import deepcopy
from types import SimpleNamespace

import pytest
from test_detected_similarity import FirstTable
from test_document_availability import checked, unit_case
from test_roster_benchmark import prediction, ref
from test_scientific_evaluation import frozen_report

from participant_bench.io import read_json, write_json, write_jsonl
from participant_bench.roster_benchmark.config import BenchmarkConfig
from participant_bench.roster_benchmark.metrics import course_metrics
from participant_bench.roster_benchmark.report import percent
from participant_bench.roster_benchmark.scientific import reanalyze
from participant_bench.roster_benchmark.scientific_efficiency import technical_observations
from participant_bench.roster_benchmark.scientific_validity import (
    anls_credit,
    evidence_axes,
    field_projection,
    load_pages,
    page_strata,
    page_template,
    raw_text_coverage,
    row_consistency,
)
from participant_bench.schema import PageResult


def decisions(predictions=None, references=None, *, swap=False):
    config = BenchmarkConfig()
    config.matching.compare_name_orientations = swap
    score, rows, fields, _ = course_metrics(
        "123456",
        predictions if predictions is not None else [prediction()],
        references or [ref()],
        config.matching,
        config.reference,
        score_original_roles=not swap,
    )
    return score, rows, fields, config


def test_coverage_detected_similarity_anls_and_legacy_have_different_denominators():
    score, rows, fields, config = decisions([prediction(user=None, code=None)])
    before = deepcopy((score, rows, fields))
    result = field_projection(fields, anls=True)
    assert result["field_coverage"] == 0.5 and result["detected_similarity"] == 1
    assert result["anls"] == 0.5 and result["anls_credit"] == 2
    assert result["soft_f1"] == pytest.approx(2 / 3)
    assert (score, rows, fields) == before
    assert field_projection(fields)["anls"] is None


@pytest.mark.parametrize(
    "value,credit", [(0, 0), (0.49, 0), (0.5, 0), (0.50001, 0.50001), (0.9, 0.9), (1, 1)]
)
def test_anls_cutoff_including_exact_boundary(value, credit):
    assert anls_credit(dict(reference_contribution=1, similarity=value)) == credit
    assert anls_credit(dict(reference_contribution=0, similarity=value)) == 0


def test_no_extraction_is_zero_anls_but_undefined_detected_similarity():
    score, rows, fields, config = decisions([])
    result = field_projection(fields, anls=True)
    assert result["anls"] == 0 and result["detected_similarity"] is None
    assert field_projection([], anls=True)["anls"] is None
    assert row_consistency(rows, fields, config.matching)["row_consistency"] == 0


def test_typos_and_extra_predictions_do_not_improve_anls_or_exact_scores():
    base, _, fields, _ = decisions([prediction(first="Anma")])
    result = field_projection(fields, anls=True)
    assert result["anls"] == pytest.approx(0.9375)
    extra, _, extra_fields, _ = decisions(
        [prediction(first="Anma"), prediction(first="Xxx", last="Yyy", user="9999", code="ZZZ")]
    )
    assert field_projection(extra_fields, anls=True)["anls"] == result["anls"]
    assert extra["overall"]["exact_f1"] < base["overall"]["exact_f1"]


def test_row_consistency_requires_original_roles_even_in_swap_sensitivity():
    _, rows, fields, config = decisions([prediction(first="Weber", last="Anna")], swap=True)
    assert rows[0]["identity_exact"]  # The existing swap view is deliberately tolerant.
    result = row_consistency(rows, fields, config.matching)
    assert result["eligible_rows"] == 1 and result["correct_rows"] == 0
    _, rows, fields, config = decisions([prediction(code="WRONG")])
    assert row_consistency(rows, fields, config.matching)["correct_rows"] == 1  # Organization is separate.


def test_partial_reference_and_ambiguous_identity_do_not_confirm_triples():
    _, rows, fields, config = decisions(references=[ref(user="")])
    assert row_consistency(rows, fields, config.matching)["row_consistency"] is None
    _, rows, fields, config = decisions()
    rows[0]["identity_exact"] = False
    assert row_consistency(rows, fields, config.matching)["correct_rows"] == 0


def page_fixture():
    fields, ctx, _ = unit_case()
    _, rows, fields, _ = decisions([])
    return ctx, rows, fields, page_template(ctx, rows)


def test_unlocalized_missing_people_stay_unknown_and_all_strata_reconcile():
    ctx, rows, fields, _ = page_fixture()
    pages, locations, _ = load_pages(None, ctx, rows)
    result = page_strata(rows, fields, pages, locations, anls=True)
    unknown = next(r for r in result if r["feature"] == "position" and r["level"] == "unknown")
    assert unknown["overall"]["reference_fields"] == 4 and unknown["overall"]["missing_fields"] == 4
    assert sum(r["overall"]["reference_fields"] for r in result if r["feature"] == "position") == 4
    assert next(r for r in result if r["level"] == "first")["overall"]["exact_recall"] is None


def annotated_page(data):
    p = data["pages"][1]
    p.update(
        role="continuation",
        header="absent",
        scan_quality="degraded",
        independent_of_predictions=True,
        reviewer="synthetic",
        reviewed_at="2026-11-17",
        note="Original inspected",
    )
    r = data["participants"][0]
    r.update(
        document_id="doc",
        page_number=2,
        independent_of_predictions=True,
        reviewer="synthetic",
        reviewed_at="2026-11-17",
        anchor_note="Independent identity anchor",
    )


def test_independent_page_labels_keep_missing_person_in_correct_group(tmp_path):
    ctx, rows, fields, data = page_fixture()
    annotated_page(data)
    path = tmp_path / "pages.json"
    write_json(path, data)
    pages, locations, _ = load_pages(path, ctx, rows)
    result = page_strata(rows, fields, pages, locations)
    group = next(r for r in result if r["level"] == "continuation_headerless")
    assert group["participants"] == 1 and group["overall"]["missing_fields"] == 4
    assert group["overall"]["exact_recall"] == 0


@pytest.mark.parametrize(
    "bad",
    [
        "binding",
        "role",
        "independence",
        "reviewer",
        "date",
        "original",
        "foreign",
        "duplicate",
        "nonparticipant",
    ],
)
def test_page_annotation_rejects_unsupported_or_prediction_based_groups(tmp_path, bad):
    ctx, rows, _, data = page_fixture()
    annotated_page(data)
    if bad == "binding":
        data["binding"] = {}
    elif bad == "role":
        data["pages"][1]["role"] = "guessed"
    elif bad == "independence":
        data["participants"][0]["independent_of_predictions"] = False
    elif bad == "reviewer":
        data["pages"][1]["reviewer"] = ""
    elif bad == "date":
        data["pages"][1]["reviewed_at"] = "yesterday"
    elif bad == "original":
        ctx["documents"]["doc"]["verified"] = False
    elif bad == "foreign":
        data["participants"][0]["page_number"] = 3
    elif bad == "duplicate":
        data["participants"].append(data["participants"][0])
    elif bad == "nonparticipant":
        data["pages"][1]["role"] = "non_participant"
    path = tmp_path / "pages.json"
    write_json(path, data)
    with pytest.raises(ValueError):
        load_pages(path, ctx, rows)


def test_multiple_error_axes_and_unknown_never_force_one_root_cause():
    row = dict(candidate="vlm", result="missing", cause={})
    case = dict(
        availability="absent",
        review=dict(reference_agrees=None),
        diagnosis=dict(category="validation", certainty="proven", stage="literal_validation"),
    )
    axes = evidence_axes(row, case)
    assert {a["cause"] for a in axes} == {"document", "validation"}
    assert evidence_axes(row)[0]["cause"] == "unknown"
    assert evidence_axes(dict(row, result="extra"))[0]["certainty"] == "reference_only"


def test_direct_vlm_does_not_inherit_auxiliary_ocr_input_failure():
    row = dict(candidate="vlm", result="missing", cause=dict(category="not_submitted", certainty="proven"))
    assert evidence_axes(row)[0]["cause"] == "unknown"


def test_raw_ocr_findability_uses_boundaries_original_transcripts_and_no_signatures():
    review = checked("f", value="2")
    review.update(availability="readable")
    refs = {"f": dict(field="user_id")}
    page = SimpleNamespace(output_kind="ocr_text", document_id="doc", page_number=1, page_text="2020")
    result = raw_text_coverage([page], {"f": review}, refs, BenchmarkConfig().matching)
    assert result["text_findability"] == 0
    page.page_text = "ID: 2"
    assert raw_text_coverage([page], {"f": review}, refs, BenchmarkConfig().matching)["text_findability"] == 1
    page.page_text = "ID: 0002"
    config = BenchmarkConfig().matching.model_copy(update=dict(ignore_leading_user_id_zeros=True))
    assert raw_text_coverage([page], {"f": review}, refs, config)["text_findability"] == 1
    assert raw_text_coverage([], {}, {}, BenchmarkConfig().matching)["text_findability"] is None


def test_technical_metrics_deduplicate_assignment_and_do_not_invent_retries(tmp_path):
    page = PageResult(
        run_id="x",
        document_id="doc",
        page_number=1,
        page_id="p",
        method_id="paddle_llm",
        status="partial",
        parse_status="valid",
    )
    response = dict(raw_response='{"rows":[]}', parse_status="valid", prompt_version="v1")
    raw = dict(responses=[response], assignment=dict(response, cache_hit=True))
    result = technical_observations(tmp_path, "paddle_llm", [page], [raw], 2)
    assert result["json_syntax"]["evaluated"] == 1 and result["page_parse_rate"] == 0.5
    assert result["model_retries"] is None and result["repeated_page_attempts"] is None
    assert result["start_regime"] == "not_recorded"
    write_jsonl(tmp_path / "paddle_llm/attempts.jsonl", [page.model_dump(), page.model_dump()])
    result = technical_observations(tmp_path, "paddle_llm", [page], [raw], 2)
    assert result["repeated_page_attempts"] == 1
    assert technical_observations(tmp_path, "ocr_rules", [page], [raw], 2)["json_syntax"]["rate"] is None


def test_frozen_replay_adds_html_json_csv_without_changing_baseline(tmp_path):
    report, source, _, metadata = frozen_report(tmp_path)
    old = read_json(report / "metrics.json")
    output = tmp_path / "new-analysis"
    reanalyze(report, output, anls=True, figures=False, resamples=200)
    assert read_json(output / "metrics.json") == old
    result = read_json(output / "scientific/validity.json")
    assert result["anls_enabled"] and result["localized_reference_participants"] == 0
    assert result["methods"] and result["matching"]
    text = (output / "validity.html").read_text(encoding="utf8")
    assert "Zeilenkonsistenz" in text and "Legacy-Soft-F1" in text and "Nicht protokolliert" in text
    assert 'href="validity.html"' in (output / "report.html").read_text(encoding="utf8")
    assert (output / "scientific/validity_fields.csv").is_file()
    parser = FirstTable()
    parser.feed(text)
    displayed = {r[0]["text"]: r for r in parser.rows[1:]}
    for method in result["methods"]:
        fields = [r for r in result["fields"] if r["candidate"] == method["candidate"]]
        assert method["overall"]["anls"] == pytest.approx(
            sum(r["anls_credit"] for r in fields) / method["overall"]["reference_fields"]
        )
        assert percent(method["overall"]["anls"]) in displayed[method["candidate"]][6]["text"]
        assert all(r["similarity"] is None for r in fields if r["prediction"] is None)
