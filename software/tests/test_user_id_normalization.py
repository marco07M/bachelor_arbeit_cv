"""Ignore ID padding during comparisons while retaining literal OCR/Excel evidence."""

from pathlib import Path

import pytest
from test_roster_benchmark import prediction, ref

from participant_bench.identifiers import normalized_user_id
from participant_bench.roster_benchmark.config import MatchingConfig, ReferenceConfig, load_config
from participant_bench.roster_benchmark.matching import normalize
from participant_bench.roster_benchmark.metrics import course_metrics


@pytest.mark.parametrize("value,expected", [("0047285", "47285"), ("47285", "47285"),
    (" 00047285 ", "47285"), ("000", "0"), ("0", "0"), ("0010200", "10200"),
    (None, ""), ("", ""), ("***", "***"), ("00A123", "00A123")])
def test_only_numeric_id_padding_is_ignored(value, expected):
    assert normalized_user_id(value) == expected


@pytest.mark.parametrize("mode", ["conservative", "best_fit"])
@pytest.mark.parametrize("actual,expected", [("0047285", "47285"), ("47285", "0047285")])
def test_id_alignment_and_scores_ignore_padding_in_both_directions(mode, actual, expected):
    config = MatchingConfig(mode=mode, ignore_leading_user_id_zeros=True)
    person = prediction(user=actual, first=None, last=None, code=None)
    reference = ref(user=expected)
    score, rows, fields, _ = course_metrics("123456", [person], [reference], config, ReferenceConfig())
    assert score["assigned_participants"] == 1
    assert score["fields"]["user_id"]["exact_fields"] == 1
    assert score["fields"]["user_id"]["soft_f1"] == 1
    assert score["fields"]["user_id"]["raw_exact_fields"] == 0
    if mode == "conservative":
        assert rows[0]["matching_source"] == "exact_user_id"
    detail = next(field for field in fields if field["field"] == "user_id")
    assert detail["levenshtein_distance"] == 0 and detail["similarity"] == 1
    assert detail["reference_value"] == expected and detail["prediction_value"] == actual
    assert person.person.personnel_number.value == actual and reference.user_id == expected


def test_edit_distance_is_calculated_after_id_padding_is_removed():
    config = MatchingConfig(ignore_leading_user_id_zeros=True)
    _, _, fields, _ = course_metrics("123456", [prediction(user="0047286")], [ref(user="47285")], config, ReferenceConfig())
    field = next(row for row in fields if row["field"] == "user_id")
    assert field["levenshtein_distance"] == 1 and field["similarity"] == .8


def test_other_fields_and_historical_configs_keep_their_existing_rule():
    config = MatchingConfig(ignore_leading_user_id_zeros=True)
    for field in ("first_name", "last_name", "short_code"):
        assert normalize("0047285", field, config) == "0047285"
    historical = MatchingConfig.model_validate({"mode": "best_fit"})
    assert normalize("0047285", "user_id", historical) == "0047285"


@pytest.mark.parametrize("path", ["testframework/config.yaml", "api_firmen_pc/testframework/config.yaml"])
def test_both_computer_profiles_enable_the_new_comparison_rule(path):
    assert load_config(Path(path)).matching.ignore_leading_user_id_zeros


def test_standalone_excel_comparison_uses_the_same_id_rule():
    from test_excel_comparison import evaluate, person, prediction, ref

    score, _, details = evaluate([prediction(person(user="47285"))], [ref(user="0047285")])
    assert score["fields"]["user_id"]["exact_match"]["value"] == 1
    field = next(row for row in details if row["field"] == "user_id")
    assert field["prediction_value"] == "47285" and field["reference_value"] == "0047285"


def test_html_and_csv_explain_the_normalized_score_without_changing_originals(tmp_path):
    import csv

    from test_roster_benchmark import page, person, saved_run, write_reference

    from participant_bench.io import file_hash
    from participant_bench.roster_benchmark.config import BenchmarkConfig
    from participant_bench.roster_benchmark.evaluation import evaluate_run

    source = saved_run(tmp_path / "source", [page([person(user="0047285")])])
    reference = tmp_path / "reference.csv"
    write_reference(reference, [["123456", "47285", "Anna", "Weber", "MUC"]])
    paths = [source / "vlm/extractions.jsonl", reference]
    before = [file_hash(path) for path in paths]
    config = BenchmarkConfig()
    config.matching.ignore_leading_user_id_zeros = True
    output, metrics = evaluate_run(source, reference, config, tmp_path / "results")
    assert metrics["vlm"]["score_percent"] == 100
    with (output / "fields.csv").open(encoding="utf-8-sig", newline="") as stream:
        field = next(row for row in csv.DictReader(stream) if row["field"] == "user_id")
    assert field["exact"] == "True" and field["raw_exact"] == "False"
    assert field["reference_value"] == "47285" and field["prediction_value"] == "0047285"
    assert field["levenshtein_distance"] == "0" and field["similarity"] == "1.0"
    for filename in ["report.html", "details.html", "zuordnungen.html"]:
        assert "0047285 = 47285" in (output / filename).read_text(encoding="utf-8")
    assert before == [file_hash(path) for path in paths]
