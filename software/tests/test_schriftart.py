"""GT-only participant strata: validation, fixed matching, additive counters and UI."""

import json
import shutil
import subprocess
from dataclasses import replace

import pytest
from openpyxl import load_workbook
from pydantic import ValidationError
from test_calibration import references as calibration_references
from test_evaluation import page as gt_page
from test_evaluation import prediction as page_prediction
from test_roster_benchmark import person, prediction, ref
from test_scientific_evaluation import frozen_report

from participant_bench.calibration.dataset import load_dataset, rows
from participant_bench.evaluation import evaluate_groups
from participant_bench.excel_columns import write_participants_xlsx
from participant_bench.excel_reference import ExcelConfig
from participant_bench.excel_reference import read_reference as strict_read
from participant_bench.io import file_hash, write_csv
from participant_bench.roster_benchmark.cli import main
from participant_bench.roster_benchmark.config import MatchingConfig, ReferenceConfig
from participant_bench.roster_benchmark.metrics import aggregate, course_metrics, empty_counts
from participant_bench.roster_benchmark.references import export_reference, read_reference, saved_reference
from participant_bench.roster_benchmark.schriftart_report import SCRIPT, prepare
from participant_bench.roster_benchmark.scientific import reanalyze
from participant_bench.schema import GroundTruthPage, GroundTruthParticipant, ModelResponse, PageResult
from participant_bench.writing_style import STYLES


def evaluate(people, references):
    return course_metrics("123456", people, references, MatchingConfig(mode="best_fit"), ReferenceConfig(),
                          score_original_roles=True)


@pytest.mark.parametrize("style,expected", [("h", "h"), ("m", "m"), ("g", "g"), (None, None), ("", None), (" H ", "h")])
def test_gt_schema_and_reference_annotation_roundtrip(style, expected):
    participant = GroundTruthParticipant(**person().model_dump(), schriftart=style)
    page = gt_page([participant])
    restored = GroundTruthPage.model_validate_json(page.model_dump_json())
    assert restored.participants[0].schriftart == expected
    assert replace(ref(), schriftart=style).schriftart == expected
    assert gt_page([person()]).participants[0].schriftart is None  # content_type=typed is not an annotation


@pytest.mark.parametrize("style", ["x", "handwritten", "hm", 1, True])
def test_invalid_annotation_rejected(style):
    with pytest.raises((ValueError, ValidationError)):
        GroundTruthParticipant(**person().model_dump(), schriftart=style)
    with pytest.raises(ValueError):
        replace(ref(), schriftart=style)


def test_extraction_schemas_and_results_cannot_acquire_gt_schriftart():
    assert "schriftart" not in json.dumps(ModelResponse.model_json_schema())
    assert "schriftart" not in json.dumps(PageResult.model_json_schema())
    assert "schriftart" in json.dumps(GroundTruthPage.model_json_schema())
    with pytest.raises(ValidationError):
        ModelResponse.model_validate(dict(participants=[dict(person().model_dump(), schriftart="h")]))


@pytest.mark.parametrize("suffix", [".csv", ".xlsx"])
def test_reference_export_import_editing_and_unknown_annotation_are_lossless(tmp_path, suffix):
    people = [replace(ref(row=i+2, first=f"Example{i}", user=f"00000{i}"), schriftart=style)
              for i, style in enumerate(("h", "m", "g", None))]
    target = tmp_path / ("reference" + suffix)
    export_reference(target, people)
    assert read_reference(target, ReferenceConfig()).people == people
    before = file_hash(target)
    with pytest.raises(ValueError, match="nicht überschrieben"):
        export_reference(target, people)
    assert file_hash(target) == before
    if suffix == ".xlsx":
        assert strict_read(target, ExcelConfig())[0] == people
        book = load_workbook(target)
        try:
            assert book["Referenz"].cell(1, 6).value == "schriftart"
            assert book["Referenz"].data_validations.count == 1
            book["Referenz"].cell(2, 6, "g")
            book.save(target)
        finally:
            book.close()
        assert read_reference(target, ReferenceConfig()).people[0].schriftart == "g"
        streamed = tmp_path / "streamed.xlsx"
        write_participants_xlsx(streamed, {}, references=people)
        assert read_reference(streamed, ReferenceConfig()).people[-1].schriftart is None
        assert strict_read(streamed, ExcelConfig())[0][-1].schriftart is None


