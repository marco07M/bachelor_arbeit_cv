"""Style error shares and rates use fixed GT denominators and existing field vectors."""

import json
import shutil
import subprocess
from copy import deepcopy
from dataclasses import replace

import pytest
from test_roster_benchmark import prediction, ref
from test_scientific_evaluation import frozen_report

from participant_bench.io import file_hash, read_json
from participant_bench.roster_benchmark.config import MatchingConfig, ReferenceConfig
from participant_bench.roster_benchmark.document_availability import field_id
from participant_bench.roster_benchmark.metrics import course_metrics
from participant_bench.roster_benchmark.schriftart_analysis_report import SCRIPT
from participant_bench.roster_benchmark.schriftart_report import analyse_fields
from participant_bench.roster_benchmark.scientific import reanalyze


def fixture_analysis(*, extra=False, partial=False, invalid=False):
    references = [
        replace(ref(row=i + 2, first=f"Person{i}", user=str(100 + i)), schriftart=s)
        for i, s in enumerate(("h", "h", "h", "m", "g", None))
    ]
    if partial:
        references[0] = replace(
            references[0], short_code="", field_states={"short_code": "empty", "last_name": "masked"}
        )
    people = [
        prediction(
            index=i,
            first=f"Person{i}",
            user="***" if invalid and i == 0 else str(100 + i),
            last="Waber" if i == 3 else "Weber",
            code=None if i == 1 else "WRONG" if i == 5 else "MUC",
        )
        for i in (0, 1, 3, 5)
    ]
    if extra:
        people.extend(prediction(index=i, first=f"Person{i}", user=str(100 + i)) for i in (2, 4))
        people.append(prediction(index=6, first="Extra", last="Other", user="9999", code="NONE"))
    score, participants, fields, _ = course_metrics(
        "123456",
        people,
        references,
        MatchingConfig(mode="best_fit"),
        ReferenceConfig(),
        score_original_roles=True,
    )
    audit = dict(
        fields=[dict(r, candidate=m) for m in ("ocr_llm", "vlm") for r in fields],
        participants=[dict(r, candidate=m) for m in ("ocr_llm", "vlm") for r in participants],
    )
    reviews = {
        field_id(r): dict(availability="unchecked", eligible=False, reference_agrees=None)
        for r in fields
        if r["reference_contribution"] == 1
    }
    availability = dict(reviews=reviews)
    ctx = dict(courses={"123456": ["doc"]}, documents={"doc": dict(name="Synthetic.pdf")})
    return audit, availability, ctx, score


def test_unequal_groups_distinguish_rates_from_error_contributions_and_do_not_double_gt():
    audit, av, ctx, score = fixture_analysis()
    before = deepcopy(audit)
    result = analyse_fields(audit, av, ctx)
    view = result["views"]["reference"]["all"]["all"]
    distribution = {r["schriftart"]: r for r in view["distribution"]}
    assert view["reference_fields"] == 24  # Two methods still share one GT population.
    assert distribution["h"]["reference_fields"] == 12 and distribution["h"]["reference_share"] == 0.5
    assert distribution["h"]["field_counts"] == dict(first_name=3, last_name=3, user_id=3, short_code=3)
    rows = {r["schriftart"]: r for r in view["comparisons"] if r["candidate"] == "vlm"}
    h, m, g, unknown = (rows[s] for s in ("h", "m", "g", "unclassified"))
    assert (h["exact_fields"], h["missing_fields"], h["incorrect_fields"]) == (7, 5, 0)
    assert h["missing_rate"] == pytest.approx(5 / 12) and h["missing_error_share"] == pytest.approx(5 / 9)
    assert h["combined_error_share"] == pytest.approx(5 / 11)
    assert m["incorrect_rate"] == 0.25 and m["incorrect_error_share"] == 0.5
    assert g["reference_fields"] == 4 and g["missing_fields"] == 4 and g["detected_similarity"] is None
    assert unknown["incorrect_fields"] == 1 and unknown["reference_fields"] == 4
    assert all(
        sum(r[k] for r in rows.values()) == score["overall"][k]
        for k in ("reference_fields", "exact_fields", "incorrect_fields", "missing_fields")
    )
    assert audit == before


