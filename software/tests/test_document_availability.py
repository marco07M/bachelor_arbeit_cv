"""Independent availability labels must never be inferred from extraction omissions."""

import json
import shutil
import subprocess
from copy import deepcopy

import pytest
import yaml
from test_roster_benchmark import prediction, ref, write_reference

from participant_bench.io import file_hash, read_json, write_json, write_jsonl
from participant_bench.roster_benchmark.config import BenchmarkConfig, MatchingConfig, ReferenceConfig
from participant_bench.roster_benchmark.document_availability import (
    build,
    classify,
    context,
    field_id,
    load_reviews,
    pipeline,
    project,
    reference_fields,
    review_template,
)
from participant_bench.roster_benchmark.evaluation import evaluate_run
from participant_bench.roster_benchmark.metrics import course_metrics
from participant_bench.roster_benchmark.missing_fields_report import SCRIPT
from participant_bench.roster_benchmark.scientific import reanalyze
from participant_bench.schema import PageResult


def unit_case():
    config = BenchmarkConfig(matching=MatchingConfig(ignore_leading_user_id_zeros=True))
    _, _, rows, _ = course_metrics(
        "123456", [prediction(user=None, code=None)], [ref()], config.matching, ReferenceConfig()
    )
    fields = [dict(r, candidate="vlm") for r in rows]
    ctx = dict(
        config=config,
        courses={"123456": ["doc"]},
        documents={"doc": dict(verified=True, pages=[1, 2], path="synthetic.pdf")},
        binding=dict(version="document-availability-v1", reference_snapshot_sha256="test", documents=["doc"]),
    )
    refs = reference_fields(fields, ctx)
    return fields, ctx, refs


def checked(key, state="readable", value="Anna"):
    return dict(
        field_id=key,
        availability=state,
        document_value=value,
        locations=[dict(document_id="doc", page_number=1, bbox=None)],
        reviewed_pages=[dict(document_id="doc", page_number=n) for n in (1, 2)],
        reviewer="synthetic-reviewer",
        reviewed_at="2026-11-17T10:00:00Z",
        anchor_note="Independent printed row anchor",
        note="Original inspected independently",
        independent_of_predictions=True,
        reference_person_verified=True,
        review_method="manual_pdf_review",
    )


def write_review(tmp_path, ctx, items):
    path = tmp_path / "review.json"
    write_json(path, dict(**ctx["binding"], annotations=items))
    return path


def test_omitted_fields_and_ocr_absence_never_create_document_labels():
    fields, ctx, refs = unit_case()
    reviews = load_reviews(None, refs, ctx)
    result = project(fields, reviews)
    assert result["baseline"]["reference_fields"] == 4 and result["baseline"]["missing_fields"] == 2
    assert result["eligible_fields"] == 0 and result["readable_reference_subset"]["exact_f1"] is None
    assert result["readable_reference_subset"]["detected_similarity"] is None
    assert result["unchecked_in_baseline"] and result["availability_counts"] == {"unchecked": 4}
    row = next(r for r in fields if r["field"] == "user_id")
    assert classify(row, reviews[field_id(row)], dict(observations=[]), [])[0] == "unknown"


def test_partial_review_reuses_frozen_counters_and_keeps_unknown_baseline(tmp_path):
    fields, ctx, refs = unit_case()
    old = deepcopy(fields)
    items = [
        checked(field_id(r), value=r["reference_value"])
        for r in fields
        if r["field"] in ("first_name", "last_name")
    ]
    reviews = load_reviews(write_review(tmp_path, ctx, items), refs, ctx)
    result = project(fields, reviews)
    assert fields == old
    assert result["baseline"]["field_coverage"] == 0.5 and result["baseline"]["exact_recall"] == 0.5
    assert result["eligible_fields"] == 2 and result["readable_reference_subset"]["exact_f1"] == 1
    assert result["readable_reference_subset"]["detected_similarity"] == 1
    assert result["availability_counts"]["unchecked"] == 2


