"""Scientific correctness: pooled denominators, paired groups, leakage and frozen replays."""

import re

import pytest
import yaml
from PIL import Image

from participant_bench.io import file_hash, read_json, write_csv, write_json, write_jsonl
from participant_bench.roster_benchmark.config import BenchmarkConfig
from participant_bench.roster_benchmark.detail_report import read_csv
from participant_bench.roster_benchmark.error_report import aggregate_findings, page_events
from participant_bench.roster_benchmark.evaluation import evaluate_run
from participant_bench.roster_benchmark.references import saved_reference
from participant_bench.roster_benchmark.scientific import analyze, reanalyze
from participant_bench.roster_benchmark.scientific_metadata import course_metadata, load_metadata, template
from participant_bench.roster_benchmark.scientific_stats import cluster_bootstrap, pareto, pooled
from participant_bench.schema import PageResult, VisualParticipant


def counter(reference, exact, predicted=None):
    return dict(
        reference_fields=reference,
        predicted_fields=reference if predicted is None else predicted,
        exact_fields=exact,
        raw_exact_fields=exact,
        similarity_credit=exact,
        missing_fields=reference - exact,
    )


def test_pooling_does_not_average_course_f1():
    groups = {"short": counter(1, 1), "long": counter(9, 0)}
    assert pooled(groups.values())["exact_f1"] == 0.1
    result = cluster_bootstrap(groups, resamples=400, minimum_groups=2)
    assert result["estimates"]["exact_f1"] == 0.1  # averaging course F1 would give .5
    assert result["intervals"]["exact_f1"]["low"] == 0
    assert result["intervals"]["exact_f1"]["high"] == 1


def test_paired_bootstrap_uses_identical_indices_and_is_reproducible():
    groups = {str(i): counter(i + 1, i) for i in range(12)}
    a = cluster_bootstrap(groups, groups, resamples=300)
    b = cluster_bootstrap(dict(reversed(list(groups.items()))), groups, resamples=300)
    assert a == b
    assert a["status"] == "estimated" and a["degenerate"]
    assert a["unit"] == "percentage_points"
    for metric in a["intervals"]:
        assert a["estimates"][metric] == 0
        assert a["intervals"][metric] == dict(low=0, high=0, valid_resamples=300)


def test_difference_is_percentage_points_and_keeps_missing_predictions():
    a = {str(i): counter(4, 1) for i in range(10)}
    b = {str(i): counter(4, 3) for i in range(10)}
    result = cluster_bootstrap(a, b, resamples=200)
    assert result["estimates"]["exact_recall"] == 50
    assert result["intervals"]["exact_f1"]["low"] == 50


@pytest.mark.parametrize(
    "kind,status",
    [
        ("small", "insufficient_groups"),
        ("unreviewed", "unverified_grouping_or_mixed_phases"),
        ("empty", "undefined_resamples"),
    ],
)
def test_no_false_precision_for_insufficient_or_unreviewed_data(kind, status):
    groups = {
        str(i): counter(0, 0) if kind == "empty" else counter(4, 1)
        for i in range(1 if kind == "small" else 10)
    }
    result = cluster_bootstrap(groups, eligible=kind != "unreviewed", resamples=200)
    assert result["status"] == status
    assert all(v["low"] is None and v["high"] is None for v in result["intervals"].values())
    if kind == "empty":
        assert result["estimates"]["exact_recall"] is None


def test_pairs_cannot_silently_shrink_or_change_reference_denominators():
    result = cluster_bootstrap({"a": counter(4, 1)}, {"b": counter(4, 1)}, resamples=200)
    assert result["status"] == "unpaired_groups" and result["missing_left"] == ["b"]
    with pytest.raises(ValueError, match="Referenznenner"):
        cluster_bootstrap({"a": counter(4, 1)}, {"a": counter(3, 1)}, resamples=200)
    with pytest.raises(ValueError):
        cluster_bootstrap({}, resamples=199)


