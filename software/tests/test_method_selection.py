"""Selection evidence, leakage boundaries and integration with the existing evaluator."""

import csv
from pathlib import Path

import pytest
import yaml
from PIL import Image

from participant_bench.io import digest, file_hash, read_json, write_csv, write_json, write_jsonl
from participant_bench.roster_benchmark.config import BenchmarkConfig
from participant_bench.roster_benchmark.matching import Prediction
from participant_bench.roster_benchmark.metrics import course_metrics
from participant_bench.schema import PageResult, VisualParticipant
from participant_bench.selection import compare, recommend, run_selected
from participant_bench.selection_config import Evidence, SelectionPolicy, load_policy, matrix
from participant_bench.selection_sample import freeze, inventory, load_plan

POLICY = Path("configs/selection.yaml")


def metadata(tmp_path, count=1, *, partition="development", prior_use="development"):
    rows = []
    for i in range(count):
        path = tmp_path / f"{123456+i}.pdf"
        path.write_bytes(f"synthetic input {i}".encode())
        rows.append(dict(document_id=file_hash(path), path=str(path), class_id=path.stem,
                         dependency_group=f"group{i}", grouping_reviewed="true", prior_use=prior_use,
                         stratum="mixed" if i % 2 else "printed", quality_flags="clean", partition=partition))
    target = tmp_path / "inventory.csv"
    write_csv(target, rows)
    return target, rows


def synthetic_run(tmp_path, plan, *, status="partial", swapped=True, method="vlm", include_extra=False):
    doc = plan["documents"][0]
    root = tmp_path / "run"
    image = root / "page.png"
    image.parent.mkdir(parents=True)
    Image.new("RGB", (100, 100), "white").save(image)
    images = [dict(document_id=doc["document_id"], page_number=1, page_id=f'{doc["document_id"]}-p0001',
                   run_image=str(image), run_image_sha256=file_hash(image), include=True)]
    manifest = dict(inputs=[dict(path=doc["path"], sha256=doc["document_id"], kind="pdf")],
                    pages=[dict(images[0], image=str(image))])
    if include_extra:
        other = plan["documents"][1]
        manifest["inputs"].append(dict(path=other["path"], sha256=other["document_id"], kind="pdf"))
    write_json(root / "manifest.json", manifest)
    write_json(root / "effective_pages.json", images)
    write_json(root / "summary.json", {method: dict(status=status, output_kind="structured")})
    (root / "config.yaml").write_text(yaml.safe_dump(plan["profiles"][method]), encoding="utf-8")
    people = [] if status in ("failed", "unavailable") else [VisualParticipant(
        first_name="Weber" if swapped else "Anna", last_name="Anna" if swapped else "Weber",
        personnel_number="001234", department="MUC").participant()]
    page = PageResult(run_id="synthetic", document_id=doc["document_id"], page_id=images[0]["page_id"],
                      page_number=1, method_id=method, status=status, parse_status="valid" if people else "not_attempted",
                      participants=people, timings={"page_wall_seconds": 2.0})
    write_jsonl(root / method / "extractions.jsonl", [page.model_dump()])
    reference = tmp_path / "reference.csv"
    reference.write_text("Class ID;User ID;First Name;Last Name;Organization\n"
                         f'{doc["class_id"]};001234;Anna;Weber;MUC\n', encoding="utf-8")
    config = tmp_path / "benchmark.yaml"
    config.write_text(yaml.safe_dump(BenchmarkConfig().model_dump()), encoding="utf-8")
    return root, reference, config