def test_absent_unreadable_and_reference_differences_have_separate_meanings(tmp_path):
    fields, ctx, refs = unit_case()
    states = dict(first_name=("readable", "Anma"), last_name=("unreadable", None), user_id=("absent", None))
    items = [checked(field_id(r), *states[r["field"]]) for r in fields if r["field"] in states]
    reviews = load_reviews(write_review(tmp_path, ctx, items), refs, ctx)
    result = project(fields, reviews)
    assert result["baseline"]["reference_fields"] == 4 and result["readable_reference_conflicts"] == 1
    assert (
        result["eligible_fields"] == 0
        and result["availability_contributions"]["absent"]["missing_fields"] == 1
    )
    by_field = {r["field"]: r for r in fields}
    for field, cause in [
        ("first_name", "reference_matching"),
        ("last_name", "unreadable"),
        ("user_id", "not_in_document"),
    ]:
        row = by_field[field]
        assert classify(row, reviews[field_id(row)], {}, [])[0] == cause


@pytest.mark.parametrize(
    "bad",
    [
        "binding",
        "document",
        "person",
        "independence",
        "reviewer",
        "reviewed_at",
        "anchor_note",
        "note",
        "location",
        "page",
        "box",
        "nan",
        "boolean_box",
        "not_verified",
        "readable_empty",
        "absent_pages",
        "duplicate",
        "unknown_key",
        "status",
    ],
)
def test_checked_labels_require_independent_verified_document_evidence(tmp_path, bad):
    fields, ctx, refs = unit_case()
    item = checked(field_id(fields[0]))
    items = [item]
    if bad == "binding":
        path = write_review(tmp_path, ctx, items)
        data = read_json(path)
        data["reference_snapshot_sha256"] = "other"
        write_json(path, data)
    else:
        if bad == "document":
            item["locations"][0]["document_id"] = "other"
        elif bad == "person":
            item["reference_person_verified"] = False
        elif bad == "independence":
            item["independent_of_predictions"] = False
        elif bad in ("reviewer", "reviewed_at", "anchor_note", "note"):
            item[bad] = ""
        elif bad == "location":
            item["locations"] = []
        elif bad == "page":
            item["locations"][0]["page_number"] = 3
        elif bad in ("box", "nan", "boolean_box"):
            item["locations"][0]["bbox"] = dict(
                x0=0.8 if bad == "box" else float("nan") if bad == "nan" else True, y0=0, x1=0.5, y1=1
            )
        elif bad == "not_verified":
            ctx["documents"]["doc"]["verified"] = False
        elif bad == "readable_empty":
            item["document_value"] = ""
        elif bad == "absent_pages":
            item.update(availability="absent", reviewed_pages=[])
        elif bad == "duplicate":
            items.append(dict(item))
        elif bad == "unknown_key":
            item["field_id"] = "different"
        elif bad == "status":
            item["availability"] = "probably_empty"
        path = write_review(tmp_path, ctx, items)
    with pytest.raises(ValueError):
        load_reviews(path, refs, ctx)


def test_normalization_is_shared_and_never_fuzzy_for_review_agreement(tmp_path):
    fields, ctx, refs = unit_case()
    items = [
        checked(field_id(r), value="  ANNA  " if r["field"] == "first_name" else "1234")
        for r in fields
        if r["field"] in ("first_name", "user_id")
    ]
    result = load_reviews(write_review(tmp_path, ctx, items), refs, ctx)
    assert all(result[i["field_id"]]["eligible"] for i in items)
    items[0]["document_value"] = "Anma"
    result = load_reviews(write_review(tmp_path, ctx, items), refs, ctx)
    assert result[items[0]["field_id"]]["reference_agrees"] is False


