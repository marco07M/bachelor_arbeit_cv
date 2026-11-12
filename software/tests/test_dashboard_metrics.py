"""Conservative identity, complete GT, effort provenance and a single dashboard data basis."""

import json
import re
import shutil
import subprocess
from dataclasses import replace

import pytest
from test_roster_benchmark import prediction, ref
from test_scientific_evaluation import frozen_report

from participant_bench.io import read_json
from participant_bench.roster_benchmark.config import MatchingConfig, ReferenceConfig
from participant_bench.roster_benchmark.dashboard_report import SCRIPT
from participant_bench.roster_benchmark.metrics import aggregate, course_metrics
from participant_bench.roster_benchmark.scientific import analyze
from participant_bench.roster_benchmark.scientific_efficiency import (
    costs_per_1000,
    distribution,
    enrich_effort,
)
from participant_bench.schema import PageResult


def evaluate(predictions, references, *, swap=False):
    return course_metrics(
        "123456",
        predictions,
        references,
        MatchingConfig(mode="best_fit", compare_name_orientations=swap),
        ReferenceConfig(),
        score_original_roles=True,
    )


def test_best_fit_pair_alone_is_not_an_identified_or_complete_participant():
    score, rows, _, _ = evaluate([prediction(first="Anny", last="Other", user="009999")], [ref()])
    assert score["assigned_participants"] == 1
    assert score["participant_quality"]["identity_exact_participants"] == 0
    assert score["participant_quality"]["participant_recall"] == 0
    assert not rows[0]["fully_correct_required"]


def test_identity_requires_all_assessable_identity_fields_even_with_an_exact_id():
    score, _, _, _ = evaluate([prediction(first="Anny")], [ref()])
    assert score["assigned_participants"] == 1
    assert score["participant_quality"]["participant_recall"] == 0
    score, _, _, _ = evaluate([prediction(code="wrong")], [ref()])
    assert score["participant_quality"]["participant_recall"] == 1
    assert score["participant_quality"]["complete_participant_accuracy"] == 0


def test_swapped_names_are_not_strictly_correct_identity_but_old_swap_score_remains():
    score, _, _, _ = evaluate([prediction(first="Weber", last="Anna")], [ref()], swap=True)
    assert score["participant_quality"]["participant_recall"] == 0
    old, _, _, _ = course_metrics(
        "123456",
        [prediction(first="Weber", last="Anna")],
        [ref()],
        MatchingConfig(mode="best_fit", compare_name_orientations=True),
        ReferenceConfig(),
    )
    assert old["overall"]["exact_fields"] == 4 and score["overall"]["exact_fields"] == 2


def test_partial_gt_is_separate_from_complete_required_records_and_missing_rows_count():
    partial = ref(row=3, user="masked", first="Ben", last="Meyer")
    partial = replace(partial, field_states={"user_id": "masked"})
    score, rows, _, _ = evaluate(
        [prediction(), prediction(index=1, user=None, first="Ben", last="Meyer")], [ref(), partial]
    )
    q = score["participant_quality"]
    assert q["complete_reference_participants"] == 1 and q["partial_reference_participants"] == 1
    assert q["fully_correct_complete_participants"] == q["fully_correct_partial_participants"] == 1
    assert q["complete_participant_accuracy"] == 1 and q["participant_recall"] == 1
    assert next(r for r in rows if r["reference_row"] == 3)["reference_completeness"] == "partial"
    missing, _, _, _ = evaluate([], [ref(), partial])
    assert missing["participant_quality"]["complete_participant_accuracy"] == 0
    assert missing["participant_quality"]["participant_recall"] == 0


def test_explicit_empty_gt_requires_explicit_empty_prediction_and_partial_only_has_no_full_rate():
    reference = ref(user="")
    reference = replace(reference, field_states={"user_id": "empty"})
    good, _, _, _ = evaluate([prediction(user="")], [reference])
    unknown, _, _, _ = evaluate([prediction(user=None)], [reference])
    assert good["participant_quality"]["complete_participant_accuracy"] == 1
    assert unknown["participant_quality"]["complete_participant_accuracy"] == 0
    reference = replace(reference, field_states={"user_id": "masked"})
    partial, _, _, _ = evaluate([prediction(user=None)], [reference])
    assert partial["fully_exact_participants"] == 1  # historical partial-GT counter is preserved
    assert partial["participant_quality"]["complete_participant_accuracy"] is None