def test_duplicate_annotation_columns_and_conflicting_duplicate_rows_are_rejected(tmp_path):
    path = tmp_path / "bad.csv"
    path.write_text("Class ID,User ID,First Name,Last Name,Organization,schriftart,Schriftart\n123456,1,A,B,C,h,m\n", encoding="utf8")
    with pytest.raises(ValueError, match="Mehrdeutige"):
        read_reference(path, ReferenceConfig(delimiter=","))
    export_reference(tmp_path / "duplicates.csv", [replace(ref(), schriftart="h"), replace(ref(row=3), schriftart="m")])
    with pytest.raises(ValueError, match="unterschiedliche Schriftart"):
        read_reference(tmp_path / "duplicates.csv", ReferenceConfig(merge_identical_duplicates=True))


def test_groups_keep_missing_rows_and_all_six_quality_dimensions():
    references = [replace(ref(), schriftart="h"),
                  replace(ref(row=3, first="Ben", last="Müller", user="002"), schriftart="m"),
                  replace(ref(row=4, first="Cora", last="Kurz", user="003"), schriftart="g"),
                  ref(row=5, first="Dora", last="Lang", user="004")]
    predictions = [prediction(), prediction(index=1, first="Ben", last="Muller", user="002"),
                   prediction(index=2, first="Dora", last="Lang", user="004")]
    score, cases, details, _ = evaluate(predictions, references)
    groups = score["schriftart_groups"]
    assert set(groups) == set(STYLES)
    for group in groups.values():
        assert group["participant_quality"]["reference_participants"] == 1
        assert group["overall"]["reference_fields"] == 4
    h, m, g = (groups[k] for k in "hmg")
    assert h["overall"]["exact_recall"] == h["overall"]["exact_f1"] == h["overall"]["field_coverage"] == h["overall"]["detected_similarity"] == 1
    assert h["participant_quality"]["participant_recall"] == h["participant_quality"]["complete_participant_accuracy"] == 1
    assert m["overall"]["exact_recall"] == m["overall"]["exact_f1"] == .75
    assert m["overall"]["field_coverage"] == 1 and m["overall"]["detected_similarity"] == pytest.approx((3+5/6)/4)
    assert m["participant_quality"]["participant_recall"] == m["participant_quality"]["complete_participant_accuracy"] == 0
    assert g["overall"]["missing_fields"] == 4 and g["overall"]["exact_recall"] == g["overall"]["field_coverage"] == 0
    assert g["overall"]["detected_similarity"] is None and g["participant_quality"]["participant_recall"] == 0
    missing = next(r for r in cases if r["status"] == "missing")
    assert missing["schriftart"] == "g" and missing["document_id"] is None
    assert sum(v["participant_quality"]["reference_participants"] for v in groups.values()) == 4
    assert all(r["schriftart"] == "g" for r in details if r["reference_row"] == 4)


def test_annotations_do_not_change_pairing_or_global_metrics():
    references = [ref(), ref(row=3, first="Ben", user="002")]
    predictions = [prediction(first="Anny"), prediction(index=1, first="Ben", user="002")]
    before, rows_before, _, candidates_before = evaluate(predictions, references)
    after, rows_after, _, candidates_after = evaluate(predictions, [replace(r, schriftart=s) for r, s in zip(references, "hg")])
    assert before["overall"] == after["overall"]
    assert before["participant_quality"] == after["participant_quality"]
    assert candidates_before == candidates_after
    assert [(r["reference_row"], r["output_index"], r["status"]) for r in rows_before] == [(r["reference_row"], r["output_index"], r["status"]) for r in rows_after]


def test_identity_uniqueness_is_not_recomputed_inside_a_style_group():
    references = [replace(ref(code="AAA"), schriftart="h"), replace(ref(row=3, code="BBB"), schriftart="m")]
    score, *_ = evaluate([prediction(code="AAA"), prediction(index=1, code="BBB")], references)
    assert score["participant_quality"]["identity_assessable_participants"] == 0
    for style in "hm":
        assert score["schriftart_groups"][style]["participant_quality"]["participant_recall"] is None


def test_global_extra_penalties_and_all_group_counters_reconcile():
    course, *_ = evaluate([prediction(), prediction(index=1, first="XXX", last="YYY", user="999", code="ZZZ")],
                          [replace(ref(), schriftart="h")])
    total = aggregate([course])
    assert total["overall"]["exact_f1"] == pytest.approx(2/3)
    assert total["schriftart_groups"]["h"]["overall"]["exact_f1"] == 1
    assert total["schriftart_unassigned"]["participants"] == 1
    assert total["schriftart_unassigned"]["fields"]["predicted_fields"] == 4
    for key in empty_counts():
        assert total["overall"][key] == pytest.approx(sum(g["overall"][key] for g in total["schriftart_groups"].values())
                                                      + total["schriftart_unassigned"]["fields"][key])
    rows, _, extras = prepare(total, "test", "original_roles", [dict(status="mapped", class_id="123456", document_id="d")])
    assert extras["counts_reconcile"] and next(r for r in rows if r["schriftart"] == "h")["documents"] == 1
    assert next(r for r in rows if r["schriftart"] == "m")["exact_f1"] is None