def test_stage_evidence_is_not_document_evidence_and_equality_is_only_a_hint():
    fields, ctx, refs = unit_case()
    row = fields[2]
    review = load_reviews(None, refs, ctx)[field_id(row)]
    cause, certainty, reason = classify(
        row, review, dict(category="column_mapping", certainty="proven", reason="saved block"), []
    )
    assert cause == "not_adopted" and certainty == "stage_verified" and "keine Lesbarkeit" in reason
    assert review["availability"] == "unchecked"
    assert classify(row, review, {}, [dict(value="001234")])[0:2] == ("wrong_assignment", "hypothesis")
    assert "kein vorgeschaltetes OCR" in pipeline("vlm")


def test_direct_vlm_auxiliary_ocr_is_not_a_primary_input_failure():
    fields, ctx, refs = unit_case()
    row = fields[2]
    review = load_reviews(None, refs, ctx)[field_id(row)]
    diagnostic = dict(category="model_omission", certainty="proven", reason="Auxiliary OCR")
    assert classify(row, review, diagnostic, [])[0] == "unknown"
    row = dict(row, candidate="ocr_llm")
    assert classify(row, review, diagnostic, [])[0:2] == ("not_adopted", "stage_verified")


def test_low_similarity_alone_is_not_an_independent_matching_failure():
    fields, ctx, refs = unit_case()
    row = dict(fields[2], matching_review_reasons="low_similarity")
    review = load_reviews(None, refs, ctx)[field_id(row)]
    assert classify(row, review, {}, [])[0] == "unknown"
    diagnostic = dict(category="column_mapping", certainty="proven")
    assert classify(row, review, diagnostic, [])[0] == "not_adopted"


def test_absence_requires_originals_for_every_course_document(tmp_path):
    fields, ctx, refs = unit_case()
    ctx["documents"]["other"] = dict(verified=False, pages=[1], path="unavailable.pdf")
    ctx["courses"]["123456"].append("other")
    ctx["binding"]["documents"].append("other")
    item = checked(field_id(fields[0]), "absent", None)
    item["reviewed_pages"].append(dict(document_id="other", page_number=1))
    with pytest.raises(ValueError, match="verifizierte Originale"):
        load_reviews(write_review(tmp_path, ctx, [item]), refs, ctx)


def actual_report(tmp_path):
    import pymupdf

    pdf_path = tmp_path / "123456.pdf"
    with pymupdf.open() as pdf:
        page = pdf.new_page()
        page.insert_text((50, 100), "Anna Weber")
        page.insert_text((50, 130), "???")
        pdf.save(pdf_path)
    doc = file_hash(pdf_path)
    source = tmp_path / "source"
    source.mkdir()
    manifest = dict(
        inputs=[dict(kind="pdf", sha256=doc, path=str(pdf_path))],
        pages=[dict(document_id=doc, page_number=1, page_id=doc + "-p0001")],
    )
    write_json(source / "manifest.json", manifest)
    write_json(source / "summary.json", dict(vlm=dict(status="success", output_kind="structured")))
    (source / "config.yaml").write_text(yaml.safe_dump(dict(models={})), encoding="utf8")
    item = prediction(user=None, code=None).person
    extra = prediction(first="Zora", last="Quast", user="998877", code="XYZ").person
    page = PageResult(
        run_id="synthetic",
        document_id=doc,
        page_id=doc + "-p0001",
        page_number=1,
        method_id="vlm",
        status="success",
        parse_status="valid",
        participants=[item, extra],
    )
    write_jsonl(source / "vlm/extractions.jsonl", [page.model_dump()])
    reference = tmp_path / "reference.csv"
    write_reference(reference)
    report = tmp_path / "original"
    evaluate_run(
        source,
        reference,
        BenchmarkConfig(),
        tmp_path,
        output=report,
        scientific_options=dict(resamples=200, figures=False),
    )
    return report, source, pdf_path


