"""Evidence limits, frozen denominators, escaping and source order in loss analysis."""

import base64
import csv
import hashlib
import json
import shutil
import subprocess

import pytest
from PIL import Image

from participant_bench.io import file_hash, read_json, write_json, write_jsonl
from participant_bench.ocr_observations import audit
from participant_bench.roster_benchmark.config import BenchmarkConfig
from participant_bench.roster_benchmark.error_report import SCRIPT, diagnose_field, render_errors
from participant_bench.roster_benchmark.evaluation import evaluate_run
from participant_bench.schema import Box, PageResult, VisualParticipant


def page():
    person = VisualParticipant(first_name="Anna", last_name="Berg", personnel_number=None, department=None).participant()
    person.bbox = Box(x0=.1, x1=.8, y0=.2, y1=.3)
    return PageResult(run_id="test", document_id="doc", page_id="doc-p0001", page_number=1,
                      method_id="paddle_llm", status="partial", parse_status="valid", participants=[person])


def field(**changes):
    return dict(dict(method="paddle_llm", field="short_code", reference_contribution="1", prediction_contribution="0",
                     exact="False", normalized_prediction="", reference_value="AB7", document_id="doc", page_number="1",
                     output_index="0", reference_row="2"), **changes)


def test_unlocalized_reference_or_missing_raw_text_never_proves_ocr_failure():
    for row, current in [(field(), page()), (field(output_index="", page_number=""), None)]:
        finding = diagnose_field(row, current, {}, {"observations": []})
        assert finding["category"] == "unknown" and finding["certainty"] == "unknown"
    assert "ohne Seitenlokalisierung" in diagnose_field(field(output_index=""))["reason"]


def test_literal_in_another_person_or_page_is_not_a_model_omission():
    observations = [dict(text="AB7", bbox=dict(x0=.1, x1=.8, y0=.7, y1=.8), submitted_to_assignment=True)]
    assert diagnose_field(field(), page(), {}, dict(observations=observations))["category"] == "unknown"
    observations[0]["bbox"].update(y0=.2, y1=.3)
    finding = diagnose_field(field(), page(), {}, dict(observations=observations))
    assert finding["category"] == "model_omission" and finding["certainty"] == "proven"
    observations[0]["submitted_to_assignment"] = False
    assert diagnose_field(field(), page(), {}, dict(observations=observations))["category"] == "not_submitted"
    observations[0]["submitted_to_assignment"] = None
    assert diagnose_field(field(), page(), {}, dict(observations=observations))["certainty"] == "unknown"


def test_rejected_field_is_proven_rejection_but_not_proven_correct_ocr():
    current = page()
    current.participants[0].department.state = "failed"
    finding = diagnose_field(field(), current)
    assert finding["category"] == "validation" and finding["certainty"] == "proven"
    assert "nicht die Richtigkeit" in finding["reason"]


def test_ocr_literal_with_wrong_reference_stays_a_hypothesis():
    current = page()
    current.participants[0].department.value = "AB1"
    result = diagnose_field(field(normalized_prediction="ab1"), current, {}, dict(observations=[
        dict(text="AB1", bbox=current.participants[0].bbox.model_dump())]))
    assert result["category"] == "ocr_suspected" and result["certainty"] == "hypothesis"


def test_paddle_prompt_ledger_uses_exact_text_and_geometry_even_with_low_scores():
    raw = dict(structure=dict(native=dict(width=100, height=100, overall_ocr_res=dict(
        rec_texts=["AB7", "Ink"], rec_boxes=[[10, 20, 20, 30], [70, 20, 80, 30]], rec_scores=[.001, .01]))),
        assignment=dict(text_prompt=json.dumps(dict(current_rows=[dict(id="r1", layout_cells=[
            ["AB7", dict(x0=.1, x1=.2, y0=.2, y1=.3), .001, []]])])), participants_before_validation=[{}]))
    result = audit(raw, page())
    assert result["counts"]["observations"] == 2
    assert result["counts"]["submitted"] == 1 and result["counts"]["not_submitted"] == 1
    assert result["counts"]["model_rows_proposed"] == 1