def test_manual_csv_participants_support_old_missing_and_new_annotations(tmp_path):
    target = calibration_references(tmp_path)
    before = load_dataset(target)
    assert all(p.schriftart is None for page in before["pages"] for p in page.participants)
    people = rows(target / "participants.csv")
    for i, person_row in enumerate(people):
        person_row["schriftart"] = ("h", "m", "g")[i % 3]
    write_csv(target / "participants.csv", people)
    after = load_dataset(target)
    assert {p.schriftart for page in after["pages"] for p in page.participants} == {"h", "m", "g"}


def test_page_groups_use_full_page_pairs_once_and_leave_extras_global(monkeypatch):
    import participant_bench.evaluation as page_eval
    people = [GroundTruthParticipant(**dict(person(first=f"P{i}").model_dump(), row_ref=str(i)), schriftart=s)
              for i, s in enumerate(("h", "m", "g", None))]
    truth = gt_page(people)
    predictions = [person(first=f"P{i}").model_copy(update={"row_ref": str(i)}) for i in (0, 1, 3)]
    predictions += [person(first="Extra").model_copy(update={"row_ref": "9"})]
    original = page_eval.match_rows
    calls = []
    def match(pred, gt):
        calls.append(len(gt))
        return original(pred, gt)
    monkeypatch.setattr(page_eval, "match_rows", match)
    result, _ = evaluate_groups([page_prediction(predictions)], [truth])
    assert calls == [4]
    assert result["aggregate"]["counts"]["extra_rows"] == 1
    assert result["groups"]["schriftart"]["g"]["counts"]["missing_rows"] == 1
    assert result["groups"]["schriftart"]["h"]["counts"]["gt_rows"] == 1


def test_frozen_report_and_reference_template_keep_old_files_and_all_unknown_gt(tmp_path):
    old, source, _, metadata = frozen_report(tmp_path)
    protected = {p: file_hash(p) for root in (old, source) for p in root.rglob("*") if p.is_file()}
    target = tmp_path / "new"
    result = reanalyze(old, target, metadata=metadata, resamples=200, figures=False)
    assert all(file_hash(p) == h for p, h in protected.items())
    snapshot = saved_reference(old)[1]
    assert all(p.schriftart is None for p in snapshot.people)
    for row in result["schriftart"]:
        if row["schriftart"] in "hmg":
            assert row["reference_participants"] == 0 and row["exact_f1"] is None
    markup = (target / "report.html").read_text(encoding="utf8")
    assert 'id="schriftart-filter"' in markup and 'data-schriftart="unclassified"' in markup
    assert "Nicht klassifiziert" in markup and "nicht definiert" in markup
    assert (target / "scientific/schriftart_fields.csv").is_file()
    exported = tmp_path / "editable.xlsx"
    assert main(["reference-template", "--report", str(old), "--output", str(exported)]) == 0
    assert len(read_reference(exported, ReferenceConfig()).people) == len(snapshot.people)


def test_schriftart_filter_selects_groups_without_mixing_or_recounting(tmp_path):
    node = shutil.which("node")
    if not node:
        pytest.skip("Node needed for existing offline JS regression mechanism")
    fixture = '''const assert=require('node:assert/strict');
const control={value:'',addEventListener(n,f){this.apply=f}};
const rows=['total','h','m','g','unclassified'].map(v=>({dataset:{schriftart:v},hidden:false}));
const root={querySelectorAll(){return rows}};
global.document={getElementById(id){return id==='schriftart'?root:control}};
'''
    checks = '''assert.equal(rows.filter(r=>!r.hidden).length,5);
for(const s of ['h','m','g','unclassified']){control.value=s;control.apply();assert.deepEqual(rows.filter(r=>!r.hidden).map(r=>r.dataset.schriftart),[s]);}
control.value='';control.apply();assert.equal(rows.filter(r=>!r.hidden).length,5);
'''
    script = tmp_path / "filter.cjs"
    script.write_text(fixture + "\neval(" + json.dumps(SCRIPT) + ");\n" + checks, encoding="utf8")
    subprocess.run([node, str(script)], check=True, capture_output=True, timeout=10)