def test_matrix_unknown_is_not_zero_or_a_renormalized_ranking():
    policy, _ = load_policy(POLICY)
    rows, result = matrix(policy)
    assert any(r["value"] is None for r in rows)
    assert result["ocr_llm"]["weighted_score"] is None
    assert result["ocr_llm"]["evidence_coverage"] == pytest.approx(.25)
    assert result["ocr_raw"]["eligibility"] == "diagnostic_only"
    policy.candidates["vlm"].gates["local_only"].passed = False
    assert matrix(policy)[1]["vlm"]["eligibility"] == "excluded"
    for candidate in policy.candidates.values():
        for rating in candidate.ratings.values():
            rating.value, rating.sources = 1, ["synthetic verified evidence"]
    assert matrix(policy)[1]["vlm"]["weighted_score"] == pytest.approx(1)
    with pytest.raises(ValueError, match="Beleg"):
        Evidence(value=.5, reason="guess")
    invalid = policy.model_dump()
    invalid["criteria"]["runtime"]["weight"] = -1
    with pytest.raises(ValueError):
        SelectionPolicy.model_validate(invalid)


def test_inventory_deduplicates_but_rejects_cross_course_duplicates(tmp_path):
    (tmp_path / "123456.pdf").write_bytes(b"same")
    other = tmp_path / "sub"
    other.mkdir()
    (other / "123456.pdf").write_bytes(b"same")
    inventory(tmp_path, tmp_path / "inventory.csv")
    with (tmp_path / "inventory.csv").open(encoding="utf-8-sig") as stream:
        assert len(list(csv.DictReader(stream))) == 1
    (other / "654321.pdf").write_bytes(b"same")
    with pytest.raises(ValueError, match="verschiedenen Schulungs"):
        inventory(tmp_path, tmp_path / "other.csv")


def test_freeze_is_order_independent_grouped_and_stratified(tmp_path):
    path, docs = metadata(tmp_path, 90, partition="", prior_use="unused")
    # Two PDFs from one course/template dependency must travel together.
    docs[1]["dependency_group"] = docs[0]["dependency_group"]
    write_csv(path, docs)
    a = read_json(freeze(path, POLICY, tmp_path / "a.json"))
    write_csv(path, list(reversed(docs)))
    b = read_json(freeze(path, POLICY, tmp_path / "b.json"))
    def assignments(plan):
        return {d["document_id"]: (d["partition"], d["selected"]) for d in plan["documents"]}
    assert assignments(a) == assignments(b)
    assert 40 <= a["pilot_lists"] <= 41
    assert not a["missing_pilot_strata"]
    groups = {}
    for d in a["documents"]:
        groups.setdefault(d["dependency_group"], set()).add((d["partition"], d["selected"]))
    assert all(len(values) == 1 for values in groups.values())
    assert set(a["partitions"]) == {"development", "pilot", "test"}


@pytest.mark.parametrize("change", ["development_to_test", "course_split", "unreviewed", "unknown_stratum"])
def test_freeze_rejects_leakage_or_unreviewed_metadata(tmp_path, change):
    path, docs = metadata(tmp_path, 2)
    if change == "development_to_test":
        docs[0]["partition"] = "test"
    elif change == "course_split":
        docs[1]["class_id"] = docs[0]["class_id"]
        docs[1]["path"] = docs[0]["path"]
        docs[1]["document_id"] = docs[0]["document_id"]
    elif change == "unreviewed":
        docs[0]["grouping_reviewed"] = "false"
    else:
        docs[0]["stratum"] = "unassigned"
    write_csv(path, docs)
    with pytest.raises(ValueError):
        freeze(path, POLICY, tmp_path / "plan.json")


def test_final_test_files_are_not_reopened_for_selection_and_tampering_is_rejected(tmp_path, monkeypatch):
    path, docs = metadata(tmp_path, 2)
    docs[1].update(partition="test", prior_use="unused")
    write_csv(path, docs)
    plan_path = freeze(path, POLICY, tmp_path / "plan.json")
    original = Path.open

    def guard(self, *args, **kwargs):
        if self == Path(docs[1]["path"]):
            raise AssertionError("Final test PDF was accessed")
        return original(self, *args, **kwargs)

    monkeypatch.setattr(Path, "open", guard)
    assert len(load_plan(plan_path, "development")[1]) == 1
    with pytest.raises(ValueError, match="Finale Testdaten"):
        load_plan(plan_path, "test")
    changed = read_json(plan_path)
    changed["policy"]["seed"] = 999
    write_json(plan_path, changed)
    with pytest.raises(ValueError, match="verändert"):
        load_plan(plan_path, "development")