def test_document_subset_remains_separate_and_never_labels_unchecked_as_absent():
    audit, av, ctx, _ = fixture_analysis()
    h = next(r for r in audit["fields"] if r["reference_row"] == 2 and r["field"] == "first_name")
    m = next(r for r in audit["fields"] if r["reference_row"] == 5 and r["field"] == "first_name")
    conflict = next(r for r in audit["fields"] if r["reference_row"] == 5 and r["field"] == "short_code")
    for row in (h, m):
        av["reviews"][field_id(row)].update(availability="readable", eligible=True, reference_agrees=True)
    av["reviews"][field_id(conflict)].update(availability="readable", reference_agrees=False)
    result = analyse_fields(audit, av, ctx)
    assert result["views"]["reference"]["all"]["all"]["reference_fields"] == 24
    doc = result["views"]["document"]["all"]["all"]
    assert doc["reference_fields"] == 2
    assert sum(r["reference_conflicts"] for r in doc["distribution"]) == 1
    assert sum(r["availability_counts"].get("unchecked", 0) for r in doc["distribution"]) == 21
    group = next(r for r in doc["comparisons"] if r["schriftart"] == "g")
    assert group["exact_recall"] is None and group["reference_fields"] == 0


def test_invalid_nonempty_ids_and_explicit_empty_or_masked_gt_reuse_existing_rules():
    for partial, invalid in ((True, False), (False, True)):
        audit, av, ctx, score = fixture_analysis(partial=partial, invalid=invalid)
        result = analyse_fields(audit, av, ctx)
        current = result["checks"]["vlm"]["global_metrics"]
        assert current == pytest.approx(score["overall"])
        if invalid:
            group = next(
                r
                for r in result["views"]["reference"]["all"]["user_id"]["comparisons"]
                if r["candidate"] == "vlm" and r["schriftart"] == "h"
            )
            assert group["invalid_prediction_fields"] == 1 and group["detected_fields"] == 2
            assert group["present_but_unusable_values"] == 1
        else:
            assert current["reference_fields"] == 22 and current["reference_empty_fields"] == 1
            assert current["excluded_reference_fields"] == 1


def test_extras_retain_global_penalties_but_cannot_acquire_a_style():
    audit, av, ctx, score = fixture_analysis(extra=True)
    result = analyse_fields(audit, av, ctx)
    assert result["checks"]["vlm"]["global_metrics"] == pytest.approx(score["overall"])
    extras = next(r for r in result["unassigned"] if r["candidate"] == "vlm")
    assert extras["fields"]["predicted_fields"] == 4 and extras["fields"]["extra_fields"] == 4
    assert all(r["reference_row"] is not None for r in result["details"])


def test_perfect_extraction_has_undefined_error_shares_and_empty_groups_are_not_zero_quality():
    _, _, fields, _ = course_metrics(
        "123456",
        [prediction()],
        [replace(ref(), schriftart="m")],
        MatchingConfig(),
        ReferenceConfig(),
        score_original_roles=True,
    )
    audit = dict(fields=[dict(r, candidate="vlm") for r in fields])
    av = dict(
        reviews={
            field_id(r): dict(availability="unchecked", eligible=False, reference_agrees=None) for r in fields
        }
    )
    ctx = dict(courses={"123456": ["doc"]}, documents={"doc": dict(name="Synthetic.pdf")})
    result = analyse_fields(audit, av, ctx)
    rows = {r["schriftart"]: r for r in result["views"]["reference"]["all"]["all"]["comparisons"]}
    assert rows["m"]["exact_recall"] == 1 and rows["m"]["combined_error_share"] is None
    assert rows["h"]["reference_fields"] == 0 and rows["h"]["exact_recall"] is None


def test_document_filter_never_uses_prediction_locations_or_loses_missing_rows():
    audit, av, ctx, _ = fixture_analysis()
    ctx["courses"]["123456"] = ["doc", "other"]
    ctx["documents"]["other"] = dict(name="Second.pdf")
    result = analyse_fields(audit, av, ctx)
    assert result["views"]["reference"]["doc"]["all"]["reference_fields"] == 0
    assert result["views"]["reference"]["course:123456"]["all"]["reference_fields"] == 24
    # Reference row 4 is completely missing; independent GT localization still assigns its four fields.
    result = analyse_fields(audit, av, ctx, {("123456", 4): ("other", 2)})
    view = result["views"]["reference"]["other"]["all"]
    assert view["reference_fields"] == 4 and all(
        r["missing_fields"] == 4 for r in view["comparisons"] if r["schriftart"] == "h"
    )


@pytest.mark.parametrize("bad", ["label", "participant", "reference", "scope", "signature"])
def test_incompatible_labels_scopes_and_signature_text_are_rejected(bad):
    audit, av, ctx, _ = fixture_analysis()
    if bad == "label":
        audit["fields"][0]["schriftart"] = "typed"
    elif bad == "participant":
        for r in audit["fields"]:
            if r["reference_row"] == 2 and r["field"] == "first_name":
                r["schriftart"] = "m"
    elif bad == "reference":
        audit["fields"][0]["reference_value"] = "Different"
    elif bad == "scope":
        audit["fields"].pop()
    else:
        audit["fields"][0]["field"] = "signature_present"
    with pytest.raises(ValueError):
        analyse_fields(audit, av, ctx)


