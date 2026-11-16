"""Manually verifiable boundary cases and full reconciliation of the primary ledger."""

import base64
import hashlib
import html
import json
import re
import shutil
import subprocess
from dataclasses import replace

import pytest
from test_roster_benchmark import prediction, ref
from test_scientific_evaluation import frozen_report

from participant_bench.io import file_hash, read_json
from participant_bench.roster_benchmark.config import MatchingConfig, ReferenceConfig
from participant_bench.roster_benchmark.metric_audit import explain
from participant_bench.roster_benchmark.metric_audit_report import SCRIPT
from participant_bench.roster_benchmark.metric_audit_report import value as render_value
from participant_bench.roster_benchmark.metrics import course_metrics
from participant_bench.roster_benchmark.scientific import analyze
from participant_bench.schema import TextField


def evaluate(predictions, references, **options):
    return course_metrics('123456', predictions, references, MatchingConfig(mode='best_fit', **options),
                          ReferenceConfig(), score_original_roles=True)


@pytest.mark.parametrize('value', [None, ''])
def test_explicit_empty_null_and_string_are_identical_and_unknown_is_not_empty(value):
    reference = replace(ref(code=''), field_states={'short_code': 'empty'})
    p = prediction(code=None)
    p.person.department = TextField(value=value, state='empty')
    score, rows, _, _ = evaluate([p], [reference])
    assert score['overall']['correct_empty_fields'] == 1
    assert score['participant_quality']['fully_correct_complete_participants'] == 1
    assert not rows[0]['review_required']
    p.person.department = TextField(value=value, state='uncertain')
    score, rows, _, _ = evaluate([p], [reference])
    assert score['overall']['correct_empty_fields'] == 0
    assert score['participant_quality']['fully_correct_complete_participants'] == 0
    assert rows[0]['review_required']


def test_extra_whitespace_does_not_add_prediction_credit():
    p = prediction(index=1, first=None, last=None, user=None, code=None)
    p.person.first_name = TextField(value=' \t ', state='uncertain')
    before = p.person.model_dump()
    score, _, fields, _ = evaluate([prediction(), p], [ref()])
    assert score['overall']['predicted_fields'] == score['overall']['exact_fields'] == 4
    assert score['overall']['extra_fields'] == 0 and score['overall']['exact_f1'] == 1
    assert all(r['prediction_contribution'] == 0 for r in fields if r['reference_row'] is None)
    assert p.person.model_dump() == before


def test_categories_distinguish_missing_invalid_wrong_field_wrong_row_and_extra():
    references = [ref(), ref(row=3, user='555555', first='Ben', last='Kurz', code='BER')]
    _, _, fields, _ = evaluate([prediction(first='Weber', last='Anna', user='unknown', code='BER')], references,
                              compare_name_orientations=True)
    paired = [r for r in fields if r['status'] == 'matched']
    index = {('123456', 'short_code', 'ber'): {3}}
    assert {r['field']: explain(r, paired, index)['category'] for r in paired} == {
        'first_name': 'wrong_field', 'last_name': 'wrong_field', 'user_id': 'invalid_placeholder',
        'short_code': 'other_reference'}
    missing = [r for r in fields if r['status'] == 'missing']
    assert len(missing) == 4
    assert all(explain(r, missing, {})['category'] == 'missing_participant' for r in missing)
    score, _, fields, _ = evaluate([prediction(), prediction(index=1)], [ref()])
    extras = [r for r in fields if r['reference_row'] is None]
    assert len(extras) == 4 and all(explain(r, extras, {})['category'] == 'extra' for r in extras)
    assert score['overall']['fp'] == 4 and score['overall']['fn'] == 0


def test_normalization_and_soft_credit_remain_separate():
    score, _, fields, _ = evaluate([prediction(first='  ANNA  ', user=' 0001234 ')], [ref()],
                                   ignore_leading_user_id_zeros=True)
    assert score['overall']['exact_fields'] == 4 and score['overall']['raw_exact_fields'] == 2
    score, _, fields, _ = evaluate([prediction(first='Anma', code=None)], [ref()])
    assert score['overall']['reference_fields'] == 4
    assert score['overall']['exact_fields'] == 2 and score['overall']['incorrect_fields'] == 1
    assert score['overall']['missing_fields'] == 1 and score['overall']['field_coverage'] == .75
    assert score['overall']['soft_f1'] > score['overall']['exact_f1']