def test_selection_reuses_field_evaluator_and_keeps_strict_name_roles_separate(tmp_path):
    path, _ = metadata(tmp_path)
    plan_path = freeze(path, POLICY, tmp_path / "plan.json")
    plan = read_json(plan_path)
    source, reference, config = synthetic_run(tmp_path, plan)
    before = file_hash(source / "vlm/extractions.jsonl")
    output = compare(plan_path, tmp_path / "comparison", {"vlm": source}, scope="development",
                     reference=reference, benchmark_path=config)
    result = read_json(output / "selection.json")
    row = next(r for r in result["candidates"] if r["candidate"] == "vlm")
    assert row["status"] == "complete"
    assert row["exact_fields"] == 2 and row["assisted_exact_fields"] == 4
    assert row["original_exact_f1"] == .5
    assert row["strict_exact_f1"] == .5 and row["assisted_exact_f1"] == 1
    assert row["reference_fields"] == 4 and row["documents_processed"] == 1
    assert result["recommendation"]["status"] == "provisional"
    assert len(result["recommendation"]["main_methods"]) == 3
    assert file_hash(source / "vlm/extractions.jsonl") == before
    assert (output / "evaluations/vlm/strict/details.html").is_file()
    assert (output / "field_scores.csv").is_file() and (output / "document_timings.csv").is_file()
    html = (output / "report.html").read_text(encoding="utf-8")
    assert "ohne Swap" in html and "keine unabhängige" in html
    assert "Anna" not in html and "Weber" not in html


@pytest.mark.parametrize("status", ["failed", "unavailable"])
def test_failure_is_not_success_and_denominator_is_preserved(tmp_path, status):
    path, _ = metadata(tmp_path)
    plan_path = freeze(path, POLICY, tmp_path / "plan.json")
    source, reference, config = synthetic_run(tmp_path, read_json(plan_path), status=status)
    output = compare(plan_path, tmp_path / "comparison", {"vlm": source}, scope="development",
                     reference=reference, benchmark_path=config)
    result = read_json(output / "selection.json")
    row = next(r for r in result["candidates"] if r["candidate"] == "vlm")
    assert row["status"] == status and row["pages_successful"] == 0
    assert row["reference_fields"] == 4 and row["missing_fields"] == 4
    absent = next(r for r in result["candidates"] if r["candidate"] == "paddle_llm")
    assert absent["status"] == "missing" and absent.get("strict_exact_f1") is None


def test_source_with_final_test_data_is_rejected_before_scoring(tmp_path):
    path, docs = metadata(tmp_path, 2)
    docs[1].update(partition="test", prior_use="unused")
    write_csv(path, docs)
    plan_path = freeze(path, POLICY, tmp_path / "plan.json")
    source, reference, config = synthetic_run(tmp_path, read_json(plan_path), include_extra=True)
    with pytest.raises(ValueError, match="finale Testdokumente"):
        compare(plan_path, tmp_path / "comparison", {"vlm": source}, scope="development",
                reference=reference, benchmark_path=config)


def test_missing_documents_do_not_become_a_smaller_comparison_set(tmp_path):
    path, _ = metadata(tmp_path, 2)
    plan_path = freeze(path, POLICY, tmp_path / "plan.json")
    source, reference, config = synthetic_run(tmp_path, read_json(plan_path))
    with reference.open("a", encoding="utf-8") as stream:
        stream.write("123457;000007;Ben;Meyer;MUC\n")
    with pytest.raises(ValueError, match="dieselben ausgewählten"):
        compare(plan_path, tmp_path / "comparison", {"vlm": source}, scope="development",
                reference=reference, benchmark_path=config)


