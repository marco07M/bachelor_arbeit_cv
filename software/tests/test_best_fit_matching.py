"""Best-fit evaluation maximizes the global assignment without treating weak pairs as identities."""

import itertools

import pytest

from participant_bench.excel_reference import ReferencePerson
from participant_bench.roster_benchmark.config import MatchingConfig, ReferenceConfig
from participant_bench.roster_benchmark.matching import Prediction, align, normalize, similarity
from participant_bench.roster_benchmark.metrics import course_metrics
from participant_bench.schema import VisualParticipant


def reference(index=0, *, first="Anna", last="Weber", user="000001", code="MUC"):
    return ReferencePerson(index + 2, "123456", user, first, last, code)


def prediction(index=0, *, first="Anna", last="Weber", user="000001", code="MUC"):
    return Prediction("doc", 1, index, VisualParticipant(
        first_name=first, last_name=last, personnel_number=user, department=code).participant())


def evaluate(predictions, references):
    return course_metrics("123456", predictions, references, MatchingConfig(mode="best_fit"), ReferenceConfig())


def test_below_threshold_still_pairs_and_earns_literal_fractional_credit():
    predictions = [prediction(first="Ax", last="Wy", user=None, code="XYZ")]
    refs = [reference()]
    old, *_ = course_metrics("123456", predictions, refs, MatchingConfig(), ReferenceConfig())
    score, rows, fields, _ = evaluate(predictions, refs)
    assert old["assigned_participants"] == 0
    assert score["assigned_participants"] == 1 and score["score_percent"] > 0
    assert score["low_similarity_assignments"] == 1
    assert rows[0]["matching_source"] == "global_best_fit" and rows[0]["review_required"]
    assert all(row["review_required"] for row in fields)


def test_zero_similarity_pair_is_retained_but_never_receives_credit():
    score, rows, *_ = evaluate([prediction(first="XXX", last="YYY", user="", code="ZZZ")],
                               [reference(first="AAA", last="BBB", user="", code="CCC")])
    assert score["assigned_participants"] == 1 and score["score_percent"] == 0
    assert rows[0]["review_required"] and "low_similarity" in rows[0]["matching_review_reasons"]


def test_global_sum_matches_exhaustive_optimum_for_real_edit_distances_and_permutations():
    refs = [reference(), reference(1, first="Anja", user="000002"),
            reference(2, first="Lina", last="Berg", user="000003", code="ABC")]
    predictions = [prediction(first="Ania", user="000007"), prediction(1, user=None),
                   prediction(2, first="Lina", last="Berg", user="000004", code="ABC")]

    def independent_credit(person, ref):
        return sum(similarity(normalize(getattr(person, model).value, field, MatchingConfig()),
                              normalize(getattr(ref, field), field, MatchingConfig()))
                   for field, model in (("first_name", "first_name"), ("last_name", "last_name"),
                                        ("user_id", "personnel_number"), ("short_code", "department"))
                   if getattr(person, model).value and getattr(ref, field))

    optimum = max(sum(independent_credit(p.person, refs[j]) for p, j in zip(predictions, order))
                  for order in itertools.permutations(range(3)))
    for reordered in itertools.permutations(predictions):
        score, rows, *_ = evaluate(list(reordered), refs)
        assert score["assigned_participants"] == 3 and score["overall"]["similarity_credit"] == pytest.approx(optimum)
        assert len({r["reference_row"] for r in rows if r["status"] == "matched"}) == 3


def test_nearly_correct_ids_disambiguate_equal_names():
    refs = [reference(), reference(1, user="999999")]
    score, rows, *_ = evaluate([prediction(user="000002")], refs)
    matched = next(row for row in rows if row["status"] == "matched")
    assert matched["reference_row"] == 2
    assert score["fields"]["user_id"]["similarity_credit"] == pytest.approx(5 / 6)


def test_ambiguous_pair_remains_and_is_explicitly_reviewable():
    score, rows, *_ = evaluate([prediction(user=None)], [reference(), reference(1, user="000002")])
    assert score["assigned_participants"] == 1 and score["ambiguous_assignments"] == 1
    matched = next(row for row in rows if row["status"] == "matched")
    assert "ambiguous" in matched["matching_review_reasons"] and matched["review_required"]
    assert score["missing_participants"] == 1


def test_conflict_is_flagged_without_rewriting_the_model_id():
    p = prediction(user="000002")
    score, rows, *_ = evaluate([p], [reference(), reference(1, first="Ben", last="Meyer", user="000002")])
    assert score["assigned_participants"] == 1 and score["conflicting_assignments"] == 1
    assert "identity_conflict" in rows[0]["matching_review_reasons"]
    assert p.person.personnel_number.value == "000002"


@pytest.mark.parametrize("excess", [False, True])
def test_unequal_counts_pair_only_available_distinct_rows(excess):
    refs = [reference(), reference(1, first="Ben", last="Meyer", user="000002")]
    predictions = [prediction()]
    if excess:
        refs = refs[:1]
        predictions.extend([prediction(1, first="Ben"), prediction(2, first="Lina")])
    score, *_ = evaluate(predictions, refs)
    assert score["assigned_participants"] == 1
    assert score["missing_participants"] == (0 if excess else 1)
    assert score["extra_participants"] == (2 if excess else 0)


def test_duplicate_predictions_do_not_get_credit_twice_for_one_reference():
    for predictions in ([prediction(first="anna"), prediction(1, first="Anna")],
                        [prediction(1, first="Anna"), prediction(first="anna")]):
        score, *_ = evaluate(predictions, [reference()])
        assert score["assigned_participants"] == 1 and score["extra_participants"] == 1
        assert score["overall"]["exact_fields"] == 4
        assert score["overall"]["raw_exact_reference_accuracy"] == 1
        assert score["score_percent"] == pytest.approx(100 * 2 / 3)


def test_completely_unreadable_prediction_is_not_forced_onto_a_person():
    score, rows, *_ = evaluate([prediction(first=None, last=None, user="***", code=None)], [reference()])
    assert score["assigned_participants"] == 0 and score["score_percent"] == 0
    assert any(row["status"] == "empty_prediction" for row in rows)


def test_masked_ids_and_swapped_field_roles_are_not_invented_or_repaired():
    p = prediction(first="Weber", last="Anna", user="***")
    score, _, fields, _ = evaluate([p], [reference()])
    assert score["assigned_participants"] == 1
    assert score["overall"]["invalid_prediction_fields"] == 1
    assert score["overall"]["reference_fields"] == 4
    assert p.person.first_name.value == "Weber" and p.person.last_name.value == "Anna"
    assert next(row for row in fields if row["field"] == "first_name")["exact"] is False
    assert next(row for row in fields if row["field"] == "short_code")["exact"] is True


def test_no_predictions_or_references_are_valid_inputs():
    matches, issues, candidates = align([], [reference()], MatchingConfig(mode="best_fit"), ReferenceConfig())
    assert not matches and not issues and not candidates
    matches, issues, candidates = align([prediction()], [], MatchingConfig(mode="best_fit"), ReferenceConfig())
    assert not matches and issues == {0: "extra"} and not candidates