def test_pdf_review_html_projection_and_replay_preserve_historical_scores(tmp_path):
    report, source, pdf_path = actual_report(tmp_path)
    before = {p: file_hash(p) for root in (report, source) for p in root.rglob("*") if p.is_file()}
    before[pdf_path] = file_hash(pdf_path)
    payload, ctx = build(report)
    envelope = review_template({r["field_id"]: r for r in payload["fields"]}, ctx)
    for r in payload["fields"]:
        item = next(i for i in envelope["annotations"] if i["field_id"] == r["field_id"])
        state = (
            "readable"
            if r["field"] in ("first_name", "last_name")
            else "absent"
            if r["field"] == "user_id"
            else "unreadable"
        )
        item.update(checked(r["field_id"], state, r["reference_value"] if state == "readable" else None))
        item["locations"] = [
            dict(
                document_id=next(iter(ctx["documents"])),
                page_number=1,
                bbox=dict(x0=0.05, y0=0.05, x1=0.5, y1=0.25),
            )
        ]
        item["reviewed_pages"] = [dict(document_id=next(iter(ctx["documents"])), page_number=1)]
    annotations = tmp_path / "annotations.json"
    write_json(annotations, envelope)
    target = tmp_path / "new"
    reanalyze(report, target, document_annotations=annotations, resamples=200, figures=False)
    assert all(file_hash(p) == h for p, h in before.items())
    result = read_json(target / "missing_fields/analysis.json")
    p = result["projections"]["vlm"]
    assert p["baseline"]["reference_fields"] == 4 and p["baseline"]["predicted_fields"] == 6
    assert p["baseline"]["extra_fields"] == 4 and p["readable_reference_subset"]["exact_f1"] == 1
    assert p["readable_reference_subset"]["reference_fields"] == 2 and p["availability_counts"]["absent"] == 1
    assert (
        read_json(target / "metrics.json")["methods"]["vlm"]["overall"]
        == read_json(report / "metrics.json")["methods"]["vlm"]["overall"]
    )
    markup = (target / "missing_fields.html").read_text(encoding="utf8")
    assert "Unabhängig geprüfter Originalausschnitt" in markup and "kein vorgeschaltetes OCR" in markup
    assert "review-export" in markup and "review-import" in markup and "review-independent" in markup
    assert 'href="missing_fields.html"' in (target / "report.html").read_text(encoding="utf8")
    assert read_json(target / "missing_fields/checks.json")["missing_partition"]["vlm"]


def test_moved_original_must_match_content_hash_not_filename(tmp_path):
    report, source, pdf_path = actual_report(tmp_path)
    doc = next(iter(context(report)["documents"]))
    relocated = tmp_path / "relocated.pdf"
    shutil.copyfile(pdf_path, relocated)
    pdf_path.write_bytes(b"Different bytes under the same filename")
    assert not context(report)["documents"][doc]["verified"]
    assert context(report, {doc: str(relocated)})["documents"][doc]["verified"]
    with pytest.raises(ValueError, match="Netzwerkpfade"):
        context(report, {doc: r"\\server\share\do-not-open.pdf"})


