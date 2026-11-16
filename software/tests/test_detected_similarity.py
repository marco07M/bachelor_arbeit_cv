"""Conditional text accuracy uses existing pairs and edits, independent of completeness."""

from dataclasses import replace
from html.parser import HTMLParser

import pytest
from test_roster_benchmark import prediction, ref
from test_scientific_evaluation import frozen_report

from participant_bench.io import file_hash, read_json
from participant_bench.roster_benchmark.config import MatchingConfig, ReferenceConfig
from participant_bench.roster_benchmark.metrics import DETECTED_LABEL, aggregate, course_metrics
from participant_bench.roster_benchmark.report import detected_basis
from participant_bench.roster_benchmark.scientific import reanalyze
from participant_bench.roster_benchmark.scientific_stats import pooled


def evaluate(predictions, references=None, **options):
    return course_metrics("123456", predictions, references or [ref()], MatchingConfig(mode="best_fit", **options),
                          ReferenceConfig(), score_original_roles=True)


def test_two_correct_of_four_is_half_coverage_but_perfect_detected_similarity():
    score, _, fields, _ = evaluate([prediction(user=None, code=None)])
    c = score["overall"]
    assert c["field_coverage"] == c["exact_recall"] == .5
    assert c["exact_f1"] == pytest.approx(2 / 3)
    assert c["detected_fields"] == c["detected_similarity_credit"] == 2
    assert c["detected_similarity"] == 1
    assert sum(r["detected_contribution"] for r in fields) == 2


def test_misspelling_reduces_only_similarity_not_availability():
    score, _, fields, _ = evaluate([prediction(last="Muller")], [ref(last="Müller")])
    c = score["overall"]
    assert c["detected_fields"] == 4 and c["field_coverage"] == 1
    assert c["detected_similarity"] == pytest.approx((3 + 5 / 6) / 4)
    assert c["exact_recall"] == c["exact_f1"] == .75
    last = next(r for r in fields if r["field"] == "last_name")
    assert last["detected_similarity"] == pytest.approx(5 / 6)
    assert last["similarity_percent"] == pytest.approx(100 * 5 / 6)


@pytest.mark.parametrize("people", [[], [prediction(first=None, last=None, user=None, code=None)],
                                    [prediction(first="", last="", user="", code="")]])
def test_no_detected_values_is_undefined_and_still_penalizes_recall(people):
    score, *_ = evaluate(people)
    assert score["overall"]["detected_fields"] == 0
    assert score["overall"]["detected_similarity"] is None
    assert score["detected_similarity_percent"] is None
    assert score["overall"]["exact_recall"] == score["overall"]["field_coverage"] == 0


def test_wrong_person_values_remain_in_the_denominator_even_at_zero_similarity():
    score, _, fields, _ = evaluate([prediction(first="XXX", last="YYY", user="999999", code="ZZZ")],
                                    [ref(first="AAA", last="BBB", user="111111", code="CCC")])
    assert score["assigned_participants"] == 1 and score["low_similarity_assignments"] == 1
    assert score["overall"]["detected_fields"] == 4 and score["overall"]["detected_similarity"] == 0
    assert score["overall"]["incorrect_fields"] == 4
    assert all(r["detected_contribution"] == 1 for r in fields)


def test_ambiguous_pairs_are_not_filtered_out_of_text_accuracy():
    score, rows, _, _ = evaluate([prediction()], [ref(), ref(row=3, user="001235")], ambiguity_margin=.5)
    assert any("ambiguous" in r["matching_review_reasons"] for r in rows)
    assert score["overall"]["detected_fields"] == 4 and score["overall"]["detected_similarity"] == 1
    assert score["participant_quality"]["identity_exact_participants"] == 0
    assert score["overall"]["exact_recall"] == .5


def test_extra_hallucinated_person_retains_existing_fp_and_participant_penalties():
    baseline, *_ = evaluate([prediction()])
    extra, _, fields, _ = evaluate([prediction(), prediction(index=1, first="XXX", last="YYY", user="999", code="ZZZ")])
    assert extra["extra_participants"] == 1 and extra["overall"]["extra_fields"] == 4
    assert extra["overall"]["exact_f1"] == pytest.approx(2 / 3)
    assert extra["overall"]["exact_f1"] < baseline["overall"]["exact_f1"]
    assert extra["overall"]["detected_fields"] == 4 and extra["overall"]["detected_similarity"] == 1
    assert all(not r["detected_contribution"] for r in fields if r["reference_row"] is None)