def test_filters_apply_combined_method_page_field_category_and_search(tmp_path):
    node = shutil.which("node")
    if not node:
        pytest.skip("Node is unavailable for the static filter interaction check")
    program = """
const assert=require('node:assert/strict');
const ids=['method','page','field','category','certainty','result','search','visible-count'];
const controls=Object.fromEntries(ids.map(id=>[id,{value:'',addEventListener(_,fn){this.apply=fn;}}]));
const cards=[
 {dataset:{method:'ocr_llm',page:'d:1',field:'user_id',category:'unknown',certainty:'unknown',result:'missing'},textContent:'value one'},
 {dataset:{method:'paddle_llm',page:'d:2',field:'short_code',category:'validation',certainty:'proven',result:'missing'},textContent:'value two'},
 {dataset:{method:'paddle_llm',page:'unknown',field:'short_code',category:'unknown',certainty:'unknown',result:'missing'},textContent:'no page'}];
const sections=[{dataset:{method:'paddle_llm',page:'d:2'}},{dataset:{method:'ocr_llm',page:'d:1'}}];
global.document={getElementById:id=>controls[id],querySelectorAll:selector=>selector==='article.field-case'?cards:sections};
""" + SCRIPT + """
const visible=()=>cards.filter(c=>!c.hidden).length;
assert.equal(visible(),3);
controls.method.value='paddle_llm';controls.method.apply();assert.equal(visible(),2);
controls.page.value='d:2';controls.page.apply();assert.equal(visible(),1);assert.equal(sections[1].hidden,true);
controls.field.value='user_id';controls.field.apply();assert.equal(visible(),0);
controls.field.value='short_code';controls.category.value='validation';controls.certainty.value='proven';
controls.search.value='TWO';controls.search.apply();assert.equal(visible(),1);
controls.category.value='unknown';controls.category.apply();assert.equal(visible(),0);
for(const id of ids)controls[id].value='';controls.search.apply();assert.equal(visible(),3);
"""
    script = tmp_path / "filter-check.cjs"
    script.write_text(program, encoding="utf-8")
    subprocess.run([node, str(script)], check=True, capture_output=True, timeout=10)


def test_error_report_keeps_scores_frozen_links_crops_and_marks_unknown_pages(tmp_path, monkeypatch):
    source, reference = tmp_path / "source", tmp_path / "reference.csv"
    current = page()
    write_json(source / "manifest.json", dict(inputs=[dict(kind="pdf", sha256="doc", path="123456.pdf")]))
    write_json(source / "summary.json", dict(paddle_llm=dict(status="partial", output_kind="structured")))
    write_jsonl(source / "paddle_llm/extractions.jsonl", [current.model_dump()])
    raw = dict(structure=dict(native=dict(width=100, height=100, overall_ocr_res=dict(
        rec_texts=['<script>alert("test")</script>'], rec_boxes=[[10, 20, 20, 30]], rec_scores=[.001])),
        tables=[dict(html="<table><tr><td>raw cell</td></tr></table>")]),
        assignment=dict(raw_response='{"value":"<script>alert(1)</script>"}'))
    write_json(source / "paddle_llm/raw-doc-p0001.json", raw)
    (source / "pages").mkdir()
    Image.new("RGB", (100, 100), "white").save(source / "pages/doc-p0001.png")
    with reference.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["Class ID", "User ID", "First Name", "Last Name", "Organization"])
        writer.writerows([["123456", "001", "Anna", "Berg", "AB7"], ["123456", "002", "Karla", "Weber", "CD8"]])
    output, metrics = evaluate_run(source, reference, BenchmarkConfig(), tmp_path / "results")
    protected = {p: file_hash(p) for p in [output / "metrics.json", output / "fields.csv", source / "paddle_llm/extractions.jsonl"]}
    reference.unlink()
    monkeypatch.setattr("socket.create_connection", lambda *a, **kw: pytest.fail("No network"))
    render_errors(output)
    assert all(file_hash(p) == value for p, value in protected.items())
    checks = read_json(output / "error_analysis/checks.json")
    counts = checks["counts"]["paddle_llm"]
    assert counts["correct"] + counts["incorrect"] + counts["missing"] == 8
    assert counts["missing"] == metrics["paddle_llm"]["overall"]["missing_fields"]
    html = (output / "extraction_errors.html").read_text(encoding="utf-8")
    assert '&lt;script&gt;' in html and '<script>alert' not in html
    assert "Seite unbekannt" in html and 'data-page="unknown"' in html
    assert 'data-page="doc:1"' in html and list((output / "error_analysis").glob("*.png"))
    fingerprint = base64.b64encode(hashlib.sha256(SCRIPT.encode()).digest()).decode()
    assert fingerprint in html
    for control in ("method", "page", "field", "category", "certainty", "result"):
        assert f'id="{control}"' in html
    assert 'href="extraction_errors.html"' in (output / "report.html").read_text(encoding="utf-8")
    assert "raw cell" in html


def test_report_rejects_changed_predictions(tmp_path):
    source, output = tmp_path / "source", tmp_path / "result"
    write_json(output / "identity.json", dict(source_run=str(source), extraction_sha256=dict(paddle_llm="changed")))
    write_json(output / "metrics.json", dict(methods=dict(paddle_llm={})))
    (output / "fields.csv").write_text("method,field\n", encoding="utf-8")
    write_jsonl(source / "paddle_llm/extractions.jsonl", [page().model_dump()])
    with pytest.raises(ValueError, match="verändert"):
        render_errors(output)