def test_pareto_requires_complete_comparable_measurements_and_strict_dominance():
    rows = [
        dict(candidate=name, quality=q, seconds=t, complete=complete, comparable=comparable)
        for name, q, t, complete, comparable in (
            ("a", 0.8, 2, True, True),
            ("b", 0.7, 3, True, True),
            ("tie", 0.8, 2, True, True),
            ("partial", 1, 1, False, True),
            ("subset", 1, 1, True, False),
            ("missing", 1, None, True, True),
        )
    ]
    assert pareto(rows) == dict(
        a="pareto_efficient",
        b="dominated",
        tie="pareto_efficient",
        partial="not_assessed",
        subset="not_assessed",
        missing="not_assessed",
    )


def manifest():
    return dict(
        inputs=[
            dict(kind="pdf", path="123456.pdf", sha256="a"),
            dict(kind="pdf", path="123456__2.pdf", sha256="b"),
        ],
        pages=[
            dict(document_id="a", page_number=1),
            dict(document_id="a", page_number=2),
            dict(document_id="b", page_number=1),
        ],
    )


def reviewed_rows():
    return [
        dict(
            document_id=d,
            class_id="123456",
            dependency_group="shared",
            grouping_reviewed="true",
            prior_use="unused",
            partition="test",
            stratum=s,
            quality_flags="",
        )
        for d, s in (("a", "printed"), ("b", "handwritten"))
    ]


def test_manual_features_are_not_inferred_and_multi_pdf_course_is_not_a_mixed_pdf(tmp_path):
    data = manifest()
    unknown, _, _ = load_metadata(data, {"123456"})
    info = course_metadata("123456", unknown, data)
    assert info["stratum"] == "unknown" and not info["grouping_reviewed"]
    assert info["headerless"] == "unknown" and info["multipage_pdf"] == "yes"
    path = tmp_path / "metadata.csv"
    write_csv(path, reviewed_rows())
    records, _, _ = load_metadata(data, {"123456"}, path)
    info = course_metadata("123456", records, data)
    assert info["stratum"] == "heterogeneous_course" and info["pdf_count"] == 2
    assert info["image_quality"] == "unknown"
    template(data, {"123456"}, tmp_path / "template.csv")
    with pytest.raises(ValueError, match="existiert"):
        template(data, {"123456"}, tmp_path / "template.csv")


@pytest.mark.parametrize("kind", ["group", "phase", "prior", "foreign", "duplicate", "class", "flag"])
def test_metadata_rejects_leakage_and_unsupported_claims(tmp_path, kind):
    rows = reviewed_rows()
    if kind == "group":
        rows[1]["dependency_group"] = "different"
    elif kind == "phase":
        rows[1]["partition"] = "pilot"
    elif kind == "prior":
        rows[0]["prior_use"] = "development"
    elif kind == "foreign":
        rows[0]["document_id"] = "foreign"
    elif kind == "duplicate":
        rows.append(rows[0])
    elif kind == "class":
        rows[0]["class_id"] = "654321"
    else:
        rows[0]["quality_flags"] = "guessed"
    path = tmp_path / "metadata.csv"
    write_csv(path, rows)
    with pytest.raises(ValueError):
        load_metadata(manifest(), {"123456"}, path)