def test_ledger_reconciles_every_method_and_preserves_frozen_sources(tmp_path):
    report, source, reference, metadata = frozen_report(tmp_path)
    protected = {p: file_hash(p) for p in source.rglob('*') if p.is_file()}
    protected[reference] = file_hash(reference)
    baseline = (report / 'metrics.json').read_bytes()
    result = analyze(report, metadata=metadata, resamples=200, figures=False)
    audit = read_json(report / 'scientific/metric_audit.json')
    assert audit == result['metric_audit']
    assert all(v['matches_metrics'] and v['reference_partition'] for v in audit['checks'].values())
    assert all(r['page_number'] is None and r['location_status'] == 'course_only_page_unknown'
               for r in audit['fields'] if r['status'] == 'missing')
    assert all(not r['original_links'] for r in audit['fields'])  # synthetic PDFs do not exist
    markup = (report / 'report.html').read_text(encoding='utf8')
    scripts = re.findall(r'<script>(.*?)</script>', markup, re.S)
    assert len(scripts) == 1
    fingerprint = base64.b64encode(hashlib.sha256(scripts[0].encode()).digest()).decode()
    assert "script-src 'sha256-" + fingerprint + "'" in html.unescape(markup)
    assert {r['category'] for r in audit['fields']} >= {'correct', 'wrong_field', 'missing_participant', 'unassessed'}
    assert (report / 'metrics.json').read_bytes() == baseline
    assert all(file_hash(p) == h for p, h in protected.items())
    again = analyze(report, metadata=metadata, resamples=200, figures=False)
    assert again['metric_audit'] == result['metric_audit']


def test_raw_values_preserve_whitespace_without_html_execution():
    text = ' <img src=x onerror=alert(1)>  '
    markup = render_value(text)
    assert '<img' not in markup and '&lt;img' in markup
    assert html.unescape(markup.removeprefix('<code>').removesuffix('</code>')) == json.dumps(text)


def test_audit_script_combines_filters_search_and_reset_independently(tmp_path):
    node = shutil.which('node')
    if not node:
        pytest.skip('Node required for offline JavaScript test')
    fixture = r"""
const assert=require('node:assert/strict');
function control(dataset={}){return {dataset,value:'',events:{},addEventListener(n,f){this.events[n]=f}}}
function root(){const controls=['method','document','page','field','category'].map(k=>control({filter:k}));
 const search=control(),reset=control(),visible={textContent:''};
 const rows=[{dataset:{method:'a',document:'d',page:'1',field:'first_name',category:'wrong_field'},textContent:'Anma',hidden:false},
 {dataset:{method:'b',document:'d',page:'unknown',field:'user_id',category:'missing_value'},textContent:'null',hidden:false}];
 return {controls,search,reset,visible,rows,querySelectorAll(q){return q==='[data-filter]'?controls:rows},
 querySelector(q){return {'[type=search]':search,'[data-reset]':reset,'[data-visible]':visible}[q]}};}
const fields=root(),participants=root();global.document={getElementById(id){return {'audit-fields':fields,'audit-participants':participants}[id]}};
"""
    checks = r"""
assert.equal(fields.visible.textContent,'2');
fields.controls[0].value='a';fields.controls[1].value='d';fields.controls[2].value='1';
fields.controls[3].value='first_name';fields.controls[4].value='wrong_field';
fields.controls[0].events.input();assert.deepEqual(fields.rows.map(r=>r.hidden),[false,true]);
assert.equal(participants.visible.textContent,'2');
fields.search.value='NULL';fields.search.events.input();assert.equal(fields.visible.textContent,'0');
fields.reset.events.click();assert.equal(fields.visible.textContent,'2');
fields.search.value='ANMA';fields.search.events.input();assert.equal(fields.visible.textContent,'1');
"""
    script = tmp_path / 'audit.cjs'
    script.write_text(fixture + '\neval(' + json.dumps(SCRIPT) + ');\n' + checks, encoding='utf8')
    subprocess.run([node, str(script)], check=True, capture_output=True, timeout=10)