def test_new_pilot_run_uses_frozen_existing_config_and_no_reference(tmp_path, monkeypatch):
    path, _ = metadata(tmp_path)
    plan_path = freeze(path, POLICY, tmp_path / "plan.json")
    calls = []

    def fake_run(config, folder, *, offline):
        calls.append((config, list(folder.rglob("*.pdf")), offline))
        return tmp_path / "generated", {}

    monkeypatch.setattr("participant_bench.runner.run", fake_run)
    output = run_selected(plan_path, tmp_path / "new", ["vlm"], scope="development")
    assert read_json(output) == {"vlm": str((tmp_path / "generated").resolve())}
    assert len(calls) == 1 and calls[0][0].methods == ["vlm"] and calls[0][2]
    assert len(calls[0][1]) == 1 and calls[0][0].signature.backend == "opencv"


def test_recommendation_cannot_promote_unavailable_candidate_or_raw_ocr():
    policy, _ = load_policy(POLICY)
    _, eligible = matrix(policy)
    rows = [dict(candidate=k, status="unavailable", strict_exact_f1=None) for k in policy.candidates]
    plan = dict(pilot_lists=40, pilot_groups=12, missing_pilot_strata=[])
    decision = recommend(policy, eligible, rows, plan, "pilot")
    assert decision["status"] == "provisional" and "ocr_raw" not in decision["main_methods"]
    assert decision["optional_experiment"] == "ocr_vlm"


def test_report_escapes_policy_text(tmp_path):
    path, _ = metadata(tmp_path)
    plan_path = freeze(path, POLICY, tmp_path / "plan.json")
    plan = read_json(plan_path)
    plan["policy"]["candidates"]["vlm"]["description"] = "<script>unsafe()</script>"
    plan["seal"] = digest({k: v for k, v in plan.items() if k != "seal"})
    write_json(plan_path, plan)
    source, reference, config = synthetic_run(tmp_path, plan, swapped=False)
    output = compare(plan_path, tmp_path / "comparison", {"vlm": source}, scope="development",
                     reference=reference, benchmark_path=config)
    html = (output / "report.html").read_text(encoding="utf-8")
    assert "<script>" not in html and "&lt;script&gt;" in html


def test_fixed_pairs_expose_role_errors_hidden_by_reassignment():
    from participant_bench.excel_reference import ReferencePerson

    config = BenchmarkConfig()
    config.matching.mode = "best_fit"
    config.matching.compare_name_orientations = True
    refs = [ReferencePerson(2, "123456", "1", "Anna", "Weber", "MUC"),
            ReferencePerson(3, "123456", "2", "Weber", "Anna", "MUC")]
    people = [VisualParticipant(first_name=p.last_name, last_name=p.first_name,
                               personnel_number=p.user_id, department=p.short_code).participant() for p in refs]
    predictions = [Prediction("doc", 1, i, p) for i, p in enumerate(people)]
    assisted = course_metrics("123456", predictions, refs, config.matching, config.reference)[0]
    original = course_metrics("123456", predictions, refs, config.matching, config.reference,
                              score_original_roles=True)[0]
    strict = course_metrics("123456", predictions, refs,
                            config.matching.model_copy(update={"compare_name_orientations": False}), config.reference)[0]
    assert assisted["overall"]["exact_fields"] == 8
    assert original["overall"]["exact_fields"] == 4
    assert strict["overall"]["exact_fields"] == 6
    assert original["overall"]["reference_fields"] == assisted["overall"]["reference_fields"] == 8


def test_assist_cannot_be_mislabeled_as_baseline_or_reverse(tmp_path):
    path, _ = metadata(tmp_path)
    plan_path = freeze(path, POLICY, tmp_path / "plan.json")
    source, reference, config = synthetic_run(tmp_path, read_json(plan_path), method="docling")
    with pytest.raises(ValueError, match="verwechselt"):
        compare(plan_path, tmp_path / "comparison", {"docling_vlm": source}, scope="development",
                reference=reference, benchmark_path=config)