def test_ambiguous_reference_identity_is_excluded_from_identity_denominator():
    references = [ref(user=""), ref(row=3, user="")]
    score, _, _, _ = evaluate([prediction(user="")], references)
    q = score["participant_quality"]
    assert q["identity_assessable_participants"] == 0 and q["identity_unassessable_participants"] == 2
    assert q["participant_recall"] is None


def test_extra_participant_and_failed_fields_preserve_old_field_penalties():
    p = prediction()
    p.person.department.state = "failed"
    score, _, _, _ = evaluate([p, prediction(index=1, first="New", last="Person", user="999999")], [ref()])
    assert score["extra_participants"] == 1 and score["overall"]["missing_fields"] == 1
    assert score["participant_quality"]["complete_participant_accuracy"] == 0
    assert score["overall"]["field_coverage"] == 0.75


def test_participant_micro_aggregation_pools_denominators_not_course_percentages():
    first = evaluate([prediction()], [ref()])[0]
    second = evaluate([], [ref(row=i + 10, user=str(i), first=f"Name{i}", last="Other") for i in range(9)])[0]
    score = aggregate([first, second])
    assert score["participant_quality"]["complete_participant_accuracy"] == 0.1
    assert score["participant_quality"]["participant_recall"] == 0.1


def test_time_distribution_keeps_zero_and_missing_values_unknown():
    d = distribution([None, 0, 2, 4, float("nan"), -1])
    assert d["n"] == 3 and d["median"] == 2 and d["minimum"] == 0
    assert distribution([])["median"] is None


def test_call_counters_are_not_invented_and_helpers_are_included():
    page = PageResult(
        run_id="r",
        document_id="d",
        page_id="d-p0001",
        page_number=1,
        method_id="paddle_llm",
        status="success",
        parse_status="valid",
        calls=2,
    )
    rows = [dict(document_id="d", page_wall_seconds=4)]
    data = enrich_effort(
        dict(scope_matches=True),
        rows,
        [page],
        dict(model_calls=2, generation_calls=1),
        "paddle_llm",
        dict(signature=dict(backend="opencv")),
    )
    assert data["selected_actual_calls"] == 2 and rows[0]["llm_calls"] == 2 and rows[0]["vlm_calls"] == 0
    other = [dict(document_id="d", page_wall_seconds=4)]
    data = enrich_effort(dict(scope_matches=True), other, [page], dict(model_calls=1), "paddle_llm", {})
    assert data["selected_actual_calls"] is None and other[0]["actual_calls"] is None


def test_cost_scenario_converts_pages_to_documents_without_claiming_measurements():
    assert costs_per_1000({}, documents=1, pages=2)["scenario_eur_per_1000"] is None
    config = dict(
        costs=dict(
            volume=10,
            hourly_rate_eur=60,
            manual_minutes_per_page=3,
            review_minutes_per_page=1,
            local_operating_eur_per_page=0.2,
        )
    )
    cost = costs_per_1000(config, documents=2, pages=6)
    assert cost["scenario_eur_per_1000"] == pytest.approx(600)
    assert cost["measured_eur_per_1000"] is None
    config["costs"]["kind"] = "measured"
    cost = costs_per_1000(config, documents=2, pages=6)
    assert cost["status"] == "declared_measurement_unverified" and cost["measured_eur_per_1000"] is None


def test_dashboard_and_error_analysis_share_strict_counters_and_no_duplicate_causes(tmp_path):
    report, _, _, metadata = frozen_report(tmp_path)
    result = analyze(report, metadata=metadata, phase="test", resamples=200, figures=False)
    html = (report / "report.html").read_text(encoding="utf-8")
    for id in ("overall", "fields", "errors", "robustness", "efficiency", "statistics"):
        assert f'id="{id}"' in html
    assert "data-sort=" in html and "error-class" in html and "Content-Security-Policy" in html
    assert (report / "standard_report.html").is_file()
    errors = read_json(report / "error_analysis/summary.json")
    primary = [r for r in result["overview"] if r.get("mode") == "original_roles"]
    assert errors["field_error_total"] == sum(
        r["missing_fields"] + r["incorrect_fields"] + r["extra_fields"] for r in primary
    )
    assert "Originalrollen" in errors["grading_label"]
    # Primary overview remains free of per-person values; they stay on existing detail pages.
    assert not re.search(r"\b(?:Anna|Weber)\b", html)
    assert read_json(report / "scientific/analysis.json")["definitions"]
    assert (report / "scientific/participant_scores.csv").is_file()
    grading = read_json(report / "scientific/error_grading.json")
    assert len(grading["fields"]) == len(
        {
            (r["method"], r["class_id"], r["reference_row"], r["document_id"], r["output_index"], r["field"])
            for r in grading["fields"]
        }
    )