def frozen_report(tmp_path, count=2, *, empty_method=None):
    source = tmp_path / "run"
    source.mkdir()
    image = source / "image.png"
    Image.new("RGB", (60, 60), "white").save(image)
    inputs, images, metadata_rows, reference_rows = [], [], [], []
    pages = {m: [] for m in ("vlm", "ocr_vlm")}
    for i in range(count):
        course, doc = str(123456 + i), f"document{i}"
        inputs.append(dict(kind="pdf", path=f"{course}.pdf", sha256=doc))
        images.append(
            dict(
                document_id=doc,
                page_number=1,
                page_id=f"{doc}-p0001",
                image=str(image),
                run_image=str(image),
                run_image_sha256=file_hash(image),
            )
        )
        reference_rows.append(f"{course};001234;Anna;Weber;MUC;{'masked' if i == 0 else 'read'}")
        metadata_rows.append(
            dict(
                document_id=doc,
                class_id=course,
                dependency_group=f"g{i}",
                grouping_reviewed="true",
                prior_use="unused",
                partition="test",
                stratum="printed",
                quality_flags="clean",
            )
        )
        for method in pages:
            person = VisualParticipant(
                first_name="Weber" if method == "vlm" else "Anna",
                last_name="Anna" if method == "vlm" else "Weber",
                personnel_number="001234",
                department="MUC",
            ).participant()
            # A missing result must retain all its reference fields.
            if method == empty_method or method == "ocr_vlm" and i == 1:
                continue
            pages[method].append(
                PageResult(
                    run_id="synthetic",
                    document_id=doc,
                    page_id=f"{doc}-p0001",
                    page_number=1,
                    method_id=method,
                    status="partial",
                    parse_status="valid",
                    participants=[person],
                    timings={"page_wall_seconds": 1.0},
                ).model_dump()
            )
    write_json(source / "manifest.json", dict(inputs=inputs, pages=images))
    write_json(source / "effective_pages.json", images)
    write_json(
        source / "summary.json",
        {m: dict(status="partial", output_kind="structured", actual_method_wall_seconds=2) for m in pages},
    )
    (source / "config.yaml").write_text(yaml.safe_dump({"models": {}}), encoding="utf-8")
    for method, records in pages.items():
        write_jsonl(source / method / "extractions.jsonl", records)
    reference = tmp_path / "reference.csv"
    reference.write_text(
        "Class ID;User ID;First Name;Last Name;Organization;short_code__state\n"
        + "\n".join(reference_rows)
        + "\n",
        encoding="utf-8",
    )
    metadata = tmp_path / "metadata.csv"
    write_csv(metadata, metadata_rows)
    report = tmp_path / "original"
    evaluate_run(source, reference, BenchmarkConfig(), tmp_path, output=report, scientific_options=False)
    return report, source, reference, metadata


def test_frozen_replay_preserves_sources_masks_and_denominators_and_does_not_reload_reference(tmp_path):
    report, source, reference, metadata = frozen_report(tmp_path)
    hashes = {p: file_hash(p) for root in (source, report) for p in root.rglob("*") if p.is_file()}
    reference.unlink()  # replay must use the original frozen snapshot
    result = reanalyze(
        report, tmp_path / "new", metadata=metadata, phase="test", resamples=200, figures=False
    )
    primary = {r["candidate"]: r for r in result["overview"] if r.get("mode") == "original_roles"}
    assisted = next(
        r for r in result["overview"] if r.get("mode") == "best_fit_swap" and r["candidate"] == "vlm"
    )
    assert primary["vlm"]["reference_fields"] == primary["ocr_vlm"]["reference_fields"] == 7
    assert primary["vlm"]["exact_fields"] == 3 and assisted["exact_fields"] == 7
    assert primary["vlm"]["excluded_reference_fields"] == 1
    assert primary["ocr_vlm"]["missing_fields"] == 4 and primary["ocr_vlm"]["status"] == "incomplete"
    effect = next(
        r for r in result["matching_effects"] if r["candidate"] == "vlm" and r["before"] == "original_roles"
    )
    assert effect["estimates"]["exact_recall"] == pytest.approx(400 / 7)
    assert effect["extraction_changed"] is False
    assert all(r["status"] == "insufficient_groups" for r in result["intervals"])
    assert result["ablations"][0]["counts"]["fields"] == 7
    assert result["ablations"][1]["status"] == "missing_comparison"
    assert result["ablations"][0]["causal_claim"] is False
    fields = read_csv(tmp_path / "new/scientific/fields.csv")
    assert (
        sum(
            int(r["reference_fields"])
            for r in fields
            if r["mode"] == "original_roles" and r["candidate"] == "vlm"
        )
        == 7
    )
    assert all(file_hash(p) == value for p, value in hashes.items())
    html = (tmp_path / "new/report.html").read_text(encoding="utf-8")
    assert "Wissenschaftliche Analyse" in html and "keine referenzunabhängige" in html
    assert not re.search(r"\b(?:Anna|Weber)\b", html)
    assert (tmp_path / "new/error_analysis/summary.csv").is_file()