def test_browser_filters_and_annotation_drafts_do_not_recalculate_scores(tmp_path):
    node = shutil.which("node")
    if not node:
        pytest.skip("Node unavailable")
    data = dict(
        storage_key="test",
        fields=[
            dict(
                field_id="f1",
                participant="Person",
                field="first_name",
                reference_value="Anna",
                documents=["doc"],
            )
        ],
        reviews={},
        binding=dict(version="document-availability-v1", reference_snapshot_sha256="test", documents=["doc"]),
        documents={
            "doc": dict(
                name="test.pdf",
                verified=True,
                pages=[1, 2],
                page_links={1: "p1.png", 2: "p2.png"},
                pdf_link="test.pdf",
            )
        },
        availability={"unchecked": "Ungeprueft", "readable": "Lesbar", "absent": "Leer"},
    )
    prelude = r"""
const assert=require('node:assert/strict');
class E{constructor(){this.value='';this.checked=false;this.textContent='';this.handlers={};this.children=[];}
 addEventListener(n,f){this.handlers[n]=f;}append(v){this.children.push(v);if(!this.value)this.value=v.value;}
 replaceChildren(){this.children=[];this.value='';}scrollIntoView(){}click(){this.clicked=true;}}
const ids=['review-data','method','document','field','schriftart','cause','availability','only-missing','search','visible-count',
 'review-key','review-doc','review-page','review-image','review-pdf','review-availability','review-document_value','review-reviewer',
 'review-anchor_note','review-note','review-independent','review-person','review-all-pages','review-pages-list','review-message',
 'review-x0','review-y0','review-x1','review-y1','review-save','review-export','review-import','review-reference','document-review'];
const c=Object.fromEntries(ids.map(k=>[k,new E()]));c['review-key'].value='f1';c['only-missing'].checked=true;
const rows=[{dataset:{method:'vlm',documents:'doc',field:'first_name',schriftart:'h',cause:'unknown',availability:'unchecked',missing:'true'},textContent:'alpha'},
 {dataset:{method:'ocr_llm',documents:'doc',field:'last_name',schriftart:'m',cause:'not_in_document',availability:'absent',missing:'false'},textContent:'beta'}];
const button=new E();button.dataset={reviewField:'f1'};
global.document={getElementById:k=>c[k],querySelectorAll:s=>s==='tr.field-cause'?rows:s==='[data-review-field]'?[button]:[],createElement:()=>new E()};
const storage={};global.localStorage={getItem:k=>storage[k],setItem:(k,v)=>storage[k]=v};
let exported;URL.createObjectURL=b=>{exported=b;return 'blob:fixture';};URL.revokeObjectURL=()=>{};
"""
    checks = r"""
assert.equal(rows.filter(r=>!r.hidden).length,1);c['only-missing'].checked=false;c['only-missing'].handlers.input();assert.equal(rows.filter(r=>!r.hidden).length,2);
c.method.value='vlm';c.method.handlers.input();assert.equal(rows.filter(r=>!r.hidden).length,1);
c.schriftart.value='m';c.schriftart.handlers.input();assert.equal(rows.filter(r=>!r.hidden).length,0);
button.handlers.click();assert.equal(c['document-review'].open,true);
c['review-availability'].value='readable';c['review-save'].handlers.click();assert.match(c['review-message'].textContent,/Unabh/);
c['review-independent'].checked=true;c['review-person'].checked=true;c['review-reviewer'].value='reviewer';
c['review-anchor_note'].value='printed row';c['review-note'].value='Original inspected';c['review-document_value'].value='Anna';
c['review-save'].handlers.click();let draft=JSON.parse(storage['document-review:test']).f1;assert.equal(draft.availability,'readable');
assert.equal(draft.eligible,undefined);assert.match(c['review-message'].textContent,/eingefroren/);
c['review-availability'].value='absent';c['review-save'].handlers.click();assert.match(c['review-message'].textContent,/Kursseiten/);
c['review-all-pages'].checked=true;c['review-save'].handlers.click();draft=JSON.parse(storage['document-review:test']).f1;assert.equal(draft.reviewed_pages.length,2);
c['review-export'].handlers.click();
exported.text().then(async text=>{const envelope=JSON.parse(text);assert.equal(envelope.annotations[0].availability,'absent');
 assert.equal(envelope.annotations[0].eligible,undefined);assert.equal(envelope.annotations[0].review_method,'manual_pdf_review');
 c['review-import'].files=[{text:async()=>JSON.stringify({...envelope,reference_snapshot_sha256:'different'})}];
 await c['review-import'].handlers.change();assert.match(c['review-message'].textContent,/andere/);
 c['review-import'].files=[{text:async()=>JSON.stringify(envelope)}];await c['review-import'].handlers.change();
 assert.match(c['review-message'].textContent,/Entw/);assert.equal(rows[0].dataset.availability,'unchecked');});
"""
    program = (
        prelude
        + '\nc["review-data"].textContent='
        + json.dumps(json.dumps(data))
        + ";\n"
        + SCRIPT
        + "\n"
        + checks
    )
    script = tmp_path / "browser.cjs"
    script.write_text(program, encoding="utf8")
    subprocess.run([node, str(script)], check=True, capture_output=True, timeout=10)
