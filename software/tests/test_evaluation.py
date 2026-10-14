import pytest
from pydantic import ValidationError

from participant_bench.evaluation import evaluate, match_rows
from participant_bench.models import check_ocr_evidence, parse_response
from participant_bench.schema import GroundTruthPage, PageResult
from participant_bench.synthetic import participants


def page(rows):
    return GroundTruthPage(
        document_id="d",
        page_number=1,
        split="development",
        dependency_group="d",
        content_type="typed",
        relevant=True,
        participants=rows,
    )


def prediction(rows):
    return PageResult(
        run_id="r",
        document_id="d",
        page_number=1,
        page_id="d-p0001",
        method_id="a",
        status="success",
        parse_status="valid",
        participants=rows,
    )


def test_perfect_text_and_strict_personnel_number():
    truth = participants()
    predicted = [p.model_copy(deep=True) for p in truth]
    predicted[0].personnel_number.value = "123"
    scores, _ = evaluate([prediction(predicted)], [page(truth)])
    assert scores["overall_exact_match"] == {"numerator": 7, "denominator": 8, "value": 0.875}
    assert scores["fields"]["personnel_number"]["cer"]["numerator"] == 2
    assert scores["assignment"]["match_coverage"]["value"] == 1
    assert scores["entry_prf"]["tp"] == 1
    assert scores["entry_prf"]["fp"] == scores["entry_prf"]["fn"] == 1


def test_missing_extra_rows_keep_denominators():
    truth = participants()
    extra = truth[1].model_copy(deep=True)
    extra.row_ref = "9"
    predicted = [truth[0].model_copy(deep=True), extra]
    scores, _ = evaluate([prediction(predicted)], [page(truth)])
    assert scores["counts"]["missing_rows"] == scores["counts"]["extra_rows"] == 1
    assert scores["overall_exact_match"]["denominator"] == 8
    assert scores["overall_exact_match"]["numerator"] == 4
    assert scores["field_prf"]["tp"] == scores["field_prf"]["fp"] == scores["field_prf"]["fn"] == 4
    assert scores["signature"]["coverage"]["denominator"] == 1
    assert scores["signature"]["unknown_rate"]["value"] == 1


def test_unknown_positive_signature_is_false_negative():
    truth = participants()
    truth[0].signature_present = True
    truth[0].signature_state = "read"
    predicted = [p.model_copy(deep=True) for p in truth]
    predicted[0].signature_present = None
    predicted[0].signature_state = "uncertain"
    scores, _ = evaluate([prediction(predicted)], [page(truth)])
    sig = scores["signature"]
    assert sig["prf"]["fn"] == 1
    assert sig["confusion"]["gt_true_pred_unknown"] == 1
    assert sig["coverage"]["value"] == 0.5


def test_unavailable_method_has_zero_recall_and_all_rows_missing():
    scores, _ = evaluate([], [page(participants())])
    assert scores["overall_exact_match"]["value"] == 0
    assert scores["overall_exact_match"]["denominator"] == 8
    assert scores["counts"]["missing_rows"] == 2
    assert scores["fields"]["first_name"]["cer"]["value"] == 1


def test_matching_not_by_personnel_number():
    truth = participants()
    predicted = [p.model_copy(deep=True) for p in reversed(truth)]
    predicted[0].personnel_number.value, predicted[1].personnel_number.value = (
        predicted[1].personnel_number.value,
        predicted[0].personnel_number.value,
    )
    pairs, extras, missing = match_rows(predicted, truth)
    assert set(pairs) == {(1, 0, "printed_row_ref"), (0, 1, "printed_row_ref")}
    assert not extras and not missing


def test_swap_association_detected_despite_correct_field_bag():
    truth = participants()
    predicted = [p.model_copy(deep=True) for p in truth]
    predicted[0].last_name, predicted[1].last_name = predicted[1].last_name, predicted[0].last_name
    scores, _ = evaluate([prediction(predicted)], [page(truth)])
    assert scores["entry_prf"]["tp"] == 0
    assert scores["assignment"]["complete_row_coverage"]["value"] == 0


def test_illegible_truth_excluded_and_counted():
    truth = participants()
    truth[0].first_name.value = None
    truth[0].first_name.state = "illegible"
    scores, _ = evaluate([], [page(truth)])
    assert scores["overall_exact_match"]["denominator"] == 7
    assert scores["fields"]["first_name"]["excluded_gt_unknown"] == 1
    assert scores["counts"]["entry_excluded_gt_unknown"] == 1


@pytest.mark.parametrize(
    "raw",
    [
        "not JSON",
        '{"participants":',
        '```json\n{"participants": []}\n```',
        '{"participants": [], "date": "2026-01-01"}',
    ],
)
def test_invalid_model_output_rejected(raw):
    with pytest.raises(ValidationError):
        parse_response(raw)


def test_personnel_number_never_coerced_to_string():
    row = participants()[0].model_dump()
    row["personnel_number"]["value"] = 123
    import json

    with pytest.raises(ValidationError):
        parse_response(json.dumps({"participants": [row]}))


def test_hallucinated_ocr_field_rejected():
    with pytest.raises(ValueError, match="Unsupported OCR"):
        check_ocr_evidence(participants(), {"text": "Anna Weber", "words": []})


def test_partial_personnel_number_rejected_by_evidence_guard():
    row = participants()[0]
    row.personnel_number.value = "123"
    data = {"text": "1 Anna Weber 00123 Technik", "words": [{"text": "1"}]}
    with pytest.raises(ValueError, match="complete observed"):
        check_ocr_evidence([row], data)
