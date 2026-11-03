"""Compare two frozen OCR/Docling runs after extraction; never give reference values to a model."""

import argparse
import csv
import shutil
import time
from pathlib import Path

from participant_bench.document_names import DocumentNameOrders
from participant_bench.excel_reference import ReferencePerson
from participant_bench.io import file_hash, read_json, read_jsonl, write_json, write_jsonl
from participant_bench.models import parse_ocr_response
from participant_bench.ocr_observations import audit
from participant_bench.person_roles import filter_page_people
from participant_bench.report import refresh_report
from participant_bench.roster_benchmark.config import BenchmarkConfig
from participant_bench.roster_benchmark.evaluation import evaluate_run
from participant_bench.roster_benchmark.references import ReferenceData
from participant_bench.schema import TEXT_FIELDS, NameOrderDecision, PageResult


def run(source_report, new_run, output, *, ocr_variant="baseline"):
    source_report, new_run, output = source_report.resolve(), new_run.resolve(), output.resolve()
    identity = read_json(source_report / "identity.json")
    source = Path(identity["source_run"])
    if output.exists() or any(output.is_relative_to(p) for p in (source, source_report, new_run)):
        raise ValueError("Neuen Ausgabeordner außerhalb der Originale wählen")
    protected = {p: file_hash(p) for root in (source, source_report, new_run) for p in root.rglob("*") if p.is_file()}
    old_pages = read_json(source / "manifest.json")["pages"]
    new_pages = read_json(new_run / "manifest.json")["pages"]
    assert [p["page_id"] for p in old_pages] == [p["page_id"] for p in new_pages]
    for page in old_pages:
        relative = Path("pages") / (page["page_id"]+".png")
        if file_hash(source / relative) != file_hash(new_run / relative):
            raise ValueError("Gleiche Seitenbilder für einen kontrollierten Vergleich erforderlich")
    working = output / "source"
    shutil.copytree(source, working)
    summary = read_json(working / "summary.json")
    stages = []
    for method in ("ocr_llm", "docling"):
        started = time.perf_counter()
        historical = working / (method+"_historical")
        current = working / method
        assert current.resolve().is_relative_to(working) and historical.resolve().is_relative_to(working)
        current.rename(historical)
        origin = source if method == "ocr_llm" and ocr_variant == "baseline" else new_run
        shutil.copytree(origin / method, current)
        pages = [PageResult.model_validate(p) for p in read_jsonl(current / "extractions.jsonl")]
        names = DocumentNameOrders()
        before_pages = {p["page_id"]: p for p in read_jsonl(source / method / "extractions.jsonl")}
        raw_records = []
        for page in pages:
            path = current / ("raw-"+page.page_id+".json")
            raw = read_json(path)
            old_raw = read_json(source / method / path.name)
            before = audit(old_raw, before_pages[page.page_id])
            if method == "ocr_llm":
                # Reapply the final confidence/evidence policy to the unchanged response.
                # This performs no recognition and no generative inference.
                if len(raw.get("responses", [])) != 1:
                    raise ValueError("Dieser Kontrolllauf erwartet eine vollständige OCR-Seitenantwort")
                prior = {key: raw.pop(key) for key in ("document_name_order", "person_role_filter") if key in raw}
                decision = prior.get("document_name_order", {}).get("decision")
                response = raw["responses"][0]
                data = dict(raw["ocr"], **raw["ocr_layout_analysis"])
                rejected, warnings, proofs = [], [], []
                page.participants = parse_ocr_response(response["raw_response"], data, rejected,
                    preserve_partial_fields=True, field_warnings=warnings, field_evidence=proofs)
                page.excluded_instructors = []
                response.update(rejected_rows=rejected, field_warnings=warnings, ocr_field_evidence=proofs)
                raw["historical_postprocessing_before_confidence_recheck"] = prior
                names.apply(page, raw, NameOrderDecision.model_validate(decision) if decision else None)
                filter_page_people(page, raw)
                page.text_fallback = not page.participants
            after = audit(raw, page)
            raw["ocr_observation_audit"] = after
            stages.append(dict(method=method, page_number=page.page_number,
                before=before["counts"], after=after["counts"], before_capture=before["capture_coverage"],
                after_capture=after["capture_coverage"]))
            write_json(path, raw)
            raw_records.append(raw)
        write_jsonl(current / "raw.jsonl", raw_records)
        write_jsonl(current / "extractions.jsonl", [p.model_dump() for p in pages])
        summary[method] = read_json(origin / "summary.json")[method]
        summary[method]["observation_recheck_seconds"] = time.perf_counter() - started
        if method == "ocr_llm" and ocr_variant == "baseline":
            summary[method]["historical_method_wall_seconds"] = summary[method].get("actual_method_wall_seconds")
            summary[method]["actual_method_wall_seconds"] = None
            summary[method]["timing_scope"] = "frozen_response_validation_only_no_new_default_inference"
        summary[method]["output_unknown_text_fields"] = sum(getattr(p, f).state not in ("read", "empty")
            for page in pages for p in page.participants for f in TEXT_FIELDS)
    write_json(working / "summary.json", summary)
    run_identity = read_json(working / "identity.json")
    run_identity["observation_retention_recheck"] = dict(new_extraction_run=str(new_run),
        ocr_variant=ocr_variant,
        original_run=str(source), script_sha256=file_hash(Path(__file__)), frozen_response_confidence_recheck=True)
    write_json(working / "identity.json", run_identity)
    refresh_report(working)
    # Open the frozen reference only after all extraction/validation decisions.
    snapshot = read_json(source_report / "reference_snapshot.json")
    reference = ReferenceData([ReferencePerson(**r) for r in snapshot["people"]], identity.get("reference_sheet"),
        snapshot.get("duplicate_rows", []), True, snapshot.get("columns", {}))
    config = BenchmarkConfig.model_validate(read_json(source_report / "config.json"))
    comparison, metrics = evaluate_run(working, Path(identity["reference_file"]), config, output,
        output=output / "comparison", frozen_reference=(reference, identity["reference_sha256"]))
    def exact_fields(folder):
        with (folder / "fields.csv").open(encoding="utf-8-sig", newline="") as stream:
            return {(r["method"], r["class_id"], r["reference_row"], r["field"]): r["exact"] == "True"
                    for r in csv.DictReader(stream) if r["reference_contribution"] == "1"}
    old, new = exact_fields(source_report), exact_fields(comparison)
    changes = {method: dict(
        retained_correct=sum(old[k] and new.get(k, False) for k in old if k[0] == method),
        newly_correct=sum(not old[k] and new.get(k, False) for k in old if k[0] == method),
        lost_correct=sum(old[k] and not new.get(k, False) for k in old if k[0] == method)) for method in summary}
    assert all(file_hash(path) == value for path, value in protected.items())
    write_json(output / "check.json", dict(original_files_unchanged=True, source_report=str(source_report),
        ocr_variant=ocr_variant,
        new_run=str(new_run), stages=stages, changes=changes,
        before=read_json(source_report / "metrics.json")["methods"], after=metrics,
        script_sha256=file_hash(Path(__file__))))
    return comparison


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-report", type=Path, required=True)
    parser.add_argument("--new-run", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--ocr-variant", choices=["baseline", "all"], default="baseline",
                        help="Baseline-Antworten erhalten oder die neue vollständige Zeilenvariante vergleichen")
    args = parser.parse_args()
    print(run(args.source_report, args.new_run, args.output, ocr_variant=args.ocr_variant))
