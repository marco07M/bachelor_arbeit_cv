"""Keep transcription availability, exactness and assignment uncertainty distinct."""

from dataclasses import replace

import pytest
from test_extraction_errors import field, page
from test_roster_benchmark import prediction, ref
from test_scientific_evaluation import frozen_report

from participant_bench.io import file_hash, read_json
from participant_bench.roster_benchmark.config import MatchingConfig, ReferenceConfig
from participant_bench.roster_benchmark.error_report import diagnose_field
from participant_bench.roster_benchmark.field_assessment import assess, counts, scoring_status
from participant_bench.roster_benchmark.metrics import course_metrics
from participant_bench.roster_benchmark.scientific import reanalyze
from participant_bench.schema import TextField


def evaluate(predictions, references, **options):
    return course_metrics("123456", predictions, references, MatchingConfig(mode="best_fit", **options),
                          ReferenceConfig(), score_original_roles=True)


@pytest.mark.parametrize("actual,status,similarity,exact,missing", [
    ("Müller", "correct", 100, 1, 0),
    ("  MÜLLER  ", "correct", 100, 1, 0),
    ("Muller", "deviating", 100 * 5 / 6, 0, 0),
    ("XXXXXX", "deviating", 0, 0, 0),
    (None, "missing", None, 0, 1),
    ("", "missing", None, 0, 1),
])
def test_readable_misspelling_never_becomes_missing_or_exact(actual, status, similarity, exact, missing):
    score, _, fields, _ = evaluate([prediction(last=actual)], [ref(last="Müller")])
    row = next(r for r in fields if r["field"] == "last_name")
    assert row["evaluation_status"] == status
    assert row["similarity_percent"] == pytest.approx(similarity) if similarity is not None else row["similarity_percent"] is None
    assert score["fields"]["last_name"]["exact_fields"] == exact
    assert score["fields"]["last_name"]["missing_fields"] == missing
    assert score["fields"]["last_name"]["field_coverage"] == 1 - missing
    assert row["original_prediction_value"] == actual


def test_no_prediction_retains_all_reference_penalties():
    score, _, fields, _ = evaluate([], [ref()])
    assert score["overall"]["reference_fields"] == score["overall"]["missing_fields"] == 4
    assert score["overall"]["exact_recall"] == score["participant_quality"]["participant_recall"] == 0
    assert counts(fields) == dict(correct=0, deviating=0, missing=4, unclear=0, unassessed=0)


def test_unpaired_text_is_unclear_and_does_not_disappear_from_p():
    score, _, fields, _ = evaluate([prediction(), prediction(index=1, last="Other")], [ref()])
    extras = [r for r in fields if r["reference_row"] is None]
    assert len(extras) == 4 and all(r["evaluation_status"] == "unclear" for r in extras)
    assert all(r["similarity_percent"] is None for r in extras)
    assert score["overall"]["predicted_fields"] == 8 and score["overall"]["extra_fields"] == 4
    assert sum(counts(fields).values()) == len(fields)


def test_ambiguous_exact_pair_is_not_a_confirmed_identity_or_complete_participant():
    references = [ref(), ref(row=3, user="001235")]
    score, rows, fields, _ = evaluate([prediction()], references, ambiguity_margin=.5)
    selected = next(r for r in rows if r["status"] == "matched")
    assert "ambiguous" in selected["matching_review_reasons"]
    assert score["overall"]["exact_fields"] == 4  # no new or removed field credit
    assert score["participant_quality"]["identity_exact_participants"] == 0
    assert score["participant_quality"]["fully_correct_complete_participants"] == 0
    assert all(r["evaluation_status"] == "unclear" for r in fields if r["status"] == "matched")


def test_unreliable_ground_truth_is_unassessable_even_with_output_text():
    reference = replace(ref(), field_states={"last_name": "unknown"})
    score, _, fields, _ = evaluate([prediction()], [reference])
    row = next(r for r in fields if r["field"] == "last_name")
    assert row["evaluation_status"] == "unassessed" and row["similarity_percent"] is None
    assert score["overall"]["reference_fields"] == 3


def test_string_csv_and_typed_rows_use_identical_metric_and_display_states():
    _, _, fields, _ = evaluate([prediction(last="Muller")], [ref(last="Müller")])
    for row in fields:
        csv_row = {k: "" if v is None else str(v) for k, v in row.items()}
        assert scoring_status(csv_row) == scoring_status(row)
        assert assess(csv_row) == assess(row)


def test_evidence_separates_ocr_submission_omission_and_unknown_without_guessing():
    current = page()
    row = field(output_index=0)  # integer zero must not look like a missing index
    unknown = diagnose_field(row, current, {}, {"observations": []})
    assert unknown["certainty"] == "unknown" and assess(row, unknown)["evaluation_status"] == "missing"
    observations = [dict(text="AB7", bbox=current.participants[0].bbox.model_dump(), submitted_to_assignment=True)]
    omission = diagnose_field(row, current, {}, dict(observations=observations))
    assert omission["category"] == "model_omission" and omission["certainty"] == "proven"
    assert assess(row, omission)["evaluation_status"] == "unclear"
    observations[0]["submitted_to_assignment"] = False
    not_submitted = diagnose_field(row, current, {}, dict(observations=observations))
    assert not_submitted["category"] == "not_submitted"
    observations[0]["bbox"] = dict(x0=.1, x1=.8, y0=.7, y1=.8)
    assert diagnose_field(row, current, {}, dict(observations=observations))["certainty"] == "unknown"


def test_mapping_diagnosis_without_text_never_invents_an_observed_value():
    row = field()
    diagnosis = dict(category="column_mapping", certainty="proven")
    assert assess(row, diagnosis)["evaluation_status"] == "missing"
    diagnosis["pipeline_trace"] = dict(stages=[dict(stage="model_response", cells=["unassigned text"])])
    assert assess(row, diagnosis)["evaluation_status"] == "unclear"


def test_nonempty_value_excluded_by_uncertainty_policy_is_visible_without_awarding_credit():
    p = prediction()
    p.person.last_name = TextField(value="Weber", state="uncertain")
    score, _, fields, _ = evaluate([p], [ref()], score_uncertain_values=False)
    row = next(r for r in fields if r["field"] == "last_name")
    assert row["original_prediction_value"] == "Weber" and row["prediction_value"] is None
    assert row["evaluation_status"] == "unclear" and row["metric_status"] == "missing"
    assert row["similarity_percent"] is None and score["overall"]["exact_fields"] == 3


def test_new_report_preserves_historical_files_and_reconciles_display_and_metric_counts(tmp_path):
    old, source, _, metadata = frozen_report(tmp_path)
    protected = {p: file_hash(p) for root in (old, source) for p in root.rglob("*") if p.is_file()}
    target = tmp_path / "new-report"
    result = reanalyze(old, target, metadata=metadata, resamples=200, figures=False)
    audit = result["metric_audit"]
    assert all(c["matches_metrics"] and c["evaluation_status_partition"] for c in audit["checks"].values())
    assert all(file_hash(p) == h for p, h in protected.items())
    assert read_json(target / "metric_checks.json")["reference_denominator_equal"]
    markup = (target / "report.html").read_text(encoding="utf8")
    assert "Erkannt, aber abweichend" in markup and "Zuordnung unklar" in markup
    assert "Levenshtein-Ähnlichkeit" in markup and "Verglichene Werte normalisiert" not in markup
    errors = (target / "extraction_errors.html").read_text(encoding="utf8")
    assert "Für Vergleich verwendeter Wert" not in errors and 'id="assessment"' in errors