def test_missing_reference_person_reduces_recall_without_reducing_detected_similarity():
    score, *_ = evaluate([prediction()], [ref(), ref(row=3, first="Ben", last="Kurz", user="222")])
    assert score["missing_participants"] == 1 and score["overall"]["missing_fields"] == 4
    assert score["overall"]["exact_recall"] == score["overall"]["field_coverage"] == .5
    assert score["overall"]["detected_fields"] == 4 and score["overall"]["detected_similarity"] == 1


@pytest.mark.parametrize("state", ["empty", "unknown", "masked", "illegible"])
def test_blank_or_unreliable_gt_never_adds_similarity_even_with_output_text(state):
    reference = replace(ref(code="" if state == "empty" else "MUC"), field_states={"short_code": state})
    score, _, fields, _ = evaluate([prediction(code="invented")], [reference])
    assert score["overall"]["detected_fields"] == 3 and score["overall"]["detected_similarity"] == 1
    assert next(r for r in fields if r["field"] == "short_code")["detected_contribution"] == 0
    if state == "empty":
        assert score["overall"]["hallucinated_empty_fields"] == 1
        assert score["overall"]["predicted_fields"] == 4


def test_nonempty_invalid_id_is_not_removed_to_improve_similarity():
    score, _, fields, _ = evaluate([prediction(user="***")])
    assert score["overall"]["detected_fields"] == 4 and score["overall"]["detected_similarity"] == .75
    assert score["overall"]["invalid_prediction_fields"] == 1 and score["overall"]["missing_fields"] == 1
    assert next(r for r in fields if r["field"] == "user_id")["detected_similarity"] == 0


def test_normalization_preserves_whitespace_case_and_numeric_id_rules():
    score, *_ = evaluate([prediction(first=" ANNA ", last="  WEBER  ", user=" 0001234 ", code=" muc ")],
                         ignore_leading_user_id_zeros=True)
    assert score["overall"]["detected_similarity"] == 1


def test_aggregation_pools_field_contributions_instead_of_averaging_course_means():
    a, *_ = evaluate([prediction(first="A", last=None, user=None, code=None)], [ref(first="A")])
    b, *_ = evaluate([prediction(first="X", last="Y", user="9", code="Z")],
                     [ref(first="A", last="B", user="1", code="C")])
    total = aggregate([a, b])["overall"]
    assert total["detected_fields"] == 5 and total["detected_similarity_credit"] == 1
    assert total["detected_similarity"] == .2
    assert pooled([a["overall"], b["overall"]])["detected_similarity"] == .2


class FirstTable(HTMLParser):
    def __init__(self):
        super().__init__()
        self.active, self.finished, self.rows, self.row, self.cell = False, False, [], None, None

    def handle_starttag(self, tag, attrs):
        if tag == "table" and not self.finished:
            self.active = True
        if not self.active:
            return
        if tag == "tr":
            self.row = []
        if tag in ("td", "th"):
            self.cell = dict(text="", **dict(attrs))

    def handle_data(self, data):
        if self.active and self.cell is not None:
            self.cell["text"] += data

    def handle_endtag(self, tag):
        if not self.active:
            return
        if tag in ("td", "th") and self.cell is not None:
            self.row.append(self.cell)
            self.cell = None
        if tag == "tr":
            self.rows.append(self.row)
        if tag == "table":
            self.active, self.finished = False, True


@pytest.mark.parametrize("empty_method", [None, "vlm"])
def test_html_sortable_values_denominators_and_exports_match_recomputed_counters(tmp_path, empty_method):
    old, source, _, metadata = frozen_report(tmp_path, empty_method=empty_method)
    protected = {p: file_hash(p) for root in (old, source) for p in root.rglob("*") if p.is_file()}
    target = tmp_path / "new"
    result = reanalyze(old, target, metadata=metadata, resamples=200, figures=False)
    parser = FirstTable()
    markup = (target / "report.html").read_text(encoding="utf8")
    parser.feed(markup)
    col = next(i for i, cell in enumerate(parser.rows[0]) if DETECTED_LABEL in cell["text"])
    primary = {r["candidate"]: r for r in result["overview"] if r.get("mode") == "original_roles"}
    for row in parser.rows[1:]:
        assert len(row) == len(parser.rows[0])
        candidate = next(m for m in primary if row[0]["data-value"] == m)
        metric = primary[candidate]
        if metric["detected_similarity"] is None:
            assert row[col]["data-value"] == "" and "nicht definiert" in row[col]["text"]
        else:
            assert float(row[col]["data-value"]) == metric["detected_similarity"]
        assert detected_basis(metric) in row[col]["text"]
    assert "Levenshtein-Feld-F1" not in markup
    assert "Fehlende Felder reduzieren diese Ähnlichkeit nicht" in markup
    audit = read_json(target / "scientific/metric_audit_checks.json")
    assert all(r["matches_metrics"] for r in audit.values())
    assert all(file_hash(p) == h for p, h in protected.items())