def test_enough_reviewed_independent_groups_enable_ci_and_render_is_idempotent(tmp_path):
    report, _, _, metadata = frozen_report(tmp_path, count=10)
    result = analyze(report, metadata=metadata, phase="test", resamples=200, figures=False)
    ci = next(r for r in result["intervals"] if r["candidate"] == "vlm" and r["mode"] == "original_roles")
    assert ci["status"] == "estimated" and ci["groups"] == 10
    assert ci["intervals"]["exact_recall"]["low"] is not None
    analyze(report, metadata=metadata, phase="test", resamples=200, figures=False)
    html = (report / "report.html").read_text(encoding="utf-8")
    assert html.count('id="scientific-analysis"') == 1


def test_tampered_frozen_reference_and_wrong_phase_are_rejected(tmp_path):
    report, _, _, metadata = frozen_report(tmp_path)
    with pytest.raises(ValueError, match="andere Phasen"):
        analyze(report, metadata=metadata, phase="pilot", resamples=200, figures=False)
    snapshot = read_json(report / "reference_snapshot.json")
    snapshot["people"][0]["first_name"] = "changed"
    write_json(report / "reference_snapshot.json", snapshot)
    with pytest.raises(ValueError, match="Snapshot|snapshot"):
        saved_reference(report)


def test_completely_missing_results_are_not_measured_improvements(tmp_path):
    report, _, _, metadata = frozen_report(tmp_path, empty_method="ocr_vlm")
    result = analyze(report, metadata=metadata, phase="test", resamples=200, figures=False)
    assert result["ablations"][0]["status"] == "missing_results"
    assert result["paired"][0]["status"] == "missing_results"
    assert all(r["status"] == "missing_results" for r in result["intervals"] if r["candidate"] == "ocr_vlm")
    assert next(r for r in result["overview"] if r["candidate"] == "ocr_vlm")["reference_fields"] == 7


def test_additional_report_must_actually_contain_the_requested_candidate(tmp_path):
    report, _, _, metadata = frozen_report(tmp_path)
    with pytest.raises(ValueError, match="Kandidaten nicht"):
        analyze(
            report, metadata=metadata, additional_reports={"docling": report}, resamples=200, figures=False
        )


def test_phase_subset_keeps_reference_denominators_without_allocating_full_run_time(tmp_path):
    report, _, _, metadata = frozen_report(tmp_path, count=3)
    rows = read_csv(metadata)
    rows[0].update(partition="development", prior_use="development")
    write_csv(metadata, rows)
    result = reanalyze(
        report, tmp_path / "subset", metadata=metadata, phase="test", resamples=200, figures=False
    )
    assert result["courses"] == 2 and result["observed_phases"] == ["test"]
    assert all(r["reference_fields"] == 8 for r in result["overview"])
    assert all(not e["scope_matches"] for e in result["effort"].values())
    assert all(r["pareto"] == "not_assessed" for r in result["pareto"])


def test_error_totals_keep_evidence_levels_and_page_events_separate():
    findings = [
        dict(
            method="vlm",
            document_id="d",
            field="first_name",
            analysis=dict(result=result, category=category, stage="unknown", certainty=certainty),
        )
        for result, category, certainty in (
            ("correct", "none", "proven"),
            ("missing", "unknown", "unknown"),
            ("incorrect", "ocr_suspected", "hypothesis"),
            ("extra", "extra", "proven"),
        )
    ]
    rows = aggregate_findings(findings)
    assert sum(r["count"] for r in rows) == 3
    assert any(r["cause"] == "recognition_or_assignment" and r["certainty"] == "hypothesis" for r in rows)
    page = PageResult(
        run_id="s",
        document_id="d",
        page_id="d-p0001",
        page_number=1,
        method_id="vlm",
        status="partial",
        parse_status="valid",
    )
    events = page_events(
        page, dict(responses=[dict(parse_status="valid", raw_response='{"participants":[]}')]), {}
    )
    assert events[0]["event"] == "empty_structured_response"
    assert events[0]["correctness_of_discarded_value"] == "unknown"
    assert "raw_response" not in events[0]