def test_real_report_integration_uses_frozen_counters_and_links_new_page(tmp_path):
    old, source, _, metadata = frozen_report(tmp_path)
    protected = {p: file_hash(p) for base in (old, source) for p in base.rglob("*") if p.is_file()}
    new = tmp_path / "new"
    result = reanalyze(old, new, figures=False, resamples=200)
    assert read_json(new / "metrics.json") == read_json(old / "metrics.json")
    report = read_json(new / "scientific/schriftart_analysis.json")
    expected = next(r["reference_fields"] for r in result["overview"] if r.get("mode") == "original_roles")
    view = report["views"]["reference"]["all"]["all"]
    assert view["reference_fields"] == expected
    assert next(r for r in view["distribution"] if r["schriftart"] == "unclassified")["reference_share"] == 1
    assert all(r["exact_recall"] is None for r in view["comparisons"] if r["schriftart"] in ("h", "m", "g"))
    text = (new / "handschrift_maschinenschrift.html").read_text(encoding="utf-8")
    assert "Handschrift vs. Maschinenschrift" in text and 'id="sa-quality-chart"' in text
    assert "pro Teilnehmer" in text and "Fehleranteil" in text and "keine erfundenen Nullwerte" in text
    assert all(
        'href="handschrift_maschinenschrift.html"' in (new / name).read_text(encoding="utf-8")
        for name in ("report.html", "missing_fields.html", "validity.html", "standard_report.html")
    )
    assert (new / "scientific/schriftart_analysis.csv").is_file()
    assert all(file_hash(p) == sha for p, sha in protected.items())


def test_offline_filters_use_precomputed_values_without_reweighting_styles(tmp_path):
    node = shutil.which("node")
    if not node:
        pytest.skip("Node needed for the existing offline JS test mechanism")
    audit, av, ctx, _ = fixture_analysis()
    payload = analyse_fields(audit, av, ctx)
    payload.update(
        field_labels=dict(
            first_name="Vorname", last_name="Nachname", user_id="ID", short_code="Organisation"
        ),
        availability=dict(unchecked="Ungeprüft", readable="Lesbar"),
    )
    fixture = r"""const assert=require('node:assert/strict');
class E{constructor(value=''){this.value=value;this.children=[];this.dataset={};}replaceChildren(){this.children=[];}appendChild(c){this.children.push(c);}setAttribute(k,v){this[k]=v;}addEventListener(n,f){this.fn=f;}}
const data=PAYLOAD,elements={};
for(const id of ['basis','method','document','field','style'])elements['sa-'+id]=new E({basis:'reference',document:'all',field:'all'}[id]||'');
elements['schriftanalyse-data']={textContent:JSON.stringify(data)};
const cases=data.details.map(r=>({dataset:{method:r.candidate,document:r.reference_document_group,field:r.field,style:r.gt_style,eligible:String(r.document_eligible)}}));
global.document={getElementById(k){return elements[k]||(elements[k]=new E());},createElement(){return new E();},createElementNS(){return new E();},querySelectorAll(){return cases;}};
new Function(SOURCE)();
assert.equal(elements['sa-distribution'].children.length,4);assert.equal(elements['sa-quality'].children.length,8);
elements['sa-style'].value='h';elements['sa-style'].fn();
assert.equal(elements['sa-quality'].children.length,2);assert.ok(elements['sa-distribution'].children[0].children[3].textContent.includes('50,00'));
const share=elements['sa-errors'].children[0].children[10].textContent;assert.ok(share.includes('5/11'));assert.ok(!share.includes('100,00'));
elements['sa-method'].value='vlm';elements['sa-method'].fn();assert.equal(elements['sa-quality'].children.length,1);
elements['sa-document'].value='doc';elements['sa-field'].value='user_id';elements['sa-field'].fn();
assert.ok(cases.filter(r=>!r.hidden).every(r=>r.dataset.method==='vlm'&&r.dataset.style==='h'&&r.dataset.field==='user_id'));
elements['sa-basis'].value='document';elements['sa-basis'].fn();assert.equal(elements['sa-empty-basis'].hidden,false);assert.ok(cases.every(r=>r.hidden));
""".replace("PAYLOAD", json.dumps(payload)).replace("SOURCE", json.dumps(SCRIPT))
    path = tmp_path / "filters.cjs"
    path.write_text(fixture, encoding="utf-8")
    run = subprocess.run([node, str(path)], text=True, capture_output=True, timeout=20)
    assert run.returncode == 0, run.stderr