def test_dashboard_script_tabs_sort_missing_last_and_combined_filters(tmp_path):
    node = shutil.which("node")
    if not node:
        pytest.skip("Node is needed for the existing offline JavaScript regression mechanism")
    fixture = r"""
const assert=require('node:assert/strict');
function element(dataset={}){return {dataset,hidden:false,value:'',textContent:'',attrs:{},events:{},
 addEventListener(name,fn){this.events[name]=fn},setAttribute(k,v){this.attrs[k]=v},
 removeAttribute(k){delete this.attrs[k]},dispatchEvent(e){this.events[e.type]?.()}};}
const ids=['overall','fields','errors','robustness','efficiency','statistics'];
const panels=ids.map(id=>Object.assign(element(),{id,classList:{contains:c=>c==='panel'}}));
const tabs=ids.map(panel=>element({panel}));
const body={rows:[3,null,1,2].map(v=>({cells:[element({value:v===null?'':String(v)})]})),
 appendChild(row){this.rows.splice(this.rows.indexOf(row),1);this.rows.push(row)}};
const head=element(),sort=element({sort:'0'}),table={tBodies:[body],tHead:{rows:[{cells:[head]}]}};
sort.closest=k=>k==='table'?table:head;
const filters=Object.fromEntries(['method','document','class','field','cause','certainty'].map(k=>['error-'+k,element()]));
const errors=[element({method:'a',document:'d1',class:'c1',field:'first_name',cause:'unknown',certainty:'unknown'}),
 element({method:'a',document:'d2',class:'c2',field:'last_name',cause:'validation',certainty:'proven'}),
 element({method:'b',document:'d1',class:'c1',field:'last_name',cause:'validation',certainty:'proven'})];
const feature=element();feature.value='stratum';
const strata=[element({feature:'stratum'}),element({feature:'multipage_pdf'})],visible=element();
global.location={hash:''};global.window={addEventListener(name,fn){this[name]=fn}};
global.document={getElementById(id){return panels.find(p=>p.id===id)||filters[id]||({'error-visible':visible,'robustness-feature':feature})[id]},
 querySelectorAll(q){return ({'[data-panel]':tabs,'.panel':panels,'[data-sort]':[sort],
 '.error-filter':Object.values(filters),'#error-table tbody tr':errors,'#strata-table tbody tr':strata})[q]||[]}};
"""
    checks = r"""
assert.deepEqual(panels.filter(p=>!p.hidden).map(p=>p.id),['overall']);
tabs[2].events.click();assert.equal(location.hash,'errors');assert.equal(panels[2].hidden,false);
location.hash='#efficiency';window.hashchange();assert.equal(panels[4].hidden,false);
location.hash='#nonexistent';window.hashchange();assert.equal(panels[0].hidden,false);
sort.events.click();assert.deepEqual(body.rows.map(r=>r.cells[0].dataset.value),['1','2','3','']);
assert.equal(head.attrs['aria-sort'],'ascending');
sort.events.click();assert.deepEqual(body.rows.map(r=>r.cells[0].dataset.value),['3','2','1','']);
assert.equal(head.attrs['aria-sort'],'descending');
filters['error-method'].value='a';filters['error-class'].value='c1';filters['error-cause'].value='unknown';
filters['error-method'].events.change();assert.deepEqual(errors.map(r=>r.hidden),[false,true,true]);
assert.equal(visible.textContent,'1');filters['error-field'].value='last_name';
filters['error-field'].events.change();assert.equal(visible.textContent,'0');
assert.deepEqual(strata.map(r=>r.hidden),[false,true]);feature.value='multipage_pdf';
feature.dispatchEvent(new Event('change'));assert.deepEqual(strata.map(r=>r.hidden),[true,false]);
"""
    script = tmp_path / "dashboard.cjs"
    script.write_text(fixture + "\neval(" + json.dumps(SCRIPT) + ");\n" + checks, encoding="utf-8")
    subprocess.run([node, str(script)], check=True, capture_output=True, timeout=10)
